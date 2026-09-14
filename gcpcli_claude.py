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
import time
from typing import Any, Dict, List, Optional
import shlex

from cloud_command_safety import is_safe_gcloud_command, is_safe_gsutil_command, is_safe_bq_command
from command_audit_log import log_command, read_recent

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
                    name="cloud-sec-gcloud-cli",
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
                    name="cloud-sec-gcloud-auth-check",
                    description="Check Google Cloud CLI authentication status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="cloud-sec-gcloud-config-check",
                    description="Check Google Cloud CLI configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="cloud-sec-gcloud-help",
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
                    name="cloud-sec-gsutil-cli",
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
                    name="cloud-sec-bq-cli",
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
                ),
                Tool(
                    name="cloud-sec-gcp-audit-log",
                    description="Show the most recent gcloud/gsutil/bq commands this server has run or blocked, from output/command_audit.log",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Max number of recent entries to return (default: 20)",
                                "default": 20
                            }
                        }
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if name == "cloud-sec-gcloud-cli":
                return await self._execute_gcloud_command(arguments)
            elif name == "cloud-sec-gcloud-auth-check":
                return await self._check_gcloud_auth()
            elif name == "cloud-sec-gcloud-config-check":
                return await self._check_gcloud_config()
            elif name == "cloud-sec-gcloud-help":
                return await self._get_gcloud_help(arguments)
            elif name == "cloud-sec-gsutil-cli":
                return await self._execute_gsutil_command(arguments)
            elif name == "cloud-sec-bq-cli":
                return await self._execute_bq_command(arguments)
            elif name == "cloud-sec-gcp-audit-log":
                return self._get_audit_log(arguments)
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
            if not self._is_safe_gcloud_command(command):
                log_command("gcp", "cloud-sec-gcloud-cli", command, allowed=False,
                            block_reason="not a recognized read-only operation")
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]

            # Prepare full gcloud command
            full_command = f"gcloud {command}"

            return await self._execute_command(full_command, timeout, "cloud-sec-gcloud-cli", command)
            
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
            if not self._is_safe_gsutil_command(command):
                log_command("gcp", "cloud-sec-gsutil-cli", command, allowed=False,
                            block_reason="not a recognized read-only operation")
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]

            # Prepare full gsutil command
            full_command = f"gsutil {command}"

            return await self._execute_command(full_command, timeout, "cloud-sec-gsutil-cli", command)
            
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
            if not self._is_safe_bq_command(command):
                log_command("gcp", "cloud-sec-bq-cli", command, allowed=False,
                            block_reason="not a recognized read-only operation")
                return [TextContent(
                    type="text",
                    text="Error: Command contains potentially dangerous operations"
                )]

            # Prepare full bq command
            full_command = f"bq {command}"

            return await self._execute_command(full_command, timeout, "cloud-sec-bq-cli", command)
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing bq command: {str(e)}"
            )]

    async def _execute_command(
        self, full_command: str, timeout: int,
        tool_name: Optional[str] = None, raw_command: Optional[str] = None,
    ) -> List[TextContent]:
        """
        Execute a command safely.

        tool_name/raw_command (when provided by a caller that already ran
        its own safety check — gcloud/gsutil/bq) identify the entry for the
        shared command_audit_log; _check_gcloud_auth/_check_gcloud_config/
        _get_gcloud_help don't pass them and simply aren't audited, same as
        before this feature existed.
        """
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
            start_time = time.monotonic()

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

            if tool_name and raw_command is not None:
                log_command("gcp", tool_name, raw_command, allowed=True,
                            exit_code=process.returncode,
                            duration_ms=int((time.monotonic() - start_time) * 1000))

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
            if tool_name and raw_command is not None:
                log_command("gcp", tool_name, raw_command, allowed=True,
                            block_reason=f"timed out after {timeout}s")
            return [TextContent(
                type="text",
                text=f"Error: Command timed out after {timeout} seconds"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing command: {str(e)}"
            )]

    def _get_audit_log(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Show recent GCP (gcloud/gsutil/bq) entries from the shared command audit log."""
        limit = arguments.get("limit", 20)
        entries = read_recent(limit=limit, provider="gcp")

        if not entries:
            return [TextContent(type="text", text="No GCP commands recorded in the audit log yet.")]

        binary_by_tool = {
            "cloud-sec-gcloud-cli": "gcloud",
            "cloud-sec-gsutil-cli": "gsutil",
            "cloud-sec-bq-cli": "bq",
        }
        lines = [f"Last {len(entries)} GCP command(s) from output/command_audit.log:\n"]
        for e in entries:
            status = "BLOCKED" if not e.get("allowed") else f"exit={e.get('exit_code')}"
            extra = f" ({e['block_reason']})" if e.get("block_reason") else ""
            binary = binary_by_tool.get(e.get("tool"), e.get("tool", "?"))
            lines.append(f"[{e.get('timestamp')}] {status}{extra}: {binary} {e.get('command')}")

        return [TextContent(type="text", text="\n".join(lines))]

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

    def _is_safe_gcloud_command(self, command: str) -> bool:
        """
        Check if a gcloud command is safe to execute.

        Delegates to cloud_command_safety.is_safe_gcloud_command(), which
        allowlists read-only gcloud subcommands (list/describe/get-*/...)
        rather than blocklisting dangerous substrings — including the old
        "delete" carve-out for "instances list" etc., which was itself a
        substring match and not actually tied to what command ran. See that
        module's docstring for why the substring-blocklist approach this
        replaced was both bypassable and prone to false positives.
        """
        if not is_safe_gcloud_command(command):
            logger.warning(f"Blocked gcloud command that isn't a recognized read-only operation: {command}")
            return False

        return True

    def _is_safe_gsutil_command(self, command: str) -> bool:
        """Check if a gsutil command is safe to execute (see is_safe_gcloud_command docstring)."""
        if not is_safe_gsutil_command(command):
            logger.warning(f"Blocked gsutil command that isn't a recognized read-only operation: {command}")
            return False

        return True

    def _is_safe_bq_command(self, command: str) -> bool:
        """Check if a bq command is safe to execute (see is_safe_gcloud_command docstring)."""
        if not is_safe_bq_command(command):
            logger.warning(f"Blocked bq command that isn't a recognized read-only operation: {command}")
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