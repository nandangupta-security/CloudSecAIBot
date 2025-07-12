#!/usr/bin/env python3
"""
GCP CLI MCP Server
A Model Context Protocol server that executes Google Cloud CLI commands safely.
"""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Dict, List, Optional
import shlex

# MCP server imports
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Resource,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource,
        LoggingLevel
    )
except ImportError:
    print("Error: MCP library not installed. Install with: pip install mcp")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gcp-mcp-server")

class GCPMCPServer:
    def __init__(self):
        self.server = Server("gcp-cli-server")
        self.setup_handlers()
        
    def setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="gcloud_cli",
                    description="Execute Google Cloud CLI commands safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The gcloud CLI command to execute (without 'gcloud' prefix)"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Command timeout in seconds (default: 30)",
                                "default": 30
                            }
                        },
                        "required": ["command"]
                    }
                ),
                Tool(
                    name="gcloud_auth_check",
                    description="Check Google Cloud CLI authentication status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="gcloud_config_check",
                    description="Check Google Cloud CLI configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="gcloud_help",
                    description="Get help for Google Cloud CLI commands",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "GCP service name (optional, e.g., 'compute', 'storage', 'iam')"
                            },
                            "command": {
                                "type": "string",
                                "description": "Specific command to get help for (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="gsutil_cli",
                    description="Execute Google Cloud Storage gsutil commands safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The gsutil command to execute (without 'gsutil' prefix)"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Command timeout in seconds (default: 30)",
                                "default": 30
                            }
                        },
                        "required": ["command"]
                    }
                ),
                Tool(
                    name="bq_cli",
                    description="Execute Google BigQuery bq commands safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The bq command to execute (without 'bq' prefix)"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Command timeout in seconds (default: 30)",
                                "default": 30
                            }
                        },
                        "required": ["command"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if name == "gcloud_cli":
                return await self._execute_gcloud_command(arguments)
            elif name == "gcloud_auth_check":
                return await self._check_gcloud_auth()
            elif name == "gcloud_config_check":
                return await self._check_gcloud_config()
            elif name == "gcloud_help":
                return await self._get_gcloud_help(arguments)
            elif name == "gsutil_cli":
                return await self._execute_gsutil_command(arguments)
            elif name == "bq_cli":
                return await self._execute_bq_command(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]

    async def _execute_gcloud_command(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute gcloud CLI command safely"""
        try:
            command = arguments.get("command", "").strip()
            timeout = arguments.get("timeout", 30)
            
            if not command:
                return [TextContent(
                    type="text",
                    text="Error: No command provided"
                )]
            
            # Validate command doesn't contain dangerous operations
            if not self._is_safe_command(command):
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]
            
            # Prepare full gcloud command
            full_command = f"gcloud {command}"
            
            return await self._execute_command(full_command, timeout)
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing gcloud command: {str(e)}"
            )]

    async def _execute_gsutil_command(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute gsutil command safely"""
        try:
            command = arguments.get("command", "").strip()
            timeout = arguments.get("timeout", 30)
            
            if not command:
                return [TextContent(
                    type="text",
                    text="Error: No command provided"
                )]
            
            # Validate command doesn't contain dangerous operations
            if not self._is_safe_command(command):
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]
            
            # Prepare full gsutil command
            full_command = f"gsutil {command}"
            
            return await self._execute_command(full_command, timeout)
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing gsutil command: {str(e)}"
            )]

    async def _execute_bq_command(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute bq command safely"""
        try:
            command = arguments.get("command", "").strip()
            timeout = arguments.get("timeout", 30)
            
            if not command:
                return [TextContent(
                    type="text",
                    text="Error: No command provided"
                )]
            
            # Validate command doesn't contain dangerous operations
            if not self._is_safe_command(command):
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]
            
            # Prepare full bq command
            full_command = f"bq {command}"
            
            return await self._execute_command(full_command, timeout)
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing bq command: {str(e)}"
            )]

    async def _execute_command(self, full_command: str, timeout: int) -> List[TextContent]:
        """Execute a command safely"""
        try:
            # Parse command safely
            try:
                cmd_parts = shlex.split(full_command)
            except ValueError as e:
                return [TextContent(
                    type="text",
                    text=f"Error parsing command: {str(e)}"
                )]
            
            # Execute command
            logger.info(f"Executing: {full_command}")
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Use asyncio.wait_for to handle timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            # Prepare response
            response_text = f"Command: {full_command}\n"
            response_text += f"Exit Code: {process.returncode}\n\n"
            
            if stdout:
                response_text += f"Output:\n{stdout.decode('utf-8')}\n"
            
            if stderr:
                response_text += f"Error:\n{stderr.decode('utf-8')}\n"
            
            return [TextContent(
                type="text",
                text=response_text
            )]
            
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text=f"Error: Command timed out after {timeout} seconds"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing command: {str(e)}"
            )]

    async def _check_gcloud_auth(self) -> List[TextContent]:
        """Check Google Cloud CLI authentication status"""
        try:
            # Check if gcloud CLI is installed
            process = await asyncio.create_subprocess_exec(
                "gcloud", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=10
            )
            
            if process.returncode != 0:
                return [TextContent(
                    type="text",
                    text="gcloud CLI is not installed or not accessible"
                )]
            
            version_info = stdout.decode('utf-8').strip()
            
            # Check authentication status
            auth_process = await asyncio.create_subprocess_exec(
                "gcloud", "auth", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            auth_stdout, auth_stderr = await asyncio.wait_for(
                auth_process.communicate(),
                timeout=10
            )
            
            response_text = f"gcloud CLI Version:\n{version_info}\n\n"
            
            if auth_process.returncode == 0:
                response_text += "Authentication Status:\n"
                response_text += auth_stdout.decode('utf-8')
            else:
                response_text += "Authentication Error:\n"
                response_text += auth_stderr.decode('utf-8')
            
            return [TextContent(
                type="text",
                text=response_text
            )]
            
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: Authentication check timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking authentication: {str(e)}"
            )]

    async def _check_gcloud_config(self) -> List[TextContent]:
        """Check Google Cloud CLI configuration"""
        try:
            # Check current configuration
            config_process = await asyncio.create_subprocess_exec(
                "gcloud", "config", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            config_stdout, config_stderr = await asyncio.wait_for(
                config_process.communicate(),
                timeout=10
            )
            
            response_text = "gcloud Configuration:\n"
            
            if config_process.returncode == 0:
                response_text += config_stdout.decode('utf-8')
            else:
                response_text += f"Error: {config_stderr.decode('utf-8')}"
            
            # Also check active configuration
            active_config_process = await asyncio.create_subprocess_exec(
                "gcloud", "config", "configurations", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            active_stdout, active_stderr = await asyncio.wait_for(
                active_config_process.communicate(),
                timeout=10
            )
            
            response_text += "\n\nActive Configurations:\n"
            
            if active_config_process.returncode == 0:
                response_text += active_stdout.decode('utf-8')
            else:
                response_text += f"Error: {active_stderr.decode('utf-8')}"
            
            return [TextContent(
                type="text",
                text=response_text
            )]
            
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: Configuration check timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking configuration: {str(e)}"
            )]

    async def _get_gcloud_help(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get Google Cloud CLI help"""
        try:
            service = arguments.get("service", "")
            command = arguments.get("command", "")
            
            if service and command:
                cmd = ["gcloud", service, command, "--help"]
            elif service:
                cmd = ["gcloud", service, "--help"]
            else:
                cmd = ["gcloud", "--help"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=15
            )
            
            if process.returncode == 0:
                # Truncate help text as it can be very long
                help_text = stdout.decode('utf-8')
                if len(help_text) > 3000:
                    help_text = help_text[:3000] + "\n... (truncated)"
                
                return [TextContent(
                    type="text",
                    text=help_text
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Error getting help: {stderr.decode('utf-8')}"
                )]
                
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: Help command timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting help: {str(e)}"
            )]

    def _is_safe_command(self, command: str) -> bool:
        """Check if command is safe to execute"""
        # List of potentially dangerous operations
        dangerous_patterns = [
            # Shell operators
            "&&", "||", ";", "|", ">", "<", ">>", "<<",
            # System commands
            "sudo", "su", "chmod", "chown", "rm", "del",
            "eval", "exec", "system", "sh", "bash",
            # GCP dangerous operations
            "delete", "destroy", "remove", "terminate",
            # File operations that could be dangerous
            "mv", "cp", "move", "copy",
            # Network operations
            "curl", "wget", "ssh", "scp", "rsync"
        ]
        
        command_lower = command.lower()
        
        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                # Allow safe delete operations for GCP resources
                if pattern == "delete" and any(safe_delete in command_lower for safe_delete in [
                    "instances list", "projects list", "images list", 
                    "disks list", "snapshots list", "--dry-run", "--help"
                ]):
                    continue
                logger.warning(f"Blocked potentially dangerous command: {command}")
                return False
        
        # Additional safety checks
        if command.startswith("-") or command.startswith("--"):
            logger.warning(f"Blocked command starting with dash: {command}")
            return False
        
        # Check for suspicious character sequences
        suspicious_chars = ["$(", "`", "${", "\\", "&&", "||"]
        for char_seq in suspicious_chars:
            if char_seq in command:
                logger.warning(f"Blocked command with suspicious characters: {command}")
                return False
        
        return True

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting GCP CLI MCP Server")
        
        # Initialize and run server
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], 
                streams[1], 
                InitializationOptions(
                    server_name="gcp-cli-server",
                    server_version="1.0.0",
                    capabilities={}
                )
            )

def main():
    """Main entry point"""
    server = GCPMCPServer()
    
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
