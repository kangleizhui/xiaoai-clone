# SkillHub Web Upload Notes

## Upload package shape

SkillHub's web uploader accepts a folder zip/compressed package containing up to 200 `SKILL.md` files and a total size no larger than 10.00 MiB.

For a single skill upload, the safest shape is:

```text
my-skill.zip
├── SKILL.md
└── references/          # optional
    └── *.md / *.py
```

Put `SKILL.md` at the archive root. Include supporting files only from the skill's normal support directories (`references/`, `templates/`, `scripts/`, `assets/`).

Use the helper script:

```bash
python scripts/package_skillhub_zip.py /path/to/skill-dir /tmp/my-skill.zip
unzip -l /tmp/my-skill.zip
```

Verification checklist:

- `unzip -l` shows `SKILL.md` with no parent directory prefix.
- Zip size is below 10 MiB.
- No secrets or environment-specific tokens appear in `SKILL.md` or references.

## Login/publish troubleshooting

If SMS login appears to succeed but immediately returns to the unauthenticated state:

1. Open `/dashboard/publish` and read the page text. If it says `需要登录才能访问`, the login token was not persisted.
2. Inspect cookie/localStorage in the visible browser. Visitor/analytics cookies such as `qcloud_visitId`, `qcloud_uid`, `ewpUid`, or Sensors/Beacon keys are not enough; the page still needs SkillHub's real auth/session token.
3. Avoid repeatedly asking the user for SMS codes. If automated filling closed the modal but did not persist auth, switch to fully manual login in noVNC or ask the user to upload from their own local browser.
4. A remote Chromium with CDP/noVNC may trigger Tencent/SkillHub environment or device-fingerprint risk checks. Treat this as a web auth/environment issue, not as a noVNC rendering failure.

