# Remote backend APIs — Hermes & OpenClaw

Authoritative reference for connecting qq-agent-bridge (or any 3rd-party tool)
to a remote Hermes or OpenClaw instance via HTTP. Both expose a "link + secret"
style endpoint, but the shapes are different.

## Hermes has TWO remote endpoints — pick the right one

Hermes exposes **two** independent remote-access platforms. Both go through
`gateway.platforms.*` in `~/.hermes/config.yaml`. Pick by what you need:

| Platform | Port (default) | Auth | Shape | Use when |
|----------|----------------|------|-------|----------|
| `api_server` | 8642 | Bearer `<extra.key>` | OpenAI `/v1/chat/completions` | You want a normal chat client — qab `hermes` backend, LangChain, any OpenAI-compatible tool |
| `webhook`    | 8644 | HMAC-SHA256 sig    | POST arbitrary JSON, prompt template renders `{dot.notation}` refs | You're triggering one-shot agent runs from CI / monitoring / GitHub events |

**For qq-agent-bridge use `api_server`** — it's a clean chat protocol and qab's
`hermes` backend talks to it directly. `webhook` is for event-driven triggers
where the caller is not a chat client.

## Hermes — `api_server` platform (OpenAI-compatible, recommended for chat clients)

### Endpoint shape
```
POST http://<host>:8642/v1/chat/completions
Authorization: Bearer <extra.key>
Content-Type: application/json

{ "model": "hermes-agent", "messages": [...], "temperature": 0.7 }
```

Also exposes `GET /v1/models` — qab WebUI's "测试连接" button hits this to
verify `base_url + api_key` without making a real chat call.

### Enable platform (one-time)
```yaml
# ~/.hermes/config.yaml
gateway:
  platforms:
    api_server:
      enabled: true              # ⚠️ MUST be true — defaults to false
      extra:
        host: 127.0.0.1          # 0.0.0.0 to expose; keep on loopback if possible
        port: 8642
        key: <your-api-key>      # callers pass as Bearer token
```

Then `systemctl restart hermes-gateway`. Verify with
`ss -tlnp | grep 8642` and `curl -s http://127.0.0.1:8642/v1/models -H "Authorization: Bearer <key>"`.

⚠️ **Two `platforms:` sections trap.** `~/.hermes/config.yaml` has both a
top-level `platforms: {}` AND a nested `gateway.platforms.*`. The platform
adapters (api_server, webhook, telegram, ...) live under `gateway.platforms`.
Putting `api_server` at the top level silently does nothing.

### Optional: per-session continuity
- Header `X-Hermes-Session-Id: <session-key>` keeps multi-turn context tied to
  a session across requests. qab passes its OneBot `(platform, chat, user)`
  session key here so each QQ conversation gets its own Hermes session.

---

## Hermes — `webhook` platform (HMAC, for event triggers)

### Endpoint shape
```
POST http://<host>:8644/webhooks/<route-name>
Content-Type: application/json
X-Hermes-Signature: sha256=<HMAC-SHA256 hex of raw body with route secret>

{ ...arbitrary JSON payload, referenced from prompt with {dot.notation} ... }
```

### Enable platform (one-time)
```yaml
# ~/.hermes/config.yaml
platforms:
  webhook:
    enabled: true
    extra:
      host: "0.0.0.0"
      port: 8644
      secret: "your-global-hmac-secret"   # used if route doesn't define its own
```

Or via env:
```bash
WEBHOOK_ENABLED=true
WEBHOOK_PORT=8644
WEBHOOK_SECRET=your-global-secret
```

### Create a route (per integration)
```bash
hermes webhook subscribe my-route \
  --prompt "User said: {message}" \
  --deliver log \
  --secret <per-route-secret>          # auto-generated if omitted
```

Flags:
- `--prompt` — template with `{dot.notation}` payload refs
- `--events` — comma-separated event types to accept
- `--deliver` — `log` / `telegram` / `discord` / `slack` / ...
- `--deliver-chat-id` — target chat for cross-platform delivery
- `--deliver-only` — skip agent, deliver rendered prompt verbatim (zero LLM cost)
- `--skills` — comma-separated skills to load for this run

### Manage
```bash
hermes webhook list                # all routes
hermes webhook test <name>         # send a test POST
hermes webhook remove <name>
```

### When platform isn't enabled
```
Webhook platform is not enabled. To set it up:
  1. hermes gateway setup
  2. Or add platforms.webhook.enabled: true to ~/.hermes/config.yaml
  3. Or set WEBHOOK_ENABLED=true in ~/.hermes/.env
```

---

## OpenClaw — OpenAI-compatible Chat Completions API

### Endpoint shape
```
POST http://<gateway-host>:<gateway-port>/v1/chat/completions
Authorization: Bearer <gateway-token>
Content-Type: application/json

{
  "model": "openclaw",                  // or "openclaw/<agentId>"
  "messages": [{"role":"user","content":"..."}],
  "temperature": 0.7
}
```

Also exposes:
- `GET /v1/models`
- `GET /v1/models/{id}`
- `POST /v1/embeddings`
- `POST /v1/responses`

### Enable (one-time)
```json5
// ~/.openclaw/config.json5
{
  gateway: {
    auth: { mode: "token", token: "<your-secret>" },
    http: {
      endpoints: {
        chatCompletions: { enabled: true },
      },
    },
  },
}
```

### Auth modes
| Mode | Use header |
|------|-----------|
| `token` | `Authorization: Bearer <gateway.auth.token>` (or env `OPENCLAW_GATEWAY_TOKEN`) |
| `password` | `Authorization: Bearer <gateway.auth.password>` (or env `OPENCLAW_GATEWAY_PASSWORD`) |
| `trusted-proxy` | route through identity-aware proxy; needs `trustedProxy.allowLoopback=true` for same-host |
| `none` | no auth — only on private ingress |

### Agent routing via `model` field
OpenClaw treats `model` as an **agent target**, not a provider model id:

- `model: "openclaw"` → default agent
- `model: "openclaw/default"` → default agent (explicit)
- `model: "openclaw/<agentId>"` → specific agent
- Aliases: `model: "openclaw:<id>"`, `model: "agent:<id>"`

### Override headers
- `x-openclaw-model: <provider/model>` — override backend model for selected agent
- `x-openclaw-agent-id: <agentId>` — compat agent override
- `x-openclaw-session-key: <key>` — control session routing
- `x-openclaw-message-channel: <channel>` — synthetic ingress channel context

### ⚠️ Security boundary
This endpoint is **full operator access**:
- Valid token = trusted operator credential, like an owner
- `token`/`password` modes restore the full default operator scope set
  (`operator.admin`, `operator.approvals`, `operator.pairing`, `operator.read`,
  `operator.talk.secrets`, `operator.write`) and ignore narrower `x-openclaw-scopes`
- `trusted-proxy` and `none` modes honor `x-openclaw-scopes` when present
- **Keep on loopback/tailnet/private ingress only** — do not expose publicly

### Pairing (DM access control) — separate from HTTP auth
OpenClaw also has "pairing" for QQ/Telegram/etc DM access (`openclaw pairing approve <channel> <CODE>`),
but that gates **inbound chat channels**, not the HTTP API.

---

## qq-agent-bridge integration patterns

As of qab commit `753c79a` (2026-05), qab ships **two dedicated remote
backends** that both speak OpenAI-compatible HTTP. No CLI backends, no local
binaries required.

```
src/qq_agent_bridge/backends/
  _openai_compat.py   # shared HTTP caller + health_check()
  hermes.py           # → http://host:8642/v1  (Hermes api_server)
  openclaw.py         # → http://host:PORT/v1  (OpenClaw gateway, auto-appends /v1)
```

### Backend selection in qab `config.yaml`
```yaml
backend: hermes      # or: openclaw
backends:
  hermes:
    base_url: http://your-hermes-host:8642/v1
    api_key: ${HERMES_API_KEY}        # = gateway.platforms.api_server.extra.key
    model: hermes-agent
    timeout: 120
  openclaw:
    base_url: http://your-openclaw-host:5757   # /v1 auto-appended
    api_key: ${OPENCLAW_TOKEN}                 # = gateway.auth.token
    model: openclaw                             # or openclaw/<agentId>
    timeout: 120
```

### Key differences between the two qab backends
| Aspect | `hermes.py` | `openclaw.py` |
|--------|-------------|---------------|
| Auto-append `/v1` | No (require explicit) | Yes (convenience) |
| Session header | `X-Hermes-Session-Id: <key>` | `x-openclaw-session-key: <key>` |
| Channel context | n/a | `x-openclaw-message-channel: qqbot` |
| Default system prompt | `"你是一个 QQ 助手。"` | `""` (OpenClaw agent has its own) |
| `test_connection()` static method | ✅ probes `/v1/models` | ✅ probes `/v1/models` |

Both backends subclass `Backend` (not each other). Shared HTTP code lives in
`_openai_compat.py::call_chat_completions()` and `health_check()`.

### WebUI "测试连接" integration
qab's WebUI POSTs `/webui/api/test-connection` with `{backend, base_url, api_key}`,
which calls `backend_class.test_connection(base_url, api_key)` — a static method
that probes `/v1/models`. Backends without `test_connection` get rejected by the
WebUI router. If you add a new backend, add the static method.

### Legacy pattern (DEPRECATED, kept for reference)
Earlier qab versions had an `openai` backend that worked for OpenClaw
out-of-the-box because OpenClaw is OpenAI-compatible. That still works for
arbitrary OpenAI providers (火山引擎方舟, DeepSeek, etc.) but for OpenClaw
specifically the dedicated `openclaw` backend gives you the auto-`/v1`,
channel header, and sane defaults.

---

## Docs sources

- Hermes: `hermes webhook --help`, `hermes webhook subscribe --help`
- OpenClaw catalog: `https://docs.openclaw.ai/llms.txt`
- OpenClaw OpenAI endpoint: `https://docs.openclaw.ai/gateway/openai-http-api.md`
- OpenClaw pairing: `https://docs.openclaw.ai/channels/pairing.md`
- OpenClaw webhooks (separate): `https://docs.openclaw.ai/cli/webhooks.md`
