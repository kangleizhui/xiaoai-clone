# SkillHub CLI & Skill Revert Workflow

## SkillHub CLI (`skillhub`)

A local CLI tool is installed at `/root/.local/bin/skillhub` for interacting with SkillHub.

### Key Commands

```bash
# Search for skills
skillhub search <query>

# Install a skill from SkillHub to a local directory
skillhub install <slug> --dir <target-dir>

# List locally installed skills
skillhub list

# Upgrade installed skills
skillhub upgrade
```

### Downloading a Skill

```bash
skillhub install tencent-novnc-chromium-cdp --dir /tmp/skillhub-download
```

This downloads the skill to `/tmp/skillhub-download/<slug>/SKILL.md` plus `_meta.json`.

The download URL pattern is: `https://api.skillhub.cn/api/v1/download?slug=<slug>`

### When to Use the CLI

- User says "从 SkillHub 重新下载" or gives a SkillHub URL
- Need to verify the current published version of a skill
- Reverting to the SkillHub-published version of a skill
- Baseline re-pull when local copy is suspect

## Skill Revert Workflow

When the user says "退回原来的版本" or "不想要最新版了":

1. **Check local backups first:**
   ```bash
   # Common backup locations
   ls /tmp/skillhub-original/SKILL.md
   ls /root/projects/<skill>/SKILL.md.*.bak
   ```

2. **If no local backup, download from SkillHub:**
   ```bash
   skillhub install <slug> --dir /tmp/skillhub-download
   head -5 /tmp/skillhub-download/<slug>/SKILL.md  # check version
   ```

3. **Compare versions:**
   ```bash
   grep "^version:" <local-file>
   grep "^version:" <downloaded-file>
   ```

4. **Replace and backup:**
   ```bash
   cp <target>/SKILL.md <target>/SKILL.md.<old-version>.bak
   cp <source>/SKILL.md <target>/SKILL.md
   ```

5. **Verify:**
   ```bash
   head -5 <target>/SKILL.md
   wc -c <target>/SKILL.md
   ```

## Version Confusion Pitfall

SkillHub versions may include YOUR previously published modifications. The "original" version might be:
- The very first version you downloaded (check `/tmp/skillhub-original/`)
- The current SkillHub published version (which may include your earlier edits)

When the user says "原来的版本", clarify whether they mean:
- The pre-modification baseline (earliest download)
- The current SkillHub published version

When in doubt, ask.
