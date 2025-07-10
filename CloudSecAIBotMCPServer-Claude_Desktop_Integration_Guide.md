**Cloud Sec AI Bot MCP Server \- Claude Desktop Integration Guide**

**Overview** This guide explains how to integrate the Cloud Sec AI Bot MCP Server with Claude Desktop, enabling you to execute AWS CLI commands directly through Claude's interface while maintaining security and proper command validation.

**Prerequisites** Before proceeding with the integration, ensure you have:

1. **Claude Desktop** installed and running  
2. **Cloud Sec AI Bot MCP Server** properly installed (see Installation Guide)  
3. **AWS CLI** configured with valid credentials  
4. **Python 3.8+** with required dependencies

**Integration Steps**

**Step 1: Prepare the MCP Server**

**Locate your MCP Server file**: Ensure `awscli_claude.py` is saved in a accessible location, such as:

\~/CloudSecAIBot/awscli\_claude.py

1. **Make the server executable**:

chmod \+x \~/CloudSecAIBot/awscli\_claude.py

1. **Test the server independently**:

python3 \~/CloudSecAIBot/awscli\_claude.py

**Step 2: Configure Claude Desktop**

1. **Open Claude Desktop Settings**:  
   * Launch Claude Desktop  
   * Navigate to Settings (gear icon)  
   * Select "Developer" or "MCP Servers" tab  
2. **Add the Cloud Sec AI Bot MCP Server**:

**Method A: Using the GUI**

* Click "Add MCP Server"  
* Fill in the configuration:  
  * **Server Name**: `cloud-sec-ai-bot-server`  
  * **Command**: `python3`  
  * **Args**: `["/path/to/your/awscli_claude.py"]`  
  * **Working Directory**: `~/CloudSecAIBot/` (optional)  
3. **Method B: Manual JSON Configuration** Edit the Claude Desktop configuration file: **On macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json` **On Windows**: `%APPDATA%/Claude/claude_desktop_config.json` **On Linux**: `~/.config/claude/claude_desktop_config.json`

**Step 3: Claude Desktop Configuration File** Add the following configuration to your `claude_desktop_config.json`:

{  
  "mcpServers": {  
    "cloud-sec-ai-bot-server": {  
      "command": "python3",  
      "args": \["/path/to/your/awscli\_claude.py"\],  
      "env": {  
        "AWS\_DEFAULT\_REGION": "us-east-1",  
        "AWS\_DEFAULT\_OUTPUT": "json"  
      }  
    }  
  }  
}

**Important**: Replace `/path/to/your/awscli_claude.py` with the actual path to your server file.

**Step 4: Complete Configuration Examples**

**macOS Example:**

{  
  "mcpServers": {  
    "cloud-sec-ai-bot-server": {  
      "command": "python3",  
      "args": \["/Users/yourusername/CloudSecAIBot/awscli\_claude.py"\],  
      "env": {  
        "AWS\_DEFAULT\_REGION": "us-east-1",  
        "AWS\_DEFAULT\_OUTPUT": "json",  
        "PATH": "/usr/local/bin:/usr/bin:/bin"  
      }  
    }  
  }  
}

**Windows Example:**

{  
  "mcpServers": {  
    "cloud-sec-ai-bot-server": {  
      "command": "python",  
      "args": \["C:\\\\Users\\\\yourusername\\\\CloudSecAIBot\\\\awscli\_claude.py"\],  
      "env": {  
        "AWS\_DEFAULT\_REGION": "us-east-1",  
        "AWS\_DEFAULT\_OUTPUT": "json"  
      }  
    }  
  }  
}

**Linux Example:**

{  
  "mcpServers": {  
    "cloud-sec-ai-bot-server": {  
      "command": "python3",  
      "args": \["/home/yourusername/CloudSecAIBot/awscli\_claude.py"\],  
      "env": {  
        "AWS\_DEFAULT\_REGION": "us-east-1",  
        "AWS\_DEFAULT\_OUTPUT": "json"  
      }  
    }  
  }  
}

**Step 5: Restart Claude Desktop** After updating the configuration:

1. **Close Claude Desktop completely**  
2. **Restart the application**  
3. **Verify the server is loaded** (check for any error messages)

**Usage in Claude Desktop** Once integrated, you can use the Cloud Sec AI Bot MCP Server through natural language commands in Claude Desktop:

**Basic Commands**

**Check AWS Configuration**:

Check my AWS configuration status

**List S3 Buckets**:

List all my public S3 buckets  
