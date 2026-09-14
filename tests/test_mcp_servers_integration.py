"""
Integration tests for the AWS/Azure/GCP MCP server classes.

These exercise the actual server classes end-to-end — safety check →
subprocess execution → audit log — rather than just the standalone helper
modules. subprocess execution is mocked out (no real aws/az/gcloud/gsutil/bq
binary required), so these tests are hermetic and safe to run in CI without
any cloud credentials configured.

Note: the tools these servers expose are registered as closures inside
setup_handlers() via the low-level mcp.server.Server's @list_tools()/
@call_tool() decorators, so there's no public method to invoke a tool by
name without a live stdio session. Testing the private _execute_*/
_get_audit_log methods directly (same pattern the manual smoke tests used
during development) is the practical way to exercise this business logic.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import awscli_claude
import azurecli_claude
import gcpcli_claude
import command_audit_log as cal


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    log_file = output_dir / "command_audit.log"
    monkeypatch.setattr(cal, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(cal, "LOG_FILE", log_file)
    yield log_file


def _fake_subprocess_exec(monkeypatch, module, stdout=b"", stderr=b"", returncode=0):
    """Patch asyncio.create_subprocess_exec (as imported in `module`) to
    return a fake process with canned output instead of spawning a real
    CLI binary."""
    async def fake_exec(*args, **kwargs):
        async def communicate():
            return stdout, stderr
        return SimpleNamespace(communicate=communicate, returncode=returncode)

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_exec)


# ─────────────────────────────────────────────────────────────────────────
# AWS
# ─────────────────────────────────────────────────────────────────────────

def test_aws_blocked_command_never_reaches_subprocess(monkeypatch, isolated_log):
    calls = []

    async def should_not_be_called(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess should not have been invoked for a blocked command")

    monkeypatch.setattr(awscli_claude.asyncio, "create_subprocess_exec", should_not_be_called)

    server = awscli_claude.AWSMCPServer()
    result = asyncio.run(server._execute_aws_command({"command": "iam create-access-key --user-name x"}))

    assert "dangerous" in result[0].text.lower()
    assert calls == []

    entries = cal.read_recent(provider="aws")
    assert len(entries) == 1
    assert entries[0]["allowed"] is False


def test_aws_allowed_command_executes_and_logs(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, awscli_claude, stdout=b'{"Account": "123"}', returncode=0)

    server = awscli_claude.AWSMCPServer()
    result = asyncio.run(server._execute_aws_command({"command": "sts get-caller-identity"}))

    assert "Exit Code: 0" in result[0].text
    assert "123" in result[0].text

    entries = cal.read_recent(provider="aws")
    assert len(entries) == 1
    assert entries[0]["allowed"] is True
    assert entries[0]["exit_code"] == 0
    assert entries[0]["command"] == "sts get-caller-identity"


def test_aws_audit_log_tool_reports_recorded_entries(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, awscli_claude, returncode=0)
    server = awscli_claude.AWSMCPServer()

    asyncio.run(server._execute_aws_command({"command": "s3 ls"}))
    asyncio.run(server._execute_aws_command({"command": "iam delete-user --user-name x"}))

    result = server._get_audit_log({"limit": 10})
    text = result[0].text
    assert "s3 ls" in text
    assert "BLOCKED" in text
    assert "delete-user" in text


# ─────────────────────────────────────────────────────────────────────────
# Azure
# ─────────────────────────────────────────────────────────────────────────

def test_azure_blocked_command_never_reaches_subprocess(monkeypatch, isolated_log):
    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("subprocess should not have been invoked for a blocked command")

    monkeypatch.setattr(azurecli_claude.asyncio, "create_subprocess_exec", should_not_be_called)

    server = azurecli_claude.AzureMCPServer()
    result = asyncio.run(server._execute_azure_command({"command": "vm delete --name x --resource-group y"}))

    assert "dangerous" in result[0].text.lower()
    entries = cal.read_recent(provider="azure")
    assert entries[0]["allowed"] is False


def test_azure_allowed_command_executes_and_logs(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, azurecli_claude, stdout=b"[]", returncode=0)

    server = azurecli_claude.AzureMCPServer()
    result = asyncio.run(server._execute_azure_command({"command": "vm list"}))

    assert "Exit Code: 0" in result[0].text
    entries = cal.read_recent(provider="azure")
    assert entries[0]["allowed"] is True
    assert entries[0]["command"] == "vm list"


# ─────────────────────────────────────────────────────────────────────────
# GCP (gcloud / gsutil / bq share one server class)
# ─────────────────────────────────────────────────────────────────────────

def test_gcloud_blocked_command_never_reaches_subprocess(monkeypatch, isolated_log):
    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("subprocess should not have been invoked for a blocked command")

    monkeypatch.setattr(gcpcli_claude.asyncio, "create_subprocess_exec", should_not_be_called)

    server = gcpcli_claude.GCPMCPServer()
    result = asyncio.run(server._execute_gcloud_command({"command": "compute instances delete my-vm"}))

    assert "dangerous" in result[0].text.lower()
    entries = cal.read_recent(provider="gcp")
    assert entries[0]["tool"] == "cloud-sec-gcloud-cli"
    assert entries[0]["allowed"] is False


def test_gsutil_blocked_command_never_reaches_subprocess(monkeypatch, isolated_log):
    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("subprocess should not have been invoked for a blocked command")

    monkeypatch.setattr(gcpcli_claude.asyncio, "create_subprocess_exec", should_not_be_called)

    server = gcpcli_claude.GCPMCPServer()
    result = asyncio.run(server._execute_gsutil_command({"command": "rm gs://bucket/key"}))

    assert "dangerous" in result[0].text.lower()
    entries = cal.read_recent(provider="gcp")
    assert entries[0]["tool"] == "cloud-sec-gsutil-cli"


def test_bq_query_is_blocked_even_though_query_is_a_read_verb_elsewhere(monkeypatch, isolated_log):
    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("subprocess should not have been invoked for bq query")

    monkeypatch.setattr(gcpcli_claude.asyncio, "create_subprocess_exec", should_not_be_called)

    server = gcpcli_claude.GCPMCPServer()
    result = asyncio.run(server._execute_bq_command({"command": "query 'DELETE FROM t'"}))

    assert "dangerous" in result[0].text.lower()


def test_gcp_allowed_commands_across_all_three_tools_execute_and_log(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, gcpcli_claude, stdout=b"ok", returncode=0)
    server = gcpcli_claude.GCPMCPServer()

    asyncio.run(server._execute_gcloud_command({"command": "compute instances list"}))
    asyncio.run(server._execute_gsutil_command({"command": "ls gs://bucket"}))
    asyncio.run(server._execute_bq_command({"command": "ls"}))

    entries = cal.read_recent(limit=10, provider="gcp")
    assert len(entries) == 3
    tools = {e["tool"] for e in entries}
    assert tools == {"cloud-sec-gcloud-cli", "cloud-sec-gsutil-cli", "cloud-sec-bq-cli"}
    assert all(e["allowed"] for e in entries)


def test_gcp_audit_log_tool_shows_correct_binary_per_tool(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, gcpcli_claude, returncode=0)
    server = gcpcli_claude.GCPMCPServer()

    asyncio.run(server._execute_gcloud_command({"command": "compute instances list"}))
    asyncio.run(server._execute_gsutil_command({"command": "ls gs://bucket"}))
    asyncio.run(server._execute_bq_command({"command": "ls"}))

    text = server._get_audit_log({"limit": 10})[0].text
    assert "gcloud compute instances list" in text
    assert "gsutil ls gs://bucket" in text
    assert "bq ls" in text


# ─────────────────────────────────────────────────────────────────────────
# Cross-provider: shared log file, correct isolation between providers
# ─────────────────────────────────────────────────────────────────────────

def test_entries_from_all_three_providers_share_one_file_without_cross_contamination(monkeypatch, isolated_log):
    _fake_subprocess_exec(monkeypatch, awscli_claude, returncode=0)
    _fake_subprocess_exec(monkeypatch, azurecli_claude, returncode=0)
    _fake_subprocess_exec(monkeypatch, gcpcli_claude, returncode=0)

    aws_server = awscli_claude.AWSMCPServer()
    az_server = azurecli_claude.AzureMCPServer()
    gcp_server = gcpcli_claude.GCPMCPServer()

    asyncio.run(aws_server._execute_aws_command({"command": "s3 ls"}))
    asyncio.run(az_server._execute_azure_command({"command": "vm list"}))
    asyncio.run(gcp_server._execute_gcloud_command({"command": "compute instances list"}))

    assert isolated_log.exists()
    all_entries = cal.read_recent(limit=100)
    assert len(all_entries) == 3
    assert {e["provider"] for e in all_entries} == {"aws", "azure", "gcp"}

    # Each provider's own audit-log tool only ever sees its own entries.
    assert len(cal.read_recent(provider="aws")) == 1
    assert len(cal.read_recent(provider="azure")) == 1
    assert len(cal.read_recent(provider="gcp")) == 1
