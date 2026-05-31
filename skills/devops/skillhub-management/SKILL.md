---
name: skillhub-management
description: Install, package, and maintain SkillHub skills and Soul packages — CLI usage, skill deployment, upload zip hygiene, and version lifecycle.
when_to_use:
  - User provides a SkillHub PackageURL or asks to "install this soul"
  - User wants to modify a SkillHub SKILL.md, bump a version, or produce an upload zip
  - User asks to install hot/contest top skills or a single skill by slug
  - User needs a changelog or wants to revert a skill version
---

# SkillHub Management

This skill covers the full SkillHub lifecycle: installing CLI and Soul packages, and maintaining/packaging individual skills for distribution.

## Installing the SkillHub CLI & Soul Packages

### 1. Install CLI

```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash
```

Installs `~/.local/bin/skillhub` and the OpenClaw workspace at `~/.openclaw/workspace/`.

### 2. Download & Extract Package

```bash
mkdir -p /tmp/soul-pkg && cd /tmp/soul-pkg
curl -sL -o package.zip "<PackageURL>"
unzip -o package.zip -d extracted/
```

### 3. Read Manifest

```bash
python3 -c "import json; m=json.load(open('extracted/manifest.json')); ..."
```

Extract unique skill slugs, compute which are already installed, then install only missing ones:

```bash
skillhub install "$slug" --dir ~/.openclaw/workspace/skills
```

For large packages (200+ skills), batch in groups of 30–40 to avoid timeout.

### 4. Deploy

```bash
cp extracted/soul.md ~/.openclaw/workspace/SOUL.md
mkdir -p ~/.openclaw/workspace/skillsets
cp extracted/skillsets/*.md ~/.openclaw/workspace/skillsets/
```

### 5. Handle Missing Skills

Some referenced skills return HTTP 404 (unpublished). Log and skip — this is expected.

### Install Hot/Contest Top 10

Fetch from `https://api.skillhub.cn/api/v1/contest/top`, parse `top10`, install slugs in batches.

### Install Single Skill by Slug

```bash
skillhub install "<slug>" --dir ~/.openclaw/workspace/skills
```

`not in index, using remote registry exact match` is normal for newly published skills.

## Packaging & Maintaining Skills

### Pure Zip Rule

For SkillHub web uploads, default to a zip whose root contains **only `SKILL.md`** unless the user explicitly asks for extras.

```text
zip root/
└── SKILL.md
```

Avoid including `references/`, README drafts, screenshots, or temporary files.

### Version Handling

- Set `version:` exactly to the value the user requests.
- Zip filename should match: `{slug}-v{version}.zip`.
- Never let version and filename diverge.

### Changelog Style

Keep it short and practical, grouped by user-visible behavior. Use plain text with bullet points — **do not wrap in markdown code blocks** (the user prefers readable inline text):

v1.1.0

新增：
• QQbot 图片适配。

修复：
• 保留部署进度提醒。

### QQbot Media Rule

QQbot channels may not deliver images via ordinary `MEDIA:` paths. For screenshots/images in QQbot:

1. Place file under `~/.openclaw/media/qqbot/`
2. Use `<qqmedia>/root/.openclaw/media/qqbot/image.png</qqmedia>`
3. For non-QQbot channels, continue using `MEDIA:/path/to/image.png`

### Review-Driven Updates

When updating from an external review/checklist:
1. Back up first.
2. Map review items to concrete changes.
3. Validate fenced code blocks.
4. Rebuild the pure zip.

### Skill Revert

Use the SkillHub CLI to download a previous version, compare, and replace:
```bash
skillhub install <slug> --dir ~/.openclaw/workspace/skills
```
Check local backups first if the user has a `backups/` directory.

### Cron Job Conflicts

If a recurring cron job periodically downloads + deletes the skill directory, **pause it** before editing:
```python
cronjob(action='pause', job_id='...')
```
Resume after packaging is complete.

## Common Pitfalls

1. **Forgetting to send the package** after editing — repack and attach immediately.
2. **Adding extra files to the zip** — keep it pure unless asked.
3. **Skipping plan confirmation on multi-item edits** — list changes and wait for user approval before patching. Valid approval signals include: 确认, 执行, 改, 改吧, 可以, 是的, 没错, 对的, 开始吧.
4. **Trusting local baseline when user said "use online version"** — re-pull from API, verify sha256, then overwrite local copy.
5. **Cron `no_agent=True` script is a filename, not inline code** — write to `~/.hermes/scripts/` first.
6. **Replacing large blocks can lose adjacent section headers** — when `old_string` ends right before a `###` heading, verify the heading survived in the diff. If dropped, patch it back immediately.
7. **Deleting content leaves empty section headings** — when de-duplicating or removing a code block that was the sole content of a subsection, delete the heading too and renumber subsequent subsections. Then scan the entire file for cross-references to the old numbering and update them. A `### 2.` with nothing but a one-line pointer underneath is worse than no subsection at all.

## References

- `references/baseline-from-skillhub-api.md` — re-pull and sha256-verify workflow.
- `references/qqbot-media-and-novnc-package.md` — concrete QQbot screenshot example.
- `references/review-driven-skill-update.md` — checklist-based update workflow.
- `references/skillhub-cli-and-revert.md` — CLI usage and revert patterns.
- `references/single-skill-update-test.md` — update → package → remote-install → test cycle.
- `references/cronjob-no-agent-script-pitfall.md` — cron script mode pitfalls.
- `references/web-upload.md` — upload package shape and SMS login quirks.
- `scripts/package_skillhub_zip.py` — helper to package a skill directory into a clean zip.
