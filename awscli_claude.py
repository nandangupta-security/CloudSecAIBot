#!/usr/bin/env python3
"""
AWS CLI MCP Server
A Model Context Protocol server that executes AWS CLI commands safely.
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
logger = logging.getLogger("aws-mcp-server")

class AWSMCPServer:
    def __init__(self):
        self.server = Server("aws-cli-server")
        self.setup_handlers()
        
    def setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="aws_cli",
                    description="Execute AWS CLI commands safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The AWS CLI command to execute (without 'aws' prefix)"
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
                    name="aws_configure_check",
                    description="Check AWS CLI configuration status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="aws_help",
                    description="Get help for AWS CLI commands",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "AWS service name (optional)"
                            }
                        }
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if name == "aws_cli":
                return await self._execute_aws_command(arguments)
            elif name == "aws_configure_check":
                return await self._check_aws_config()
            elif name == "aws_help":
                return await self._get_aws_help(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]

    async def _execute_aws_command(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute AWS CLI command safely"""
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
            
            # Prepare full AWS command
            full_command = f"aws {command}"
            
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
            
            # Create subprocess without timeout parameter
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

    async def _check_aws_config(self) -> List[TextContent]:
        """Check AWS CLI configuration"""
        try:
            # Check if AWS CLI is installed
            process = await asyncio.create_subprocess_exec(
                "aws", "--version",
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
                    text="AWS CLI is not installed or not accessible"
                )]
            
            version_info = stdout.decode('utf-8').strip()
            
            # Check configuration
            config_process = await asyncio.create_subprocess_exec(
                "aws", "configure", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            config_stdout, config_stderr = await asyncio.wait_for(
                config_process.communicate(),
                timeout=10
            )
            
            response_text = f"AWS CLI Version: {version_info}\n\n"
            
            if config_process.returncode == 0:
                response_text += "Configuration:\n"
                response_text += config_stdout.decode('utf-8')
            else:
                response_text += "Configuration Error:\n"
                response_text += config_stderr.decode('utf-8')
            
            return [TextContent(
                type="text",
                text=response_text
            )]
            
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text="Error: AWS configuration check timed out"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking AWS configuration: {str(e)}"
            )]

    async def _get_aws_help(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get AWS CLI help"""
        try:
            service = arguments.get("service", "")
            
            if service:
                cmd = ["aws", service, "help"]
            else:
                cmd = ["aws", "help"]
            
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

    def _is_safe_command(self, command: str) -> bool:
        """Check if command is safe to execute"""
        # List of potentially dangerous operations
        dangerous_patterns = [
            "rm", "delete", "destroy", "terminate",
            "&&", "||", ";", "|", ">", "<",
            "sudo", "su", "chmod", "chown",
            "eval", "exec", "system"
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
        
        return True

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting AWS CLI MCP Server")
        
        # Initialize and run server
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], 
                streams[1], 
                InitializationOptions(
                    server_name="aws-cli-server",
                    server_version="1.0.0",
                    capabilities={}
                )
            )

def main():
    """Main entry point"""
    server = AWSMCPServer()
    
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
