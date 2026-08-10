#!/bin/bash
# Run Neptune MCP Server locally for testing

# Require the graph ID to be supplied by the local environment.
: "${NEPTUNE_GRAPH_ID:?Set NEPTUNE_GRAPH_ID before running this script}"

# Set AWS region if not already set
export AWS_REGION="${AWS_REGION:-us-east-1}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

# Run the MCP server
echo "Starting Neptune MCP Server locally..."
echo "Graph ID: $NEPTUNE_GRAPH_ID"
echo "AWS Region: $AWS_REGION"
echo ""
echo "Server will start with streamable HTTP transport"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")"
"$PYTHON_BIN" main.py
