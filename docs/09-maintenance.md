# 09. Maintenance

[Back to README](../README.md) | Previous: [08. Troubleshooting](08-troubleshooting.md)

Updates, secret rotation and backups.

## Update ProxmoxMCP-Plus to a new tag

Read the release notes first: <https://github.com/RekklesNA/ProxmoxMCP-Plus/releases>. Look for renamed or new tools, changed config keys, and anything about read-only mode. Note the new tag (`<NEW_TAG>`) and its commit hash from the release page.

**Step 1 [CT].** Go to the project folder.

```
cd /opt/pve-mcp
```

Expected: no output.

**Step 2 [CT].** Fetch the new tag.

```
git -C /opt/pve-mcp/ProxmoxMCP-Plus fetch --depth 1 origin tag <NEW_TAG>
```

Expected: a line like `* [new tag]  <NEW_TAG> -> <NEW_TAG>`.

**Step 3 [CT].** Check it out.

```
git -C /opt/pve-mcp/ProxmoxMCP-Plus checkout <NEW_TAG>
```

Expected: `HEAD is now at ...` and a detached HEAD notice.

**Step 4 [CT].** Verify the commit.

```
git -C /opt/pve-mcp/ProxmoxMCP-Plus rev-parse HEAD
```

Expected: the commit hash shown on the release page. Stop if it differs.

**Step 5 [CT].** Change the image tag in compose.yaml so old and new images are easy to tell apart (`image: proxmoxmcp-plus:<NEW_TAG>`).

```
nano /opt/pve-mcp/compose.yaml
```

Expected: the file saves without errors.

**Step 6 [CT].** Check that the read-only tool names still exist in the new code. This lists any allowlisted name that the source no longer mentions.

```
for t in $(grep '^MCP_TOOL_ALLOWLIST=' .env | cut -d= -f2 | tr ',' ' '); do grep -rqw "$t" ProxmoxMCP-Plus/src || echo "missing: $t"; done
```

Expected: no output. Any `missing:` line means a tool was renamed or removed. Edit `MCP_TOOL_ALLOWLIST` in `.env` before you start the new version, or startup fails.

**Step 7 [CT].** Build the new image and start it.

```
docker compose up -d --build
```

Expected: the build runs, then `Container pve-mcp  Started`.

**Step 8 [CT].** Repeat the local tests from [04, steps 21 to 24](04-proxmoxmcp-plus.md#part-4-build-start-test), then the public tests from [06, part 3](06-cloudflare-access.md#part-3-verify-both-layers).

**Step 9 [CT].** Remove old, unused images once the new one works.

```
docker image prune
```

Expected: a list of deleted images and the space reclaimed.

If the new version fails, check out the previous tag, set the old image tag in `compose.yaml`, and run `docker compose up -d` again.

## Update the container OS and base image

**Step 1 [CT].** Refresh the package lists.

```
apt update
```

Expected: a count of upgradable packages.

**Step 2 [CT].** Install updates (this includes Docker and cloudflared from their apt repos).

```
apt full-upgrade -y
```

Expected: ends without errors.

**Step 3 [CT].** Rebuild the image with a fresh base image, to pick up Python and Debian security fixes inside it.

```
docker compose --project-directory /opt/pve-mcp build --pull
```

Expected: the build finishes with the image name.

**Step 4 [CT].** Restart with the rebuilt image.

```
docker compose --project-directory /opt/pve-mcp up -d
```

Expected: `Container pve-mcp  Started` (or `Running` if nothing changed).

## Rotate secrets

Rotate when a secret may have leaked, when someone who had it leaves, or on a schedule.

### Proxmox API token

**Step 1 [NODE].** Remove the old token.

```
pveum user token remove mcp-ro@pve <TOKEN_NAME>
```

Expected: no output. The MCP server stops working until step 4.

**Step 2 [NODE].** Create a new token. Copy the `value` (the new `<TOKEN_SECRET>`).

```
pveum user token add mcp-ro@pve <TOKEN_NAME> --privsep 1 --comment "pve-mcp read-only"
```

Expected: a table with the new secret in the `value` row.

**Step 3 [NODE].** Give the new token the PVEAuditor role. Removing a token also removes its ACL entries.

```
pveum acl modify / --tokens 'mcp-ro@pve!<TOKEN_NAME>' --roles PVEAuditor
```

Expected: no output.

**Step 4 [CT].** Put the new secret in `token_value`.

```
nano /opt/pve-mcp/proxmox-config/config.json
```

Expected: the file saves. Ownership and mode stay the same when you edit with nano as root.

**Step 5 [CT].** Restart the server so it reads the new config.

```
docker compose --project-directory /opt/pve-mcp restart
```

Expected: `Container pve-mcp  Started`.

**Step 6 [NODE].** Confirm the permissions are still audit-only.

```
pveum user token permissions mcp-ro@pve <TOKEN_NAME>
```

Expected: only `*.Audit` privileges.

### MCP bearer key

**Step 1 [CT].** Write a new key into .env without showing it.

```
sed -i "s|^MCP_API_KEY=.*|MCP_API_KEY=$(openssl rand -hex 32)|" /opt/pve-mcp/.env
```

Expected: no output.

**Step 2 [CT].** Recreate the container. Changes to `.env` need a recreate, not just a restart.

```
docker compose --project-directory /opt/pve-mcp up -d --force-recreate
```

Expected: `Container pve-mcp  Started`.

**Step 3 [CT].** Show the new key once, to copy it into your password manager and the client config.

```
grep '^MCP_API_KEY=' /opt/pve-mcp/.env
```

Expected: `MCP_API_KEY=` followed by 64 hex characters. Clear the screen afterward (`clear`).

**Step 4 [WORKSTATION].** Update `PVE_MCP_API_KEY` in your MCP client config and restart the client.

### Cloudflare Access service token

Rotate without downtime by running both tokens for a short time.

**Step 1 [DASHBOARD].** Create a new service token ([06, part 1](06-cloudflare-access.md#part-1-create-the-service-token)). Use a new name, for example `<SERVICE_TOKEN_NAME>-2027`.

**Step 2 [DASHBOARD].** Open the Access application `<ACCESS_APP_NAME>` > Policies > the Service Auth policy. Add the new token as a second Include value. Save.

**Step 3 [WORKSTATION].** Update `PVE_MCP_CF_CLIENT_ID` and `PVE_MCP_CF_CLIENT_SECRET` in the client config, restart the client, and confirm it works.

**Step 4 [DASHBOARD].** Remove the old token from the policy. Save.

**Step 5 [DASHBOARD].** Delete the old service token under Service Tokens.

**Step 6 [WORKSTATION].** Confirm the old credentials are refused (use the old values).

```
 curl -sS -o /dev/null -w '%{http_code}\n' https://<MCP_HOSTNAME>/mcp -H 'CF-Access-Client-Id: <OLD_CF_ACCESS_CLIENT_ID>' -H 'CF-Access-Client-Secret: <OLD_CF_ACCESS_CLIENT_SECRET>'
```

Expected: `403`.

### Tunnel token

The tunnel token gives the power to run a connector for your tunnel. If it leaked, the simplest fix is a new tunnel: create it ([05, part 1](05-cloudflare-tunnel.md#part-1-create-the-tunnel)), run `cloudflared service uninstall` in the container, install the service with the new token, move the route to the new tunnel, and delete the old tunnel in the dashboard.

## Service token expiry alert

Service tokens expire (the test host used 1 year). When the token expires, the client gets `403` and stops working. Set an alert.

**Step 1 [DASHBOARD].** In the Cloudflare dashboard (account level, not Zero Trust), open Notifications (newer UI: Manage Account > Notifications) and click Add.

**Step 2 [DASHBOARD].** Choose the Access product and the "Expiring Access Service Token Alert" type.

**Step 3 [DASHBOARD].** Enter your email address and save.

Expected: the notification is listed. Cloudflare emails you before any service token in the account expires. Also put the expiry date in your own calendar.

## What to back up

The three config files hold everything specific to your setup. Two of them contain secrets. Store copies in a password manager or an encrypted backup, never in git.

| File (in the container) | Contains secrets | Notes |
|---|---|---|
| `/opt/pve-mcp/proxmox-config/config.json` | yes (Proxmox token secret) | owner uid 1000, mode 600 |
| `/opt/pve-mcp/.env` | yes (bearer key) | mode 600 |
| `/opt/pve-mcp/compose.yaml` | no | same as [files/compose.yaml](../files/compose.yaml) |
| `/opt/pve-mcp/proxmox-config/pve-root-ca.pem` | no | can be copied again from the node |
| `/etc/systemd/system/cloudflared.service` | yes (tunnel token) | recreated by `cloudflared service install` |

The `ProxmoxMCP-Plus` folder and the Docker image can be rebuilt from the pinned tag. The `proxmox-jobs` volume only holds the server's job history.

### Back up the whole container

A vzdump backup captures everything above in one file. It includes the secrets, so keep backups on storage you trust.

**Step 1 [NODE].** Back up the container while it runs.

```
vzdump <CTID> --storage <BACKUP_STORAGE> --mode snapshot --compress zstd
```

Expected: a task log that ends with `INFO: Finished Backup of VM <CTID>` and `INFO: Backup job finished successfully`. If the storage does not support snapshots, vzdump falls back to suspend mode and says so.

**Step 2 [NODE].** List the backups for the container.

```
pvesm list <BACKUP_STORAGE> --content backup --vmid <CTID>
```

Expected: one line per backup, with a `vzdump-lxc-<CTID>-...tar.zst` volume name.

For regular backups, add a job under Datacenter > Backup in the web UI instead of running vzdump by hand.

To restore, use the web UI (storage > Backups > Restore) or `pct restore <CTID> <BACKUP_VOLUME>` on the node. A restored container keeps its MAC address, so the DHCP reservation still applies.

## Health check

**Step 1 [CT].** Show container status.

```
docker compose --project-directory /opt/pve-mcp ps
```

Expected: `pve-mcp` with status `Up` and `127.0.0.1:8000->8000/tcp`.

**Step 2 [CT].** Show tunnel status.

```
systemctl is-active cloudflared
```

Expected: `active`.

**Step 3 [WORKSTATION].** Check that Access still blocks anonymous requests.

```
curl -sS -o /dev/null -w '%{http_code}\n' https://<MCP_HOSTNAME>/mcp
```

Expected: `403`.
