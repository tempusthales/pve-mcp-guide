#!/usr/bin/env python3
# pve_mcp_bridge.py: stdio to Streamable HTTP bridge for a ProxmoxMCP-Plus server
# behind Cloudflare Access.
#
# Author: Tempus Thales
# License: MIT
#
# The MCP client starts this script as a local stdio server. Every list_tools and
# call_tool request is forwarded to the remote server over HTTPS.
#
# Configuration comes from the environment only. Nothing is logged or written to disk.
#   PVE_MCP_URL               https://<MCP_HOSTNAME>/mcp
#   PVE_MCP_CF_CLIENT_ID      Cloudflare Access service token Client ID
#   PVE_MCP_CF_CLIENT_SECRET  Cloudflare Access service token Client Secret
#   PVE_MCP_API_KEY           ProxmoxMCP-Plus bearer key (MCP_API_KEY on the server)
#
# Run it with: uv run --no-project --with mcp==1.30.0 pve_mcp_bridge.py
# stdout carries the MCP protocol. Errors go to stderr only.
import os
import sys

import anyio
import mcp.types as types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

SECRET_VARS = ("PVE_MCP_CF_CLIENT_ID", "PVE_MCP_CF_CLIENT_SECRET", "PVE_MCP_API_KEY")


def fail(message: str) -> None:
    print(f"pve-mcp bridge: {message}", file=sys.stderr)
    sys.exit(1)


def url() -> str:
    value = os.environ.get("PVE_MCP_URL", "").strip()
    if not value:
        fail("missing env var: PVE_MCP_URL (example: https://pve-mcp.example.com/mcp)")
    if not value.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        fail("PVE_MCP_URL must start with https:// (plain http is allowed for localhost only)")
    return value


def headers() -> dict[str, str]:
    missing = [name for name in SECRET_VARS if not os.environ.get(name)]
    if missing:
        fail(f"missing env vars: {', '.join(missing)}")
    return {
        "CF-Access-Client-Id": os.environ["PVE_MCP_CF_CLIENT_ID"],
        "CF-Access-Client-Secret": os.environ["PVE_MCP_CF_CLIENT_SECRET"],
        "Authorization": f"Bearer {os.environ['PVE_MCP_API_KEY']}",
    }


async def main() -> None:
    target, auth = url(), headers()
    async with streamablehttp_client(target, headers=auth) as (read, write, _):
        async with ClientSession(read, write) as upstream:
            await upstream.initialize()
            server = Server("proxmox")

            @server.list_tools()
            async def list_tools() -> list[types.Tool]:
                return (await upstream.list_tools()).tools

            @server.call_tool()
            async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
                return await upstream.call_tool(name, arguments)

            async with stdio_server() as (sin, sout):
                await server.run(sin, sout, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
