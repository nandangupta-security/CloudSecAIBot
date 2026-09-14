"""
Unit tests for command_audit_log.py.

Uses monkeypatch to redirect OUTPUT_DIR/LOG_FILE into a pytest tmp_path for
every test, so nothing here ever touches the real output/command_audit.log.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import command_audit_log as cal


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Point the module at a throwaway log file for every test in this file."""
    output_dir = tmp_path / "output"
    log_file = output_dir / "command_audit.log"
    monkeypatch.setattr(cal, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(cal, "LOG_FILE", log_file)
    yield log_file


def test_log_command_creates_output_dir_and_file(isolated_log):
    assert not isolated_log.exists()
    cal.log_command("aws", "cloud-sec-aws-cli", "s3 ls", allowed=True, exit_code=0, duration_ms=10)
    assert isolated_log.exists()


def test_log_command_writes_valid_json_line_with_expected_fields(isolated_log):
    cal.log_command(
        "aws", "cloud-sec-aws-cli", "s3 ls",
        allowed=True, block_reason=None, exit_code=0, duration_ms=42,
    )
    lines = isolated_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["provider"] == "aws"
    assert entry["tool"] == "cloud-sec-aws-cli"
    assert entry["command"] == "s3 ls"
    assert entry["allowed"] is True
    assert entry["block_reason"] is None
    assert entry["exit_code"] == 0
    assert entry["duration_ms"] == 42
    assert "timestamp" in entry and entry["timestamp"]  # non-empty ISO8601 string


def test_log_command_records_blocked_entries(isolated_log):
    cal.log_command(
        "aws", "cloud-sec-aws-cli", "iam put-user-policy --user-name x",
        allowed=False, block_reason="not a recognized read-only operation",
    )
    entry = json.loads(isolated_log.read_text(encoding="utf-8").strip())
    assert entry["allowed"] is False
    assert entry["block_reason"] == "not a recognized read-only operation"
    assert entry["exit_code"] is None
    assert entry["duration_ms"] is None


def test_log_command_never_raises_on_write_failure(isolated_log, monkeypatch):
    """Auditing must never take down command execution — even if the
    filesystem write itself fails."""
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cal.os, "open", boom)
    # Should not raise.
    cal.log_command("aws", "cloud-sec-aws-cli", "s3 ls", allowed=True)


def test_read_recent_returns_empty_list_when_no_log_exists(isolated_log):
    assert cal.read_recent() == []


def test_read_recent_returns_entries_in_original_order(isolated_log):
    for i in range(5):
        cal.log_command("aws", "cloud-sec-aws-cli", f"cmd-{i}", allowed=True, exit_code=0)

    entries = cal.read_recent(limit=100)
    assert [e["command"] for e in entries] == [f"cmd-{i}" for i in range(5)]


def test_read_recent_respects_limit_and_keeps_the_newest(isolated_log):
    for i in range(10):
        cal.log_command("aws", "cloud-sec-aws-cli", f"cmd-{i}", allowed=True, exit_code=0)

    entries = cal.read_recent(limit=3)
    assert [e["command"] for e in entries] == ["cmd-7", "cmd-8", "cmd-9"]


def test_read_recent_filters_by_provider(isolated_log):
    cal.log_command("aws", "cloud-sec-aws-cli", "s3 ls", allowed=True, exit_code=0)
    cal.log_command("azure", "cloud-sec-azure-cli", "vm list", allowed=True, exit_code=0)
    cal.log_command("gcp", "cloud-sec-gcloud-cli", "compute instances list", allowed=True, exit_code=0)

    aws_entries = cal.read_recent(limit=100, provider="aws")
    assert len(aws_entries) == 1
    assert aws_entries[0]["provider"] == "aws"

    azure_entries = cal.read_recent(limit=100, provider="azure")
    assert len(azure_entries) == 1
    assert azure_entries[0]["provider"] == "azure"


def test_read_recent_skips_malformed_lines_instead_of_raising(isolated_log):
    isolated_log.parent.mkdir(exist_ok=True)
    with open(isolated_log, "w", encoding="utf-8") as f:
        f.write('{"provider": "aws", "command": "good-1"}\n')
        f.write("not valid json at all\n")
        f.write("\n")  # blank line
        f.write('{"provider": "aws", "command": "good-2"}\n')

    entries = cal.read_recent(limit=100)
    assert [e["command"] for e in entries] == ["good-1", "good-2"]


def test_concurrent_style_appends_do_not_corrupt_the_file(isolated_log):
    """Simulate what happens when multiple provider processes append to the
    same shared file: many sequential single-syscall writes must each stay
    on their own line with no interleaving/corruption."""
    for i in range(50):
        cal.log_command("aws", "cloud-sec-aws-cli", f"cmd-{i}", allowed=True, exit_code=0)

    lines = isolated_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 50
    for i, line in enumerate(lines):
        entry = json.loads(line)  # raises if any line is corrupted/interleaved
        assert entry["command"] == f"cmd-{i}"
