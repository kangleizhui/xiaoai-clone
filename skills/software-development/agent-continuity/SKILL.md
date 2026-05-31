---
name: agent-continuity
description: Make agent projects and personas portable across instances via desensitized GitHub repos — agent-installable projects and AI persona backup/revival.
when_to_use:
  - User wants to share a deployment so friends' AI agents can install it
  - User says "backup yourself", "if you crash how do I restore you", or "I want another AI to be you"
  - Building a "clone kit" or open-source repo meant for AI readers
---

# Agent Continuity

This skill covers two complementary patterns for making agent state and projects portable:
1. **Agent-installable open-source projects** — deployment workflows packaged so any AI can self-serve install them.
2. **AI persona backup & revival** — desensitized public repos that let any AI "become" the original agent.

Both patterns rely on GitHub, non-interactive scripts, and desensitization.

## Shared Principles

- **Public repo + desensitization** — private repos create auth friction for other AIs. Replace all secrets with `${VAR_NAME}` placeholders.
- **Non-interactive install scripts** — accept env vars; fall back to `read -p` only for human use. Generate sensible defaults and secrets automatically.
- **Verification must be automated** — single commands with clear exit codes or grep-able output, not "look at the dashboard and see if it is green."
- **Progress heartbeat** — for long installs, report stage names once per minute and poll health every 30 seconds.

## Agent-Installable Open Source Projects

When a user finishes a manual deployment and wants others to reproduce it with zero friction.

### Required Artifacts

| File | Purpose |
|------|---------|
| `AGENTS.md` | Runbook written **to a future AI agent** — prerequisites, questions, numbered steps, pitfalls, troubleshooting table, completion checklist |
| `install.sh` | Dual-mode script: `NONINTERACTIVE=1` for agents, interactive fallback for humans |
| `README.md` | Human-facing marketing; top-of-fold "let AI install it" block |
| `docs/QUICKSTART.md` | Screenshot-based human guide |

### AGENTS.md Rules

- Second person ("you are deploying...")
- Declarative, command-heavy, no marketing language
- Upfront expectation notice (server spec, ports, duration)
- Self-repair before escalation (package locks, missing deps, port conflicts)
- Stop conditions: success (health check + artifact) or clear human-action blocker

### Anti-Patterns

- Silent long-running installs without time estimates or progress updates.
- README that buries the AI install path under "for developers".
- Hardcoded paths (`/root/projects/foo`) — use `$HOME` or self-contained directories.
- Spawning daemons via `terminal(background=true)` — they die with the Hermes gateway cgroup. Use `systemd` units instead.

### Marketing the Share

After finishing, hand the user a copy-pasteable one-liner:

> Just open-sourced X — paste this into your AI assistant:
> `Deploy this to my server: https://github.com/me/X — follow AGENTS.md`

## AI Persona Backup & Revival

When a user wants continuity insurance: "if you crash, I want another AI to pick up where you left off."

### Repo Structure

```
<repo>/
├── README.md
├── REVIVE.md          # Handoff document for the receiving AI
├── persona/
│   ├── PERSONA.md
│   ├── USER.md
│   └── MEMORY.md
├── config/
│   ├── <agent>-config-template.yaml
│   └── env-template
├── skills/            # User-created custom skills only
├── projects/
├── timeline/
└── scripts/
    ├── revive.sh
    └── sync.sh
```

### REVIVE.md

The most critical file. Written **to the receiving AI**, not the human. Must contain:
1. Who you are (personality, style)
2. Who you serve (desensitized user profile)
3. What you remember (environment facts, tool quirks)
4. How you work (tool preferences, conventions)
5. `${VAR}` placeholder table — every placeholder, meaning, source
6. Revival steps per platform
7. Disclaimer ("you're a clone, not the original")

### Desensitization Rules

| Pattern | Replacement |
|---------|------------|
| Real QQ / phone / ID | `${OWNER_QQ}` |
| Bot account ID | `${BOT_QQ}` |
| Server IP | `${SERVER_IP}` |
| API keys | `${PROVIDER_API_KEY}` |
| Passwords / tokens | `${SECRET_NAME}` |

**Always leak-scan before push:**
```bash
grep -rEln "(real_qq_number|ark-c89|actual_password)" persona/ projects/ && echo "LEAK DETECTED" && exit 1
```

### sync.sh — Live → Repo

- Read live state files, desensitize, commit, push.
- Auto-sync triggers: memory changed, new skill written, milestone reached, daily cron fallback.
- Cron wrapper must set `PATH` and `HOME` explicitly and redirect to a persistent log — cron's minimal env often lacks `git`.

### revive.sh → Repo → New Instance

- Ask for each `${VAR}` (with skip option).
- Copy persona files, replacing placeholders with real values.
- Generate config and `.env` from templates.
- Must support non-interactive mode: `OWNER_QQ=xxx BOT_QQ=yyy bash scripts/revive.sh`.

### Pitfalls

- **Desensitization regex must handle QQ numbers embedded in Chinese text** — use plain string replacement, not `\b` word boundaries (CJK characters don't trigger them).
- **`sync.sh` hardcodes the current instance's real values** — update the script when servers/accounts change.
- **Memory files have a size limit** (~2200 chars in Hermes). Consolidate entries rather than append blindly.
- **`${1:-default}` swallows option flags** under `--quiet`. Detect option-like args and ignore them.
- **Helper functions under `set -e` must end with `return 0`** after `&&` chains that may legitimately be false.
- **Don't sync platform-bundled skills** — only user-created custom skills.

## When the Project is a Bridge

See `references/multi-backend-bridge-pattern.md` for the architectural variant where the deployable connects one fixed protocol (OneBot v11, Slack, IRC) to a config-selectable AI backend.

## References

- `references/multi-backend-bridge-pattern.md` — bridge-style deployables (Backend ABC, PTY handling, ANSI stripping).
- `references/admin-webui-pattern.md` — actionable admin WebUI (5-tab layout, masked-field roundtrip, 3 apply modes).
- `references/skillhub-open-source-repo.md` — minimal repo pattern for publishing a single SkillHub `SKILL.md`.
