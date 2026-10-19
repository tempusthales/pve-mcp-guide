# 03. Docker

[Back to README](../README.md) | Previous: [02. Create the LXC](02-create-lxc.md) | Next: [04. ProxmoxMCP-Plus](04-proxmoxmcp-plus.md)

This part installs Docker Engine and the Compose plugin inside the container with Docker's official convenience script.

All steps run in `[CT]`. Open the shell from the node with `pct enter <CTID>`. The prompt looks like `root@pve-mcp:~#`.

**Step 1 [CT].** Install the basic tools used in the rest of this guide.

```
apt install -y ca-certificates curl git nano openssl
```

Expected: ends without errors. Some packages may already be installed.

**Step 2 [CT].** Download Docker's convenience script. This only downloads it.

```
curl -fsSL https://get.docker.com -o /root/get-docker.sh
```

Expected: no output.

**Step 3 [CT].** Optional: preview what the script will do. Nothing changes.

```
sh /root/get-docker.sh --dry-run
```

Expected: a list of the commands the script would run (adding Docker's apt repo and installing `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`).

**Step 4 [CT].** Install Docker Engine and the Compose plugin.

```
sh /root/get-docker.sh
```

Expected: ends with a client and server version block and a note about rootless mode. You can ignore the rootless note. This guide runs Docker as root inside an unprivileged container, which maps to an unprivileged user on the host.

**Step 5 [CT].** Run the test image.

```
docker run --rm hello-world
```

Expected: a message that starts with `Hello from Docker!`.

If it fails:

- `open sysctl net.ipv4.ip_unprivileged_port_start ... permission denied`: lxc-pve is too old. See [01](01-proxmox-prereqs.md#check-the-lxc-pve-version).
- keyring, overlay or cgroup errors: check the features from [02](02-create-lxc.md#enable-features-and-start). On the node, `pct config <CTID> | grep features` must print `features: keyctl=1,nesting=1`.

**Step 6 [CT].** Confirm Compose v2 is installed.

```
docker compose version
```

Expected: `Docker Compose version v2.x.x`.

**Step 7 [CT].** Confirm Docker starts at boot.

```
systemctl is-enabled docker
```

Expected: `enabled`.

Next: [04. ProxmoxMCP-Plus](04-proxmoxmcp-plus.md)
