#!/usr/bin/env python3
"""
cloud_command_safety.py — Shared read-only command allowlist for CloudSecAIBot's
AWS / Azure / GCP MCP servers (awscli_claude.py, azurecli_claude.py, gcpcli_claude.py).

CloudSecAIBot is meant to be a read-only cloud auditing tool. The real
enforcement boundary for that is least-privilege IAM on whatever credentials
the underlying CLI is using (see aws-iam-user-setup.md) — this module is
defense-in-depth on top of that, not a substitute for it. Treat "allowed"
here as "didn't match a recognized mutating pattern", not as a guarantee.

WHY THIS REPLACED THE OLD PER-SERVER BLOCKLISTS
-------------------------------------------------
Each server previously carried its own hand-written list of "dangerous"
substrings (e.g. "delete", "rm", "&&") and rejected any command containing
one, anywhere in the raw string. That approach has two failure modes, both
demonstrable:

  - False positives: a read-only command with a filter that happens to
    mention a blocked word gets rejected, e.g.
      aws cloudformation describe-stack-events \\
          --query "StackEvents[?ResourceStatus=='DELETE_COMPLETE']"
    is pure read/describe traffic, but the old blocklist rejected it because
    "delete" appears in the query string.

  - False negatives: plenty of real mutating operations don't contain any
    blocklisted word at all and sailed straight through, e.g.
      aws iam put-user-policy ...
      aws iam attach-role-policy ...
      aws ec2 authorize-security-group-ingress --cidr 0.0.0.0/0 ...
    None of "delete/destroy/terminate/rm/sudo/..." appear in any of these.

This module instead does the opposite: default-deny, and only allow a
command whose actual verb token (not the whole string) matches a known
read-only naming pattern. Each provider's CLI has a different structural
convention for where that verb sits, so each has its own parser below —
but they share the same READ_PREFIXES vocabulary.
"""

import shlex

# Verb prefixes considered read-only across all three providers' naming
# conventions (AWS operations, Azure CLI subcommands, gcloud subcommands).
# Extend this — not a blocklist — if a legitimate read command gets rejected.
READ_PREFIXES = (
    "list", "describe", "get", "search", "lookup", "check", "view", "show",
    "simulate", "test", "generate", "validate", "estimate", "export", "head",
    "filter", "query", "scan", "preview", "summarize", "count", "verify",
    "exists",
)

# Verbs gcloud commonly uses for mutating operations. Only used as an
# ordering tie-breaker in is_safe_gcloud_command() — see its docstring.
_GCLOUD_MUTATING_VERBS = (
    "create", "delete", "add", "remove", "set", "update", "patch", "deploy",
    "undeploy", "enable", "disable", "revoke", "grant", "import", "start",
    "stop", "restart", "reset", "move", "rename", "attach", "detach",
    "bind", "unbind", "promote", "reject", "approve", "submit", "cancel",
    "rollback", "clone", "restore", "activate", "deactivate", "upload",
    "sign-url", "ssh", "scp",
)


def _is_read_verb(token: str) -> bool:
    token = token.lower()
    return any(token == prefix or token.startswith(prefix + "-") for prefix in READ_PREFIXES)


def _leading_path(tokens: list[str]) -> list[str]:
    """Tokens up to (not including) the first flag — the command's fixed
    'path' before any --options or positional values that follow flags."""
    path = []
    for tok in tokens:
        if tok.startswith("-"):
            break
        path.append(tok)
    return path


def is_safe_aws_command(command: str) -> bool:
    """
    AWS CLI structure is fixed: `<service> <operation> [flags...]` — the
    operation is always the second token, so this is an exact check, not a
    heuristic.

    Special case: s3's high-level commands (ls/cp/mv/rm/sync/mb/rb/website/
    presign) don't follow the list-/describe-/get- naming convention every
    other service uses. Only `s3 ls` is allowed; everything else under s3
    is excluded by default (rm, sync, cp, mv, mb, rb, website, presign).
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) < 2:
        return False

    service, operation = tokens[0].lower(), tokens[1].lower()

    if service == "s3":
        return operation == "ls"

    return _is_read_verb(operation)


def is_safe_azure_command(command: str) -> bool:
    """
    az's command path (group/subgroup/.../verb) always comes before any
    flags, and az never places bare positional resource identifiers in that
    path — resources are always passed via named flags (--name, --resource-
    group, etc). That makes the last token before the first flag reliably
    the verb.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    path = _leading_path(tokens)
    if not path:
        return False

    return _is_read_verb(path[-1])


def is_safe_gcloud_command(command: str) -> bool:
    """
    Unlike az, gcloud frequently places positional resource identifiers
    right after the verb (e.g. `projects describe PROJECT_ID`,
    `iam service-accounts get-iam-policy SA_EMAIL`), so "last token before
    the first flag" doesn't reliably land on the verb the way it does for az.

    Instead, scan the leading command path left-to-right and classify by
    whichever known verb — read or mutating — appears first. This correctly
    allows `projects describe PROJECT_ID` (first verb-like token: "describe")
    and correctly blocks `compute instances delete get-my-instance` (first
    verb-like token: "delete", even though a later positional value happens
    to start with "get").
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    path = _leading_path(tokens)
    for tok in path:
        low = tok.lower()
        if _is_read_verb(low):
            return True
        if any(low == verb or low.startswith(verb + "-") for verb in _GCLOUD_MUTATING_VERBS):
            return False

    return False


def is_safe_gsutil_command(command: str) -> bool:
    """
    gsutil's structure is `gsutil <command> [sub] [args]`. Plain read
    commands (ls/cat/du/hash/stat) take no sub-verb. Config-style commands
    (iam/acl/defacl/lifecycle/versioning/logging/notification/retention/
    requesterpays/label/pap) have get/set-style subcommands — only their
    "get"/"list" sub-forms are read-only.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    path = _leading_path(tokens)
    if not path:
        return False

    verb = path[0].lower()

    if verb in ("ls", "cat", "du", "hash", "stat"):
        return True

    if verb in (
        "iam", "acl", "defacl", "lifecycle", "versioning", "logging",
        "notification", "retention", "requesterpays", "label", "pap",
    ):
        sub = path[1].lower() if len(path) > 1 else ""
        return sub in ("get", "list")

    return False


def is_safe_bq_command(command: str) -> bool:
    """
    Deliberately conservative: bq's `query` subcommand executes arbitrary
    SQL against BigQuery, including DML/DDL (INSERT/UPDATE/DELETE/DROP/
    CREATE TABLE ...) — the command-level allowlist here has no way to
    inspect the SQL text itself, so `query` is not treated as safe even
    though the word "query" is otherwise a read verb elsewhere in this
    module. Only `ls` (list datasets/tables) and `show` (describe a
    dataset/table's schema) are allowed.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False

    return tokens[0].lower() in ("ls", "show")
