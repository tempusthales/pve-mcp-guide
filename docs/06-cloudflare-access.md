# 06. Cloudflare Access

[Back to README](../README.md) | Previous: [05. Cloudflare Tunnel](05-cloudflare-tunnel.md) | Next: [07. Connect a client](07-connect-client.md)

This part puts Cloudflare Access in front of `https://<MCP_HOSTNAME>`. Only requests that carry a valid service token get through. There is no browser login, so no person can reach the server through the hostname.

Cloudflare renames Zero Trust menus from time to time. Both the older and newer names are given where they are known to differ.

## Part 1: Create the service token

**Step 1 [DASHBOARD].** Open Zero Trust > Access controls > Service credentials > Service Tokens (older UI: Access > Service Auth > Service Tokens).

**Step 2 [DASHBOARD].** Click Create Service Token.

**Step 3 [DASHBOARD].** Name it `<SERVICE_TOKEN_NAME>` and choose a duration. The test host used 1 year. Click Generate token.

**Step 4 [DASHBOARD].** Copy the Client ID (`<CF_ACCESS_CLIENT_ID>`) and Client Secret (`<CF_ACCESS_CLIENT_SECRET>`) into your password manager. The Client Secret is shown only once. If you lose it, create a new token.

Expected: the token appears in the list with its expiry date. Set an expiry reminder now ([09](09-maintenance.md#service-token-expiry-alert)).

## Part 2: Create the Access application

**Step 5 [DASHBOARD].** Open Zero Trust > Access controls > Applications (older UI: Access > Applications) and click Add an application.

**Step 6 [DASHBOARD].** Choose Self-hosted and private (older UI: Self-hosted).

**Step 7 [DASHBOARD].** Add a public hostname: subdomain from `<MCP_HOSTNAME>`, domain `<DOMAIN>`, path empty.

**Step 8 [DASHBOARD].** Under policies, click Create new policy and set:

| Field | Value |
|---|---|
| Policy name | `<SERVICE_TOKEN_NAME>` (any name works) |
| Action | `Service Auth` |
| Include, Selector | `Service Token` |
| Include, Value | `<SERVICE_TOKEN_NAME>` |

The Action must be Service Auth. With Allow, Access expects a logged-in person and redirects requests to a login page, so the service token alone does not get through.

Save the policy. In older UIs the policy is created inside the application wizard. In newer UIs it may open in a new tab. Go back to the application tab, refresh the policy list and select it.

**Step 9 [DASHBOARD].** Make sure the application has only this one policy. Add no Allow, email or "Everyone" policies.

**Step 10 [DASHBOARD].** Name the application `<ACCESS_APP_NAME>`. Leave login methods and other settings at their defaults. Click through to the end and click Create (or Save).

Expected: the application appears in the list with the domain `<MCP_HOSTNAME>`.

## Part 3: Verify both layers

Run these from your workstation in bash. Commands with secrets start with a space to stay out of history. Run `export HISTCONTROL=ignoreboth` first if your shell does not already set it. In fish, a leading space also skips history, and `fish --private` starts a session that saves nothing.

**Step 11 [WORKSTATION].** No credentials at all.

```
curl -sS -o /dev/null -w '%{http_code}\n' https://<MCP_HOSTNAME>/mcp
```

Expected: `403`. Access blocked the request before it reached your network. If you get `302`, a policy uses Allow instead of Service Auth. If you get `401`, the Access application does not cover this hostname yet (changes can take a minute).

**Step 12 [WORKSTATION].** Service token headers, no bearer key.

```
 curl -sS -i https://<MCP_HOSTNAME>/mcp -H 'CF-Access-Client-Id: <CF_ACCESS_CLIENT_ID>' -H 'CF-Access-Client-Secret: <CF_ACCESS_CLIENT_SECRET>'
```

Expected: `HTTP/2 401` with `www-authenticate: Bearer` and `{"detail":"Unauthorized"}`. This 401 comes from ProxmoxMCP-Plus, which proves Access let the request through and the server still demands its own key.

**Step 13 [WORKSTATION].** All three headers and an MCP `initialize` request.

```
 curl -sS -i -X POST https://<MCP_HOSTNAME>/mcp -H 'CF-Access-Client-Id: <CF_ACCESS_CLIENT_ID>' -H 'CF-Access-Client-Secret: <CF_ACCESS_CLIENT_SECRET>' -H 'Authorization: Bearer <MCP_API_KEY>' -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Expected: `HTTP/2 200` and a body that contains `"serverInfo":{"name":"ProxmoxMCP"`.

You need `<MCP_API_KEY>` on the workstation for this step and for the client. To read it, run `grep '^MCP_API_KEY=' /opt/pve-mcp/.env` in `[CT]` and copy the value straight into your password manager. That is the only time it needs to show on screen.

Summary:

| Headers sent | Expected | Who answered |
|---|---|---|
| none | `403` | Cloudflare Access |
| CF-Access-Client-Id and Secret | `401` | ProxmoxMCP-Plus (bearer check) |
| CF-Access headers and Bearer key | `200` | ProxmoxMCP-Plus (MCP response) |

Next: [07. Connect a client](07-connect-client.md)
