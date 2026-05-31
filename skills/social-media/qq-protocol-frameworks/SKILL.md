---
name: qq-protocol-frameworks
description: Deploy and manage QQ protocol-side frameworks (NapCatQQ, LLOneBot, Lagrange, etc.) on Linux servers. Covers rootless install, headless QQ login via xvfb, WebUI/OneBot config, screen-based supervision, and dual-layer firewall setup.
when_to_use:
  - User wants to deploy a QQ bot framework (NapCatQQ, LLOneBot, Lagrange.Core, go-cqhttp successor)
  - Setting up OneBot 11/12 endpoints for downstream bots (NoneBot, Koishi, Hoshino)
  - Login/scan/QR issues with headless QQ on a server
  - WebUI token retrieval, port exposure, or "扫码无反应" debugging
  - Migrating between QQ protocol frameworks or upgrading them
---

# QQ Protocol Frameworks (NapCatQQ / Lagrange / LLOneBot)

QQ protocol-side frameworks let you run QQ as a backend service that exposes **OneBot v11/v12** APIs over WebSocket/HTTP so bot frameworks (NoneBot, Koishi) can talk to it. They generally work by either **injecting into Tencent's official NTQQ Electron client** (NapCatQQ, LLOneBot) or by **reimplementing the protocol** (Lagrange.Core).

The user runs these on their own Tencent Cloud server, so all deployments here are **rootless install + screen supervision** by default, not Docker.

## Concrete frameworks covered

| Framework | Type | Best for | Detail |
|---|---|---|---|
| **NapCatQQ** | NTQQ injection | Most stable, active dev, WebUI included | [references/napcatqq.md](references/napcatqq.md) |
| LLOneBot | NTQQ injection | Simpler, plugin for LiteLoaderQQNT | (add ref when used) |
| Lagrange.Core | Protocol reimpl | No QQ binary needed | (add ref when used) |

## General deployment shape (any framework)

1. **Pick install mode**: rootless shell install >> Docker for this user (they prefer lightweight, native installs on their Tencent Cloud server).
2. **Verify deps**: `xvfb-run`, `screen`, `curl`, `jq` — needed for headless GUI QQ and supervision.
3. **Run the installer non-interactively** — every official installer has interactive prompts. ALWAYS read the script's arg parser first (`grep -E "case \\\$1|while.*\\\$#" installer.sh`) before piping to bash. See pitfall §1.
4. **Start under `screen`** so logs survive disconnect:
   ```bash
   screen -dmS <framework> bash -c "xvfb-run -a /path/to/qq --no-sandbox 2>&1 | tee /tmp/<framework>.log"
   ```
5. **Extract WebUI token** — CLI tools and logs almost always mask tokens as `***`. Read it directly from the on-disk config JSON. See pitfall §2.
6. **Dual-layer firewall**: `ufw allow <port>/tcp` on the VM AND add a security-group rule in **腾讯云控制台** (Tencent Cloud console). Forgetting the cloud-side rule is the #1 "为什么打不开 WebUI" complaint.
7. **Show the user the QR code as MEDIA:** for scan-login. Frameworks save QR PNGs to a predictable cache path; deliver it via QQ image attachment.

## Pitfalls

### 1. Installer interactive-flag mismatch
Installers reuse flag names across modes. A flag valid for Docker mode often errors out in Shell mode and dumps the help text. Before running, grep the script's `case "$1"` block, then test with `--help` if uncertain. For NapCatQQ specifically: `--confirm y` is **Docker-only**; passing it in Shell mode causes immediate exit 1.

### 2. WebUI token is masked in logs and CLI output
NapCatQQ (and similar) prints `WebUi User Panel Url: http://...?token=***` in stdout and the CLI status commands also redact it. The actual token is in the on-disk JSON config. Read it with Python (not `cat`, which on NapCatQQ's webui.json dumps a 200-line theme config and buries the token):
```bash
python3 -c "import json; d=json.load(open('<path>/webui.json')); print('TOKEN:', d['token'])"
```
For NapCatQQ the path is `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json`.

### 3. Tencent Cloud security group is a separate layer from ufw
The user's server (101.32.98.240) sits behind Tencent Cloud's security group. `ufw allow` alone is not enough — you must remind them to add the same port to the cloud console security group, or the WebUI port appears closed from the public internet. Always state both steps explicitly when exposing a new port.

### 4. Headless QQ needs `xvfb-run`, not `DISPLAY=:99`
Even though this server has Xvfb running on `:99` for the noVNC browser, mixing the QQ instance into that display causes weird focus stealing and visible QQ window flashes on the noVNC view. Use `xvfb-run -a` instead — it spawns its own throwaway X server for QQ.

### 5. Don't shell-background the installer
Installers download hundreds of MB of QQ Linux client. Use Hermes `terminal(background=true, notify_on_complete=true)`, never `nohup ... &` (Hermes blocks shell-level backgrounding).

### 6. After install, the config files don't exist yet
WebUI token, OneBot config, account config — none of these JSONs are created until the framework starts at least once. Start under screen, wait ~5 seconds, then read configs.

## Quick reference: NapCatQQ one-liner deployment

```bash
# Download installer
cd /root && curl -o napcat.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh

# Install non-interactively (Shell mode, with CLI, force reinstall)
bash napcat.sh --docker n --cli y --force

# Start under screen
screen -dmS napcat bash -c "xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox 2>&1 | tee /tmp/napcat.log"
sleep 5

# Extract WebUI token
python3 -c "import json; d=json.load(open('/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json')); print('TOKEN:', d['token'])"

# Open firewall (still need Tencent Cloud security group!)
ufw allow 6099/tcp

# Show QR
echo "MEDIA:/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png"
```

Full deep-dive: [references/napcatqq.md](references/napcatqq.md).

## CLI management (NapCatQQ)

NapCat installs a `napcat` wrapper at `/usr/local/bin/napcat`:
- `napcat start <QQ>` — start a specific account
- `napcat stop [QQ]` — stop one or all
- `napcat status` — show running instances
- `napcat log <QQ>` — tail log
- `napcat startup <QQ>` — enable systemd autostart
- `napcat update` / `rebuild` / `remove` — lifecycle

`napcat` does NOT have a token-print command. Use the Python one-liner in pitfall §2.
