# 04. ProxmoxMCP-Plus

[Back to README](../README.md) | Previous: [03. Docker](03-docker.md) | Next: [05. Cloudflare Tunnel](05-cloudflare-tunnel.md)

This part downloads ProxmoxMCP-Plus at a pinned tag, writes the three config files, builds the image and tests the server locally.

Where this ends: the MCP server runs in the container and answers on `127.0.0.1:8000` only.

## Before you start: two shells

Most steps run in `[CT]`. One step (copying the CA certificate) runs in `[NODE]`. Keep both open in separate browser tabs and check the prompt before every paste.

| Label | How to open it | Prompt |
|---|---|---|
| `[NODE]` | Proxmox web UI > Datacenter > `<PVE_NODE>` > Shell | `root@pve:~#` |
| `[CT]` | Proxmox web UI > `<CTID>` > Console (log in as root), or `pct enter <CTID>` from the node | `root@pve-mcp:~#` |

How to use nano (steps 6, 11 and 16):

1. Run the `nano ...` command. An empty editor opens.
2. Paste the block the step gives you. In the browser console, use Ctrl+Shift+V.
3. Save with Ctrl+O, then Enter.
4. Exit with Ctrl+X.

You also need `<TOKEN_SECRET>` from [01](01-proxmox-prereqs.md#create-the-read-only-user-and-api-token).

## Part 1: Get the code

**Step 1 [CT].** Create the folders.

```
mkdir -p /opt/pve-mcp/proxmox-config
```

Expected: no output.

**Step 2 [CT].** Clone the pinned release tag (shallow).

```
git clone --branch v0.6.3 --depth 1 https://github.com/RekklesNA/ProxmoxMCP-Plus.git /opt/pve-mcp/ProxmoxMCP-Plus
```

Expected: `Cloning into '/opt/pve-mcp/ProxmoxMCP-Plus'...` and a "detached HEAD" notice. The notice is normal for a tag.

**Step 3 [CT].** Verify the commit. Tags can be moved. A commit hash cannot.

```
git -C /opt/pve-mcp/ProxmoxMCP-Plus rev-parse HEAD
```

Expected: exactly `9aa91b3cbfcad1b1e69accde7bfa593a44669fd7`. If it prints anything else, stop. Compare against the [v0.6.3 release page](https://github.com/RekklesNA/ProxmoxMCP-Plus/releases/tag/v0.6.3) before you go on.

**Step 4 [NODE].** Copy the Proxmox root CA into the container. This command only works on the node.

```
pct push <CTID> /etc/pve/pve-root-ca.pem /opt/pve-mcp/proxmox-config/pve-root-ca.pem --perms 0644
```

Expected: no output.

**Step 5 [CT].** Confirm the certificate arrived.

```
openssl x509 -in /opt/pve-mcp/proxmox-config/pve-root-ca.pem -noout -subject -enddate
```

Expected: a `subject=` line that mentions `Proxmox Virtual Environment`, and a `notAfter=` date in the future.

## Part 2: config.json

**Step 6 [CT].** Create config.json.

```
nano /opt/pve-mcp/proxmox-config/config.json
```

Paste the block below (it is the same as [files/config.json](../files/config.json)). Then, in nano, replace the placeholders and keep the quotes:

- `<PVE_IP>` with the host's management IP
- `<TOKEN_NAME>` with your token name
- `<TOKEN_SECRET>` with the UUID from [01](01-proxmox-prereqs.md#create-the-read-only-user-and-api-token)
- `<MCP_HOSTNAME>` (two lines) with your public hostname, for example `pve-mcp.example.com`

Keep `"readonly": true`. The target key `"pve"` is only a label. If you change it, change it in `client_permissions` too.

```json
{
  "targets": {
    "pve": {
      "host": "<PVE_IP>",
      "port": 8006,
      "timeout": 30,
      "verify_ssl": true,
      "allow_insecure_tls": false,
      "service": "PVE",
      "kind": "standalone",
      "readonly": true,
      "auth": {
        "user": "mcp-ro@pve",
        "token_name": "<TOKEN_NAME>",
        "token_value": "<TOKEN_SECRET>"
      },
      "command_policy": {
        "mode": "deny_all",
        "require_approval_token": false,
        "high_risk_mode": "enforce",
        "high_risk_require_approval_token": true
      }
    }
  },
  "mcp": {
    "transport": "STREAMABLE",
    "host": "0.0.0.0",
    "port": 8000,
    "dns_rebinding_protection": true,
    "allowed_hosts": [
      "<MCP_HOSTNAME>",
      "<MCP_HOSTNAME>:*",
      "127.0.0.1:*",
      "localhost:*"
    ],
    "allow_unauthenticated_http": false,
    "client_permissions": {
      "_shared_key": {
        "tools": ["*"],
        "targets": ["pve"]
      }
    }
  },
  "logging": { "level": "INFO" },
  "security": { "dev_mode": false },
  "command_policy": {
    "mode": "deny_all",
    "require_approval_token": false,
    "high_risk_mode": "enforce",
    "high_risk_require_approval_token": true
  }
}
```

Save and exit.

**Step 7 [CT].** Check that no placeholder is left.

```
grep -n '<' /opt/pve-mcp/proxmox-config/config.json
```

Expected: no output. If a line prints, reopen the file (step 6) and fix it.

**Step 8 [CT].** Check the JSON syntax. This uses Debian's python3 and does not run any repo code.

```
python3 -m json.tool /opt/pve-mcp/proxmox-config/config.json > /dev/null
```

Expected: no output. An error names the line with the problem (often a missing comma or quote). If you see `python3: command not found`, run `apt install -y python3-minimal` and try again.

**Step 9 [CT].** Make config.json owned by the container's app user (uid 1000, checked in step 19).

```
chown 1000:1000 /opt/pve-mcp/proxmox-config/config.json
```

Expected: no output.

**Step 10 [CT].** Restrict it. It contains the token secret.

```
chmod 600 /opt/pve-mcp/proxmox-config/config.json
```

Expected: no output.

Note: `config.json` is read as-is. It has no `${VAR}` substitution, so the token secret must be written literally in the file. The `MCP_*` variables in `.env` override the file's `mcp` section.

## Part 3: .env and compose.yaml

**Step 11 [CT].** Create .env.

```
nano /opt/pve-mcp/.env
```

Paste the block below. Replace `<MCP_HOSTNAME>` (two places). Leave `MCP_API_KEY=` empty. Step 12 fills it in. A commented version is in [files/.env.example](../files/.env.example).

```text
MCP_TRANSPORT=STREAMABLE_HTTP
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_API_KEY=
MCP_ALLOW_UNAUTHENTICATED_HTTP=false
MCP_DNS_REBINDING_PROTECTION=true
MCP_ALLOWED_HOSTS=<MCP_HOSTNAME>,<MCP_HOSTNAME>:*,127.0.0.1:*,localhost:*
MCP_TOOL_ALLOWLIST=get_cluster_log,get_cluster_status,get_container_config,get_container_ip,get_containers,get_guest_firewall_log,get_job,get_next_vmid,get_node_diagnostics,get_node_firewall_log,get_node_status,get_node_storage,get_node_syslog,get_node_time,get_nodes,get_storage,get_task_log,get_vm_config,get_vm_ip_addresses,get_vms,list_backups,list_bridges,list_isos,list_jobs,list_snapshots,list_targets,list_templates,poll_job,preflight_container_migration
REQUESTS_CA_BUNDLE=/app/proxmox-config/pve-root-ca.pem
```

Save and exit. No quotes, no spaces around `=` or after commas.

**Step 12 [CT].** Generate the bearer key and write it straight into .env. The key never appears on screen.

```
sed -i "s|^MCP_API_KEY=.*|MCP_API_KEY=$(openssl rand -hex 32)|" /opt/pve-mcp/.env
```

Expected: no output.

**Step 13 [CT].** Confirm a 64-character key went in. This prints only the length.

```
grep '^MCP_API_KEY=' /opt/pve-mcp/.env | cut -d= -f2 | tr -d '\n' | wc -c
```

Expected: `64`.

**Step 14 [CT].** Check that no placeholder is left in the non-comment lines.

```
grep -n '^[^#].*<' /opt/pve-mcp/.env
```

Expected: no output.

**Step 15 [CT].** Restrict .env. It holds the bearer key.

```
chmod 600 /opt/pve-mcp/.env
```

Expected: no output.

**Step 16 [CT].** Create compose.yaml.

```
nano /opt/pve-mcp/compose.yaml
```

Paste the block below unchanged (same as [files/compose.yaml](../files/compose.yaml) without the comments). YAML cares about spaces, so keep the indentation.

```yaml
name: pve-mcp
services:
  proxmox-mcp-http:
    build:
      context: ./ProxmoxMCP-Plus
      dockerfile: Dockerfile
    image: proxmoxmcp-plus:v0.6.3
    container_name: pve-mcp
    restart: unless-stopped
    env_file: .env
    environment:
      PROXMOX_MCP_CONFIG: /app/proxmox-config/config.json
      PROXMOX_JOBS_SQLITE_PATH: /app/data/proxmox-jobs.sqlite3
      PROXMOX_MCP_MODE: mcp-http
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./proxmox-config:/app/proxmox-config:ro
      - proxmox-jobs:/app/data
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
volumes:
  proxmox-jobs:
```

Save and exit.

Why not use the repo's own `docker-compose.yml`? Its `proxmox-mcp-http` service publishes `"8000:8000"` on all interfaces, and the same file has an always-on `proxmox-mcp-api` service that requires `PROXMOX_API_KEY`. The `compose.yaml` above copies the `proxmox-mcp-http` service with the same build, environment and volumes. The only changes are loopback-only publishing, `no-new-privileges` and `cap_drop: ALL`.

## Part 4: Build, start, test

**Step 17 [CT].** Go to the project folder. The remaining steps assume you are here.

```
cd /opt/pve-mcp
```

Expected: no output. The prompt shows `/opt/pve-mcp`.

**Step 18 [CT].** Build the image from the pinned source.

```
docker compose build
```

Expected: takes a few minutes the first time (about 6 minutes on 1 core). It ends with a line like `naming to docker.io/library/proxmoxmcp-plus:v0.6.3` or `Built`.

**Step 19 [CT].** Check which user the app runs as.

```
docker compose run --rm --no-deps --entrypoint id proxmox-mcp-http
```

Expected: `uid=1000(proxmoxmcp) gid=1000(proxmoxmcp) groups=1000(proxmoxmcp)`. If the uid is not 1000, redo step 9 with that number.

**Step 20 [CT].** Start the service.

```
docker compose up -d
```

Expected: `Container pve-mcp  Started`.

**Step 21 [CT].** Watch the log for about 10 seconds, then press Ctrl+C. Ctrl+C only stops the log view, not the server.

```
docker compose logs -f
```

Expected: a line like `Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)` and no `Traceback`. The `0.0.0.0` is inside the Docker container. Step 22 checks what the host side exposes. If you see an error, copy the log without any token or key and see [08](08-troubleshooting.md).

**Step 22 [CT].** Confirm the port is published on loopback only.

```
ss -ltnp | grep 8000
```

Expected: `127.0.0.1:8000` and no `0.0.0.0:8000` or `[::]:8000`.

**Step 23 [CT].** Send a request without the key.

```
curl -i http://127.0.0.1:8000/mcp
```

Expected: `HTTP/1.1 401 Unauthorized`, a `www-authenticate: Bearer` header and the body `{"detail":"Unauthorized"}`. That is the correct result.

**Step 24 [CT].** Send an MCP `initialize` request with the key. The command reads the key from .env, so nothing secret appears on screen.

```
curl -sS -i -X POST http://127.0.0.1:8000/mcp -H "Authorization: Bearer $(grep '^MCP_API_KEY=' /opt/pve-mcp/.env | cut -d= -f2)" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Expected: `HTTP/1.1 200 OK` and a body (often in `event: message` / `data: ...` form) that contains `"serverInfo":{"name":"ProxmoxMCP"`.

- `421 Invalid Host header`: `MCP_ALLOWED_HOSTS` in .env is wrong.
- `406 Not Acceptable`: the Accept header was cut off while pasting.

**Step 25 [WORKSTATION].** Confirm the MCP port is not reachable from the LAN.

```
curl -m 5 -sS -o /dev/null -w '%{http_code}\n' http://<CT_IP>:8000/mcp
```

Expected: `000` plus an error such as `Failed to connect` or `Connection refused`.

## The 29 tools

These are the tools in `MCP_TOOL_ALLOWLIST`. All of them are in the server's internal read-only set. `get_cluster_join_info` is left out on purpose. It returns cluster join details, which monitoring does not need.

| Area | Tools |
|---|---|
| Cluster | `get_cluster_status`, `get_cluster_log`, `list_targets` |
| Nodes | `get_nodes`, `get_node_status`, `get_node_storage`, `get_node_syslog`, `get_node_time`, `get_node_diagnostics`, `get_node_firewall_log`, `list_bridges` |
| VMs | `get_vms`, `get_vm_config`, `get_vm_ip_addresses` |
| Containers | `get_containers`, `get_container_config`, `get_container_ip`, `preflight_container_migration` |
| Guests | `get_guest_firewall_log`, `get_next_vmid`, `list_snapshots` |
| Storage | `get_storage`, `list_backups`, `list_isos`, `list_templates` |
| Tasks and jobs | `get_task_log`, `get_job`, `list_jobs`, `poll_job` |

`preflight_container_migration` only checks whether a migration would work. It does not migrate.

Next: [05. Cloudflare Tunnel](05-cloudflare-tunnel.md)
