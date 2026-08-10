#!/usr/bin/env python3
"""
Neptune MCP Server Runtime Entrypoint

This script serves as the entrypoint for the Neptune MCP Runtime.
It constructs the NEPTUNE_ENDPOINT from environment variables and
runs the AWS Labs Neptune MCP server with AgentCore-compatible settings.
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Starting Neptune MCP Runtime...")

# Construct NEPTUNE_ENDPOINT from environment variables
# Format: neptune-graph://<graph-id>
graph_id = os.environ.get('NEPTUNE_GRAPH_ID')
logger.info(f"Neptune Graph ID: {graph_id}")

if not graph_id:
    logger.error("NEPTUNE_GRAPH_ID environment variable is required")
    sys.exit(1)

# Set AWS region - CRITICAL for boto3 client initialization
aws_region = os.environ.get('AWS_REGION', 'us-east-1')
os.environ['AWS_REGION'] = aws_region
os.environ['AWS_DEFAULT_REGION'] = aws_region
logger.info(f"AWS Region: {aws_region}")

# Set the NEPTUNE_ENDPOINT that the AWS Labs MCP server expects
neptune_endpoint = f'neptune-graph://{graph_id}'
os.environ['NEPTUNE_ENDPOINT'] = neptune_endpoint
logger.info(f"NEPTUNE_ENDPOINT set to: {neptune_endpoint}")

# Now import the MCP server (after setting environment variables)
try:
    from awslabs.amazon_neptune_mcp_server.server import mcp
    logger.info("Successfully imported Neptune MCP server")
except Exception as e:
    logger.error(f"Failed to import Neptune MCP server: {e}")
    raise

# Configure for AgentCore compatibility
# AgentCore requires stateless_http=True for proper operation
logger.info("Configuring MCP server for AgentCore compatibility...")
mcp.settings.stateless_http = True
# AgentCore Runtime must reach the HTTP server inside the managed container.
mcp.settings.host = "0.0.0.0"  # nosec B104
try:
    mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
except ValueError:
    logger.error("MCP_PORT must be an integer")
    sys.exit(1)

if not 1 <= mcp.settings.port <= 65535:
    logger.error("MCP_PORT must be between 1 and 65535")
    sys.exit(1)

# Disable DNS rebinding protection for AgentCore
# AgentCore sends requests with internal AWS hostnames that need to be allowed
mcp.settings.transport_security.enable_dns_rebinding_protection = False
logger.info(
    "MCP server settings: stateless_http=%s, host=%s, port=%s, "
    "dns_rebinding_protection=%s",
    mcp.settings.stateless_http,
    mcp.settings.host,
    mcp.settings.port,
    mcp.settings.transport_security.enable_dns_rebinding_protection,
)

if __name__ == "__main__":
    # Run the MCP server with streamable-http transport for AgentCore
    logger.info("Starting MCP server with streamable-http transport...")
    mcp.run(transport="streamable-http")
