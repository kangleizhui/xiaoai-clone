# SkillHub Package Revision Workflow

Use this when the user asks to revise a SkillHub skill package and send a new zip.

## Durable workflow

1. Edit the skill's `SKILL.md` directly.
2. Set the version exactly as the user requested; if they later correct the version, change it and repackage immediately. If the user only asks for wording/text changes and does **not** specify a new version, keep the current version.
3. For exact wording changes, replace only the requested phrase/section and avoid opportunistic edits elsewhere. If the user says “意思不变/优化一下”, polish the wording while preserving the original meaning and link/text semantics.
4. Keep the package pure: zip root contains only `SKILL.md` unless the user explicitly asks for extra files.
5. Validate before sending:
   - zip contains exactly `['SKILL.md']`
   - frontmatter version matches the requested version/current version
   - requested keywords/sections are present
6. Send the zip in the same reply; do not merely say it was created.
7. Include a short changelog. This user prefers concise changelogs over long, detailed ones; for tiny copy edits, one bullet plus “其他内容保持不变” is enough.

## Common content reminders from recent SkillHub edits

- For long deployments, add a pre-run reminder with server config, required ports, estimated time, estimated token usage, and progress cadence.
- Token warning should tell users their remaining token budget must be greater than the estimate; recommend a safety buffer when appropriate.
- For QQbot/QQ channel screenshots, generated instructions should use `<qqmedia>` and place files under `~/.openclaw/media/qqbot/`; non-QQ channels can use normal `MEDIA:` attachments.
- When documenting install fallbacks, preserve the user's exact policy: if they say "prefer X, then try other versions", do not turn it into "forbid Y" or extra risk warnings. Express it as priority order + fallback, e.g. "deb Chromium/Chrome first; if that fails, use the system-available Chromium/Chrome variant."

## Skill simplification technique

When the user asks to simplify or says the skill is "太臃肿", apply these cuts in order:

1. **Merge duplicate sections.** Port reminders, Token warnings, deploy reminders — scan for near-identical text blocks and keep only one.
2. **Merge similar templates.** If 3+ reply templates differ only in IP type and port wording, collapse to 1 template + a short conditional note.
3. **Condense long prose.** "重要原则" sections that run 30+ lines with bullet-point reasoning can become 1-3 lines. The AI agent understands the principle; the skill just needs to state the rule.
4. **Replace duplicated scripts with cross-references.** If a CDP Python script appears in both an intro example and a later section, remove the intro version and add "详见 第X节".
5. **Collapse tables to inline.** Two-column component tables can become `→` arrow chains.
6. **Remove progress message examples.** If rules already describe the cadence, example messages are clutter.
7. **Delete source article references.** Users who installed the skill don't need the original blog link.

Target: ~15% reduction is a good outcome without losing functionality.

8. **Security consistency audit.** After simplifying, grep the SKILL.md for `ufw`, `allow`, `安全组`, `暴露`, `公网` — check that every port-opening instruction aligns with the security boundary stated in the skill. The most common mistake: a `ufw allow` line opens a port that the text elsewhere says "不建议对外暴露". Delete the offending command, not the warning. Also check the user-facing reminder text, cloud security group sections, and ANY mention of the port — a single "可选开放" in an earlier section contradicts a "不建议对公网开放" policy set later. Fix the contradiction everywhere, not just in the ufw block.

9. **Post-deletion heading cleanup.** When you replace a subsection's content with a cross-reference (per item 4), check if the heading is now vestigial — a 3-line subsection under a `###` heading looks broken. If the subsection was reduced to a single reference line and its content is already covered by the parent section's body, delete the heading and fold the reference line into the parent section. Then renumber any sibling subsections and grep for cross-references to verify no stale `八-2` / `八-3` links remain.

10. **Execution flow dry-run.** After editing a procedural skill, trace through the document as if you're an AI agent executing it for the first time. Watch for:
    - Gaps: does section N naturally lead to section N+1, or does the agent hit a reference section and wonder "do I execute this, skip it, or wait for instructions?"
    - Missing bridges: after "setup complete" sections (systemd, install), is there an explicit "now do this next" instruction, or does the skill silently jump into reference code or reply templates?
    - Reference vs. execution ambiguity: sections that contain executable code but are meant as reference should be clearly labeled "(参考代码，需要时使用)" so an agent doesn't execute them as part of the main flow.

11. **Bridge insertion pattern.** When a procedure has an implicit dependency chain (e.g., setup → open browser → screenshot → send reply), insert an explicit numbered sequence block between the last setup step and the reference/template sections. Use a horizontal rule (`---`) to visually separate it, and state "不可跳过或调换顺序". The bridge should be self-contained: name each step, give the concrete command or section reference, and specify the order.

12. **`--headless` prohibition for visual browser skills.** Any skill that deploys Chromium + Xvfb + noVNC (or any stack where the browser MUST render visually) must explicitly forbid `--headless` / `--headless=new` at every Chromium launch site: the startup script comment, the systemd service comment, AND the principles/conventions section. A silent Chromium with a blank noVNC screen is an unrecoverable failure. Use exact phrasing: `# ⚠️ 严禁添加 --headless 或 --headless=new，否则 noVNC 画面无法显示。`

13. **QQbot/QQ media path is non-negotiable.** For skills that produce screenshots consumed via QQ, the `<qqmedia>` tag requires an absolute path under `~/.openclaw/media/qqbot/`. Always include the `mkdir -p` + `cp` commands as executable code blocks — never as prose. Example:

    ```bash
    mkdir -p ~/.openclaw/media/qqbot
    cp /tmp/screenshot.png ~/.openclaw/media/qqbot/screenshot.png
    ```
    Reply tag: `<qqmedia>/root/.openclaw/media/qqbot/screenshot.png</qqmedia>`

## Changelog style

Present changelogs as plain text with bullet points. **Never use markdown tables or code blocks.** This user explicitly rejects both formats — tables are the most common mistake.

Good:

v1.0.12 更新日志
• 优化 Token 消耗提醒
• 明确提醒剩余 Token 必须大于预计消耗
• 建议预留 10万 tokens 以上，避免部署中断
• 其他内容保持不变

Rules:
- No tables. No code blocks. Plain text with bullet points (• or -).
- Format: `vX.Y.Z` followed by bullets.
- Keep it concise; for tiny copy edits, one bullet plus "其他内容保持不变" is enough.
- Avoid "简版" or multi-section explanations unless the user asks for detail.
