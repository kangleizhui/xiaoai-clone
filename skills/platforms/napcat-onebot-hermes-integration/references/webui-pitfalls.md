# qq-agent-bridge WebUI pitfalls

Context: `qq-agent-bridge` (companion repo) ships an aiohttp WebUI bolted onto
the same port as the OneBot WS server (`/onebot/v11/ws` + `/webui` on one
shared app). When extending or debugging that WebUI, these two bugs are the
ones that already bit and got fixed in production — don't reintroduce them.

## Pitfall A — Hot-reload must rebuild ALL dependent state, not just `backend`

**Symptom:** User edits permissions (`allow_all`, `group_require_at`,
whitelists) or session config (`scope`, `timeout`) in the WebUI, clicks "热重载",
gets `{"ok": true}` back — but the bot still uses the old rules. Only a full
process restart picks up the new values.

**Root cause:** Early `_api_reload` only re-instantiated the `Backend` from
fresh config. The `PermissionChecker`, `SessionManager`, and the cached
`bridge.group_require_at` flag all kept their startup-time values, because
nothing told them to re-read config.

**Fix (already shipped in commit `59b790c`):**

```python
async def _api_reload(self, request):
    await self.bridge.backend.shutdown()
    from .backends import create_backend
    from .permissions import PermissionChecker
    from .session import SessionManager
    cfg = self.bridge.config
    self.bridge.backend = create_backend(cfg.get("backend", "openai"), cfg)
    await self.bridge.backend.start()
    self.bridge.perms = PermissionChecker(cfg.get("permissions", {}))
    self.bridge.group_require_at = self.bridge.perms.group_require_at
    self.bridge.sessions = SessionManager(
        scope=cfg.get("session", {}).get("scope", "per_chat"),
        timeout=cfg.get("session", {}).get("timeout", 1800),
        history_turns=cfg.get("session", {}).get("history_turns", 10),
    )
```

**General principle:** any "hot-reload" endpoint in a long-running service
must enumerate **every object built from config at startup** and rebuild each
one. Grep for places where the original `Bridge.__init__` (or equivalent
boot path) instantiates from `self.config[...]`. If it's in the constructor,
it needs to be in the reload path too. Cached scalar flags (like
`bridge.group_require_at = self.perms.group_require_at`) are easy to miss
and silently keep the old value — re-derive them.

## Pitfall B — Masked-secret round-trip wipes credentials on save

**Symptom:** WebUI displays `access_token: ***` and `api_key: ***` (masked
for safety). User clicks Save on the form (without touching those fields).
Next reload, OneBot fails auth (`unauthorized`) and the LLM backend errors
out, because the literal string `***` was written into config.yaml.

**Root cause:** `_masked_config` deep-copies the live config and replaces
secrets with `***` for display. The frontend round-trips that masked payload
back on Save. Naive save logic wrote the entire payload to disk, overwriting
real secrets with `***`.

**Fix (already shipped):**

1. `_masked_config` MUST use `copy.deepcopy` (not shallow copy) — otherwise
   masking the displayed copy mutates `bridge.config` in place, and the
   real secrets are gone before the user even touches Save.

2. `_api_save_config` must inspect every known secret field and, if the
   incoming value is `***`, replace it with the original value from
   `self.bridge.config` before writing to disk. Pattern:

   ```python
   SECRET_FIELDS = [
       ("onebot", "access_token"),
       ("backends", "openai", "api_key"),
       # ... add new secrets here as they appear
   ]
   for path in SECRET_FIELDS:
       new_val = _get_nested(new_cfg, path)
       if new_val == "***":
           _set_nested(new_cfg, path, _get_nested(self.bridge.config, path))
   ```

**General principle:** whenever a UI masks a field for display, the
*round-trip semantics* are part of the contract. Either (a) the frontend must
strip masked fields before POSTing, or (b) the backend must detect the
sentinel and preserve the original. Always do (b) defensively in addition to
(a), because frontends can change. The sentinel must be a value the real
secret can never equal (`***` is fine; empty string is dangerous because a
user might legitimately want to clear a field).

## Pitfall C — NapCat reverse-WS auth: token field, not Authorization header

The qq-agent-bridge WS endpoint authenticates incoming NapCat reverse
websockets via the `?access_token=` query string OR an `Authorization:
Bearer` header — but NapCat's `websocketClients` entry sends it as
`"token": "..."` in its config, which it translates into the
`Authorization` header. If your config.yaml `onebot.access_token` and
NapCat's `token` differ, connection drops silently with 401 in bridge logs
and "connection closed" in NapCat logs. First thing to check when
`onebot_connected: false` after adding a reverse-WS entry.

## Two-bot collision (NapCat broadcasts to ALL configured endpoints)

NapCat's `network` config is **additive**: every entry in `httpServers`,
`websocketServers`, `httpClients`, and `websocketClients` that's `enable:
true` receives a copy of every event. There is no routing or first-match —
it's a fan-out. If two different bot processes are listening on those
endpoints, both will reply to the same message.

**Common collision pattern** (the one this skill's user repeatedly hit):

1. `hermes-qq-bot` was installed first → registered `websocketServers :3001`
   (Hermes adapter dials in via `NAPCAT_WS_URL=ws://127.0.0.1:3001`).
2. Then `qq-agent-bridge` was added → wrote `websocketClients` reverse-WS to
   `ws://127.0.0.1:8080/onebot/v11/ws`.
3. Now every QQ message is delivered to **both** the Hermes adapter AND qab.
   Both backends generate a reply. User sees two responses (often one
   garbled, e.g. "无法连接到后端 8642" from qab + a normal answer from Hermes).

### Diagnosing

```bash
# Show every process holding an ESTABLISHED connection on NapCat's ports.
# Each line = one live consumer of NapCat events. >1 = collision.
ss -tnp | grep -E ":(3000|3001|8080)\b" | grep -v LISTEN
```

Read the NapCat config directly to confirm what's enabled:
```bash
NAPCAT_CFG=$(find /root/Napcat -name "onebot11_<QQ>.json" 2>/dev/null | head -1)
python3 -c "
import json
cfg = json.load(open('$NAPCAT_CFG'))
n = cfg['network']
for key in ('httpServers','websocketServers','httpClients','websocketClients'):
    for x in n.get(key, []):
        if x.get('enable'): print(f'{key:20s} {x.get(\"name\")} → {x.get(\"url\") or x.get(\"port\")}')"
```

### Distinguishing replies in chat

When the user is trying to verify which bot is responding (e.g. before
disabling one), patch each bot's `system_prompt` to prefix its replies:

```yaml
# qab config.test.yaml
backends:
  hermes:
    system_prompt: 你是 qab-test 实例（不是主实例），回复时开头说"[qab-test]"。
```

Hermes-qq-bot's main instance uses its own system prompt → no prefix. So
`[qab-test] 你好` vs `你好` makes the source obvious.

### Fixing

Pick ONE consumer per NapCat instance:

- **Want only qab**: edit the NapCat config, set the `websocketServers` entry
  to `enable: false`. Restart NapCat. Hermes adapter loses connection.
- **Want only hermes-qq-bot**: set `websocketClients` entry to `enable: false`.
  qab loses its inbound feed.
- **Want both selectively**: use distinct `permissions.allow_all` /
  `whitelist_users` / `whitelist_groups` per bot so each only answers
  non-overlapping scopes (e.g. one bot owns one group, the other owns DMs).

## Distinguishing "idle bot" from "broken bot"

WebUI's "实时消息流" stays empty for two very different reasons. Don't
confuse them:

| Symptom | `onebot_connected` | `session_count` | `messages` | Meaning |
|---------|--------------------|------------------|------------|---------|
| Stays empty, polling steady | `true` | `0` | `[]` | Bot is healthy, **no one sent a message yet**. Polling traffic is unrelated to message activity. |
| Stays empty, polling steady | `false` | `0` | `[]` | NapCat's `websocketClients` isn't connecting back — check token, URL, NapCat logs. |
| Receives msg → error reply | `true` | `>0` | non-empty | Bot is wired up but backend is broken (wrong `base_url`, dead service, bad key). Check `/api/test-connection` from WebUI. |

**Diagnostic snapshot script** for the impatient:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/webui/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
curl -s http://127.0.0.1:8080/webui/api/status -H "Authorization: Bearer $TOKEN"
echo
curl -s "http://127.0.0.1:8080/webui/api/messages?limit=5" -H "Authorization: Bearer $TOKEN"
```

If `onebot_connected: true` and `session_count: 0` after many minutes of you
staring at the WebUI, the truthful diagnosis is "nobody has talked to the
bot yet" — not "the bot is broken". WebUI poll traffic (visible in
`journalctl -u qab-test`) is just `/api/status` + `/api/messages` running
every 3s and is independent of inbound QQ events.
