#!/usr/bin/env python3
"""
scheduler_mcp.py — Scheduler MCP Server for CloudSecAIBot
==========================================================
PURPOSE:
    Exposes scheduling capabilities to Claude Desktop (or any MCP client)
    via the Model Context Protocol. Claude can create, list, and delete
    scheduled cloud security jobs by calling the tools defined here.
    All jobs are written to jobs.json, which scheduler_daemon.py polls.

HOW IT FITS IN THE PROJECT:
    Claude Desktop  →  scheduler_mcp.py  →  reads/writes jobs.json
                                                     ↑
                                         scheduler_daemon.py polls this file

TOOLS EXPOSED:
    schedule_create_task   → add a new scheduled job to jobs.json
    schedule_list_tasks    → show all jobs currently in jobs.json
    schedule_delete_task   → remove a job from jobs.json
    schedule_toggle_task   → enable or disable a job without deleting it
    schedule_get_results   → list result files in output/ for a task

EXAMPLE CONVERSATION WITH CLAUDE:
    User:   "Schedule a daily S3 public bucket check at 9am"
    Claude: (calls schedule_create_task with task_id, cron, prompt)
    Claude: "Done — scheduled daily at 09:00. The daemon will run it automatically."

    User:   "Show me all scheduled tasks"
    Claude: (calls schedule_list_tasks)
    Claude: "You have 2 scheduled tasks: ..."

    User:   "Show me the results from yesterday's S3 check"
    Claude: (calls schedule_get_results with task_id)
    Claude: "Found 3 result files. Here is the latest: ..."
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 ── Setup & Constants
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("scheduler-mcp")

BASE_DIR   = Path(__file__).parent
JOBS_FILE  = BASE_DIR / "jobs.json"    # shared with scheduler_daemon.py
OUTPUT_DIR = BASE_DIR / "output"       # where agent_runner saves results

app = Server("cloudsec-scheduler")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 ── Jobs File Helpers
# ──────────────────────────────────────────────────────────────────────────────
def read_jobs() -> list[dict]:
    """
    Read all jobs from jobs.json.
    Returns an empty list if the file doesn't exist or is empty.
    """
    if not JOBS_FILE.exists():
        return []
    try:
        raw = JOBS_FILE.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Failed to read jobs file: {exc}")
        return []


def write_jobs(jobs: list[dict]) -> None:
    """
    Write the full jobs list back to jobs.json.
    Pretty-printed so it's human-readable and easy to debug.
    """
    JOBS_FILE.write_text(
        json.dumps(jobs, indent=2, default=str),
        encoding="utf-8",
    )


def find_job(jobs: list[dict], task_id: str) -> dict | None:
    """Return the first job matching task_id, or None if not found."""
    return next((j for j in jobs if j.get("task_id") == task_id), None)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 ── Tool Definitions
# ──────────────────────────────────────────────────────────────────────────────
@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    Declare all tools this MCP server exposes.
    Claude Desktop reads this list to know what scheduling actions are available.
    """
    return [

        Tool(
            name="schedule_create_task",
            description=(
                "Create a new scheduled cloud security task. "
                "The task will run automatically on the given cron schedule. "
                "Use standard 5-field cron syntax: minute hour day month weekday. "
                "Examples: '0 9 * * *' = daily at 9am, '0 */6 * * *' = every 6 hours."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Unique identifier for this task (e.g. 'daily-s3-check'). No spaces.",
                    },
                    "cron": {
                        "type": "string",
                        "description": "5-field cron schedule (e.g. '0 9 * * *' for daily at 9am).",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The cloud security question the agent will answer on each run.",
                    },
                    "servers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["aws", "azure", "gcp", "prowler"]},
                        "description": "Which MCP servers to use (optional). Default: all servers.",
                    },
                },
                "required": ["task_id", "cron", "prompt"],
            },
        ),

        Tool(
            name="schedule_list_tasks",
            description="List all scheduled tasks currently in jobs.json, including their status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),

        Tool(
            name="schedule_delete_task",
            description="Permanently delete a scheduled task from jobs.json.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task_id of the job to delete.",
                    },
                },
                "required": ["task_id"],
            },
        ),

        Tool(
            name="schedule_toggle_task",
            description=(
                "Enable or disable a scheduled task without deleting it. "
                "Disabled tasks remain in jobs.json but the daemon will not run them."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task_id of the job to toggle.",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "True to enable, False to disable.",
                    },
                },
                "required": ["task_id", "enabled"],
            },
        ),

        Tool(
            name="schedule_get_results",
            description=(
                "List result files saved in the output directory for a specific task. "
                "Returns the content of the most recent result file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task_id to look up results for.",
                    },
                    "show_latest": {
                        "type": "boolean",
                        "description": "If true, include the content of the most recent result file (default: true).",
                    },
                },
                "required": ["task_id"],
            },
        ),

    ]


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 ── Tool Handlers
# ──────────────────────────────────────────────────────────────────────────────
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """
    Route incoming tool calls to the appropriate handler function.
    Each handler reads/writes jobs.json and returns a plain-text response.
    """
    if name == "schedule_create_task":
        return _handle_create(arguments)
    elif name == "schedule_list_tasks":
        return _handle_list()
    elif name == "schedule_delete_task":
        return _handle_delete(arguments)
    elif name == "schedule_toggle_task":
        return _handle_toggle(arguments)
    elif name == "schedule_get_results":
        return _handle_get_results(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Handler: Create ───────────────────────────────────────────────────────────
def _handle_create(args: dict) -> list[TextContent]:
    """
    Add a new job to jobs.json.
    Rejects duplicate task_ids to prevent accidental overwrites.
    """
    task_id = args.get("task_id", "").strip()
    cron    = args.get("cron", "").strip()
    prompt  = args.get("prompt", "").strip()

    if not task_id or not cron or not prompt:
        return [TextContent(type="text", text="Error: task_id, cron, and prompt are all required.")]

    jobs = read_jobs()

    # Prevent duplicate task IDs
    if find_job(jobs, task_id):
        return [TextContent(
            type="text",
            text=f"Error: A task with task_id '{task_id}' already exists. Delete it first or use a different task_id.",
        )]

    # Build the new job entry.
    # model is intentionally not stored here — it is configured globally
    # via the CLOUDSEC_AI_MODEL env var in .env at installation time.
    new_job = {
        "task_id":    task_id,
        "cron":       cron,
        "prompt":     prompt,
        "servers":    args.get("servers"),    # None → daemon uses all servers
        "enabled":    True,
        "created_at": datetime.now().isoformat(),
    }

    jobs.append(new_job)
    write_jobs(jobs)

    logger.info(f"[create] Task created: {task_id} | cron={cron}")
    return [TextContent(
        type="text",
        text=(
            f"✅ Task '{task_id}' scheduled successfully.\n"
            f"Cron     : {cron}\n"
            f"Prompt   : {prompt}\n"
            f"Servers  : {new_job['servers'] or 'all'}\n\n"
            f"The scheduler daemon will pick this up within 30 seconds."
        ),
    )]


# ── Handler: List ─────────────────────────────────────────────────────────────
def _handle_list() -> list[TextContent]:
    """
    Return a formatted summary of all jobs in jobs.json.
    """
    jobs = read_jobs()

    if not jobs:
        return [TextContent(
            type="text",
            text="No scheduled tasks found. Use schedule_create_task to add one.",
        )]

    lines = [f"Found {len(jobs)} scheduled task(s):\n"]
    for job in jobs:
        status = "✅ enabled" if job.get("enabled", True) else "⏸ disabled"
        lines.append(
            f"─────────────────────────────\n"
            f"Task ID  : {job.get('task_id')}\n"
            f"Status   : {status}\n"
            f"Cron     : {job.get('cron')}\n"
            f"Servers  : {job.get('servers') or 'all'}\n"
            f"Prompt   : {job.get('prompt')}\n"
            f"Created  : {job.get('created_at', 'unknown')}\n"
        )

    return [TextContent(type="text", text="\n".join(lines))]


# ── Handler: Delete ───────────────────────────────────────────────────────────
def _handle_delete(args: dict) -> list[TextContent]:
    """
    Remove a job from jobs.json by task_id.
    The scheduler daemon will stop running it within 30 seconds.
    """
    task_id = args.get("task_id", "").strip()
    if not task_id:
        return [TextContent(type="text", text="Error: task_id is required.")]

    jobs = read_jobs()
    original_count = len(jobs)
    jobs = [j for j in jobs if j.get("task_id") != task_id]

    if len(jobs) == original_count:
        return [TextContent(type="text", text=f"Error: No task found with task_id '{task_id}'.")]

    write_jobs(jobs)
    logger.info(f"[delete] Task deleted: {task_id}")
    return [TextContent(
        type="text",
        text=f"✅ Task '{task_id}' deleted. The daemon will stop running it within 30 seconds.",
    )]


# ── Handler: Toggle ───────────────────────────────────────────────────────────
def _handle_toggle(args: dict) -> list[TextContent]:
    """
    Set the enabled flag on a job without removing it.
    Useful for temporarily pausing a job.
    """
    task_id = args.get("task_id", "").strip()
    enabled = args.get("enabled")

    if not task_id or enabled is None:
        return [TextContent(type="text", text="Error: task_id and enabled (true/false) are required.")]

    jobs = read_jobs()
    job  = find_job(jobs, task_id)

    if not job:
        return [TextContent(type="text", text=f"Error: No task found with task_id '{task_id}'.")]

    job["enabled"] = bool(enabled)
    write_jobs(jobs)

    status = "enabled" if enabled else "disabled"
    logger.info(f"[toggle] Task {status}: {task_id}")
    return [TextContent(
        type="text",
        text=f"✅ Task '{task_id}' is now {status}. The daemon will update within 30 seconds.",
    )]


# ── Handler: Get Results ──────────────────────────────────────────────────────
def _handle_get_results(args: dict) -> list[TextContent]:
    """
    List result files for a task and optionally show the most recent one.

    Result files are written by agent_runner.save_result() and named:
        output/<task_id>_<YYYY-MM-DD_HH-MM-SS>.txt
    """
    task_id     = args.get("task_id", "").strip()
    show_latest = args.get("show_latest", True)

    if not task_id:
        return [TextContent(type="text", text="Error: task_id is required.")]

    if not OUTPUT_DIR.exists():
        return [TextContent(type="text", text="No results found — output directory does not exist yet.")]

    # Find all result files for this task, sorted newest first
    result_files = sorted(
        OUTPUT_DIR.glob(f"{task_id}_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not result_files:
        return [TextContent(
            type="text",
            text=f"No results found for task '{task_id}'. Has the daemon run it yet?",
        )]

    # Build response: file list + optionally the latest file content
    lines = [f"Found {len(result_files)} result file(s) for '{task_id}':\n"]
    for f in result_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"  {f.name}  (saved: {mtime})")

    if show_latest:
        latest = result_files[0]
        lines.append(f"\n{'=' * 50}")
        lines.append(f"Latest result ({latest.name}):\n")
        try:
            lines.append(latest.read_text(encoding="utf-8"))
        except OSError as exc:
            lines.append(f"Error reading file: {exc}")

    return [TextContent(type="text", text="\n".join(lines))]


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 ── Server Entry Point
# ──────────────────────────────────────────────────────────────────────────────
async def main() -> None:
    """Start the MCP server and listen on stdio for requests from Claude Desktop."""
    logger.info("Starting CloudSecAIBot Scheduler MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="cloudsec-scheduler",
                server_version="1.0.0",
                capabilities={},
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
