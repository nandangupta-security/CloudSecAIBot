## **Cloud Sec AI Bot — AI-Powered Security Configuration Analyzer for Multi-Cloud**


**Cloud Sec AI Bot** is an intelligent assistant that helps teams understand and audit their cloud **security configurations** using simple, natural language. Built for security teams, auditors, and DevSecOps professionals, it analyzes configuration states across **AWS**, **Azure**, and **GCP**, surfacing misconfigurations and policy violations in real time.

> Ask questions like:
> *"Are there any publicly accessible cloud storage buckets?"*
> *"Which IAM roles have full admin access?"*
> *"List all firewall rules open to the internet"*

Cloud Sec AI Bot translates these into secure cloud queries, executes them using **read-only access**, and returns clear, actionable insights.

---

## 🧠 What It Does

Cloud Sec AI Bot focuses specifically on **security configuration visibility and analysis**, helping you:

* Detect misconfigurations like public storage, or missing MFA
* Identify over-permissioned roles and unused credentials
* Validate least-privilege adherence in IAM policies
* Run comprehensive security audits using **Prowler** across AWS, Azure, and GCP

---

## 🔍 Supported Cloud Platforms

Cloud Sec AI Bot works across:

* **Amazon Web Services (AWS)**: IAM, S3, EC2, Security Groups, CloudTrail, etc.
* **Microsoft Azure**: Role assignments, NSGs, Storage, Key Vault, Defender settings
* **Google Cloud Platform (GCP)**: IAM, Firewalls, Buckets, Projects, Audit configs

**Note**: Also includes **Prowler** integration for automated security audits and compliance checks across all supported cloud platforms.

---

## 📊 Example Insights

| Prompt                                    | Result                                            |
| ----------------------------------------- | ------------------------------------------------- |
| "Which storage buckets are public?"       | Lists all buckets with public read/write access   |
| "Show roles with admin privileges"        | Flags roles with `AdministratorAccess` or similar |
| "Do any security groups allow 0.0.0.0/0?" | Identifies overexposed EC2 or VM instances        |
| "List users without MFA enabled"          | Flags IAM or Azure AD users missing MFA           |

---

## 🔐 Secure by Design

* **Read-only access only**: All cloud interactions are conducted using least-privilege, read-only credentials.
* **MCP execution layer**: Queries are routed through a **Middleware Command Processor (MCP)** to validate and execute commands safely.
* **No write or destructive actions**: The system is designed for analysis and visibility only—**not remediation**.

---

## 🎯 Use Cases

* Cloud security audits and assessments
* Red/blue team reconnaissance

---

## 🏗️ Designed For

* Security analysts and engineers
* DevSecOps teams
* Cloud architects
* Risk and compliance auditors
* Consultants and penetration testers

---

## 📦 Installation

### Prerequisites

* Python 3.11 or higher
* Cloud CLI tools configured with appropriate credentials:
  * **AWS**: `aws configure` or `aws sso login`
  * **Azure**: `az login`
  * **GCP**: `gcloud auth login`

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd CloudSecAIBot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Claude Desktop to use the MCP servers (see `CloudSecAIBotMCPServer-Claude_Desktop_Integration_Guide.md`)

### Dependencies

* `mcp>=1.0.0` - Model Context Protocol server framework
* `prowler>=4.0.0` - Security auditing tool (optional, for Prowler integration)

## 🚀 Vision & Roadmap

We are building toward:

* Multi-Cloud Misconfiguration Detection
* Context-Aware Risk Scoring
* AI-Generated Remediation Guidance


---

## Contributors

Thanks to all the people who already contributed!
* Prashant Venkatesh
* Swarup Natukula
* Nandan Gupta
