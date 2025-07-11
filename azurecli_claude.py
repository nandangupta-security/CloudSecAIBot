#!/usr/bin/env python3
"""
Azure CLI MCP Server
A Model Context Protocol server that executes Azure CLI commands safely.
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
logger = logging.getLogger("azure-mcp-server")

class AzureMCPServer:
    def __init__(self):
        self.server = Server("azure-cli-server")
        self.setup_handlers()
        
    def setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="azure_cli",
                    description="Execute Azure CLI commands safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The Azure CLI command to execute (without 'az' prefix)"
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
                    name="azure_login_check",
                    description="Check Azure CLI login status and configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="azure_help",
                    description="Get help for Azure CLI commands",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "Azure service/command name (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="azure_account_info",
                    description="Get current Azure account and subscription information",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if name == "azure_cli":
                return await self._execute_azure_command(arguments)
            elif name == "azure_login_check":
                return await self._check_azure_login()
            elif name == "azure_help":
                return await self._get_azure_help(arguments)
            elif name == "azure_account_info":
                return await self._get_account_info()
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]

    async def _execute_azure_command(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute Azure CLI command safely"""
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
            
            # Prepare full Azure command
            full_command = f"az {command}"
            
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

    async def _check_azure_login(self) -> List[TextContent]:
        """Check Azure CLI login status"""
        try:
            # Check if Azure CLI is installed
            process = await asyncio.create_subprocess_exec(
                "az", "--version",
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
                    text="Azure CLI is not installed or not accessible"
                )]
            
            version_info = stdout.decode('utf-8').strip()
            
            # Check login status
            login_process = await asyncio.create_subprocess_exec(
                "az", "account", "show",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            login_stdout, login_stderr = await asyncio.wait_for(
                login_process.communicate(),
                timeout=10
            )
            
            response_text = f"Azure CLI Version:\n{version_info}\n\n"
            
            if login_process.returncode == 0:
                response_text += "Login Status: Logged in\n"
                response_text += "Current Account:\n"
                response_text += login_stdout.decode('utf-8')
            else:
                response_text += "Login Status: Not logged in\n"
                response_text += "Error:\n"
                response_text += login_stderr.decode('utf-8')
            
            return [TextContent(
                type="text",
                text=response_text
            )]
            
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: Azure login check timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking Azure login: {str(e)}"
            )]

    async def _get_azure_help(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get Azure CLI help"""
        try:
            service = arguments.get("service", "")
            
            if service:
                cmd = ["az", service, "--help"]
            else:
                cmd = ["az", "--help"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10
            )
            
            if process.returncode == 0:
                # Truncate help text as it can be very long
                help_text = stdout.decode('utf-8')
                if len(help_text) > 2000:
                    help_text = help_text[:2000] + "\n... (truncated)"
                
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

    async def _get_account_info(self) -> List[TextContent]:
        """Get Azure account and subscription information"""
        try:
            # Get account list
            process = await asyncio.create_subprocess_exec(
                "az", "account", "list", "--output", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=15
            )
            
            if process.returncode == 0:
                try:
                    accounts = json.loads(stdout.decode('utf-8'))
                    response_text = "Azure Account Information:\n\n"
                    
                    for account in accounts:
                        response_text += f"Subscription: {account.get('name', 'Unknown')}\n"
                        response_text += f"ID: {account.get('id', 'Unknown')}\n"
                        response_text += f"State: {account.get('state', 'Unknown')}\n"
                        response_text += f"Default: {'Yes' if account.get('isDefault', False) else 'No'}\n"
                        response_text += f"Tenant ID: {account.get('tenantId', 'Unknown')}\n"
                        response_text += "-" * 50 + "\n"
                    
                    return [TextContent(
                        type="text",
                        text=response_text
                    )]
                except json.JSONDecodeError:
                    return [TextContent(
                        type="text",
                        text=f"Raw output:\n{stdout.decode('utf-8')}"
                    )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Error getting account info: {stderr.decode('utf-8')}"
                )]
                
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: Account info command timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting account info: {str(e)}"
            )]

    def _is_safe_command(self, command: str) -> bool:
        """Check if command is safe to execute"""
        # List of potentially dangerous operations
        dangerous_patterns = [
            "delete", "remove", "destroy", "purge",
            "&&", "||", ";", "|", ">", "<",
            "sudo", "su", "chmod", "chown",
            "eval", "exec", "system", "rm ",
            # Azure-specific dangerous operations
            "deployment delete", "group delete",
            "vm delete", "disk delete",
            "keyvault delete", "storage delete"
        ]
        
        command_lower = command.lower()
        
        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                logger.warning(f"Blocked potentially dangerous command: {command}")
                return False
        
        # Additional safety checks
        if command.startswith("-") or command.startswith("--"):
            logger.warning(f"Blocked command starting with dash: {command}")
            return False
        
        # Check for delete operations in various forms
        if " delete " in command_lower or command_lower.endswith(" delete"):
            logger.warning(f"Blocked delete operation: {command}")
            return False
        
        return True

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Azure CLI MCP Server")
        
        # Initialize and run server
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], 
                streams[1], 
                InitializationOptions(
                    server_name="azure-cli-server",
                    server_version="1.0.0",
                    capabilities={}
                )
            )

def main():
    """Main entry point"""
    server = AzureMCPServer()
    
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
