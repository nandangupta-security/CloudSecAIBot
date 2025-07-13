# **Cloud Sec AI Bot MCP Server - Claude Desktop Integration Guide**

## **Overview** 
This guide explains how to integrate the Cloud Sec AI Bot MCP Server with Claude Desktop, enabling you to execute AWS, Azure, and GCP CLI commands directly through Claude's interface while maintaining security and proper command validation.

## **Prerequisites**
Before proceeding with the integration, ensure you have:

1. **Claude Desktop** installed and running
2. **Git** installed for cloning the repository
3. **AWS CLI** configured with valid credentials
4. **Azure CLI** configured with active login  
5. **Google Cloud SDK** configured with authenticated account
6. **Python 3.8+** with required dependencies

## **Installation Steps**

### **Step 1: Download the MCP Server Files**

```bash
# Clone the CloudSecAIBot repository
git clone https://github.com/nandangupta-security/CloudSecAIBot.git

# Navigate to the directory
cd CloudSecAIBot

# Make the server files executable
chmod +x awscli_claude.py azurecli_claude.py gcpcli_claude.py
```

### **Step 2: Install Dependencies**
```bash
# Navigate to the CloudSecAIBot directory
cd ~/CloudSecAIBot

# Install required Python packages
pip3 install -r requirements.txt

# Alternative: Install packages manually if requirements.txt is not available
pip3 install mcp boto3 azure-cli google-cloud-storage
```

### **Step 3: Verify Installation**
Test each server independently to ensure they're working correctly:
```bash
# Test AWS MCP Server
python3 ~/CloudSecAIBot/awscli_claude.py

# Test Azure MCP Server
python3 ~/CloudSecAIBot/azurecli_claude.py

# Test GCP MCP Server
python3 ~/CloudSecAIBot/gcpcli_claude.py
```

## **Cloud CLI Setup**

### **AWS CLI Configuration**
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
```

### **Azure CLI Configuration**
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

### **Google Cloud SDK Configuration**
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Initialize and authenticate
gcloud init
gcloud auth login
```

## **Claude Desktop Configuration**

### **Step 1: Open Claude Desktop Settings**:
* Launch Claude Desktop
* Navigate to Settings (gear icon)
* Select "Developer" or "MCP Servers" tab

### **Step 2: Add the Cloud Sec AI Bot MCP Servers**:
**Method A: Using the GUI**
* Click "Add MCP Server" for each cloud provider
* Fill in the configuration for each:

**AWS Server:**
* **Server Name**: `cloud-sec-ai-bot-aws`
* **Command**: `python3`
* **Args**: `["/path/to/your/CloudSecAIBot/awscli_claude.py"]`
* **Working Directory**: `~/CloudSecAIBot/` (optional)

**Azure Server:**
* **Server Name**: `cloud-sec-ai-bot-azure`
* **Command**: `python3`
* **Args**: `["/path/to/your/CloudSecAIBot/azurecli_claude.py"]`
* **Working Directory**: `~/CloudSecAIBot/` (optional)

**GCP Server:**
* **Server Name**: `cloud-sec-ai-bot-gcp`
* **Command**: `python3`
* **Args**: `["/path/to/your/CloudSecAIBot/gcpcli_claude.py"]`
* **Working Directory**: `~/CloudSecAIBot/` (optional)

**Method B: Manual JSON Configuration**
Edit the Claude Desktop configuration file:
* **On macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
* **On Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
* **On Linux**: `~/.config/claude/claude_desktop_config.json`

### **Step 3: Claude Desktop Configuration File**
Add the following configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-aws": {
      "command": "python3",
      "args": ["/path/to/your/CloudSecAIBot/awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json"
      }
    },
    "cloud-sec-ai-bot-azure": {
      "command": "python3",
      "args": ["/path/to/your/CloudSecAIBot/azurecli_claude.py"],
      "env": {
        "AZURE_CLI_DISABLE_CONNECTION_VERIFICATION": "1"
      }
    },
    "cloud-sec-ai-bot-gcp": {
      "command": "python3",
      "args": ["/path/to/your/CloudSecAIBot/gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1"
      }
    }
  }
}
```

**Important**: Replace `/path/to/your/CloudSecAIBot/` with the actual path where you downloaded the repository.

### **Step 4: Platform-Specific Configuration Examples**

**macOS Example:**
```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-aws": {
      "command": "python3",
      "args": ["/Users/yourusername/CloudSecAIBot/awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-azure": {
      "command": "python3",
      "args": ["/Users/yourusername/CloudSecAIBot/azurecli_claude.py"],
      "env": {
        "AZURE_CLI_DISABLE_CONNECTION_VERIFICATION": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    },
    "cloud-sec-ai-bot-gcp": {
      "command": "python3",
      "args": ["/Users/yourusername/CloudSecAIBot/gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

**Windows Example:**
```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-aws": {
      "command": "python",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json"
      }
    },
    "cloud-sec-ai-bot-azure": {
      "command": "python",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\azurecli_claude.py"],
      "env": {
        "AZURE_CLI_DISABLE_CONNECTION_VERIFICATION": "1"
      }
    },
    "cloud-sec-ai-bot-gcp": {
      "command": "python",
      "args": ["C:\\Users\\yourusername\\CloudSecAIBot\\gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1"
      }
    }
  }
}
```

**Linux Example:**
```json
{
  "mcpServers": {
    "cloud-sec-ai-bot-aws": {
      "command": "python3",
      "args": ["/home/yourusername/CloudSecAIBot/awscli_claude.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_DEFAULT_OUTPUT": "json"
      }
    },
    "cloud-sec-ai-bot-azure": {
      "command": "python3",
      "args": ["/home/yourusername/CloudSecAIBot/azurecli_claude.py"],
      "env": {
        "AZURE_CLI_DISABLE_CONNECTION_VERIFICATION": "1"
      }
    },
    "cloud-sec-ai-bot-gcp": {
      "command": "python3",
      "args": ["/home/yourusername/CloudSecAIBot/gcpcli_claude.py"],
      "env": {
        "CLOUDSDK_CORE_PROJECT": "your-default-project-id",
        "CLOUDSDK_COMPUTE_REGION": "us-central1"
      }
    }
  }
}
```

### **Step 5: Restart Claude Desktop**
After updating the configuration:
1. **Close Claude Desktop completely**
2. **Restart the application**
3. **Verify all servers are loaded** (check for any error messages)

## **Verification**
After restarting Claude Desktop, you should see the MCP servers listed in the interface. You can verify the integration by checking:
- Server status indicators in Claude Desktop
- Available tools/functions in the interface
- Error messages in the Claude Desktop console (if any)

## **Usage in Claude Desktop**
Once integrated, you can use the Cloud Sec AI Bot MCP Server through natural language commands in Claude Desktop:

### **Basic Commands**

**Check AWS Configuration**:
```
Check my AWS configuration status
```

### **Multi-Cloud Commands**
```
List all buckets across all clouds
```

```
Check authentication status for all cloud providers
```

```
Show all users across AWS, Azure, and GCP
```

