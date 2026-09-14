#!/usr/bin/env python3
"""
command_audit_log.py — Shared append-only audit trail for CloudSecAIBot's
AWS / Azure / GCP MCP servers (awscli_claude.py, azurecli_claude.py,
gcpcli_claude.py).

Every command any of those servers' CLI-execution tools attempt — whether
it was allowed and run, or blocked by cloud_command_safety.py — is appended
here as one JSON line. This exists because CloudSentinel's scheduled jobs
already get a timestamped result file per run (see scheduler_daemon.py),
but ad-hoc queries run through Claude Desktop or agent_runner.py previously
left no record at all once the response was returned — there was no way to
later answer "what commands actually ran against this account, and when?"

FORMAT: JSON Lines (one JSON object per line) at output/command_audit.log.
Chosen over free-text logging so entries are trivially greppable/parseable
(`jq` on any line) without a custom parser, e.g.:
    tail -f output/command_audit.log | jq .
    jq 'select(.allowed == false)' output/command_audit.log

WHAT'S DELIBERATELY NOT LOGGED: command stdout/stderr. Logging full output
would duplicate potentially sensitive account data (ARNs, resource names,
IAM policy documents, ...) into a second file with its own retention/access
surface, for marginal benefit over the exit code + command text already
captured here. If you need full output, that's what output/<task_id>_*.txt
from agent_runner.py's scheduled runs already provides.

CONCURRENCY NOTE: aws/azure/gcp each run as a separate OS process (spawned
over stdio by the MCP client) and all three can append to this same file
concurrently. Each entry is written with a single write() syscall under
O_APPEND, which is atomic on POSIX for writes under PIPE_BUF — sufficient
for this tool's usage pattern (interactive, low-frequency). No file lock is
taken; if you're adapting this for high-concurrency use, add one.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = OUTPUT_DIR / "command_audit.log"


def log_command(
    provider: str,
    tool: str,
    command: str,
    allowed: bool,
    block_reason: Optional[str] = None,
    exit_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """
    Append one audit entry.

    Never raises — a logging failure (e.g. a read-only filesystem) must
    never take down the MCP server or block the command it's trying to log.
    """
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "tool": tool,
            "command": command,
            "allowed": allowed,
            "block_reason": block_reason,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        pass  # Auditing must never break command execution.


def read_recent(limit: int = 20, provider: Optional[str] = None) -> list[dict]:
    """
    Return up to the most recent `limit` audit entries, optionally filtered
    to one provider ("aws" / "azure" / "gcp"). Malformed lines are skipped
    rather than raising, since a log is more useful partially-readable than
    not readable at all.
    """
    if not LOG_FILE.exists():
        return []

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if provider is None or entry.get("provider") == provider:
                entries.append(entry)

    return entries[-limit:]
