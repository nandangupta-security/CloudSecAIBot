#!/usr/bin/env python3
"""
Prowler MCP Server - Security audit tool for AWS, Azure, and GCP
Leverages existing CLI credentials for authentication
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import mcp.server.stdio

# Initialize MCP server
app = Server("prowler-security-audit")

# Output directory path (created only when needed)
OUTPUT_DIR = Path(__file__).parent / "output"


def ensure_output_directory() -> Path:
    """
    Ensure the output directory exists and is readable/writable.
    Called only when an audit is requested.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    # Ensure the directory is readable and writable
    os.chmod(OUTPUT_DIR, 0o755)
    return OUTPUT_DIR


def run_prowler_command(args: list[str], timeout: int = 300) -> dict[str, Any]:
    """
    Execute Prowler CLI command safely
    
    Args:
        args: Command arguments (without 'prowler' prefix)
        timeout: Command timeout in seconds (default: 300)
    
    Returns:
        Dictionary with stdout, stderr, returncode, and success status
    """
    try:
        # Build full command
        cmd = ["prowler"] + args
        
        # Execute command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1,
            "success": False
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": "Prowler is not installed or not found in PATH. Install with: pip install prowler",
            "returncode": -1,
            "success": False
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "returncode": -1,
            "success": False
        }


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available Prowler security audit tools"""
    return [
        Tool(
            name="prowler_aws_audit",
            description="Run Prowler security audit on AWS account using AWS CLI credentials. Supports filtering by services, regions, severity, and compliance frameworks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "services": {
                        "type": "string",
                        "description": "Comma-separated AWS services to audit (e.g., 's3,ec2,iam'). Leave empty for all services."
                    },
                    "regions": {
                        "type": "string",
                        "description": "Comma-separated AWS regions to audit (e.g., 'us-east-1,eu-west-1'). Leave empty for all regions."
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity: critical, high, medium, low, informational",
                        "enum": ["critical", "high", "medium", "low", "informational"]
                    },
                    "compliance": {
                        "type": "string",
                        "description": "Filter by compliance framework (e.g., 'cis_1.5_aws', 'hipaa_aws', 'gdpr_aws', 'pci_3.2.1_aws')"
                    },
                    "profile": {
                        "type": "string",
                        "description": "AWS CLI profile name to use. Leave empty for default profile."
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format for results",
                        "enum": ["json-ocsf", "json-asff", "csv", "html"],
                        "default": "json-ocsf"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 600)",
                        "default": 600
                    }
                }
            }
        ),
        Tool(
            name="prowler_azure_audit",
            description="Run Prowler security audit on Azure subscription using Azure CLI credentials. Supports filtering by services and compliance frameworks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "services": {
                        "type": "string",
                        "description": "Comma-separated Azure services to audit (e.g., 'storage,compute,network'). Leave empty for all services."
                    },
                    "subscription_id": {
                        "type": "string",
                        "description": "Azure subscription ID to audit. Leave empty to use current subscription."
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity: critical, high, medium, low, informational",
                        "enum": ["critical", "high", "medium", "low", "informational"]
                    },
                    "compliance": {
                        "type": "string",
                        "description": "Filter by compliance framework (e.g., 'cis_2.0_azure', 'ens_rd2022_azure')"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format for results",
                        "enum": ["json-ocsf", "json-asff", "csv", "html"],
                        "default": "json-ocsf"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 600)",
                        "default": 600
                    }
                }
            }
        ),
        Tool(
            name="prowler_gcp_audit",
            description="Run Prowler security audit on GCP project using gcloud CLI credentials. Supports filtering by services and compliance frameworks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "GCP project ID to audit. Required for GCP audits."
                    },
                    "services": {
                        "type": "string",
                        "description": "Comma-separated GCP services to audit (e.g., 'storage,compute,iam'). Leave empty for all services."
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity: critical, high, medium, low, informational",
                        "enum": ["critical", "high", "medium", "low", "informational"]
                    },
                    "compliance": {
                        "type": "string",
                        "description": "Filter by compliance framework (e.g., 'cis_1.3_gcp')"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format for results",
                        "enum": ["json-ocsf", "json-asff", "csv", "html"],
                        "default": "json-ocsf"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 600)",
                        "default": 600
                    }
                },
                "required": ["project_id"]
            }
        ),
        Tool(
            name="prowler_list_services",
            description="List all available services that can be audited by Prowler for a specific cloud provider",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Cloud provider",
                        "enum": ["aws", "azure", "gcp"]
                    }
                },
                "required": ["provider"]
            }
        ),
        Tool(
            name="prowler_list_compliance",
            description="List all available compliance frameworks supported by Prowler for a specific cloud provider",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Cloud provider",
                        "enum": ["aws", "azure", "gcp"]
                    }
                },
                "required": ["provider"]
            }
        ),
        Tool(
            name="prowler_check_installation",
            description="Check if Prowler is installed and configured correctly, and verify CLI credentials for each cloud provider",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls for Prowler security audits"""
    
    if name == "prowler_aws_audit":
        # Ensure output directory exists (only created when audit is requested)
        output_dir = ensure_output_directory()
        
        # Build Prowler AWS command
        args = ["aws"]
        
        if arguments.get("profile"):
            args.extend(["--profile", arguments["profile"]])
        
        if arguments.get("services"):
            args.extend(["--services", arguments["services"]])
        
        if arguments.get("regions"):
            args.extend(["--region", arguments["regions"]])
        
        if arguments.get("severity"):
            args.extend(["--severity", arguments["severity"]])
        
        if arguments.get("compliance"):
            args.extend(["--compliance", arguments["compliance"]])
        
        # Set output format
        output_format = arguments.get("output_format", "json-ocsf")
        args.extend(["--output-formats", output_format])
        
        # Set output directory
        args.extend(["--output-directory", str(output_dir)])
        
        # Execute command
        timeout = arguments.get("timeout", 600)
        result = run_prowler_command(args, timeout)
        
        if result["success"]:
            return [TextContent(
                type="text",
                text=f"✅ AWS Security Audit Completed Successfully\n\nOutput files saved to: {output_dir}\n\n{result['stdout']}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"❌ AWS Security Audit Failed\n\nError: {result['stderr']}\n\nOutput: {result['stdout']}"
            )]
    
    elif name == "prowler_azure_audit":
        # Ensure output directory exists (only created when audit is requested)
        output_dir = ensure_output_directory()
        
        # Build Prowler Azure command
        args = ["azure"]
        
        if arguments.get("subscription_id"):
            args.extend(["--subscription-id", arguments["subscription_id"]])
        
        if arguments.get("services"):
            args.extend(["--services", arguments["services"]])
        
        if arguments.get("severity"):
            args.extend(["--severity", arguments["severity"]])
        
        if arguments.get("compliance"):
            args.extend(["--compliance", arguments["compliance"]])
        
        # Set output format
        output_format = arguments.get("output_format", "json-ocsf")
        args.extend(["--output-formats", output_format])
        
        # Set output directory
        args.extend(["--output-directory", str(output_dir)])
        
        # Execute command
        timeout = arguments.get("timeout", 600)
        result = run_prowler_command(args, timeout)
        
        if result["success"]:
            return [TextContent(
                type="text",
                text=f"✅ Azure Security Audit Completed Successfully\n\nOutput files saved to: {output_dir}\n\n{result['stdout']}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"❌ Azure Security Audit Failed\n\nError: {result['stderr']}\n\nOutput: {result['stdout']}"
            )]
    
    elif name == "prowler_gcp_audit":
        # Ensure output directory exists (only created when audit is requested)
        output_dir = ensure_output_directory()
        
        # Build Prowler GCP command
        project_id = arguments.get("project_id")
        if not project_id:
            return [TextContent(
                type="text",
                text="❌ Error: project_id is required for GCP audits"
            )]
        
        args = ["gcp", "--project-id", project_id]
        
        if arguments.get("services"):
            args.extend(["--services", arguments["services"]])
        
        if arguments.get("severity"):
            args.extend(["--severity", arguments["severity"]])
        
        if arguments.get("compliance"):
            args.extend(["--compliance", arguments["compliance"]])
        
        # Set output format
        output_format = arguments.get("output_format", "json-ocsf")
        args.extend(["--output-formats", output_format])
        
        # Set output directory
        args.extend(["--output-directory", str(output_dir)])
        
        # Execute command
        timeout = arguments.get("timeout", 600)
        result = run_prowler_command(args, timeout)
        
        if result["success"]:
            return [TextContent(
                type="text",
                text=f"✅ GCP Security Audit Completed Successfully\n\nOutput files saved to: {output_dir}\n\n{result['stdout']}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"❌ GCP Security Audit Failed\n\nError: {result['stderr']}\n\nOutput: {result['stdout']}"
            )]
    
    elif name == "prowler_list_services":
        provider = arguments.get("provider")
        result = run_prowler_command([provider, "--list-services"])
        
        if result["success"]:
            return [TextContent(
                type="text",
                text=f"Available {provider.upper()} Services:\n\n{result['stdout']}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"❌ Failed to list services\n\nError: {result['stderr']}"
            )]
    
    elif name == "prowler_list_compliance":
        provider = arguments.get("provider")
        result = run_prowler_command([provider, "--list-compliance"])
        
        if result["success"]:
            return [TextContent(
                type="text",
                text=f"Available {provider.upper()} Compliance Frameworks:\n\n{result['stdout']}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"❌ Failed to list compliance frameworks\n\nError: {result['stderr']}"
            )]
    
    elif name == "prowler_check_installation":
        # Check Prowler installation
        version_result = run_prowler_command(["--version"])
        
        output = "🔍 Prowler Installation Check\n\n"
        
        if version_result["success"]:
            output += f"✅ Prowler is installed\n{version_result['stdout']}\n\n"
        else:
            output += f"❌ Prowler is not installed or not found in PATH\n{version_result['stderr']}\n\n"
            return [TextContent(type="text", text=output)]
        
        # Track available environments
        available_envs = []
        
        # Check AWS credentials
        output += "Cloud Environment Status:\n"
        output += "=" * 50 + "\n\n"
        
        try:
            aws_check = subprocess.run(
                ["aws", "sts", "get-caller-identity"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output += "AWS CLI:\n"
            if aws_check.returncode == 0:
                output += f"✅ Configured and ready\n{aws_check.stdout}\n"
                available_envs.append("AWS")
            else:
                output += f"⚠️ Not configured or invalid credentials\n"
        except FileNotFoundError:
            output += "AWS CLI:\n⚠️ AWS CLI not installed\n"
        except Exception as e:
            output += f"AWS CLI:\n⚠️ Error checking credentials: {str(e)}\n"
        
        # Check Azure credentials
        try:
            azure_check = subprocess.run(
                ["az", "account", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output += "\nAzure CLI:\n"
            if azure_check.returncode == 0:
                output += f"✅ Configured and ready\n{azure_check.stdout}\n"
                available_envs.append("Azure")
            else:
                output += f"⚠️ Not logged in or invalid credentials\n"
        except FileNotFoundError:
            output += "\nAzure CLI:\n⚠️ Azure CLI not installed\n"
        except Exception as e:
            output += f"\nAzure CLI:\n⚠️ Error checking credentials: {str(e)}\n"
        
        # Check GCP credentials
        try:
            gcp_check = subprocess.run(
                ["gcloud", "auth", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output += "\nGCP CLI:\n"
            if gcp_check.returncode == 0:
                output += f"✅ Configured and ready\n{gcp_check.stdout}\n"
                available_envs.append("GCP")
            else:
                output += f"⚠️ Not authenticated or invalid credentials\n"
        except FileNotFoundError:
            output += "\nGCP CLI:\n⚠️ GCP CLI (gcloud) not installed\n"
        except Exception as e:
            output += f"\nGCP CLI:\n⚠️ Error checking credentials: {str(e)}\n"
        
        # Summary
        output += "\n" + "=" * 50 + "\n"
        output += "Summary:\n"
        if available_envs:
            output += f"✅ Ready to audit: {', '.join(available_envs)}\n"
            output += f"💡 You can run security audits on {len(available_envs)} cloud environment(s)\n"
        else:
            output += "❌ No cloud environments configured\n"
            output += "💡 Please configure at least one cloud provider:\n"
            output += "   - AWS: Run 'aws configure'\n"
            output += "   - Azure: Run 'az login'\n"
            output += "   - GCP: Run 'gcloud auth login'\n"
        
        return [TextContent(type="text", text=output)]
    
    else:
        return [TextContent(
            type="text",
            text=f"❌ Unknown tool: {name}"
        )]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List all available Prowler output files"""
    resources = []
    
    # Ensure output directory exists (in case user wants to list resources)
    output_dir = ensure_output_directory()
    
    # List all files in the output directory
    if output_dir.exists():
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                # Create a URI for the resource
                uri = f"prowler-output://{file_path.name}"
                resources.append(
                    Resource(
                        uri=uri,
                        name=file_path.name,
                        description=f"Prowler audit output file: {file_path.name}",
                        mimeType="application/json" if file_path.suffix == ".json" else "text/plain"
                    )
                )
    
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read the content of a Prowler output file"""
    # Ensure output directory exists
    output_dir = ensure_output_directory()
    
    # Parse the URI to get the filename
    if not uri.startswith("prowler-output://"):
        raise ValueError(f"Invalid resource URI: {uri}")
    
    filename = uri.replace("prowler-output://", "")
    file_path = output_dir / filename
    
    # Security check: ensure the file is within the output directory
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise ValueError(f"Invalid resource path: {filename}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Resource not found: {filename}")
    
    # Read and return the file content
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
