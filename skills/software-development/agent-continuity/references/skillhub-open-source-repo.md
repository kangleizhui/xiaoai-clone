# SkillHub Skill Open-Source Repo Pattern

Use this when the deliverable is a single SkillHub skill (`SKILL.md`) that the user wants to publish on GitHub for other people or AI agents to reuse.

## Minimal repo shape

A SkillHub-only open-source repo does **not** need a full app scaffold or `install.sh` if the skill itself is the executable runbook. Use this shape:

```text
repo-root/
  SKILL.md      # source of truth, exact version requested by user
  README.md     # human-facing summary and copy-paste prompt
  AGENTS.md     # AI-facing deployment/use guide pointing to SKILL.md
  LICENSE       # usually MIT unless user says otherwise
```

Avoid adding generated zip files, session notes, screenshots, or extra docs unless the user explicitly asks.

## README requirements

Keep it short and shareable:

- What the skill does in one sentence.
- The easiest copy-paste prompt for an AI Agent.
- Link to any source article/reference if the skill is derived from one.
- Server requirements and required ports if it is a deployment skill.
- Current version.

Example AI share line:

```text
把这个仓库发给你的 AI Agent：
https://github.com/<user>/<repo>

让它读取 AGENTS.md 和 SKILL.md，帮你部署 <thing>。
```

## AGENTS.md requirements

Write directly to a future AI Agent. For a SkillHub-only repo, AGENTS.md should:

- Tell the agent to read and execute `SKILL.md` first.
- Include the recommended user prompt.
- Repeat only the high-value operational reminders: permissions, ports, time/token estimate, progress cadence, final verification, screenshot/media rules.
- Include unattended verification commands.
- Include the final reply format.

Do not duplicate the entire SKILL.md; AGENTS.md is a routing guide and checklist.

## Version and changelog handling

- Preserve the version in `SKILL.md` unless the user explicitly asks to change it.
- If the user asks for a version change, change frontmatter and repackage/push immediately.
- Changelog titles should be `## vX.Y.Z 更新日志`; do not add “简版”.
- Keep changelogs concise: one to four bullets, plus “其他内容保持不变” for tiny edits.

## Browser-install fallback wording

When documenting browser install strategy, preserve the user's policy exactly:

- Good: “deb 版优先；deb 版安装失败后，自动切换至系统可用的其他 Chromium/Chrome 版本。”
- Bad: “禁用 snap / snap 有风险 / 检测到 snap 就警告或中断。”

Do not add risk language the user did not ask for.

## GitHub publish checklist

1. Create a clean repo directory.
2. Copy the latest `SKILL.md` into the root.
3. Add `README.md`, `AGENTS.md`, and `LICENSE`.
4. Commit on `main`.
5. Create a public GitHub repo.
6. Push and verify via GitHub API or `git ls-remote` that `SKILL.md`, `README.md`, and `AGENTS.md` exist.
7. Return the repo URL and a copy-paste share prompt.
