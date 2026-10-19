# 05. Cloudflare Tunnel

[Back to README](../README.md) | Previous: [04. ProxmoxMCP-Plus](04-proxmoxmcp-plus.md) | Next: [06. Cloudflare Access](06-cloudflare-access.md)

This part publishes `http://127.0.0.1:8000` in the container as `https://<MCP_HOSTNAME>` through a Cloudflare Tunnel. The tunnel connects outbound from the container, so no router port is opened.

This guide uses a dashboard-managed tunnel (recommended). The first attempt on the test host used a locally-managed tunnel and stalled at `cloudflared tunnel login` (see [Why not locally-managed](#why-not-locally-managed)). The locally-managed path is kept as an [appendix](#appendix-locally-managed-tunnel) for people who want config in a file.

Cloudflare renames dashboard menus from time to time. Where a name differs between UI versions, both are given.

## Before you start

- `<DOMAIN>` is an active zone in your Cloudflare account.
- You have a Zero Trust organization (Cloudflare dashboard > Zero Trust; the free plan is enough).
- The MCP server answers locally ([04, step 24](04-proxmoxmcp-plus.md#part-4-build-start-test)).

About the window between this doc and the next: once the route exists, `https://<MCP_HOSTNAME>` is public until the Access application from [06](06-cloudflare-access.md) is in place. The server still requires the bearer key during that time. To close the window completely, do parts 1 and 2 of [06](06-cloudflare-access.md) (service token and Access application) before step 13 here. Access applications can be created before the hostname exists.

## Part 1: Create the tunnel

**Step 1 [DASHBOARD].** Open Zero Trust > Networks > Tunnels (newer UI: Networks > Connectors > Cloudflare Tunnels) and click Create a tunnel.

**Step 2 [DASHBOARD].** Choose Cloudflared as the connector type and click Next.

**Step 3 [DASHBOARD].** Name the tunnel `<TUNNEL_NAME>` and save it.

**Step 4 [DASHBOARD].** On the install page, choose Debian as the operating system and 64-bit as the architecture. Leave the page open. You need the "Install as a service" command in step 11. Do not copy the token anywhere but the container.

## Part 2: Install cloudflared in the container

All of these run in `[CT]` as root.

**Step 5 [CT].** Create the keyring folder.

```
mkdir -p --mode=0755 /usr/share/keyrings
```

Expected: no output.

**Step 6 [CT].** Download Cloudflare's package signing key.

```
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
```

Expected: no output.

**Step 7 [CT].** Add the cloudflared apt repository.

```
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' > /etc/apt/sources.list.d/cloudflared.list
```

Expected: no output.

**Step 8 [CT].** Refresh the package lists.

```
apt update
```

Expected: a line that mentions `pkg.cloudflare.com/cloudflared any InRelease` and no `NO_PUBKEY` error.

**Step 9 [CT].** Install cloudflared.

```
apt install -y cloudflared
```

Expected: ends without errors. `cloudflared --version` prints a version.

## Part 3: Run the tunnel as a service

The dashboard's command looks like `sudo cloudflared service install eyJ...`. The long `eyJ...` string is `<TUNNEL_TOKEN>`. In the container you are already root, and Debian's minimal template has no sudo, so drop `sudo`.

Start the command with a space so bash does not save it in history. Debian's root `.bashrc` does not always set `HISTCONTROL`, so set it first.

**Step 10 [CT].** Tell bash to skip commands that start with a space (this shell only).

```
export HISTCONTROL=ignoreboth
```

Expected: no output.

**Step 11 [CT].** Paste the dashboard's install command without `sudo` and with a leading space.

```
 cloudflared service install <TUNNEL_TOKEN>
```

Expected: log lines ending with something like `Linux service for cloudflared installed successfully`. The token is stored in the systemd unit, so treat container backups as secret-bearing.

**Step 12 [CT].** Check the service.

```
systemctl status cloudflared --no-pager
```

Expected: `active (running)` and log lines with `Registered tunnel connection`. In the dashboard, the tunnel status changes to Healthy and the Next button becomes active.

## Part 4: Add the public route

**Step 13 [DASHBOARD].** Click Next (or open the tunnel and go to the Public Hostname tab; newer UI: Published application routes) and add a route:

| Field | Value |
|---|---|
| Subdomain | the first label of `<MCP_HOSTNAME>`, for example `pve-mcp` |
| Domain | `<DOMAIN>` |
| Path | empty |
| Service type | `HTTP` |
| URL | `127.0.0.1:8000` |

Newer UIs may ask you to choose "Published application" as the route type first. Save. Cloudflare creates the DNS CNAME record for `<MCP_HOSTNAME>` automatically.

Use `127.0.0.1`, not `localhost`. `localhost` can resolve to `::1`, and Docker publishes the port on IPv4 loopback only.

**Step 14 [WORKSTATION].** Check that the hostname resolves.

```
dig +short <MCP_HOSTNAME>
```

Expected: one or more Cloudflare IP addresses. It can take a minute after step 13. If `dig` is missing, `nslookup <MCP_HOSTNAME>` works too.

**Step 15 [WORKSTATION].** Send a request without any credentials.

```
curl -sS -o /dev/null -w '%{http_code}\n' https://<MCP_HOSTNAME>/mcp
```

Expected before Access exists: `401` (the server's bearer check, which proves the tunnel works). Expected after [06](06-cloudflare-access.md): `403`.

If you get `502` or `530`, see [08](08-troubleshooting.md#cloudflare-errors).

Next: [06. Cloudflare Access](06-cloudflare-access.md)

## Why not locally-managed

`cloudflared tunnel login` prints a URL and waits with `Waiting for login...`. It keeps waiting until you open that URL in a browser, pick the zone (`<DOMAIN>`) and click Authorize. On the test host this looked like a hang. The dashboard-managed path avoids the login step and the certificate file it creates, and you can change routes from the dashboard without touching the container.

## Appendix: locally-managed tunnel

Use this instead of parts 1, 3 and 4 if you want the tunnel defined in a config file. Do part 2 (install cloudflared) first. All steps run in `[CT]` unless marked otherwise.

**Step A1 [CT].** Start the login. It prints a URL.

```
cloudflared tunnel login
```

Expected: a `https://dash.cloudflare.com/argotunnel?...` URL and `Waiting for login...`.

**Step A2 [WORKSTATION].** Open the URL in a browser, pick `<DOMAIN>` and click Authorize.

Expected: the container prints `You have successfully logged in` and saves `/root/.cloudflared/cert.pem`.

**Step A3 [CT].** Create the tunnel.

```
cloudflared tunnel create <TUNNEL_NAME>
```

Expected: `Created tunnel <TUNNEL_NAME> with id <TUNNEL_ID>` and a credentials file at `/root/.cloudflared/<TUNNEL_ID>.json`. Write down `<TUNNEL_ID>`.

**Step A4 [CT].** Create the DNS record for the hostname.

```
cloudflared tunnel route dns <TUNNEL_NAME> <MCP_HOSTNAME>
```

Expected: `Added CNAME <MCP_HOSTNAME> which will route to this tunnel`.

**Step A5 [CT].** Create the system config folder.

```
mkdir -p /etc/cloudflared
```

Expected: no output.

**Step A6 [CT].** Copy the credentials file next to the config.

```
cp /root/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/
```

Expected: no output.

**Step A7 [CT].** Restrict the credentials file.

```
chmod 600 /etc/cloudflared/<TUNNEL_ID>.json
```

Expected: no output.

**Step A8 [CT].** Create the config file.

```
nano /etc/cloudflared/config.yml
```

Paste this, replace the placeholders, save and exit. The last rule returns 404 for any other hostname. cloudflared requires a catch-all rule at the end.

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: <MCP_HOSTNAME>
    service: http://127.0.0.1:8000
  - service: http_status:404
```

**Step A9 [CT].** Validate the ingress rules.

```
cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate
```

Expected: `OK`.

**Step A10 [CT].** Check which rule a request would match.

```
cloudflared tunnel --config /etc/cloudflared/config.yml ingress rule https://<MCP_HOSTNAME>/mcp
```

Expected: a `Matched rule` line followed by `hostname: <MCP_HOSTNAME>` and `service: http://127.0.0.1:8000`.

**Step A11 [CT].** Install the service. Without a token, it reads `/etc/cloudflared/config.yml`.

```
cloudflared service install
```

Expected: `Linux service for cloudflared installed successfully`.

**Step A12 [CT].** Check the service.

```
systemctl status cloudflared --no-pager
```

Expected: `active (running)` with `Registered tunnel connection` lines.

**Step A13 [CT].** Remove the account certificate. It can create and delete tunnels in your account, and the running tunnel does not need it.

```
rm /root/.cloudflared/cert.pem
```

Expected: no output. Run `cloudflared tunnel login` again if you need to manage tunnels from the CLI later.

Then continue with step 14 above.
