#!/usr/bin/env python3
"""
agent_runner_cli.py — Claude Code SDK Backend for CloudSecAIBot
===============================================================
PURPOSE:
    Drop-in replacement for agent_runner.py that uses the Claude Code SDK
    instead of the LiteLLM API. The Claude Code SDK runs the local `claude`
    CLI binary as its engine, so no separate API key is needed — it uses
    whatever account the `claude` CLI is already authenticated with.

HOW IT DIFFERS FROM agent_runner.py:
    agent_runner.py      →  litellm.acompletion() → Anthropic/OpenAI/Gemini/etc. API
    agent_runner_cli.py  →  claude_code_sdk.query() → local `claude` CLI binary

    The agentic loop (tool call → MCP execution → feed result back → repeat)
    is managed entirely inside the claude CLI process. We do NOT manually
    dispatch tool calls — the SDK streams back AssistantMessage and
    ResultMessage objects, and we just collect the final answer.

HOW IT FITS IN THE PROJECT:
    Set CLOUDSEC_BACKEND=cli in .env to activate this backend.
    scheduler_daemon.py reads that variable and imports run_agent() from
    this file instead of agent_runner.py. The function signature is identical
    so the rest of the project is unaffected.

LIMITATIONS vs agent_runner.py:
    - Only Claude models are supported (not gpt-4o, gemini, mistral, etc.)
      because the claude CLI only runs Claude models.
    - CLOUDSEC_RATE_LIMIT is not applied here — the Claude CLI manages
      its own request pacing internally.
    - Requires `claude` CLI to be installed and authenticated:
        which claude          # should print a path
        claude --version      # should print version

INSTALL:
    pip install claude-code-sdk
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 ── Setup & Constants
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv(override=True)

# The CLI backend authenticates via the local `claude` CLI binary, not an API key.
# If ANTHROPIC_API_KEY is set (e.g. a placeholder from .env), the SDK will try to
# use it and fail. Remove it so the SDK falls back to the CLI's stored auth.
os.environ.pop("ANTHROPIC_API_KEY", None)

_debug = os.getenv("CLOUDSEC_DEBUG", "false").lower() == "true"
logging.basicConfig(
    level=logging.DEBUG if _debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("agent-runner-cli")

BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# The system prompt is identical to agent_runner.py so both backends
# produce consistently structured answers.
SYSTEM_PROMPT = (
    "You are a cloud security analyst. Use the available tools to answer "
    "the user's cloud security question. Run all necessary commands, collect "
    "all required data, and provide a clear structured actionable summary. "
    "Do not ask for clarification — make sensible assumptions and proceed."
)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 ── MCP Server Registry (Claude Code SDK format)
# ──────────────────────────────────────────────────────────────────────────────
# Same 4 servers as agent_runner.py, but expressed as McpStdioServerConfig
# dicts instead of StdioServerParameters. The claude CLI will spawn these
# subprocesses itself and manage the MCP handshake internally.
#
# Format: { "server_name": { "type": "stdio", "command": ..., "args": [...] } }
#
# To add a new provider:
#   1. Create its MCP server script (e.g. newcloud_claude.py)
#   2. Add an entry here — nothing else needs to change.

MCP_SERVERS_CLI: dict[str, dict] = {
    "aws": {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(BASE_DIR / "awscli_claude.py")],
    },
    "azure": {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(BASE_DIR / "azurecli_claude.py")],
    },
    "gcp": {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(BASE_DIR / "gcpcli_claude.py")],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 ── Save Result to File
# ──────────────────────────────────────────────────────────────────────────────
def save_result(task_id: str | None, prompt: str, model: str, result: str) -> Path:
    """
    Write the agent's final answer to output/<task_id>_<timestamp>.txt.

    Identical to agent_runner.save_result() — same format so result files
    from both backends are interchangeable.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath  = OUTPUT_DIR / f"{task_id or 'adhoc'}_{timestamp}.txt"

    filepath.write_text(
        f"Task     : {task_id or 'ad-hoc'}\n"
        f"Model    : {model}\n"
        f"Backend  : claude-code-sdk\n"
        f"Timestamp: {timestamp}\n"
        f"Prompt   : {prompt}\n"
        f"{'=' * 60}\n"
        f"{result}\n",
        encoding="utf-8",
    )
    logger.info(f"[save] Result written → {filepath}")
    return filepath


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 ── Public Entry Point: run_agent()
# ──────────────────────────────────────────────────────────────────────────────
async def run_agent(
    prompt: str,
    model: str | None = None,
    max_iterations: int = 20,
    task_id: str | None = None,
    save_output: bool = True,
    servers_to_use: list[str] | None = None,
) -> str:
    """
    Run a cloud security prompt using the Claude Code SDK backend.

    This function has the same signature as agent_runner.run_agent() so
    scheduler_daemon.py can call either one without modification.

    HOW IT WORKS:
        1. Builds a dict of MCP server configs (filtered by servers_to_use).
        2. Creates ClaudeCodeOptions with model, system prompt, MCP servers,
           max turns, and bypassPermissions so tool calls aren't blocked.
        3. Calls claude_code_sdk.query() which:
              a. Spawns the `claude` CLI binary as a subprocess.
              b. Passes the MCP server configs — claude CLI spawns those
                 subprocesses and handles all MCP tool call/result cycles.
              c. Streams back AssistantMessage and ResultMessage objects.
        4. Extracts the final answer from ResultMessage.result.
        5. Saves to output/ if save_output=True.

    Args:
        prompt:         The cloud security question to answer.
        model:          Claude model string. Priority:
                          1. This argument
                          2. CLOUDSEC_AI_MODEL env var
                          3. Default: "claude-opus-4-6"
                        NOTE: Only Claude models work here (not gpt-4o etc.)
        max_iterations: Max agentic loop turns (maps to ClaudeCodeOptions.max_turns).
        task_id:        Output filename label (e.g. "daily-s3-check").
        save_output:    Write result to output/ (default True).
        servers_to_use: Which MCP servers to connect (None = all four).

    Returns:
        The final plain-text answer from Claude.
    """
    _CLI_DEFAULT_MODEL = "claude-sonnet-4-6"
    _env_model = os.getenv("CLOUDSEC_AI_MODEL", _CLI_DEFAULT_MODEL)
    # CLI backend only supports Claude models — fall back if a non-Claude model is set
    if not _env_model.startswith("claude"):
        logger.warning(
            f"[run_agent_cli] CLOUDSEC_AI_MODEL={_env_model!r} is not a Claude model "
            f"and is not supported by the CLI backend. Falling back to {_CLI_DEFAULT_MODEL}."
        )
        _env_model = _CLI_DEFAULT_MODEL
    resolved_model = model or _env_model
    logger.info(
        f"[run_agent_cli] model={resolved_model} | "
        f"task={task_id or 'ad-hoc'} | "
        f"servers={servers_to_use or 'all'}"
    )

    # ── Build the MCP servers dict, optionally filtering by servers_to_use ────
    # servers_to_use=None means use all four; ["aws", "gcp"] means only those two.
    mcp_servers = {
        name: config
        for name, config in MCP_SERVERS_CLI.items()
        if servers_to_use is None or name in servers_to_use
    }

    if not mcp_servers:
        return "Error: No MCP servers matched the requested servers_to_use list."

    logger.info(f"[run_agent_cli] MCP servers: {list(mcp_servers.keys())}")

    # ── Call claude CLI directly via subprocess (bypasses SDK rate_limit_event bug) ──
    # The claude_code_sdk.query() raises "Unknown message type: rate_limit_event"
    # on newer claude CLI builds because the SDK hasn't caught up. Calling
    # `claude --print` as a subprocess is equivalent and avoids the SDK entirely.
    mcp_config = {
        "mcpServers": {
            name: {
                "type": "stdio",
                "command": cfg["command"],
                "args": cfg["args"],
            }
            for name, cfg in mcp_servers.items()
        }
    }

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=tempfile.gettempdir()
    )
    try:
        json.dump(mcp_config, tmp)
        tmp.close()
        config_path = tmp.name
        logger.debug(f"[mcp_config] {config_path}\n{json.dumps(mcp_config, indent=2)}")

        # Prompt is passed via stdin so variadic flags (--disallowedTools) don't
        # accidentally consume it as their value.
        cmd = [
            "claude", "--print",
            "--output-format", "stream-json",
            "--verbose",
            "--model", resolved_model,
            "--mcp-config", config_path,
            "--max-turns", str(max_iterations),
            "--dangerously-skip-permissions",
            "--disallowedTools", "Bash",
        ]

        logger.info(f"[run_agent_cli] Spawning claude --print --model {resolved_model}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        final_text = ""
        stderr_lines: list[str] = []

        # ── Stream and log every event from claude CLI ────────────────────────
        # stream-json emits one JSON object per line. Types we handle:
        #   assistant  — Claude's text reasoning and tool_use calls
        #   user       — MCP tool results fed back to Claude
        #   result     — Final answer with cost/turn metadata
        async for raw_line in proc.stdout:
            line = raw_line.decode().strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"[raw] {line}")
                continue

            etype = event.get("type", "")

            if etype == "assistant":
                for block in event.get("message", {}).get("content", []):
                    btype = block.get("type", "")
                    if btype == "text" and block.get("text", "").strip():
                        logger.info(f"[claude] {block['text'].strip()[:400]}")
                    elif btype == "tool_use":
                        tool_input = json.dumps(block.get("input", {}))
                        logger.info(
                            f"[mcp_call] tool={block.get('name')} "
                            f"input={tool_input[:300]}"
                        )

            elif etype == "user":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, list):
                            for chunk in content:
                                if chunk.get("type") == "text":
                                    logger.info(
                                        f"[mcp_result] {chunk['text'].strip()[:400]}"
                                    )
                        else:
                            logger.info(f"[mcp_result] {str(content)[:400]}")

            elif etype == "result":
                final_text = event.get("result", "")
                cost = event.get("cost_usd") or event.get("total_cost_usd")
                turns = event.get("num_turns", "?")
                cost_str = f"${cost:.4f}" if cost is not None else "unknown"
                logger.info(
                    f"[run_agent_cli] Done — turns={turns} cost={cost_str}"
                )

        # Drain stderr for error reporting
        stderr_bytes = await proc.stderr.read()
        await proc.wait()

    finally:
        os.unlink(tmp.name)

    if proc.returncode != 0:
        err = stderr_bytes.decode().strip()
        logger.error(f"[run_agent_cli] claude CLI exited {proc.returncode}: {err}")
        return f"Error: claude CLI failed (exit {proc.returncode}) — {err}"

    if not final_text:
        logger.warning("[run_agent_cli] No output from claude CLI.")
        return "Error: claude CLI returned no output."

    # ── Save result to output/ ────────────────────────────────────────────────
    if save_output:
        save_result(task_id, prompt, resolved_model, final_text)

    return final_text


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 ── CLI Entry Point
# ──────────────────────────────────────────────────────────────────────────────
# Run directly for ad-hoc checks:
#   python3 agent_runner_cli.py "Which S3 buckets are public?"
#   python3 agent_runner_cli.py "Audit GCP IAM" --servers gcp,prowler
#   python3 agent_runner_cli.py "Check Azure NSGs" --model claude-sonnet-4-6

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="CloudSecAIBot — Claude Code SDK backend",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("prompt", help="Cloud security question")
    parser.add_argument(
        "--model",
        default=None,
        help="Claude model string (e.g. claude-opus-4-6, claude-sonnet-4-6)\n"
             "Note: only Claude models are supported in this backend.",
    )
    parser.add_argument("--task-id",        default=None,  help="Label for the output filename")
    parser.add_argument("--servers",        default=None,  help="Comma-separated servers: aws,azure,gcp,prowler (default: all)")
    parser.add_argument("--max-iterations", type=int, default=20, help="Max agentic loop turns (default: 20)")
    args = parser.parse_args()

    servers_list = [s.strip() for s in args.servers.split(",")] if args.servers else None

    result = asyncio.run(run_agent(
        prompt=args.prompt,
        model=args.model,
        task_id=args.task_id,
        max_iterations=args.max_iterations,
        servers_to_use=servers_list,
    ))

    print("\n" + "=" * 60 + "\nRESULT\n" + "=" * 60)
    print(result)
