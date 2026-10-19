# 07. Connect a client

[Back to README](../README.md) | Previous: [06. Cloudflare Access](06-cloudflare-access.md) | Next: [08. Troubleshooting](08-troubleshooting.md)

This part connects an AI assistant to the server through a small stdio bridge that runs on your workstation.

## Why a custom bridge

Many MCP clients only start local stdio servers, or cannot send custom headers to a remote server. A bridge solves that: the client talks stdio to a local process, and the process talks Streamable HTTP to `https://<MCP_HOSTNAME>/mcp` with the three headers.

The common choice is the `mcp-remote` npm package. It was rejected here on supply-chain grounds. At the time, it had several releases in a single day and a maintainer we did not expect. That may have been harmless, but a package that receives all three secrets should be easy to review. So the bridge here is about 50 lines of Python on the official MCP Python SDK, pinned to `mcp==1.30.0` and run with `uv`.

If your client supports remote Streamable HTTP servers with custom headers, you can skip the bridge and give it the URL and the three headers from [06](06-cloudflare-access.md#part-3-verify-both-layers) directly.

## Files

| File | Purpose |
|---|---|
| [bridge/pve_mcp_bridge.py](../bridge/pve_mcp_bridge.py) | The bridge. Reads four env vars, forwards `list_tools` and `call_tool`. |
| [bridge/pve-mcp-bridge](../bridge/pve-mcp-bridge) | Bash wrapper. Finds `uv` and runs the bridge with the pinned SDK. |
| [bridge/test_bridge.py](../bridge/test_bridge.py) | Smoke test: `initialize`, `list_tools`, `get_nodes`. |

Environment variables:

| Variable | Value | Secret |
|---|---|---|
| `PVE_MCP_URL` | `https://<MCP_HOSTNAME>/mcp` | no |
| `PVE_MCP_CF_CLIENT_ID` | `<CF_ACCESS_CLIENT_ID>` | yes |
| `PVE_MCP_CF_CLIENT_SECRET` | `<CF_ACCESS_CLIENT_SECRET>` | yes |
| `PVE_MCP_API_KEY` | `<MCP_API_KEY>` | yes |
| `UV_BIN` | full path to `uv` (optional) | no |
| `PVE_MCP_PYTHON` | Python version for uv (optional, default `3.13`) | no |

The bridge exits with a clear message on stderr if a required variable is missing, for example `pve-mcp bridge: missing env vars: PVE_MCP_API_KEY`.

## Part 1: Install

The steps assume you cloned this repo to `~/pve-mcp-guide` and keep the bridge in `~/bin`. Any folder works, as long as the two bridge files stay together.

**Step 1 [WORKSTATION].** Check whether uv is installed.

```
uv --version
```

Expected: `uv 0.x.y`. If the command is not found, install uv from <https://docs.astral.sh/uv/getting-started/installation/> (or your package manager) and open a new terminal.

**Step 2 [WORKSTATION].** Create the folder for the bridge.

```
mkdir -p ~/bin
```

Expected: no output.

**Step 3 [WORKSTATION].** Copy the bridge script.

```
cp ~/pve-mcp-guide/bridge/pve_mcp_bridge.py ~/bin/
```

Expected: no output.

**Step 4 [WORKSTATION].** Copy the wrapper.

```
cp ~/pve-mcp-guide/bridge/pve-mcp-bridge ~/bin/
```

Expected: no output.

**Step 5 [WORKSTATION].** Make the wrapper executable.

```
chmod 755 ~/bin/pve-mcp-bridge
```

Expected: no output.

**Step 6 [WORKSTATION].** Run the wrapper with no variables set, to check that uv works and the error message shows.

```
env -i HOME="$HOME" PATH="$PATH" ~/bin/pve-mcp-bridge
```

Expected (the first run may take a few seconds while uv downloads Python and the SDK): `pve-mcp bridge: missing env var: PVE_MCP_URL (example: https://pve-mcp.example.com/mcp)`.

## Part 2: Smoke test

The test starts the wrapper the same way an MCP client does. It never prints the secrets.

**Step 7 [WORKSTATION].** Allow commands that start with a space to stay out of history (this shell only).

```
export HISTCONTROL=ignoreboth
```

Expected: no output.

**Step 8 [WORKSTATION].** Set the URL.

```
export PVE_MCP_URL='https://<MCP_HOSTNAME>/mcp'
```

Expected: no output.

**Step 9 [WORKSTATION].** Set the Access Client ID.

```
 export PVE_MCP_CF_CLIENT_ID='<CF_ACCESS_CLIENT_ID>'
```

Expected: no output.

**Step 10 [WORKSTATION].** Set the Access Client Secret.

```
 export PVE_MCP_CF_CLIENT_SECRET='<CF_ACCESS_CLIENT_SECRET>'
```

Expected: no output.

**Step 11 [WORKSTATION].** Set the bearer key.

```
 export PVE_MCP_API_KEY='<MCP_API_KEY>'
```

Expected: no output.

fish users: use `set -x NAME 'value'` instead of `export NAME='value'`, and keep the leading space.

**Step 12 [WORKSTATION].** Run the test.

```
uv run --no-project --with mcp==1.30.0 ~/pve-mcp-guide/bridge/test_bridge.py
```

Expected:

```text
initialize: OK (server name: proxmox)
list_tools: 29 tools
  get_cluster_log
  get_cluster_status
  ...
  preflight_container_migration
get_nodes: OK
<JSON or text describing your node(s), status, CPU and memory>
```

`proxmox` is the bridge's own server name. The remote server reports itself as `ProxmoxMCP` (seen in [06](06-cloudflare-access.md#part-3-verify-both-layers)).

`test_bridge.py` runs the wrapper next to itself, so this tests the copy in the repo. Both copies are the same file.

**Step 13 [WORKSTATION].** Close the terminal (or unset the variables) so the secrets do not linger in the shell.

```
unset PVE_MCP_CF_CLIENT_ID PVE_MCP_CF_CLIENT_SECRET PVE_MCP_API_KEY
```

Expected: no output.

## Part 3: Register it in your MCP client

Most clients accept a JSON block with a command and environment variables. Use the absolute path to the wrapper (no `~`), because many clients do not expand it.

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "/home/<YOUR_USER>/bin/pve-mcp-bridge",
      "args": [],
      "env": {
        "PVE_MCP_URL": "https://<MCP_HOSTNAME>/mcp",
        "PVE_MCP_CF_CLIENT_ID": "<CF_ACCESS_CLIENT_ID>",
        "PVE_MCP_CF_CLIENT_SECRET": "<CF_ACCESS_CLIENT_SECRET>",
        "PVE_MCP_API_KEY": "<MCP_API_KEY>"
      }
    }
  }
}
```

Where that block goes:

| Client | Location |
|---|---|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Code (project scope) | `.mcp.json` in the project root. Do not commit it with real values. |
| Other clients | See the client's docs for "stdio MCP server" or "mcpServers". |

On macOS, the home folder is `/Users/<YOUR_USER>`, so the command is `/Users/<YOUR_USER>/bin/pve-mcp-bridge`.

The config file now holds secrets. Restrict it.

**Step 14 [WORKSTATION].** Restrict the client config file (example for Claude Desktop on macOS).

```
chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Expected: no output.

Claude Code alternative, from the command line (user scope, so nothing lands in a project folder). Start the line with a space.

**Step 15 [WORKSTATION].** Add the server to Claude Code.

```
 claude mcp add proxmox --scope user -e PVE_MCP_URL='https://<MCP_HOSTNAME>/mcp' -e PVE_MCP_CF_CLIENT_ID='<CF_ACCESS_CLIENT_ID>' -e PVE_MCP_CF_CLIENT_SECRET='<CF_ACCESS_CLIENT_SECRET>' -e PVE_MCP_API_KEY='<MCP_API_KEY>' -- /home/<YOUR_USER>/bin/pve-mcp-bridge
```

Keep the server name first and the `--` before the command. Expected: `Added stdio MCP server proxmox ...`. Check with `claude mcp list`, which should show `proxmox` as connected.

**Step 16 [WORKSTATION].** Restart the client (fully quit Claude Desktop, not just close the window) and ask the assistant something like "List my Proxmox nodes and VMs".

Expected: the assistant calls `get_nodes` and `get_vms` and shows your nodes and guests. Write tools are not registered, so for a request such as "stop VM 100" the assistant has no tool to call.

### Windows

The wrapper is a bash script. On Windows, skip it and let the client call uv directly:

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "uv",
      "args": ["run", "--quiet", "--no-project", "--python", "3.13", "--with", "mcp==1.30.0", "C:\\Users\\<YOUR_USER>\\bin\\pve_mcp_bridge.py"],
      "env": {
        "PVE_MCP_URL": "https://<MCP_HOSTNAME>/mcp",
        "PVE_MCP_CF_CLIENT_ID": "<CF_ACCESS_CLIENT_ID>",
        "PVE_MCP_CF_CLIENT_SECRET": "<CF_ACCESS_CLIENT_SECRET>",
        "PVE_MCP_API_KEY": "<MCP_API_KEY>"
      }
    }
  }
}
```

If the client cannot find `uv`, put the full path to `uv.exe` in `command`.

Next: [08. Troubleshooting](08-troubleshooting.md)
