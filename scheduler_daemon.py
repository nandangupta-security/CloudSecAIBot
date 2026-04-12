#!/usr/bin/env python3
"""
scheduler_daemon.py — CloudSecAIBot Background Scheduler
=========================================================
PURPOSE:
    Runs continuously in the background. Polls jobs.json every 30 seconds,
    keeps APScheduler in sync with what's in the file, and fires agent_runner
    when a job's cron time arrives.

HOW IT FITS IN THE PROJECT:
    scheduler_mcp.py  ──writes──▶  jobs.json  ◀──polls──  scheduler_daemon.py
                                                                  │
                                                    (cron fires) ↓
                                                          agent_runner.run_agent()
                                                                  │
                                                                  ↓
                                                          output/<task_id>_<timestamp>.txt

HOW TO RUN:
    python3 scheduler_daemon.py

    The daemon will:
      1. Read jobs.json on startup and register all enabled jobs.
      2. Poll jobs.json every 30s — picks up new jobs, removes deleted ones.
      3. Fire agent_runner.run_agent() when a job's cron schedule triggers.
      4. Save results to output/ automatically (via agent_runner).
      5. Shut down cleanly on Ctrl+C or SIGTERM.

STORAGE:
    Jobs are held in APScheduler's in-memory store only.
    If the daemon restarts, it re-reads jobs.json and recovers automatically.
    No database required.

JOBS.JSON FORMAT:
    [
      {
        "task_id":  "daily-s3-check",      ← unique identifier
        "cron":     "0 9 * * *",           ← standard 5-field cron expression
        "prompt":   "Check for public S3 buckets and report findings",
        "servers":  ["aws"],               ← optional, falls back to all servers
        "enabled":  true                   ← set false to pause without deleting
      }
    ]
"""

import asyncio
import json
import logging
import os
import signal
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Import the agent runner — this is what actually runs the LLM + MCP loop
from agent_runner import run_agent


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 ── Setup & Constants
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

_debug = os.getenv("CLOUDSEC_DEBUG", "false").lower() == "true"
logging.basicConfig(
    level=logging.DEBUG if _debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("scheduler-daemon")

BASE_DIR  = Path(__file__).parent
JOBS_FILE = BASE_DIR / "jobs.json"   # single source of truth for all scheduled jobs

# How often the daemon checks jobs.json for changes (seconds)
POLL_INTERVAL = 30


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 ── Job File Reader
# ──────────────────────────────────────────────────────────────────────────────
def read_jobs_file() -> list[dict]:
    """
    Read and parse jobs.json, returning a list of job dicts.

    Returns an empty list (not an error) if:
      - The file doesn't exist yet (daemon started before any jobs were created)
      - The file is empty or contains invalid JSON (we log the error)

    This means the daemon starts cleanly even if jobs.json doesn't exist.
    """
    if not JOBS_FILE.exists():
        return []  # Normal on first start — file will appear once scheduler_mcp creates a job

    try:
        raw = JOBS_FILE.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"[file] Failed to read {JOBS_FILE.name}: {exc}")
        return []


def get_enabled_jobs(jobs: list[dict]) -> dict[str, dict]:
    """
    Filter the jobs list to only enabled jobs, keyed by task_id.

    A job is enabled when:
      - "enabled" key is missing (defaults to True)
      - "enabled" is explicitly True

    Returns:
        { task_id: job_dict } for all enabled jobs.
    """
    return {
        job["task_id"]: job
        for job in jobs
        if job.get("enabled", True) and job.get("task_id") and job.get("cron") and job.get("prompt")
    }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 ── Job Executor
# ──────────────────────────────────────────────────────────────────────────────
async def execute_job(job: dict) -> None:
    """
    Called by APScheduler when a job's cron schedule fires.

    Passes the job's prompt to agent_runner, which:
      1. Connects to the relevant MCP servers
      2. Runs the LLM agentic loop
      3. Saves the result to output/<task_id>_<timestamp>.txt

    Args:
        job: The full job dict from jobs.json (task_id, prompt, servers, ...)
    """
    task_id = job["task_id"]
    logger.info(f"[executor] Firing job: {task_id}")

    try:
        await run_agent(
            prompt=job["prompt"],
            # model is not stored in jobs.json — always resolved from CLOUDSEC_AI_MODEL env var
            task_id=task_id,
            save_output=True,
            servers_to_use=job.get("servers"),  # None → agent_runner uses all servers
        )
        logger.info(f"[executor] Job completed: {task_id}")
    except Exception as exc:
        # Log but don't crash the daemon — other jobs must keep running
        logger.error(f"[executor] Job failed [{task_id}]: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 ── Job Reconciler
# ──────────────────────────────────────────────────────────────────────────────
def reconcile_jobs(
    scheduler: AsyncIOScheduler,
    tracked: dict[str, str],
) -> None:
    """
    Sync APScheduler with the current state of jobs.json.

    Called on startup and on every poll tick.

    Logic:
      - Jobs in file but NOT in scheduler  →  add them
      - Jobs in scheduler but NOT in file  →  remove them
      - Jobs already in both               →  leave them unchanged

    Args:
        scheduler: The running APScheduler instance.
        tracked:   Dict of { task_id → apscheduler_job_id } for jobs we registered.
                   Mutated in place — this is the daemon's memory of what's scheduled.
    """
    file_jobs = get_enabled_jobs(read_jobs_file())  # what the file says should run

    # ── Add new jobs found in file ─────────────────────────────────────────
    for task_id, job in file_jobs.items():
        if task_id not in tracked:
            _register_job(scheduler, tracked, task_id, job)

    # ── Remove jobs that are no longer in the file (or were disabled) ──────
    removed = [tid for tid in tracked if tid not in file_jobs]
    for task_id in removed:
        _unregister_job(scheduler, tracked, task_id)


def _register_job(
    scheduler: AsyncIOScheduler,
    tracked: dict[str, str],
    task_id: str,
    job: dict,
) -> None:
    """
    Add a single job to APScheduler using its cron expression.

    replace_existing=True means if the job somehow already exists in the
    scheduler (e.g. after a quick restart), it will be replaced cleanly.

    misfire_grace_time=300 means: if the daemon was down at the scheduled
    time, fire the job within the next 5 minutes instead of skipping it.
    """
    try:
        ap_job = scheduler.add_job(
            execute_job,
            trigger=CronTrigger.from_crontab(job["cron"]),
            kwargs={"job": job},
            id=task_id,
            name=task_id,
            replace_existing=True,
            misfire_grace_time=300,
        )
        tracked[task_id] = ap_job.id
        logger.info(f"[reconcile] Registered [{task_id}] cron='{job['cron']}' next={ap_job.next_run_time}")
    except Exception as exc:
        logger.error(f"[reconcile] Could not register [{task_id}]: {exc}")


def _unregister_job(
    scheduler: AsyncIOScheduler,
    tracked: dict[str, str],
    task_id: str,
) -> None:
    """
    Remove a job from APScheduler and from the tracked dict.
    """
    try:
        scheduler.remove_job(task_id)
        logger.info(f"[reconcile] Removed [{task_id}] (not in file or disabled)")
    except Exception:
        pass  # Job may have already been removed; safe to ignore
    tracked.pop(task_id, None)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 ── Scheduler Daemon (Main Loop)
# ──────────────────────────────────────────────────────────────────────────────
async def run_daemon() -> None:
    """
    Start the scheduler and run the poll loop until interrupted.

    The poll loop:
      - Waits POLL_INTERVAL seconds (or until stop signal).
      - Calls reconcile_jobs() to sync scheduler with jobs.json.

    Handles SIGINT (Ctrl+C) and SIGTERM gracefully so APScheduler can
    finish any in-progress job before shutting down.
    """
    scheduler = AsyncIOScheduler()
    tracked: dict[str, str] = {}   # { task_id → apscheduler_job_id }

    # Load existing jobs from file before starting the scheduler
    reconcile_jobs(scheduler, tracked)
    scheduler.start()

    logger.info(
        f"Scheduler daemon started. "
        f"Watching {JOBS_FILE.name} every {POLL_INTERVAL}s. "
        f"{len(tracked)} job(s) loaded."
    )

    # Set up graceful shutdown on Ctrl+C or kill signal
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal(sig):
        logger.info(f"Received {sig.name} — shutting down")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal, sig)

    # ── Poll loop ─────────────────────────────────────────────────────────
    while not stop_event.is_set():
        try:
            # Wait for POLL_INTERVAL seconds, but wake up early if stop_event is set
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            # Normal path — poll interval elapsed, check the file
            pass

        if not stop_event.is_set():
            reconcile_jobs(scheduler, tracked)

    # ── Shutdown ──────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Scheduler daemon stopped.")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6 ── Entry Point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_daemon())
