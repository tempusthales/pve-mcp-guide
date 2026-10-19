# 08. Troubleshooting

[Back to README](../README.md) | Previous: [07. Connect a client](07-connect-client.md) | Next: [09. Maintenance](09-maintenance.md)

Errors seen while building this setup, and their fixes. When you share logs for help, remove tokens, keys and hostnames first.

## Quick reference

| Symptom | Likely cause | Section |
|---|---|---|
| `pct: command not found` | Node command run inside the container | [Wrong shell](#pct-command-not-found) |
| `^[[200~` at the start of a command | Bracketed paste in the browser console | [Bracketed paste](#200-garbage-when-pasting) |
| `curl` to `https://<PVE_IP>:8006` prints `000` | Container on the wrong bridge or VLAN | [No route to the host](#container-cannot-reach-the-proxmox-api-000) |
| `ip_unprivileged_port_start ... permission denied` | lxc-pve too old | [Docker fails](#docker-fails-in-the-container) |
| `SSL: CERTIFICATE_VERIFY_FAILED` in the server log | CA or SAN mismatch | [Certificates](#certificate-errors) |
| `PermissionError` on `config.json` | Wrong owner or uid | [Startup errors](#server-does-not-start) |
| `401` locally, with the key | Key mismatch or extra characters | [HTTP status codes](#http-status-codes) |
| `421 Invalid Host header` | `MCP_ALLOWED_HOSTS` wrong | [HTTP status codes](#http-status-codes) |
| `406 Not Acceptable` | Missing `Accept` header | [HTTP status codes](#http-status-codes) |
| `302` from the public hostname | Access policy uses Allow | [Cloudflare errors](#cloudflare-errors) |
| `502` or `530` from the public hostname | Tunnel down or wrong service URL | [Cloudflare errors](#cloudflare-errors) |
| `cloudflared tunnel login` stuck on `Waiting for login...` | Authorization not finished in the browser | [Cloudflare errors](#cloudflare-errors) |
| Client shows the server as failed | uv not found, env vars missing | [Bridge and client](#bridge-and-client) |

## Shell mix-ups

### pct: command not found

`pct` exists only on the Proxmox node. If you see this, you ran a `[NODE]` command inside the container. Look at the prompt:

| Prompt | Where you are |
|---|---|
| `root@pve:~#` | the node |
| `root@pve-mcp:~#` | the container |

Type `exit` to leave a shell opened with `pct enter`, or switch to the node's Shell tab in the web UI.

Two node commands that help:

**Step 1 [NODE].** Open a root shell in the container.

```
pct enter <CTID>
```

Expected: the prompt changes to `root@pve-mcp:~#`.

**Step 2 [NODE].** Run a single command in the container without entering it (example: show its IP).

```
pct exec <CTID> -- ip -4 -brief addr show eth0
```

Expected: the container's `eth0` line with `<CT_IP>`.

### ^[[200~ garbage when pasting

Errors such as `-bash: $'\E[200~pct': command not found` come from bracketed paste: the browser console (noVNC or xterm.js) sends invisible markers around pasted text, and the shell sees them as part of the command. Retype the command by hand, or paste into an SSH session instead of the browser console. In the container console, `bind 'set enable-bracketed-paste off'` turns it off for that shell.

### Heredocs in fish

This guide does not use heredocs, but if you adapt it: fish has no `<<EOF` syntax. Run such commands in bash, or use `printf` or an editor instead.

## Network

### Container cannot reach the Proxmox API (000)

`curl -sk -o /dev/null -w "%{http_code}\n" https://<PVE_IP>:8006` prints `000` and `ping <PVE_IP>` shows 100% loss.

Cause seen on the test host: the container was on a VLAN-tagged bridge in another subnet, with no route to the management subnet. Fix: put the container on the same bridge (and VLAN, if any) as the host's management IP. Full steps are in [02. Network lesson](02-create-lxc.md#network-lesson-same-bridge-as-the-host).

Other causes: a wrong `<PVE_IP>`, the Proxmox firewall blocking port 8006 from the container's address, or no DHCP lease (check with `pct exec <CTID> -- ip -4 -brief addr show eth0`).

### Container IP changed

The DHCP reservation was made for an old MAC address. `pct set ... --net0` without `hwaddr=` creates a new MAC. Update the reservation with the MAC from `pct config <CTID> | grep net0`, then `pct reboot <CTID>`.

## Docker fails in the container

| Error from `docker run --rm hello-world` | Fix |
|---|---|
| `open sysctl net.ipv4.ip_unprivileged_port_start ... permission denied` | Upgrade the host so `lxc-pve` is 6.0.5-2 or newer ([01](01-proxmox-prereqs.md#check-the-lxc-pve-version)). |
| keyring, overlay or cgroup errors | Enable `nesting=1,keyctl=1` and reboot the container ([02](02-create-lxc.md#enable-features-and-start)). |
| `Cannot connect to the Docker daemon` | `systemctl status docker` in the container. Restart it with `systemctl restart docker`. |

## Certificate errors

### Certificate SAN does not list the host IP

If `openssl x509 -in /etc/pve/local/pve-ssl.pem -noout -ext subjectAltName` does not show `IP Address:<PVE_IP>` (for example after the host IP changed), regenerate the node certificate.

**Step 1 [NODE].** Regenerate the node certificates from the current host settings.

```
pvecm updatecerts --force
```

Expected: a few lines about generating and merging certificates, no errors.

**Step 2 [NODE].** Restart the web and API proxy.

```
systemctl restart pveproxy
```

Expected: no output. Browser sessions to the web UI may need a reload.

### Custom or ACME certificate on the Proxmox API

If `/etc/pve/local/pveproxy-ssl.pem` exists, the API serves that certificate and the Proxmox root CA does not apply. Choose one:

- Replace `/opt/pve-mcp/proxmox-config/pve-root-ca.pem` in the container with the CA chain that issued your certificate (same filename), then `docker compose up -d --force-recreate` in `/opt/pve-mcp`.
- For a public CA such as Let's Encrypt: delete the `REQUESTS_CA_BUNDLE` line from `.env` so the server uses its bundled public CA store, set `host` in `config.json` to a DNS name on that certificate, then recreate the container.

### Temporary bypass (last resort)

Only to confirm that TLS is the problem: in `config.json`, set `"verify_ssl": false` and `"allow_insecure_tls": true` in the target. `verify_ssl: false` alone is rejected at startup on purpose. Recreate the container, test, and revert as soon as CA trust works.

## Server does not start

Check the log first.

**Step 1 [CT].** Show the last 50 log lines.

```
docker compose --project-directory /opt/pve-mcp logs --tail 50
```

Expected: either `Uvicorn running on http://0.0.0.0:8000` or an error near the end.

| Log message | Fix |
|---|---|
| `PermissionError` on `/app/proxmox-config/config.json` | Owner must be the app uid (1000). Run `chown 1000:1000` and `chmod 600` on the file ([04, steps 9 and 10](04-proxmoxmcp-plus.md#part-2-configjson)). If step 19 showed another uid, use that. |
| `JSONDecodeError` | Syntax error in `config.json`. Run `python3 -m json.tool /opt/pve-mcp/proxmox-config/config.json > /dev/null` to find the line. |
| Error about `MCP_API_KEY` | `.env` has an empty key. Redo [04, step 12](04-proxmoxmcp-plus.md#part-3-env-and-composeyaml). |
| Error naming an unknown tool | A name in `MCP_TOOL_ALLOWLIST` does not exist in this release. Check spelling, or compare with the release notes after an update. |
| `verify_ssl` / `allow_insecure_tls` error | See [Temporary bypass](#temporary-bypass-last-resort). |
| Startup fails after adding `cap_drop: ALL` | Remove the two `cap_drop` lines from `compose.yaml` and report it upstream. It was not needed on the test host. |

After any change to `config.json`, `.env` or `compose.yaml`, apply it:

**Step 2 [CT].** Recreate the container with the new settings.

```
docker compose --project-directory /opt/pve-mcp up -d --force-recreate
```

Expected: `Container pve-mcp  Started`.

## HTTP status codes

| Code | Where you see it | Meaning and fix |
|---|---|---|
| `000` | any curl | No connection at all. Wrong address, server down, or firewall. |
| `401` | local test with the key | The bearer key does not match `.env`. Check for quotes, spaces or a cut-off paste. |
| `401` | public hostname, no CF headers | Access is not active for this hostname yet. See [06](06-cloudflare-access.md). |
| `403` | public hostname | Access blocked the request. Expected without the service token. With the token, check the Client ID and Secret, and that the policy includes this token. |
| `406` | any MCP request | The `Accept: application/json, text/event-stream` header is missing. |
| `421` | any MCP request | The Host header is not in `MCP_ALLOWED_HOSTS`. Add `<MCP_HOSTNAME>` and `<MCP_HOSTNAME>:*`, then recreate the container. |

## Cloudflare errors

| Symptom | Fix |
|---|---|
| `302` redirect to a Cloudflare login page | The Access policy action is Allow. Change it to Service Auth, and remove any other policies ([06](06-cloudflare-access.md#part-2-create-the-access-application)). |
| `502 Bad Gateway` | cloudflared runs, but nothing answers at the route's URL. Check that the service URL is `http://127.0.0.1:8000` (not `https`, not `localhost`) and that `docker compose ps` shows the container running. |
| `530` or error 1033 | The tunnel has no healthy connector. In the container, run `systemctl status cloudflared --no-pager` and `journalctl -u cloudflared -n 50`. |
| `cloudflared tunnel login` stuck on `Waiting for login...` | Open the printed URL in a browser, pick the zone and click Authorize. Or use the dashboard-managed tunnel ([05](05-cloudflare-tunnel.md)). |
| Tunnel shows Down after a reboot | `systemctl enable --now cloudflared` in the container. |
| Hostname does not resolve | Check DNS in the Cloudflare dashboard for a CNAME to `<TUNNEL_ID>.cfargotunnel.com`. The route step creates it. |

## Bridge and client

| Symptom | Fix |
|---|---|
| `pve-mcp bridge: missing env var(s): ...` | Set the named variables in the client config `env` block. The names are case-sensitive. |
| `pve-mcp-bridge: uv not found` | GUI apps often start with a short PATH. Set `UV_BIN` to the output of `command -v uv`, or install uv to `~/.local/bin`. |
| `Permission denied` starting the wrapper | `chmod 755` the wrapper. |
| `pve_mcp_bridge.py not found` | Keep both files in the same folder. |
| Client shows the server failed, no message | Run the smoke test from [07](07-connect-client.md#part-2-smoke-test). It shows the real error. Claude Desktop also writes logs (macOS: `~/Library/Logs/Claude/`). |
| `403` or `401` inside the bridge error | Same meaning as in [HTTP status codes](#http-status-codes). |
| Works in the test, not in the client | The client config has a typo, uses `~` in the path, or was not restarted. |

Next: [09. Maintenance](09-maintenance.md)
