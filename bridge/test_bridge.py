#!/usr/bin/env python3
# test_bridge.py: smoke test for pve-mcp-bridge.
#
# Author: Tempus Thales
# License: MIT
#
# Starts ./pve-mcp-bridge the same way an MCP client does (stdio), then runs
# initialize, list_tools and a get_nodes call. Secrets are passed through from
# your environment to the bridge and are never printed.
#
# Run from the repo root:
#   uv run --no-project --with mcp==1.30.0 bridge/test_bridge.py
import os
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

REQUIRED = ("PVE_MCP_URL", "PVE_MCP_CF_CLIENT_ID", "PVE_MCP_CF_CLIENT_SECRET", "PVE_MCP_API_KEY")
OPTIONAL = ("UV_BIN", "PVE_MCP_PYTHON")


async def main() -> int:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print(f"test_bridge: missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    # The SDK passes only a minimal environment to the child process by default,
    # so add the bridge's variables explicitly.
    env = get_default_environment()
    env.update({name: os.environ[name] for name in REQUIRED + OPTIONAL if os.environ.get(name)})

    wrapper = Path(__file__).resolve().parent / "pve-mcp-bridge"
    params = StdioServerParameters(command=str(wrapper), args=[], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"initialize: OK (server name: {init.serverInfo.name})")

            tools = (await session.list_tools()).tools
            print(f"list_tools: {len(tools)} tools")
            for name in sorted(tool.name for tool in tools):
                print(f"  {name}")

            result = await session.call_tool("get_nodes", {})
            if result.isError:
                print("get_nodes: ERROR", file=sys.stderr)
                for block in result.content:
                    if block.type == "text":
                        print(block.text, file=sys.stderr)
                return 1
            print("get_nodes: OK")
            for block in result.content:
                if block.type == "text":
                    print(block.text)
    return 0


if __name__ == "__main__":
    sys.exit(anyio.run(main))
