# Multi-Backend Bridge Pattern

A variant of the agent-installable project where the goal is **a service that connects one upstream (an IM platform, a webhook source, a workflow trigger) to N possible AI/agent backends, switchable by config**. Extracted from `qq-agent-bridge` (https://github.com/kangleizhui/qq-agent-bridge).

## When to use this pattern

- The upstream protocol is fixed (OneBot v11, Slack Events API, Discord, IRC, email — pick one) but the user wants to swap brains: today Hermes, tomorrow Claude Code, next week OpenAI.
- Multiple agent CLIs already work standalone; you want to expose all of them through one server without forking it per backend.
- The same project should run for the user with `openai`-compatible HTTP for low cost AND with a real agent CLI for full tool use.

## Architecture (the contract that makes this work)

```
upstream (NapCat / Slack / IRC / …)
       │  one well-defined protocol
       ▼
┌───────────────────────────┐
│   bridge (FastAPI/aiohttp)│
│   ┌────────────────────┐  │
│   │ Router             │  │   normalize event → ChatContext
│   │ Permissions        │  │
│   │ SessionManager     │  │   key = scope(per_user|per_group|per_chat)
│   └────────────────────┘  │
└──────────┬────────────────┘
           │ Backend ABC
   ┌───────┼───────┬────────────┐
   ▼       ▼       ▼            ▼
 HTTP    PTY-1   PTY-2        PTY-N
 (openai)(hermes)(openclaude) (claude-code)
```

### Two non-negotiable abstractions

```python
# 1. Inputs that survive cross-backend swap
@dataclass
class ChatContext:
    user_id: str
    chat_id: str
    chat_kind: str          # "user" | "group"
    user_nickname: str = ""
    session_key: str = ""   # filled by SessionManager
    history: list = field(default_factory=list)  # OpenAI-format for stateless backends

# 2. Single interface every backend implements
class Backend(ABC):
    name: str
    async def start(self) -> None: ...
    async def ask(self, message: str, ctx: ChatContext) -> AgentResponse: ...
    async def reset_session(self, ctx: ChatContext) -> None: ...
    async def shutdown(self) -> None: ...
```

If a new backend can't fit `ask(message, ctx) -> response`, the contract is wrong, not the backend. Bend the abstraction (e.g. add streaming) once and only once.

## The two backend families

### Family A: HTTP API backends (openai-compatible)

Trivial — just `httpx.AsyncClient` calling `/chat/completions`. Notes:

- **Bring your own history**: HTTP backends are stateless, so `SessionManager` keeps OpenAI-format `[{role, content}, …]` and re-sends every turn. CLI backends ignore this (they manage their own context inside the subprocess).
- **`${ENV_VAR}` substitution**: never put API keys in the config file. Read `api_key: "${OPENAI_API_KEY}"` and expand at load time so the user can keep secrets in `.env`.
- **Same code path covers DeepSeek / 火山 / Moonshot / Together / Groq** — they all speak OpenAI dialect. Document `base_url` examples for each in the config template.

### Family B: CLI subprocess backends (hermes / openclaude / claude-code)

These are the hard ones. Patterns that survived contact with reality:

- **One subprocess per session_key** — agent CLIs keep context in-process; one shared subprocess for all users would entangle their conversations.
- **PTY, not pipes** — most agent CLIs detect non-TTY stdin and fall back to a non-interactive single-shot mode (or refuse to run). Use `pty.openpty()` and pass the slave fd as the child's stdin/stdout/stderr.
- **Strip ANSI** — agent CLIs paint colored prompts; the response you forward to the IM platform must be plain text. `re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)`.
- **Echo suppression** — PTY mode echoes back what you wrote to stdin. The first line of the response usually contains your own prompt — drop it before forwarding.
- **End-of-response heuristic is hard** — agent CLIs don't emit a clean terminator. Working approach: read until ~2 seconds of stdin silence, then trim trailing prompt markers (`> `, `❯ `, `? `). This is brittle; document it as such.
- **Concurrency lock per subprocess** — even within one session, two messages arriving 500ms apart will interleave responses in the PTY. Use `asyncio.Lock()` on each session.
- **First request is slow** — agent CLIs take 5-15s to boot. Either pre-warm on bridge start or warn the user the first reply lags.

### What NOT to abstract

Resist the urge to model "stream vs non-stream" or "tool calls vs text" inside `Backend`. CLI agents already serialize tool use into their own output stream; the bridge just forwards the final text. Trying to surface structured tool calls cross-backend means inventing a fourth protocol that nobody implements correctly.

## Config-as-switch — the user-visible payoff

```yaml
backend: "hermes"     # one line. change to "openai" / "claude-code" / "openclaude".

backends:
  hermes:
    binary: "hermes"
    workdir: "~/qq-agent-workspace"
  openai:
    base_url: "https://api.deepseek.com/v1"
    api_key: "${OPENAI_API_KEY}"
    model: "deepseek-chat"
  # … only the selected backend is instantiated; others are inert.
```

Whoever onboards via your `AGENTS.md` (see umbrella skill) should be asked one question — "which backend?" — and the deploy script writes that one line into `config.yaml`. No matrix of N install scripts.

## Smoke test before shipping

Always end the build with a single end-to-end async test the agent can run unattended:

```python
import asyncio, yaml
from <pkg>.backends import create_backend
from <pkg>.backends.base import ChatContext

async def smoke():
    cfg = yaml.safe_load(open("config/config.yaml"))
    b = create_backend(cfg["backend"], cfg)
    await b.start()
    ctx = ChatContext(user_id="t", chat_id="t", chat_kind="user", session_key="t")
    r = await b.ask("ping", ctx)
    assert r.text and not r.error, r.error
    print("OK:", r.text[:80])
    await b.shutdown()

asyncio.run(smoke())
```

If this passes, the upstream→bridge→backend round-trip is wired correctly. If it fails, you know the bug is below the OneBot layer, not above it.

## File layout that scales

```
<project>/
├── src/<pkg>/
│   ├── __main__.py            # bridge bootstrap, signal handlers
│   ├── <upstream>.py          # protocol server (e.g. onebot.py)
│   ├── session.py             # SessionManager
│   ├── permissions.py         # whitelist/blacklist
│   └── backends/
│       ├── base.py            # Backend ABC + ChatContext + AgentResponse
│       ├── __init__.py        # create_backend() registry
│       ├── openai_backend.py
│       └── cli_backend.py     # one file is enough for hermes/openclaude/claude-code via subclassing
├── config/config.example.yaml
├── AGENTS.md                  # see umbrella skill
└── README.md                  # see umbrella skill (three-tier entry)
```

One file per backend family, not per backend product — the CLI family is one base class with three trivial subclasses that differ only in `binary` and `default_args`.

## Failure modes that bit during development

| Symptom | Root cause | Fix |
|---|---|---|
| CLI backend hangs forever on first ask | No PTY — child detected non-TTY stdin and is waiting for headers/escape codes that will never come | Use `pty.openpty()`, pass slave fd to subprocess |
| Replies contain `^[[32m> ^[[0m` | ANSI not stripped | `ANSI_RE.sub("", text)` before forwarding |
| Two concurrent group messages get interleaved replies | Same session_key, no per-session lock | `asyncio.Lock()` on each `CLISession` |
| OpenAI backend works in dev, returns 401 in prod | `${API_KEY}` env var not exported in systemd unit | Add `Environment=OPENAI_API_KEY=…` or `EnvironmentFile=` to the unit |
| Group chats don't isolate users | `session.scope` set to `per_group` | Use `per_chat` (default) — per-user even within groups |
| Save permissions in WebUI → hot reload → permissions still old | Hot reload only rebuilt backend, not `PermissionChecker` or `SessionManager` | Hot reload must rebuild ALL config-dependent objects (backend + perms + sessions) |
| NapCat snippet shows `***` for token | Read from masked config API, or `bridge.config` was mutated by a prior save call that overwrote with `***` | Read from `self.bridge.config` directly (unmasked); ensure save handler preserves real secrets when form sends `***` |
| Multiple bots reply to same group message | NapCat `websocketServers` (hermes gateway) + `websocketClients` (bridge) both deliver the same events | Expected when running alongside another bot; disable one or use separate QQ accounts |
| WebUI config save turns `api_key` into `***` in YAML | Save handler replaces entire config block with the masked form values | Compare incoming value to `***`; if masked, preserve the original from the file |

## Companion to the umbrella

This pattern slots inside the umbrella `agent-installable-project` skill: still write `AGENTS.md`, still write `install.sh` with `NONINTERACTIVE` mode, still ship the three-tier README. The bridge-specific extras are (1) the Backend abstraction file layout above and (2) one extra question in `AGENTS.md` ("which backend?") whose answer is templated into one line of `config.yaml`.
