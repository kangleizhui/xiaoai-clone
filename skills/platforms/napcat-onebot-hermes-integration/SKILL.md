---
name: napcat-onebot-hermes-integration
description: Integrate a real QQ account into Hermes via NapCatQQ + custom OneBot v11 plugin. Use when user wants Hermes to operate a real QQ号 (see actual QQ numbers, group numbers, distinguish users in groups). Covers NapCat install, OneBot config, plugin scaffolding, and the three pitfalls that took hours to find.
when_to_use:
  - User asks to "接入 QQ"/"对接 QQ"/"让 Hermes 上 QQ" with a real account
  - Existing Hermes qqbot platform doesn't fit (官方 QQ Bot API uses openid not real QQ#)
  - Need to read real QQ numbers, group numbers, distinguish users in a group
---

# NapCatQQ + Hermes Integration

End-to-end recipe to make Hermes operate a real QQ account.
**Key distinction:** Hermes' built-in `qqbot` adapter = official QQ Bot API
(openid only,审核制). This skill is for **NapCat** = NTQQ hook, real QQ#.

## Architecture

```
User QQ ──> 林知予 QQ (real account, NapCat-injected NTQQ)
              │
              ├── OneBot v11 HTTP :3000 (Hermes → NapCat for outbound)
              └── OneBot v11 WS  :3001 (NapCat → Hermes for inbound)
                                  │
                                  └─> Hermes napcat plugin adapter
```

## Step 1 — Install NapCat (Linux rootless)

```bash
cd /root && curl -o napcat.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh
bash napcat.sh --docker n --cli y --force   # ~3-5 min
```

Installs to `~/Napcat`. CLI `napcat` available globally.

## Step 2 — Launch & scan-login (one-time)

```bash
screen -dmS napcat bash -c "xvfb-run -a ~/Napcat/opt/QQ/qq --no-sandbox 2>&1 | tee /tmp/napcat.log"
sleep 8
# QR code appears in /tmp/napcat.log and at:
# ~/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png
# Scan with phone QQ to log in.
```

After login, find your QQ number: `ls ~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/ | grep onebot11_` → file is `onebot11_<QQ>.json`.

## Step 3 — Configure OneBot endpoints

Replace `~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_<QQ>.json`:

```json
{
  "network": {
    "httpServers": [{"name":"hermes-http","enable":true,"port":3000,"host":"127.0.0.1","enableCors":true,"enableWebsocket":false,"messagePostFormat":"array","token":"YOUR_TOKEN","debug":false}],
    "httpSseServers": [], "httpClients": [],
    "websocketServers": [{"name":"hermes-ws","enable":true,"host":"127.0.0.1","port":3001,"messagePostFormat":"array","reportSelfMessage":false,"token":"YOUR_TOKEN","enableForcePushEvent":true,"debug":false,"heartInterval":30000}],
    "websocketClients": [], "plugins": []
  },
  "musicSignUrl":"","enableLocalFile2Url":false,"parseMultMsg":false,"imageDownloadProxy":"",
  "timeout":{"baseTimeout":10000,"uploadSpeedKBps":256,"downloadSpeedKBps":256,"maxTimeout":1800000}
}
```

## Step 4 — ⚠️ PITFALL #1: NapCat MUST run as independent systemd service

If NapCat runs as child of hermes-gateway (e.g. via `terminal(background=true)`),
systemd will SIGKILL it whenever gateway restarts — its OneBot ports die →
Hermes adapter can't reconnect → silent failure.

Create `/etc/systemd/system/napcat.service`:

```ini
[Unit]
Description=NapCatQQ - QQ OneBot v11
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Napcat
ExecStart=/usr/bin/xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox -q YOUR_QQ_NUMBER
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/napcat.log
StandardError=append:/var/log/napcat.log
KillMode=control-group
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now napcat
ss -tlnp | grep -E ":3000|:3001"   # both should listen
```

## Step 5 — Write Hermes plugin

Create `~/.hermes/plugins/platforms/napcat/`:
- `plugin.yaml` — manifest with `requires_env: [NAPCAT_WS_URL, NAPCAT_HTTP_URL, NAPCAT_ACCESS_TOKEN]`
- `__init__.py` — `from .adapter import register`
- `adapter.py` — see `references/adapter.py` for complete reference implementation

Plugin structure follows `plugins/platforms/irc/` exactly. Key components:
- Subclass `BasePlatformAdapter`, set `platform = Platform("napcat")` (dynamic enum)
- `connect()` opens `aiohttp.ws_connect(ws_url)` with `Authorization: Bearer <token>`
- `_receive_loop()` reads JSON events, dispatches by `post_type` (meta_event / message / notice / request)
- For message events: distinguish `message_type` ∈ {"private", "group"} → build `SessionSource(chat_type="dm"|"group", user_id=<real QQ#>, chat_id=<peer QQ or group#>)`
- For sending: HTTP POST `{http_url}/send_private_msg` or `/send_group_msg` with OneBot v11 message segment array

## Step 6 — ⚠️ PITFALL #2: Cache chat_id → kind mapping

When base class calls `adapter.send(chat_id, content)`, it passes **only the
bare chat_id** (e.g. `"770967860"`). The adapter has no way to know if that's
a user QQ or a group # — naive code routes to `send_private_msg` and fails
with "无法获取用户信息" for group messages.

**Fix:** in adapter `__init__`, add `self._chat_kind_cache: Dict[str, str] = {}`.
In `_dispatch()` (called per inbound message), write
`self._chat_kind_cache[str(chat_id)] = "group" if chat_type=="group" else "user"`.
Add helper `_resolve_chat_kind(chat_id)` that checks (1) explicit prefix
`user:123`/`group:456`, (2) cache lookup, (3) fallback `("user", chat_id)`.
**Every** send_* method must use `_resolve_chat_kind`, never `_parse_chat_id`
directly on a bare ID.

## Step 7 — ⚠️ PITFALL #3: Plugin discovery path

Plugin must live under `~/.hermes/plugins/platforms/napcat/` (category-nested
2 levels deep — Hermes scanner handles this). Then:

```bash
hermes plugins list | grep napcat        # appears as "platforms/napcat"
hermes plugins enable platforms/napcat
```

`Platform("napcat")` only works AFTER plugin is loaded by gateway —
direct standalone `python -c 'Platform("napcat")'` fails with ValueError,
that's expected.

## Step 8 — Configure & restart

```bash
cat >> ~/.hermes/.env << 'EOF'
NAPCAT_WS_URL=ws://127.0.0.1:3001
NAPCAT_HTTP_URL=http://127.0.0.1:3000
NAPCAT_ACCESS_TOKEN=YOUR_TOKEN
NAPCAT_SELF_ID=YOUR_BOT_QQ
NAPCAT_ALLOWED_USERS=YOUR_OWNER_QQ
NAPCAT_ALLOWED_GROUPS=GROUP_QQ_NUM
NAPCAT_ALLOW_ALL_USERS=false
NAPCAT_GROUP_RESPOND_ONLY_AT_ME=true
NAPCAT_HOME_CHANNEL=user:YOUR_OWNER_QQ
EOF
```

⚠️ **Self-restart paradox & cgroup-inheritance trap.** Two related failure modes
when you're an agent running inside `hermes-gateway.service`:

1. **Direct self-restart**: `hermes gateway restart` or `systemctl restart hermes-gateway`
   from inside the gateway kills your own session mid-turn. Workaround:
   ```bash
   systemd-run --on-active=8s --unit=hg-restart systemctl restart hermes-gateway
   ```
   Your current turn finishes, restart fires 8s later.

2. **Cgroup inheritance kills child processes too**: when you spawn a subprocess
   via `terminal(background=true)`, `nohup`, or any shell mechanism inside the
   gateway, that subprocess joins `hermes-gateway.service`'s cgroup. The next
   gateway restart sends SIGKILL to **the entire cgroup** — your subprocess
   dies even if you never touched it. Symptoms: a test instance you started
   minutes ago is suddenly gone, journalctl shows
   `Killing process <pid> (python) with signal SIGKILL`.

   **Fix**: put long-lived child processes in their own systemd unit, not as
   children of your shell. Pattern used for qab test instances:
   ```bash
   sudo tee /etc/systemd/system/qab-test.service >/dev/null <<EOF
   [Unit]
   Description=qq-agent-bridge (test)
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/root/projects/qq-agent-bridge
   ExecStart=/root/projects/qq-agent-bridge/.venv/bin/python -m qq_agent_bridge config/config.test.yaml
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   EOF
   sudo systemctl daemon-reload && sudo systemctl enable --now qab-test
   ```
   Now `qab-test` is in its own cgroup and survives gateway restarts.

   The same rule applies to NapCat, Chromium-for-CDP, Xvfb, and any other
   long-lived support process you want to keep alive across agent restarts.

## Verification

```bash
tail -f ~/.hermes/logs/gateway.log | grep napcat
# Should show: "NapCat: connected to ws://127.0.0.1:3001 ... as QQ <id>"
# Then on inbound: "inbound message: platform=napcat user=<NAME> chat=<ID> msg='...'"
```

## Identity model (what the agent sees)

| Scenario | source.chat_id | source.chat_type | source.user_id | source.user_name |
|----------|---------------|------------------|----------------|------------------|
| DM       | peer QQ#      | "dm"             | peer QQ#       | nickname         |
| Group    | group #       | "group"          | sender QQ#     | group card / nickname |

Hermes' session store keys on `(platform, chat_id, user_id)` — multi-user
groups get independent conversation context per user automatically.

## Remote backends (link + secret)

qab routes QQ messages to a remote AI backend. As of qab `753c79a` (2026-05),
**both backends are remote-only, OpenAI-compatible HTTP**. No local CLI binary
needed on the qab host.

### Hermes remote — two endpoint options, pick by use case

| Endpoint | Port | Auth | qab backend | Use when |
|----------|------|------|-------------|----------|
| `api_server` platform | 8642 | Bearer `<extra.key>` | `hermes` | Chat clients (qab, LangChain, anything OpenAI-compatible). **Default choice.** |
| `webhook` platform    | 8644 | HMAC-SHA256          | n/a (no built-in qab backend) | Event triggers from CI, monitoring, GitHub. Prompt template renders `{dot.notation}` from POST body. |

Enable `api_server` (one-time on Hermes server):
```yaml
# ~/.hermes/config.yaml — note: gateway.platforms.*, NOT top-level platforms
gateway:
  platforms:
    api_server:
      enabled: true             # defaults to false
      extra:
        host: 0.0.0.0           # or 127.0.0.1 to keep on loopback
        port: 8642
        key: <your-api-key>
```

Restart `hermes-gateway` (mind the self-restart paradox above), verify:
```bash
ss -tlnp | grep 8642
curl -s http://127.0.0.1:8642/v1/models -H "Authorization: Bearer <key>"
```

qab `hermes` backend then connects with:
```yaml
backend: hermes
backends:
  hermes:
    base_url: http://hermes-host:8642/v1
    api_key: ${HERMES_API_KEY}     # the extra.key value
    model: hermes-agent
```

### OpenClaw remote → OpenAI-compatible API (Bearer token)

OpenClaw Gateway serves a standard OpenAI `/v1/chat/completions` endpoint.
qab `openclaw` backend speaks to it directly:

```yaml
backend: openclaw
backends:
  openclaw:
    base_url: http://openclaw-host:5757   # /v1 auto-appended
    api_key: ${OPENCLAW_TOKEN}            # = gateway.auth.token
    model: openclaw                        # or openclaw/<agentId>
```

Enable (one-time on OpenClaw server):
```json5
// ~/.openclaw/config.json5
{
  gateway: {
    auth: { mode: "token", token: "<your-secret>" },
    http: { endpoints: { chatCompletions: { enabled: true } } },
  }
}
```

The `model` field routes to agents: `openclaw` = default, `openclaw/<agentId>` = specific.
qab automatically passes `x-openclaw-message-channel: qqbot` and per-session
`x-openclaw-session-key` so OpenClaw can isolate sessions per QQ chat.

⚠️ **Security boundary** (both Hermes `api_server` and OpenClaw token modes):
a valid bearer = full operator access to that gateway. Keep on
loopback/tailnet/private ingress only.

### Reference files

- `references/remote-backend-api.md` — full endpoint specs for Hermes `api_server` + `webhook` + OpenClaw, qab code structure, auth tables

## Reference files

- `references/adapter.py` — complete 965-line adapter implementation
- `references/plugin.yaml` — manifest template
- `references/napcat.service` — systemd unit
- `references/onebot11_config.json` — OneBot config template
- `references/webui-pitfalls.md` — qq-agent-bridge WebUI: hot-reload-rebuilds-everything, masked-secret round-trip wipes credentials, NapCat multi-endpoint broadcast → two-bot collision (with `ss -tnp` diagnosis + per-bot system_prompt tagging trick), and the "idle vs broken" status-table for empty message flows

## Companion open-source projects

If the user just wants to deploy this end-to-end without re-running the build, two repos by kangleizhui already package everything:

| Repo | What it does | When to use |
|------|--------------|-------------|
| **github.com/kangleizhui/hermes-qq-bot** | NapCat install + Hermes plugin + systemd, one-command `install.sh`, ships with the exact adapter from this skill | User wants the "default Hermes-on-QQ" experience. Has `AGENTS.md` so the user can hand the URL to their own AI agent and it self-deploys. |
| **github.com/kangleizhui/qq-agent-bridge** | Standalone Python service that accepts NapCat OneBot v11 and routes to a remote AI gateway via OpenAI-compatible HTTP. Two backends shipped: `hermes` (→ Hermes `api_server` :8642) and `openclaw` (→ OpenClaw gateway). Both are link+secret only — no local CLI binary required on the qab host. Ships with a 5-tab WebUI (admin/admin default) for live config + 🔌 test-connection button. | User wants the QQ ↔ AI brain swap configurable from a web UI without editing YAML by hand, or wants qab and the AI agent on different machines. Sits behind hermes-qq-bot or any NapCat install. |

Both repos include `AGENTS.md` files that walk an AI deployment agent through setup — pointing the user at the repo URL with "tell your AI to read AGENTS.md" is usually faster than rebuilding from this skill.

For a **new deployment**, prefer the companion repos. For **debugging or extending** an existing install, this skill is the deeper reference.
