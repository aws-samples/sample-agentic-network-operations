#!/usr/bin/env python3
"""Test the Neptune MCP server locally over its streamable HTTP transport."""

import asyncio
import json
import os
import socket
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError:
    print("ERROR: mcp package not found. Install with: pip install mcp==1.26.0")
    sys.exit(1)


STARTUP_TIMEOUT_SECONDS = 15
EXPECTED_TOOLS = {
    "run_opencypher_query",
    "get_graph_schema",
    "get_graph_status",
}


async def stop_server(process: asyncio.subprocess.Process) -> None:
    """Stop the local runtime without leaving a child process behind."""
    if process.returncode is not None:
        return

    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


def find_available_port() -> int:
    """Select a free loopback port for an isolated local test runtime."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def wait_for_server(
    process: asyncio.subprocess.Process, server_url: str
) -> None:
    """Wait until the local runtime accepts TCP connections."""
    parsed_url = urlparse(server_url)
    host = parsed_url.hostname
    port = parsed_url.port
    if not host or not port:
        raise RuntimeError(f"Invalid local MCP server URL: {server_url}")

    last_error: OSError | None = None
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if process.returncode is not None:
            raise RuntimeError(
                f"Neptune MCP runtime exited during startup with code {process.returncode}."
            )

        try:
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError as error:
            last_error = error
            await asyncio.sleep(0.25)

    raise RuntimeError(
        f"Neptune MCP runtime did not become ready at {server_url} within "
        f"{STARTUP_TIMEOUT_SECONDS} seconds."
    ) from last_error


@asynccontextmanager
async def create_mcp_client() -> AsyncIterator[ClientSession]:
    """Start the local runtime and connect to its streamable HTTP endpoint."""
    env = os.environ.copy()
    if not env.get("NEPTUNE_GRAPH_ID"):
        raise RuntimeError(
            "Set NEPTUNE_GRAPH_ID to the Neptune Analytics graph ID before running this test."
        )
    env.setdefault("AWS_REGION", "us-east-1")
    port = find_available_port()
    server_url = f"http://127.0.0.1:{port}/mcp"
    env["MCP_PORT"] = str(port)

    runtime_directory = Path(__file__).resolve().parent
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "main.py",
        cwd=runtime_directory,
        env=env,
    )

    try:
        await wait_for_server(process, server_url)
        async with streamable_http_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    finally:
        await stop_server(process)


async def test_list_tools(session: ClientSession) -> None:
    """Test that the pinned server exposes the documented tool catalog."""
    print("=" * 60)
    print("Testing: List Tools")
    print("=" * 60)

    tools = await session.list_tools()
    tool_names = {tool.name for tool in tools.tools}
    missing_tools = EXPECTED_TOOLS - tool_names
    if missing_tools:
        raise RuntimeError(
            "The local MCP server is missing documented tools: "
            + ", ".join(sorted(missing_tools))
        )

    print(f"\nFound {len(tools.tools)} tools:")
    for tool in tools.tools:
        print(f"\n  - {tool.name}")
        print(f"    Description: {tool.description[:100]}...")
        if hasattr(tool, "inputSchema"):
            print(f"    Input Schema: {json.dumps(tool.inputSchema, indent=6)[:200]}...")


def ensure_tool_succeeded(tool_name: str, result: object) -> None:
    """Fail the integration test when an MCP tool returns an error response."""
    if getattr(result, "isError", False):
        raise RuntimeError(
            f"{tool_name} returned an error response. Check the runtime logs for details."
        )


async def test_execute_query(session: ClientSession) -> None:
    """Test executing a simple Neptune query."""
    print("\n" + "=" * 60)
    print("Testing: Execute Query")
    print("=" * 60)

    query = "MATCH (n) RETURN count(n) as node_count"
    print(f"\nExecuting query: {query}")

    result = await session.call_tool(
        "run_opencypher_query",
        arguments={"query": query},
    )
    ensure_tool_succeeded("run_opencypher_query", result)

    print("\nResult:")
    for content in result.content:
        print(content.text if hasattr(content, "text") else content)


async def test_get_schema(session: ClientSession) -> None:
    """Test getting the graph schema."""
    print("\n" + "=" * 60)
    print("Testing: Get Schema")
    print("=" * 60)

    result = await session.call_tool("get_graph_schema", arguments={})
    ensure_tool_succeeded("get_graph_schema", result)

    print("\nSchema:")
    for content in result.content:
        output = content.text if hasattr(content, "text") else str(content)
        print(output[:500] + "...")


async def main() -> None:
    """Run all local integration checks against one runtime process."""
    print("\nNeptune MCP Server Local Test\n")

    try:
        async with create_mcp_client() as session:
            await test_list_tools(session)
            await test_execute_query(session)
            await test_get_schema(session)

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as error:
        print(f"\nError: {error}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
