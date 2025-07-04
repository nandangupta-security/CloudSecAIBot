from setuptools import setup, find_packages

setup(
    name="aws-mcp-server",
    version="1.0.0",
    description="MCP server for AWS CLI commands",
    packages=find_packages(),
    install_requires=[
        "mcp>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "aws-mcp-server=aws_mcp_server:main",
        ],
    },
)
