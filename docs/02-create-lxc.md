# 02. Create the LXC

[Back to README](../README.md) | Previous: [01. Proxmox prerequisites](01-proxmox-prereqs.md) | Next: [03. Docker](03-docker.md)

This part creates an unprivileged Debian 12 container, enables the features Docker needs, and puts it on the right network.

Proxmox recommends VMs for Docker workloads. Docker in an unprivileged LXC works with the features and lxc-pve version in this guide, and it uses far fewer resources. If you prefer a VM, docs 03 to 09 still apply. Only the `pct` commands change.

## Container settings used

| Setting | Value |
|---|---|
| CT ID | `<CTID>` (example `113`) |
| Hostname | `<CT_HOSTNAME>` (example `pve-mcp`) |
| Unprivileged | Yes |
| Template | `debian-12-standard` (tested with `debian-12-standard_12.2-1_amd64`) |
| Root disk | 32 GB |
| CPU | 1 core |
| Memory | 2048 MB |
| Swap | 1024 MB |
| Network | `<MGMT_BRIDGE>`, no VLAN tag (unless the host IP is on a VLAN), DHCP, firewall on |
| Features | `nesting=1,keyctl=1` |

2048 MB matters mostly during the image build. 1 core is enough, the build just takes longer (about 6 minutes on the test host).

## Download the template

**Step 1 [DASHBOARD].** In the Proxmox web UI, open Datacenter > `<PVE_NODE>` > `local` (or another storage that holds CT templates) > CT Templates > Templates.

**Step 2 [DASHBOARD].** Search for `debian-12-standard`, select the newest version listed, and click Download.

Expected: a task log that ends with `TASK OK`.

## Create the container

**Step 3 [DASHBOARD].** Click Create CT (top right).

**Step 4 [DASHBOARD].** General tab:

- Node: `<PVE_NODE>`
- CT ID: `<CTID>`
- Hostname: `<CT_HOSTNAME>`
- Unprivileged container: ticked
- Nesting: ticked (if the box is shown)
- Password: a strong root password (needed for the console login)
- SSH public key: load your workstation's public key file, for example `~/.ssh/id_ed25519.pub`

**Step 5 [DASHBOARD].** Template tab: pick the storage from step 1 and the `debian-12-standard` template.

**Step 6 [DASHBOARD].** Disks tab: root disk size `32` GB.

**Step 7 [DASHBOARD].** CPU tab: Cores `1`.

**Step 8 [DASHBOARD].** Memory tab: Memory `2048` MB, Swap `1024` MB.

**Step 9 [DASHBOARD].** Network tab:

- Name: `eth0`
- Bridge: `<MGMT_BRIDGE>` (the bridge you found in [01](01-proxmox-prereqs.md#find-the-management-bridge))
- VLAN Tag: empty, unless the host's management IP is on a VLAN
- Firewall: ticked
- IPv4: DHCP
- IPv6: your choice (SLAAC, DHCP or static)

Read [the network lesson](#network-lesson-same-bridge-as-the-host) below before you pick a different bridge or tag.

**Step 10 [DASHBOARD].** DNS tab: leave "use host settings".

**Step 11 [DASHBOARD].** Confirm tab: leave "Start after created" unticked, then click Finish.

Expected: a task log that ends with `TASK OK`.

## Enable features and start

**Step 12 [NODE].** Enable nesting and keyctl. Docker needs both in an unprivileged container.

```
pct set <CTID> --features nesting=1,keyctl=1
```

Expected: no output.

**Step 13 [NODE].** Confirm the features.

```
pct config <CTID> | grep features
```

Expected: `features: keyctl=1,nesting=1`.

**Step 14 [NODE].** Start the container.

```
pct start <CTID>
```

Expected: no output. The container shows a green running icon in the web UI.

**Step 15 [NODE].** Open a root shell in the container. This is the quickest way to get a `[CT]` shell.

```
pct enter <CTID>
```

Expected: the prompt changes to `root@pve-mcp:~#` (your `<CT_HOSTNAME>`). Type `exit` to go back to the node. The CT console in the web UI (`<CTID>` > Console, log in as root) works too.

## Update the template

The template can be months old. Update it before installing anything.

**Step 16 [CT].** Refresh the package lists.

```
apt update
```

Expected: ends with a line like `NN packages can be upgraded` or `All packages are up to date`.

**Step 17 [CT].** Install all updates.

```
apt full-upgrade -y
```

Expected: ends without errors. If a prompt asks about a changed config file, keep the installed version (the default).

## Find the container's IP

**Step 18 [NODE].** Show the container's IPv4 address.

```
pct exec <CTID> -- ip -4 -brief addr show eth0
```

Expected: a line like `eth0@if12  UP  192.0.2.50/24`. The address is `<CT_IP>`.

Optional, if you want to see which LAN addresses are in use (for example to pick a static address outside the DHCP pool, or to spot the new container), run a ping scan from your workstation. Install nmap first if needed.

**Step 19 [WORKSTATION].** Ping scan the LAN.

```
nmap -sn <LAN_SUBNET>
```

Expected: one `Nmap scan report for ...` line per live host, then `Nmap done: 256 IP addresses (NN hosts up)`. Addresses not listed did not answer. That does not prove they are free (some hosts drop pings), so check your router's DHCP leases too.

## Check that the container reaches the Proxmox API

**Step 20 [CT].** Request the Proxmox web UI port and print only the HTTP status. `-k` skips certificate checks for this test only.

```
curl -sk -o /dev/null -w "%{http_code}\n" https://<PVE_IP>:8006
```

Expected: `200`.

If you get `000`, the container cannot reach the host. Read the next section.

## Network lesson: same bridge as the host

What happened on the test host: the container was first put on a VLAN-tagged bridge (a separate `vmbr1` with VLAN tag 2, on a different subnet) while the Proxmox management IP lived on `vmbr0` in another subnet. From the container, `curl` to `https://<PVE_IP>:8006` returned `000` and `ping` showed 100% packet loss. The VLAN had no route to the management subnet.

The fix was to move the container to the same bridge as the host's management IP, untagged, on DHCP.

You could instead allow routing between the VLANs on your router and firewall. That is more work and more to get wrong, so this guide uses the same bridge.

**Step 21 [NODE].** Show the container's current network setting.

```
pct config <CTID> | grep net0
```

Expected: a line like `net0: name=eth0,bridge=vmbr1,firewall=1,hwaddr=...,ip=dhcp,tag=2,type=veth`. If `bridge` is already `<MGMT_BRIDGE>` and there is no `tag=` (or the tag matches the host's VLAN), your network setting is fine. Look elsewhere (host firewall, wrong `<PVE_IP>`).

**Step 22 [NODE].** Move the container to the management bridge with DHCP and no tag.

```
pct set <CTID> --net0 name=eth0,bridge=<MGMT_BRIDGE>,ip=dhcp,firewall=1
```

Expected: no output. Because the command does not pass `hwaddr=`, Proxmox gives the interface a new MAC address. Create the DHCP reservation (below) after this step, not before.

**Step 23 [NODE].** Reboot the container so it picks up the new network.

```
pct reboot <CTID>
```

Expected: no output. The container comes back in a few seconds.

**Step 24 [NODE].** Show the new address.

```
pct exec <CTID> -- ip -4 -brief addr show eth0
```

Expected: an address in `<LAN_SUBNET>`. This is your `<CT_IP>`.

**Step 25 [CT].** Run the API test again.

```
curl -sk -o /dev/null -w "%{http_code}\n" https://<PVE_IP>:8006
```

Expected: `200`.

## Reserve the address in DHCP

The container's IP should not change. Reserve it in your router so it always gets `<CT_IP>`.

**Step 26 [DASHBOARD].** In your router, find the DHCP client for `<CT_HOSTNAME>` (match it by hostname or by the MAC address shown in `pct config <CTID> | grep net0`) and set a fixed IP (also called a DHCP reservation or static lease).

UniFi example: open the UniFi Network application of your gateway, then Client Devices > select the container > Settings > Fixed IP Address, enter `<CT_IP>`, and apply. The UniFi Site Manager device list shows only UniFi devices, not clients, so open the gateway's Network application to find this setting.

**Step 27 [NODE].** If you picked a different address than the one the container has now, reboot it so it renews the lease.

```
pct reboot <CTID>
```

Expected: after the reboot, `pct exec <CTID> -- ip -4 -brief addr show eth0` shows `<CT_IP>`.

Next: [03. Docker](03-docker.md)
