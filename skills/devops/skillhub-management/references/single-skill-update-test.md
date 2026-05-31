# Single SkillHub Skill Update, Package, and Install-Test Workflow

Use this when updating one SkillHub skill and the user asks for a zip package or asks to test the published SkillHub URL/slug.

## Update and package

1. Edit the installed/source skill `SKILL.md`.
2. If the user specifies a version, patch the frontmatter `version:` first.
3. For this user, package as a pure SkillHub zip unless asked otherwise: archive root contains only `SKILL.md`.
4. Verify archive contents and version before sending.

```bash
python scripts/package_skillhub_zip.py /path/to/skill-dir /tmp/<slug>-v<version>.zip
unzip -l /tmp/<slug>-v<version>.zip
python3 - <<'PY' /tmp/<slug>-v<version>.zip
import zipfile, re, sys
p=sys.argv[1]
with zipfile.ZipFile(p) as z:
    names=z.namelist()
    assert names == ['SKILL.md'] or 'SKILL.md' in names
    s=z.read('SKILL.md').decode()
    print(re.search(r'^version:\s*(.+)$', s, re.M).group(0))
PY
```

## Remote install-test from SkillHub

Install into a temporary directory so you test what the registry serves, not just the local edited copy:

```bash
export PATH="$HOME/.local/bin:$PATH"
rm -rf /tmp/skillhub-test-install
mkdir -p /tmp/skillhub-test-install
skillhub install <slug> --dir /tmp/skillhub-test-install --force
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/skillhub-test-install/<slug>/SKILL.md')
s=p.read_text()
print('SKILL.md exists:', p.exists())
print('version line:', next(x for x in s.splitlines() if x.startswith('version:')))
for key in ['权限预检', '完成后必须回复用户', '6080/tcp']:
    print(key, key in s)
PY
```

`not in index, using remote registry exact match` is normal for newly published or not-yet-indexed skills if the final install succeeds.

## Execute-test noVNC/Chromium skills

When testing a noVNC + Chromium skill after installation:

1. Run the skill's permission preflight first (`id -u`, `sudo -n true`).
2. Start/restart the remote browser script.
3. Verify ports and HTTP/CDP readiness.
4. Generate the screenshot and final user-facing response.

```bash
bash /root/start-remote-browser.sh
ss -tlnp | grep -E '6080|5900|9222' || true
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:6080/vnc.html
curl -sf http://127.0.0.1:9222/json/version >/dev/null && echo cdp-ok
PUBLIC_IP=$(curl -4 -s --max-time 5 https://ifconfig.me 2>/dev/null || curl -4 -s --max-time 5 https://api.ipify.org 2>/dev/null || true)
if [ -n "$PUBLIC_IP" ]; then NOVNC_URL="http://${PUBLIC_IP}:6080/vnc.html"; else NOVNC_URL="http://$(hostname -I | awk '{print $1}'):6080/vnc.html"; fi
DISPLAY=:99 import -window root /tmp/remote-browser.png
file /tmp/remote-browser.png
printf '%s\n' "$NOVNC_URL"
```

Final reply should include the noVNC URL, a 6080/tcp security-group/firewall reminder, and `MEDIA:/tmp/remote-browser.png`.
