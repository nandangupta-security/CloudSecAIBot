# CloudSecAIBot — Installation & Integration Guide

## Overview

This guide covers everything needed to get CloudSecAIBot fully operational: installing dependencies, configuring cloud credentials, registering all MCP servers with Claude Desktop, setting up your AI provider, and starting the **CloudSentinel** CSPM scheduler daemon.

---

## Prerequisites

Before proceeding, ensure you have:

1. **Claude Desktop** installed and running
2. **Git** installed for cloning the repository
3. **Python 3.11+** with pip available
4. **AWS CLI** configured with valid credentials
5. **Azure CLI** configured with an active login
6. **Google Cloud SDK** configured with an authenticated account

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/nandangupta-security/CloudSecAIBot.git
cd CloudSecAIBot

# Make the MCP server files executable (Mac/Linux)
chmod +x awscli_claude.py azurecli_claude.py gcpcli_claude.py prowler_mcp.py scheduler_mcp.py
```

---

## Step 2: Create a Virtual Environment

```bash
python3 -m venv .venv

# Activate — Mac/Linux
source .venv/bin/activate

# Activate — Windows
# .venv\Scripts\activate
```

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4: Configure Your AI Provider

CloudSentinel uses `.env` as the single source of truth for your AI provider settings. All scheduled CSPM jobs read from this file.

```bash
cp .env.example .env
```

Open `.env` and configure:

```bash
# ── AI Provider — set only the key for your chosen provider ──────────────────
ANTHROPIC_API_KEY=your-key-here   # Claude
OPENAI_API_KEY=your-key-here      # GPT-4o
GEMINI_API_KEY=your-key-here      # Gemini
MISTRAL_API_KEY=your-key-here     # Mistral
GROQ_API_KEY=your-key-here        # Groq

# ── Default model for all agent runs and scheduled CSPM jobs ─────────────────
# This is the single source of truth — do not set this anywhere else.
# Examples: claude-opus-4-6 | gpt-4o | gemini/gemini-1.5-pro | groq/llama-3.3-70b-versatile
CLOUDSEC_AI_MODEL=claude-opus-4-6

# ── Rate limiting — max LLM calls per minute ──────────────────────────────────
# Anthropic Tier 1 = 50 | Tier 2+ = 0 (no limit)
# OpenAI paid = 0 | Groq free = 5 | Gemini free = 10
CLOUDSEC_RATE_LIMIT=50

# ── Debug logging — set to "true" for verbose LiteLLM logs ───────────────────
CLOUDSEC_DEBUG=false
```

**Supported AI providers:**

| Provider | Model string | API key env var |
|----------|-------------|-----------------|
| Anthropic | `claude-opus-4-6`, `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-1.5-pro`, `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Mistral | `mistral/mistral-large-latest` | `MISTRAL_API_KEY` |
| Groq | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |

---

## Step 5: Configure Cloud CLIs

### AWS CLI

```bash
# Install AWS CLI v2 (Linux)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure credentials
aws configure
# Or for SSO:
aws sso login
```

### Azure CLI

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login
```

### Google Cloud SDK

```bash
# Install
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud init
gcloud auth login
```

---

## Step 6: Configure Claude Desktop

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

Add all six MCP servers. Replace the path prefix with your actual repo location.

### macOS

```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-AWS": {
      "command": "/Users/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/Users/yourusername/CloudSecAIBot/awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-Azure": {
      "command": "/Users/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/Users/yourusername/CloudSecAIBot/azurecli_claude.py"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-GCP": {
      "command": "/Users/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/Users/yourusername/CloudSecAIBot/gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-prowler": {
      "command": "/Users/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/Users/yourusername/CloudSecAIBot/prowler_mcp.py"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-scheduler": {
      "command": "/Users/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/Users/yourusername/CloudSecAIBot/scheduler_mcp.py"]
    }
  }
}
```

### Windows

```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-AWS": {
      "command": "C:\\Users\\yourusername\\CloudSecAIBot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json"
      }
    },
    "cloud-sec-ai-bot-Azure": {
      "command": "C:\\Users\\yourusername\\CloudSecAIBot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\azurecli_claude.py"]
    },
    "cloud-sec-ai-bot-GCP": {
      "command": "C:\\Users\\yourusername\\CloudSecAIBot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1"
      }
    },
    "cloud-sec-ai-bot-prowler": {
      "command": "C:\\Users\\yourusername\\CloudSecAIBot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\prowler_mcp.py"]
    },
    "cloud-sec-ai-bot-scheduler": {
      "command": "C:\\Users\\yourusername\\CloudSecAIBot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\scheduler_mcp.py"]
    }
  }
}
```

### Linux

```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-AWS": {
      "command": "/home/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/home/yourusername/CloudSecAIBot/awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-Azure": {
      "command": "/home/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/home/yourusername/CloudSecAIBot/azurecli_claude.py"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-GCP": {
      "command": "/home/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/home/yourusername/CloudSecAIBot/gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-prowler": {
      "command": "/home/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/home/yourusername/CloudSecAIBot/prowler_mcp.py"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-scheduler": {
      "command": "/home/yourusername/CloudSecAIBot/.venv/bin/python",
      "args": ["/home/yourusername/CloudSecAIBot/scheduler_mcp.py"]
    }
  }
}
```

> **Note on the scheduler entry**: No `env` block is needed here. The model is configured via `CLOUDSEC_AI_MODEL` in `.env`, which the scheduler daemon reads at startup.

> **A note on TLS verification**: earlier revisions of this guide set `AZURE_CLI_DISABLE_CONNECTION_VERIFICATION` and `PROWLER_DISABLE_CONNECTION_VERIFICATION` by default. Both silently disable TLS certificate validation on every request the Azure CLI / Prowler make (confirmed via the `InsecureRequestWarning: Unverified HTTPS request` urllib3 emits with them set), which exposes cloud API traffic — including auth tokens — to interception on a hostile network, with no corresponding benefit for a normal setup. Neither variable is required for the servers in this repo to function; testing without them succeeds cleanly. Only set them if you are behind a corporate TLS-inspecting proxy that requires it, and understand the tradeoff before doing so.

### Step 7: Restart Claude Desktop

1. Close Claude Desktop completely
2. Restart the application
3. Verify all five servers appear under MCP Servers in Settings
4. Check for any error indicators next to server names

---

## Step 8: Start the CloudSentinel CSPM Daemon

The CloudSentinel scheduler daemon is a separate background process that executes your scheduled CSPM jobs. It must be running for automated posture checks to fire.

```bash
source .venv/bin/activate     # Mac/Linux
# .venv\Scripts\activate      # Windows

python scheduler_daemon.py
```

The daemon will:
- Read `jobs.json` on startup and register all enabled jobs
- Poll `jobs.json` every 30 seconds — picks up new jobs, removes deleted ones
- Fire `agent_runner.py` when a job's cron time arrives
- Save results to `output/<task_id>_<timestamp>.txt`

Stop it with `Ctrl+C` — it shuts down cleanly.

> To keep it running persistently, consider running it as a background service using `nohup`, `screen`, `tmux`, or a system service manager (`launchd` on macOS, `systemd` on Linux).

---

## Step 9: Verify the Integration

### Verify MCP servers (Claude Desktop)

In Claude Desktop, open a new conversation and try:

```
Check my AWS configuration status
```

```
List all buckets across all clouds
```

```
Check authentication status for all cloud providers
```

### Verify CloudSentinel

In Claude Desktop:

```
Show me all scheduled tasks
```

```
Schedule a test S3 check at 9am daily
```

You should see confirmation that the job was written to `jobs.json` and the daemon will pick it up within 30 seconds.

### Verify ad-hoc agent runs

From the terminal:

```bash
# Basic check
python agent_runner.py "Which S3 buckets are publicly accessible?"

# Target a specific provider and model
python agent_runner.py "List Azure NSGs open to the internet" --model gpt-4o --servers azure
```

Results are saved to `output/`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| MCP server not appearing in Claude Desktop | Path incorrect in config | Verify the `.venv/bin/python` path matches your actual virtualenv |
| `ModuleNotFoundError` on server start | Dependencies not installed in venv | Ensure you ran `pip install -r requirements.txt` inside the activated venv |
| Scheduler jobs not firing | Daemon not running | Start `python scheduler_daemon.py` in a separate terminal |
| LLM call fails with auth error | API key missing or wrong | Check `.env` has the correct key for `CLOUDSEC_AI_MODEL` |
| Rate limit errors | `CLOUDSEC_RATE_LIMIT` too high for your tier | Lower the value in `.env` to match your provider's limit |
| AWS/Azure/GCP commands fail | Cloud CLI not authenticated | Re-run `aws configure` / `az login` / `gcloud auth login` |
