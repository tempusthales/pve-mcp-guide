# 01. Proxmox prerequisites

[Back to README](../README.md) | Next: [02. Create the LXC](02-create-lxc.md)

This part runs on the Proxmox host. It checks the LXC package version, creates a read-only API token, and confirms which certificate authority the MCP server must trust.

All steps here run in `[NODE]`: web UI > Datacenter > `<PVE_NODE>` > Shell. The prompt looks like `root@pve:~#`.

## Check the lxc-pve version

Docker inside an unprivileged LXC needs `lxc-pve` 6.0.5-2 or newer. Older versions fail with `open sysctl net.ipv4.ip_unprivileged_port_start ... permission denied` (an interaction between the runc fix for CVE-2025-52881 and AppArmor).

**Step 1 [NODE].** Show the installed lxc-pve and pve-manager versions.

```
pveversion -v | grep -E 'lxc-pve|pve-manager'
```

Expected: a line like `lxc-pve: 6.0.5-2` (or a higher version) and a `pve-manager` line.

If lxc-pve is older, upgrade the host first (Datacenter > `<PVE_NODE>` > Updates, or `apt update` then `apt full-upgrade` on the node) and reboot it if a new kernel was installed.

## Find the management bridge

You need to know which bridge carries the host's management IP. The container goes on that same bridge in [02](02-create-lxc.md).

**Step 2 [NODE].** Show the interface block that holds the management IP.

```
grep -B2 -A6 "<PVE_IP>" /etc/network/interfaces
```

Expected: a block like this.

```text
auto vmbr0
iface vmbr0 inet static
        address 192.0.2.10/24
        gateway 192.0.2.1
        bridge-ports eno1
        bridge-stp off
        bridge-fd 0
```

Write down the bridge name (`vmbr0` here) as `<MGMT_BRIDGE>` and the gateway as `<LAN_GATEWAY>`. If the address sits on a VLAN interface such as `vmbr0.20`, the container needs the same bridge and VLAN tag (`tag=20`).

## Create the read-only user and API token

The token gets the `PVEAuditor` role, which only contains `*.Audit` privileges. With privilege separation on, the token's effective rights are the intersection of the user's rights and the token's rights, so both need the role.

**Step 3 [NODE].** Check whether the user already exists.

```
pveum user list
```

Expected: a table of users. If `mcp-ro@pve` is listed, skip step 4.

**Step 4 [NODE].** Create the user in the Proxmox VE realm. It gets no password, so nobody can log in to the web UI with it.

```
pveum user add mcp-ro@pve --comment "MCP read-only"
```

Expected: no output.

**Step 5 [NODE].** Create the API token with privilege separation. The secret is shown only once.

```
pveum user token add mcp-ro@pve <TOKEN_NAME> --privsep 1 --comment "pve-mcp read-only"
```

Expected: a table with `full-tokenid` (`mcp-ro@pve!<TOKEN_NAME>`), `info` and `value`. The `value` row is the secret, a UUID like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. This is `<TOKEN_SECRET>`.

Keep this shell tab open until you paste the secret into `config.json` in [04](04-proxmoxmcp-plus.md), or store it in a password manager. Do not save it anywhere else. If you lose it, remove the token with `pveum user token remove mcp-ro@pve <TOKEN_NAME>` and create it again.

**Step 6 [NODE].** Give the user the PVEAuditor role on the whole tree.

```
pveum acl modify / --users mcp-ro@pve --roles PVEAuditor
```

Expected: no output.

**Step 7 [NODE].** Give the token the same role. The single quotes stop the shell from treating `!` as history expansion.

```
pveum acl modify / --tokens 'mcp-ro@pve!<TOKEN_NAME>' --roles PVEAuditor
```

Expected: no output.

**Step 8 [NODE].** Show the token's effective permissions.

```
pveum user token permissions mcp-ro@pve <TOKEN_NAME>
```

Expected: a table of paths (`/`, `/nodes/...`, `/vms/...`, `/storage/...` and so on). Every privilege listed ends in `.Audit`, for example `Sys.Audit`, `VM.Audit`, `Datastore.Audit`, `SDN.Audit`, `Pool.Audit`, `Mapping.Audit`. If you see anything else (such as `VM.PowerMgmt` or `Sys.Modify`), stop and fix the ACLs before going on.

## Check the API certificate

The MCP server verifies the Proxmox TLS certificate. It must trust the issuing CA, and the certificate must list the address you connect to.

**Step 9 [NODE].** List the certificate's Subject Alternative Names.

```
openssl x509 -in /etc/pve/local/pve-ssl.pem -noout -ext subjectAltName
```

Expected: a line like `IP Address:127.0.0.1, IP Address:0:0:0:0:0:0:0:1, DNS:localhost, IP Address:<PVE_IP>, DNS:<PVE_NODE>, DNS:<PVE_NODE>.<your-search-domain>`. It must contain `IP Address:<PVE_IP>`. If it does not, see [08. Troubleshooting](08-troubleshooting.md#certificate-san-does-not-list-the-host-ip).

**Step 10 [NODE].** Check whether a custom or ACME certificate is installed.

```
ls -l /etc/pve/local/pveproxy-ssl.pem
```

Expected: `No such file or directory`. That means the API uses the self-signed `pve-ssl.pem`, issued by the Proxmox root CA at `/etc/pve/pve-root-ca.pem`. You copy that CA into the container in [04](04-proxmoxmcp-plus.md).

If the file exists, the API serves that certificate instead and the Proxmox root CA does not apply. See [08](08-troubleshooting.md#custom-or-acme-certificate-on-the-proxmox-api) for the change you need.

Next: [02. Create the LXC](02-create-lxc.md)
