#!/usr/bin/env python3
"""
agent_runner.py — AI-Agnostic Agentic Loop for CloudSecAIBot
=============================================================
PURPOSE:
    Receives a natural-language cloud security prompt, connects to the
    existing MCP servers (AWS / Azure / GCP / Prowler), and runs an
    "agentic loop" with any LLM provider via LiteLLM:
        1. Send prompt + available tools to the LLM.
        2. LLM says which tool to call → we call it via MCP.
        3. Feed the result back to the LLM.
        4. Repeat until the LLM gives a final plain-text answer.

HOW IT FITS IN THE PROJECT:
    scheduler_daemon.py  →  calls run_agent()  →  saves to output/
    CLI (direct use)     →  calls run_agent()  →  prints result

SUPPORTED PROVIDERS (just change the model string):
    Anthropic   →  "claude-opus-4-6", "claude-sonnet-4-6"
    OpenAI      →  "gpt-4o", "gpt-4o-mini"
    Google      →  "gemini/gemini-1.5-pro", "gemini/gemini-2.0-flash"
    Mistral     →  "mistral/mistral-large-latest"
    Groq        →  "groq/llama-3.3-70b-versatile"

ENV VARS (set only the ones you need):
    ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / MISTRAL_API_KEY / GROQ_API_KEY
    CLOUDSEC_AI_MODEL      →  default model (falls back to claude-opus-4-6)
    CLOUDSEC_RATE_LIMIT    →  max LLM requests per minute (e.g. 5 for Groq free tier, 0 = no limit)
    CLOUDSEC_DEBUG         →  "true" for verbose LiteLLM logging
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import deque
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path

import litellm
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 ── Setup & Constants
# ──────────────────────────────────────────────────────────────────────────────
# Load .env file if present (optional — shell env vars work too)
load_dotenv()

_debug = os.getenv("CLOUDSEC_DEBUG", "false").lower() == "true"
litellm.set_verbose = _debug  # turn on LiteLLM request/response logs when debugging

logging.basicConfig(
    level=logging.DEBUG if _debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("agent-runner")

BASE_DIR   = Path(__file__).parent   # project root
OUTPUT_DIR = BASE_DIR / "output"     # where result files are written

# Max LLM API calls per minute. Read from env so it's easy to adjust per provider.
# Set to 5 for Groq free tier, 0 to disable rate limiting entirely.
# Example: CLOUDSEC_RATE_LIMIT=5
RATE_LIMIT_RPM: int = int(os.getenv("CLOUDSEC_RATE_LIMIT", "0"))

# Sliding window of recent LLM call timestamps used by the rate limiter.
# Shared across all agent runs in the same process (e.g. scheduled jobs).
_llm_call_times: deque = deque()


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 ── MCP Server Registry
# ──────────────────────────────────────────────────────────────────────────────
# Maps a short name → how to launch that MCP server as a subprocess.
# The MCP client spawns each server via stdio and talks JSON-RPC with it.
#
# To add a new cloud provider:
#   1. Create its MCP server script (e.g. newcloud_claude.py)
#   2. Add an entry here — nothing else needs to change.
#
# sys.executable ensures the same Python environment is used for all scripts.

MCP_SERVERS: dict[str, StdioServerParameters] = {
    "aws":     StdioServerParameters(command=sys.executable, args=[str(BASE_DIR / "awscli_claude.py")]),
    "azure":   StdioServerParameters(command=sys.executable, args=[str(BASE_DIR / "azurecli_claude.py")]),
    "gcp":     StdioServerParameters(command=sys.executable, args=[str(BASE_DIR / "gcpcli_claude.py")]),
    "prowler": StdioServerParameters(command=sys.executable, args=[str(BASE_DIR / "prowler_mcp.py")]),
}

# The system prompt shapes how the LLM behaves during every agent run.
SYSTEM_PROMPT = (
    "You are a cloud security analyst. Use the available tools to answer "
    "the user's cloud security question. Run all necessary commands, collect "
    "all required data, and provide a clear structured actionable summary. "
    "Do not ask for clarification — make sensible assumptions and proceed."
)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 ── MCP ↔ LiteLLM Tool Schema Conversion
# ──────────────────────────────────────────────────────────────────────────────
def _to_litellm_tool(mcp_tool) -> dict:
    """
    Convert an MCP tool definition to the OpenAI/LiteLLM tool format.

    MCP tools have: name, description, inputSchema (JSON Schema)
    LiteLLM needs:  { "type": "function", "function": { name, description, parameters } }
    """
    return {
        "type": "function",
        "function": {
            "name":        mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters":  mcp_tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 ── Rate Limiter
# ──────────────────────────────────────────────────────────────────────────────
async def _wait_for_rate_limit() -> None:
    """
    Enforce the CLOUDSEC_RATE_LIMIT requests-per-minute cap before each LLM call.

    HOW IT WORKS (sliding window):
      - We keep a deque of timestamps for every LLM call made in the last 60s.
      - Before each call, we drop timestamps older than 60 seconds.
      - If the number of remaining timestamps equals the limit, we calculate
        exactly how long to wait until the oldest call falls outside the window,
        then sleep for that duration.
      - After sleeping, we record the new call timestamp and proceed.

    WHY SLIDING WINDOW vs fixed window:
      A fixed window resets every minute on the clock (e.g. at :00, :01...).
      A sliding window is more accurate — it always looks at the last 60 seconds
      from right now, which prevents bursting at window boundaries.

    If CLOUDSEC_RATE_LIMIT is 0 (default), this function returns immediately
    with no delay.
    """
    if RATE_LIMIT_RPM <= 0:
        return  # Rate limiting disabled

    now = time.monotonic()
    window = 60.0  # 1 minute sliding window

    # Drop timestamps that are older than the window
    while _llm_call_times and now - _llm_call_times[0] >= window:
        _llm_call_times.popleft()

    # If we're at the limit, wait until the oldest call exits the window
    if len(_llm_call_times) >= RATE_LIMIT_RPM:
        wait_seconds = window - (now - _llm_call_times[0])
        if wait_seconds > 0:
            logger.info(
                f"[rate_limit] {RATE_LIMIT_RPM} RPM limit reached. "
                f"Waiting {wait_seconds:.1f}s before next LLM call..."
            )
            await asyncio.sleep(wait_seconds)

        # Clean up again after the sleep
        now = time.monotonic()
        while _llm_call_times and now - _llm_call_times[0] >= window:
            _llm_call_times.popleft()

    # Record this call
    _llm_call_times.append(time.monotonic())


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 ── Connect to MCP Servers
# ──────────────────────────────────────────────────────────────────────────────
async def connect_servers(
    stack: AsyncExitStack,
    servers_to_use: list[str] | None,
) -> tuple[dict[str, ClientSession], list[dict], dict[str, str]]:
    """
    Spawn and connect to each MCP server subprocess, then collect their tools.

    Uses AsyncExitStack so all connections stay open for the full agent run
    and are automatically cleaned up when the stack closes.

    Args:
        stack:          An open AsyncExitStack that owns the connection lifetimes.
        servers_to_use: Subset of server names to connect (None = all).

    Returns:
        sessions       — { server_name: ClientSession }
        tools_for_llm  — all tools in LiteLLM format (passed to the LLM)
        tool_server_map — { tool_name: server_name } for routing tool calls
    """
    active = {
        name: params
        for name, params in MCP_SERVERS.items()
        if servers_to_use is None or name in servers_to_use
    }

    sessions: dict[str, ClientSession]  = {}
    tools_for_llm: list[dict]           = []
    tool_server_map: dict[str, str]     = {}

    for server_name, server_params in active.items():
        try:
            # Spawn the server subprocess and open stdio streams
            read, write = await stack.enter_async_context(stdio_client(server_params))
            # Wrap streams in an MCP ClientSession (handles JSON-RPC framing)
            session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
            # Perform the MCP handshake
            await session.initialize()
            sessions[server_name] = session

            # Discover all tools this server exposes
            for tool in (await session.list_tools()).tools:
                tools_for_llm.append(_to_litellm_tool(tool))
                tool_server_map[tool.name] = server_name

            logger.info(f"[connect] [{server_name}] ready — {len([t for t in tool_server_map if tool_server_map[t] == server_name])} tools")

        except Exception as exc:
            # Non-fatal: one broken server won't stop the others
            logger.warning(f"[connect] [{server_name}] failed: {exc}")

    return sessions, tools_for_llm, tool_server_map


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6 ── Execute a Single Tool Call via MCP
# ──────────────────────────────────────────────────────────────────────────────
async def call_tool(
    tool_name: str,
    tool_args: dict,
    sessions: dict[str, ClientSession],
    tool_server_map: dict[str, str],
) -> str:
    """
    Route a tool call to the correct MCP server and return the result as text.

    The LLM receives this return value as the "tool result" on the next turn.
    Always returns a string — never raises — so the loop can continue even
    if a tool fails.

    Args:
        tool_name:       Name of the tool the LLM wants to call.
        tool_args:       Arguments the LLM provided for this call.
        sessions:        Active server sessions from connect_servers().
        tool_server_map: Which server handles which tool.

    Returns:
        Tool output as plain text, or an error message string.
    """
    server_name = tool_server_map.get(tool_name)
    if not server_name or server_name not in sessions:
        return f"Error: tool '{tool_name}' not found in any connected MCP server."

    logger.info(f"[call_tool] {tool_name} → [{server_name}]")
    try:
        result = await sessions[server_name].call_tool(tool_name, tool_args)
        # MCP results are a list of content items — extract all text parts
        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts) if texts else "Tool executed (no output)"
    except Exception as exc:
        return f"Error calling [{tool_name}]: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7 ── Agentic Loop
# ──────────────────────────────────────────────────────────────────────────────
async def run_loop(
    prompt: str,
    model: str,
    sessions: dict[str, ClientSession],
    tools_for_llm: list[dict],
    tool_server_map: dict[str, str],
    max_iterations: int,
) -> str:
    """
    Iteratively call the LLM and execute its tool requests until it gives
    a final plain-text answer (or we hit max_iterations).

    Conversation flow per iteration:
        messages → LiteLLM → response
            if response has tool_calls:
                execute each tool → append result to messages → repeat
            else:
                return response.content as the final answer

    Args:
        prompt:          The user's security question.
        model:           LiteLLM model string (provider-agnostic).
        sessions:        Active MCP sessions for tool execution.
        tools_for_llm:   Tool schemas to send to the LLM.
        tool_server_map: Routing table for call_tool().
        max_iterations:  Safety cap on the number of loop iterations.

    Returns:
        The LLM's final plain-text answer.
    """
    # Seed the conversation with the system role and the user's question
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    for iteration in range(1, max_iterations + 1):
        logger.info(f"[loop] Iteration {iteration}/{max_iterations}")

        # ── Respect rate limit before calling the LLM ────────────────────
        # This will sleep if we've hit the CLOUDSEC_RATE_LIMIT RPM cap.
        # No-op if CLOUDSEC_RATE_LIMIT is 0 (default).
        await _wait_for_rate_limit()

        # ── Call the LLM (works with any provider via LiteLLM) ────────────
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                tools=tools_for_llm or None,
                tool_choice="auto" if tools_for_llm else None,
            )
        except Exception as exc:
            logger.error(f"[loop] LLM call failed: {exc}")
            return f"LLM call failed (model={model}): {exc}"

        message = response.choices[0].message

        # ── No tool calls → LLM is done ───────────────────────────────────
        if not message.tool_calls:
            logger.info(f"[loop] Done in {iteration} iteration(s)")
            return message.content or ""

        # ── Append the assistant turn (with tool_calls) to history ─────────
        # The tool_call_id fields must be preserved exactly so subsequent
        # "tool" role messages can reference them correctly.
        messages.append({
            "role":       "assistant",
            "content":    message.content or "",
            "tool_calls": [
                {
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        })

        # ── Execute each requested tool and feed results back ──────────────
        for tc in message.tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_args = {}

            result_text = await call_tool(
                tc.function.name, tool_args, sessions, tool_server_map
            )

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "name":         tc.function.name,
                "content":      result_text,
            })

    # Exhausted iterations without a final answer
    logger.warning(f"[loop] Reached max iterations ({max_iterations})")
    return f"[Stopped at max iterations ({max_iterations}) — answer may be incomplete]"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7 ── Save Result to File
# ──────────────────────────────────────────────────────────────────────────────
def save_result(task_id: str | None, prompt: str, model: str, result: str) -> Path:
    """
    Write the agent's final answer to output/<task_id>_<timestamp>.txt.

    The plain-text format keeps results easy to inspect and grep.
    The scheduler_mcp.py "get results" tool simply lists files in output/.

    Args:
        task_id: Label for the filename (e.g. "daily-s3-check"). None → "adhoc".
        prompt:  The original prompt (included for context in the file).
        model:   The model that was used.
        result:  The LLM's final answer.

    Returns:
        Path to the written file.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath  = OUTPUT_DIR / f"{task_id or 'adhoc'}_{timestamp}.txt"

    filepath.write_text(
        f"Task     : {task_id or 'ad-hoc'}\n"
        f"Model    : {model}\n"
        f"Timestamp: {timestamp}\n"
        f"Prompt   : {prompt}\n"
        f"{'=' * 60}\n"
        f"{result}\n",
        encoding="utf-8",
    )
    logger.info(f"[save] Result written → {filepath}")
    return filepath


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8 ── Public Entry Point: run_agent()
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
    Orchestrate a full agent run: connect → loop → save → return.

    Called by scheduler_daemon.py for scheduled jobs,
    and by the CLI below for ad-hoc checks.

    Args:
        prompt:         The cloud security question to answer.
        model:          LiteLLM model string. Priority:
                          1. This argument
                          2. CLOUDSEC_AI_MODEL env var
                          3. Default: "claude-opus-4-6"
        max_iterations: Max LLM ↔ tool rounds (default 20).
        task_id:        Output filename label (e.g. "daily-s3-check").
        save_output:    Write result to output/ (default True).
        servers_to_use: Which MCP servers to connect (None = all).

    Returns:
        The LLM's final plain-text answer.
    """
    resolved_model = model or os.getenv("CLOUDSEC_AI_MODEL", "claude-opus-4-6")
    logger.info(f"[run_agent] model={resolved_model} | task={task_id or 'ad-hoc'} | servers={servers_to_use or 'all'}")

    async with AsyncExitStack() as stack:
        # Step 1: Connect to MCP servers and collect tools
        sessions, tools_for_llm, tool_server_map = await connect_servers(stack, servers_to_use)

        if not sessions:
            return "Error: Could not connect to any MCP server. Check server scripts and dependencies."

        logger.info(f"[run_agent] {len(tools_for_llm)} tools available from: {list(sessions.keys())}")

        # Step 2: Run the agentic loop
        result = await run_loop(
            prompt=prompt,
            model=resolved_model,
            sessions=sessions,
            tools_for_llm=tools_for_llm,
            tool_server_map=tool_server_map,
            max_iterations=max_iterations,
        )

    # Step 3: Save result (connections already closed cleanly above)
    if save_output and result:
        save_result(task_id, prompt, resolved_model, result)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9 ── CLI Entry Point
# ──────────────────────────────────────────────────────────────────────────────
# Run directly for ad-hoc checks:
#   python3 agent_runner.py "Which S3 buckets are public?"
#   python3 agent_runner.py "List Azure NSGs open to internet" --model gpt-4o
#   python3 agent_runner.py "Audit GCP IAM" --servers gcp,prowler

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="CloudSecAIBot — AI-agnostic cloud security agent",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("prompt", help="Cloud security question")
    parser.add_argument("--model",          default=None, help="LiteLLM model string (e.g. gpt-4o, claude-opus-4-6)")
    parser.add_argument("--task-id",        default=None, help="Label for the output filename")
    parser.add_argument("--servers",        default=None, help="Comma-separated servers: aws,azure,gcp,prowler (default: all)")
    parser.add_argument("--max-iterations", type=int, default=20, help="Max tool-call rounds (default: 20)")
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
