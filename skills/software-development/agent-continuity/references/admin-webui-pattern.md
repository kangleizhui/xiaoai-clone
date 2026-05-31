# Admin WebUI Pattern for Self-Hosted Projects

When a self-hosted project (bridge, bot, server) ships a WebUI, the UI must be **end-to-end actionable** — a new user should be able to complete full onboarding through the browser without ever editing `config.yaml`. This reference covers the architecture, pitfalls, and implementation patterns extracted from `qq-agent-bridge`.

## Why "actionable" matters

A read-only dashboard (status cards, log stream, config viewer) is **decoration**. The user's first thought is always "how do I make this thing work?" — if they have to SSH in and edit YAML, the WebUI has failed its primary purpose. The actionable surface (forms + save + apply) must ship before or alongside observability.

User feedback that drove this: "你写的这个没有按钮啊 肯定需要几个功能呀 用户 部署这个项目 然后 添加自己的 爱马仕或者龙虾 就对接上"

## Tab layout (5-tab minimum)

| Tab | Purpose | Key interactive elements |
|-----|---------|--------------------------|
| 📊 概览 (Overview) | Status cards + message stream + test send bar | Read-heavy but test bar is the "smoke test" CTA |
| ⚡ 后端配置 (Backend) | Backend type selector + type-specific fields + save | Dropdown switches form fields; **save triggers apply** |
| 🔗 连接配置 (Connection) | Upstream protocol settings + one-click snippet generation | "Generate NapCat config" + copy button = zero-friction onboarding |
| 🔦 权限管理 (Permissions) | Owner / whitelist / blacklist + toggle switches | Simple comma-separated inputs; toggles for `allow_all` / `group_require_at` |
| 💬 会话 (Sessions) | Active session list + per-session reset | Minimal but necessary for debugging |

## Architecture: single aiohttp app, dual-mount

Both the protocol server (e.g. OneBot WS) and the WebUI HTTP routes share **one `aiohttp.Application`** on **one port**, differentiated by path prefix. This avoids port conflicts and simplifies firewall rules.

```python
# In Bridge.__init__
self.app = web.Application()

# In Bridge.start()
self.app.router.add_get("/onebot/v11/ws", self.onebot._handle_ws)
self.webui.attach(self.app, prefix="/webui")

self._runner = web.AppRunner(self.app)
await self._runner.setup()
site = web.TCPSite(self._runner, host, port)
await site.start()
```

Key: OneBotServer no longer creates its own app/runner. Bridge owns the lifecycle.

## The masked-field roundtrip rule

Config APIs return masked secrets (`***`) to the frontend. When the user saves a form without changing the secret, the frontend sends back `***`. The save handler MUST NOT overwrite the real secret with `***`.

```python
# WRONG — if payload has api_key: "***", this overwrites the real key
current["backends"][bname] = payload["config"]

# CORRECT — compare and preserve
new_backend = payload.get("config", old_backend)
if new_backend.get("api_key") == "***" and old_backend.get("api_key"):
    new_backend["api_key"] = old_backend["api_key"]
current["backends"][bname] = new_backend
```

This applies to: `api_key`, `access_token`, any password field. Use `copy.deepcopy` before masking for GET responses — never mutate `bridge.config` in-place.

## The 3 apply modes

After saving config, present the user with 3 options (not just one):

| Mode | What it does | When to use |
|------|--------------|-------------|
| 🔄 Hot reload | Rebuild backend + perms + sessions in-process; OneBot WS stays up | Changed backend type, API key, or permissions |
| ♻ Restart process | `os._exit(0)`; systemd auto-restarts | Changed OneBot port/path or anything else hot-reload can't cover |
| Later | Dismiss the banner; user will restart manually | Non-urgent changes; user is mid-testing |

### Critical pitfall: hot reload must rebuild ALL config-dependent objects

Initial implementation only rebuilt the `Backend` instance. But `PermissionChecker` and `SessionManager` also read from `bridge.config` at init time. After saving new permissions, the in-memory `bridge.perms` still had the old rules.

**Fix**: hot reload must rebuild backend + perms + sessions:

```python
async def _api_reload(self, request):
    await self.bridge.backend.shutdown()
    cfg = self.bridge.config
    self.bridge.backend = create_backend(cfg["backend"], cfg)
    await self.bridge.backend.start()
    self.bridge.perms = PermissionChecker(cfg.get("permissions", {}))
    self.bridge.group_require_at = self.bridge.perms.group_require_at
    self.bridge.sessions = SessionManager(...)
```

## One-click snippet generation

For projects that bridge to an upstream (NapCat, Slack, Discord), generate the **exact JSON snippet** the user needs to paste into the upstream's config. This eliminates the #1 onboarding friction: "which URL do I put where?"

```python
async def _api_napcat_snippet(self, request):
    cfg = self.bridge.config.get("onebot", {})
    snippet = {
        "name": "to-qq-agent-bridge",
        "enable": True,
        "url": f"ws://{cfg['ws_host']}:{cfg['ws_port']}{cfg['ws_path']}",
        "token": cfg.get("access_token", ""),
        ...
    }
    return web.json_response({"snippet": snippet})
```

**Important**: Read token from `bridge.config` directly (not from the masked config API) — the snippet MUST contain the real token so the user can copy-paste it into NapCat.

Frontend: JSON in a `<pre>` block + a "复制" button (`navigator.clipboard.writeText()`).

## Frontend: single-file SPA (Tailwind CDN + Alpine.js)

One `index.html` file, no build step. Alpine.js for reactivity, Tailwind CDN for styling. Trade-off: slower initial load (CDN fetch), but zero deployment complexity. For self-hosted tools this is the right trade-off.

Key Alpine patterns:
- `x-data="app()"` with `x-init="init()"` for the main data store
- `localStorage` for auth token persistence across reloads
- `setInterval` for polling (3s for status/messages, 30s for config)
- Tab switching via `@click="tab='backend'"` + `x-show="tab==='backend'"`

## Minimal auth

In-memory token map with 24h expiry. Cookie + Bearer header both accepted. Default `admin/admin` for fast onboarding — user can change in `config.yaml` after first login.

```python
def _check_token(self, request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = request.cookies.get("qab_token", "")
    exp = self._tokens.get(token)
    return exp and exp > time.time()
```

## Failure modes

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| Save config → hot reload → permissions still old | Only rebuilt backend, not perms | Hot reload must rebuild ALL config-dependent objects (backend + perms + sessions) |
| NapCat snippet shows `***` for token | Read from masked config or bridge.config was mutated earlier | Read from `self.bridge.config` directly (unmasked); ensure GET /api/config uses deepcopy before masking |
| Save onebot config → access_token becomes `***` in YAML | Save handler overwrites real token with masked value from form | Compare incoming value to `***`; if masked, preserve original from file |
| Multiple bots reply to same group message | NapCat `websocketServers` + `websocketClients` both deliver events | This is expected when running bridge alongside another bot; use different QQ accounts or disable one |
| API key not working after save | Same masked-field roundtrip bug as access_token | Apply the same compare-and-preserve pattern for all secret fields |
