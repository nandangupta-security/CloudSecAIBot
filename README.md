# CloudSecAIBot — AI-Powered Cloud Security for Multi-Cloud

**CloudSecAIBot** is an intelligent cloud security assistant that lets you query, audit, and monitor your cloud environments using plain English. Instead of writing CLI commands or learning cloud-specific query languages, you ask a question — CloudSecAIBot figures out which cloud APIs to call, executes them securely, and returns a clear, structured answer.

Built for security teams, auditors, and DevSecOps professionals, it covers **AWS**, **Azure**, **GCP**, and **Prowler** — and works with any AI provider (Claude, GPT, Gemini, Mistral, Groq).

CloudSecAIBot also ships with **CloudSentinel** — a built-in CSPM engine that runs these same security checks automatically on a cron schedule, building a continuous audit trail of your cloud security posture over time.

> *"Which S3 buckets are publicly accessible?"*
> *"List all Azure users without MFA"*
> *"Show GCP service accounts with owner-level permissions"*
> *"Run a CIS benchmark audit across all clouds"*
> *"Schedule a daily IAM check every morning at 9am"*

---

## Core Capabilities

### Multi-Cloud Security Analysis

CloudSecAIBot connects to all three major cloud providers simultaneously. A single question can span your entire cloud estate — ask *"which storage buckets are publicly accessible?"* and CloudSecAIBot will check S3, Azure Blob, and GCS in one go, returning a unified answer across all your accounts.

**Cross-cloud example queries:**
```
Which storage buckets are publicly accessible across all my cloud accounts?
Show all users without MFA enabled across AWS, Azure, and GCP
List all firewall rules open to the internet across all clouds
Check authentication status for all cloud providers
Show all users with admin-level access across my cloud accounts
```

#### AWS

The AWS MCP server connects Claude Desktop directly to your AWS environment via the AWS CLI.

**What it covers:**
- **IAM**: Users, roles, policies, access keys, MFA status, permission boundaries
- **S3**: Bucket ACLs, public access blocks, encryption, versioning, logging
- **EC2**: Security groups, open ports, instance metadata, key pairs
- **Networking**: VPCs, subnets, NACLs, internet gateways, VPN configuration
- **Audit & Compliance**: CloudTrail status, Config rules, GuardDuty findings
- **Credentials**: Access key age, unused credentials, root account usage

**Example queries:**
```
Which S3 buckets have public read or write access?
List all IAM users with access keys older than 90 days
Show security groups that allow inbound traffic from 0.0.0.0/0
Is CloudTrail enabled and logging to all regions?
List EC2 instances with public IP addresses
```

#### Azure

The Azure MCP server connects to your Azure environment via the Azure CLI, covering identity, network, storage, and compliance across your subscriptions.

**What it covers:**
- **Identity & Access**: Role assignments, privileged accounts, guest users, conditional access
- **Network**: NSGs, inbound rules, public IPs, exposed services
- **Storage**: Blob containers with public access, storage account security settings
- **Key Vault**: Access policies, soft delete status, key expiry
- **Defender for Cloud**: Security score, active recommendations, alerts
- **Compliance**: Policy assignments, audit logs, diagnostic settings

**Example queries:**
```
List all Azure users without MFA enabled
Show NSGs with rules allowing any inbound traffic from the internet
Which storage accounts have public blob access enabled?
List service principals with Owner or Contributor roles
Show the current Defender for Cloud security score
```

#### GCP

The GCP MCP server connects to your Google Cloud environment via the gcloud SDK, inspecting IAM, networking, storage, and audit configurations across your projects.

**What it covers:**
- **IAM**: Service accounts, role bindings, primitive roles, workload identity
- **Firewall**: Rules allowing 0.0.0.0/0, overly permissive ingress/egress
- **Cloud Storage**: Bucket ACLs, allUsers / allAuthenticatedUsers access
- **Compute**: Instances with public IPs, OS login disabled, shielded VM status
- **Audit Logging**: Data access logs, admin activity logs per project and service
- **Projects**: IAM policy drift, org policy violations

**Example queries:**
```
List GCP service accounts with owner or editor roles at the project level
Which Cloud Storage buckets are accessible to allUsers?
Show firewall rules that allow ingress from 0.0.0.0/0
Are audit logs enabled for all services in this project?
List compute instances with the default service account attached
```

---

## CloudSentinel — Built-in CSPM

**Cloud Security Posture Management (CSPM)** continuously monitors cloud environments for misconfigurations, policy violations, and compliance drift — giving security teams the visibility to act before attackers do.

Traditional CSPM tools are rigid, expensive, and require learning proprietary query languages. **CloudSentinel replaces that with AI** — describe what you want to check in plain English, set a schedule, and it runs automatically.

### How CloudSentinel Works

```
Claude Desktop
    │
    │  "Schedule a daily S3 check at 9am"
    ↓
scheduler_mcp.py  ──writes──▶  jobs.json
                                   ▲
scheduler_daemon.py  ──polls every 30s──┘
    │
    │  (cron fires at 9am)
    ↓
agent_runner.py  →  LiteLLM (any AI)  →  MCP servers (aws / azure / gcp / prowler)
    │
    ↓
output/daily-s3-check_2026-04-11_09-00-00.txt
```

### What CloudSentinel Delivers

| CSPM Capability | How CloudSentinel Delivers It |
|----------------|-------------------------------|
| Continuous Monitoring | Scheduler daemon runs 24/7, fires checks on cron schedule |
| Multi-Cloud Coverage | AWS + Azure + GCP + Prowler in a single deployment |
| Misconfiguration Detection | AI agent chains real API calls and interprets findings |
| Compliance Auditing | Prowler integration for CIS, NIST, SOC2, PCI-DSS |
| Audit Trail | Timestamped result files saved to `output/` after every run |
| AI-Driven Analysis | LLM returns structured summaries, not raw JSON |
| AI-Agnostic | Swap provider in `.env` — no code changes required |

### Managing CloudSentinel Jobs via Claude Desktop

**Create a recurring CSPM job:**
> "Schedule a daily S3 public bucket check at 9am"
> "Run a GCP IAM audit every Monday at 8am"
> "Check Azure NSGs open to the internet every 6 hours"

**Manage jobs:**
> "Show me all scheduled tasks"
> "Disable the daily S3 check"
> "Delete the GCP IAM audit schedule"

**View results:**
> "Show me the latest results from the daily S3 check"

### `jobs.json` reference

```json
[
  {
    "task_id":    "daily-s3-check",
    "cron":       "0 9 * * *",
    "prompt":     "Check for publicly accessible S3 buckets and report findings",
    "servers":    ["aws"],
    "enabled":    true,
    "created_at": "2026-04-11T10:00:00"
  }
]
```

| Field | Required | Description |
|-------|----------|-------------|
| `task_id` | Yes | Unique identifier, used in output filename |
| `cron` | Yes | 5-field cron expression (`minute hour day month weekday`) |
| `prompt` | Yes | The cloud security question to run |
| `servers` | No | `["aws"]`, `["gcp","prowler"]`, etc. Defaults to all servers |
| `enabled` | No | `true`/`false` — pause without deleting (default: `true`) |

**Common cron expressions:**

| Cron | Meaning |
|------|---------|
| `0 9 * * *` | Daily at 9:00 AM |
| `0 9 * * 1` | Every Monday at 9:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 9,17 * * *` | Daily at 9 AM and 5 PM |

### Running Ad-Hoc Checks from the Terminal

```bash
# Basic usage
python agent_runner.py "Which S3 buckets are publicly accessible?"

# Use a specific AI provider
python agent_runner.py "List Azure NSGs open to the internet" --model gpt-4o

# Restrict to specific MCP servers
python agent_runner.py "Audit GCP IAM policies" --servers gcp,prowler

# Save with a custom task label
python agent_runner.py "Check for IAM users without MFA" --task-id iam-mfa-check
```

---

## Architecture

```
Claude Desktop
    │
    ├── cloud-sec-ai-bot-AWS       → awscli_claude.py    (AWS CLI wrapper)
    ├── cloud-sec-ai-bot-Azure     → azurecli_claude.py  (Azure CLI wrapper)
    ├── cloud-sec-ai-bot-GCP       → gcpcli_claude.py    (gcloud SDK wrapper)
    ├── cloud-sec-ai-bot-prowler   → prowler_mcp.py      (Prowler compliance audits)
    └── cloud-sec-ai-bot-scheduler → scheduler_mcp.py    (CloudSentinel CSPM jobs)
                                              │
                                              ▼
                                        scheduler_daemon.py  (background process)
                                              │
                                              ▼
                                        agent_runner.py  +  LiteLLM  →  output/
```

| File | Role |
|------|------|
| `awscli_claude.py` | MCP server — exposes AWS CLI security commands to Claude Desktop |
| `azurecli_claude.py` | MCP server — exposes Azure CLI security commands to Claude Desktop |
| `gcpcli_claude.py` | MCP server — exposes gcloud security commands to Claude Desktop |
| `prowler_mcp.py` | MCP server — runs Prowler compliance audits and returns findings |
| `scheduler_mcp.py` | MCP server — manages CloudSentinel CSPM jobs via Claude Desktop |
| `scheduler_daemon.py` | Background daemon — fires `agent_runner` on cron schedule |
| `agent_runner.py` | AI-agnostic agentic loop — connects to MCP servers, calls LLM, saves output |

---

## Secure by Design

- **Read-only access only**: All cloud interactions use least-privilege, read-only credentials
- **MCP execution layer**: Commands are routed through the **Model Context Protocol (MCP)** to execute safely
- **No write or destructive actions**: Designed for analysis and visibility only — not remediation
- **AI-agnostic**: Uses [LiteLLM](https://github.com/BerriAI/litellm) to support any LLM provider via a single model string

---

## Quick Start

1. **Clone** the repo and create a Python virtual environment
2. **Install** dependencies: `pip install -r requirements.txt`
3. **Configure** your AI provider API key and model in `.env` (copy from `.env.example`)
4. **Register** the MCP servers with Claude Desktop using `claude_desktop_config.json`
5. **Start** the CloudSentinel daemon: `python scheduler_daemon.py`

For full step-by-step instructions including cloud CLI setup, platform-specific config examples, and CloudSentinel configuration, see the **[Setup Guide](CloudSecAIBot_Setup_Guide.md)**.

---

## Supported AI Providers

Switch providers by changing `CLOUDSEC_AI_MODEL` in `.env` — no other code changes needed.

| Provider | Model string | API key env var |
|----------|-------------|-----------------|
| Anthropic | `claude-opus-4-6`, `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-1.5-pro`, `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Mistral | `mistral/mistral-large-latest` | `MISTRAL_API_KEY` |
| Groq | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |

---

## Use Cases

- Interactive cloud security Q&A via Claude Desktop
- Continuous posture monitoring with CloudSentinel
- Scheduled compliance and misconfiguration audits
- Cloud security assessments and penetration testing recon
- DevSecOps pipeline security gates
- Risk and compliance reporting

---

## Designed For

- Security analysts and engineers
- DevSecOps teams
- Cloud architects
- Risk and compliance auditors
- Consultants and penetration testers

---

## Vision & Roadmap

- Context-aware risk scoring across findings
- AI-generated remediation guidance
- Alerting and notification integrations (Slack, email, PagerDuty)
- Drift detection — alert when posture changes between CloudSentinel runs
- Compliance trend reporting over time

---

## Contributors

Thanks to all the people who have already contributed:

- Prashant Venkatesh
- Swarup Natukula
- Nandan Gupta
- Kannan Prabu Ramamoorthy
