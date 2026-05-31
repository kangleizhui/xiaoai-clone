# Review-driven Skill Update / Rollback Notes

Use this when a user gives an external review/checklist for an existing SkillHub skill and asks to update the package.

## Workflow

1. **Back up before editing.** Copy the current `SKILL.md` to a timestamped backup path before any patch.
2. **Map review items to concrete diffs.** Do not blindly apply every review item as a permanent behavior change; preserve the skill's existing public-facing defaults unless the user explicitly accepts changing them.
3. **Treat security/default-behavior changes as opt-in.** If a review suggests changing externally visible defaults (for example CDP binding from `0.0.0.0` to `127.0.0.1`, removing `ufw allow 9222`, changing ports, disabling remote access), either keep the previous behavior or clearly separate it as an optional hardened mode. Do not silently invert the original deployment contract.
4. **Validate fenced code blocks.** After automated edits, check Markdown fences and run `bash -n` over bash fences when possible. Watch for accidental flattened line continuations or malformed nested fences.
5. **Package a pure zip.** For this user, the zip root should contain only `SKILL.md` unless explicitly requested otherwise.
6. **Rollback fast when requested.** If the user says to delete the new version and restore the backup, remove the newer zip, restore the backed-up `SKILL.md`, verify the original version, then repackage the original version as a pure zip.

## Pitfall from session

A review page recommended hardening CDP by changing `--remote-debugging-address=0.0.0.0` to `127.0.0.1` and removing `ufw allow 9222`. The user later rejected those two changes because they changed the original remote-CDP behavior. Future review-driven updates should not silently change public access semantics; keep such items optional or ask before applying if the user did not explicitly request hardening.

## Security audit / scanner handling

When a security audit flags items in a skill that the user wants to keep (e.g. CDP on `0.0.0.0`, `ufw allow 9222`, direct credential requests), do NOT remove the flagged functionality. Instead:

1. Add a `# ⚠️` block-comment in the relevant code fence pointing out the risk, so executing agents see it inline.
2. Ensure the skill's user-facing output template includes a corresponding safety reminder.
3. Present the fix as a diff suggestion and get user approval before applying.

This preserves the original deployment contract while satisfying audit requirements.
