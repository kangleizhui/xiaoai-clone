# NapCatQQ Deployment Reference

GitHub: https://github.com/NapNeko/NapCatQQ
Docs (real path, the linked `/zh-CN/` 404s): https://napneko.github.io/guide/start-install

NapCatQQ injects a JS launcher into Tencent's Linux NTQQ Electron client to expose OneBot v11 APIs. Mature, 9k+ stars, actively maintained.

## Install paths (rootless mode, the recommended one)

| Item | Path |
|---|---|
| Install base | `$HOME/Napcat` (so `/root/Napcat` for root user) |
| QQ binary | `/root/Napcat/opt/QQ/qq` |
| Plugin folder | `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/` |
| WebUI config | `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json` |
| OneBot config (per-account) | `…/napcat/config/onebot11_<QQ号>.json` (created after first login) |
| QR code PNG | `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png` |
| Wrapper CLI | `/usr/local/bin/napcat` |

## Installer flag map (`napcat.sh`)

Discovered by reading the installer source (`grep -A2 "case \\\$1" napcat.sh`):

| Flag | Mode | Notes |
|---|---|---|
| `--tui` | both | Launch interactive TUI |
| `--docker [y/n]` | both | Pick install method. **Required to skip the y/n prompt.** |
| `--cli [y/n]` | Shell only | Whether to install the `napcat` wrapper CLI. Default y after 10s timeout. |
| `--force` | Shell only | Reinstall LinuxQQ + NapCat even if present |
| `--proxy [0-n]` | both | Download proxy choice (0 = direct) |
| `--qq "<num>"` | Docker only | QQ account for the container |
| `--mode [ws\|reverse_ws\|http\|...]` | Docker only | OneBot connection mode |
| `--confirm [y]` | **Docker only** | Skip final confirmation. **Passing this in Shell mode causes immediate exit 1.** |

**Non-interactive Shell install command** (verified working 2026-05):
```bash
bash napcat.sh --docker n --cli y --force
```

This skips both interactive prompts (the y/n install-mode question and the y/n install-CLI question).

## What the installer does

1. Installs apt deps: `jq`, `libnss3`, `libxss1`, `libasound2`, `xvfb`, `screen`, etc.
2. Downloads QQ Linux `.deb` (~150 MB), extracts it under `$HOME/Napcat/opt/QQ/` (NOT into `/opt/QQ` — rootless mode).
3. Patches `resources/app/package.json` and `loadNapCat.js` to bootstrap the NapCat injection.
4. Installs the `napcat` TUI-CLI wrapper to `/usr/local/bin/napcat`.

Total time on a fresh Debian 13 with good network: ~2 minutes.

## First-run flow

1. Start under screen: `screen -dmS napcat bash -c "xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox 2>&1 | tee /tmp/napcat.log"`
2. Within ~5s, log shows:
   - `[NapCat] [WebUi] WebUi User Panel Url: http://...?token=***` (token masked)
   - ASCII QR code in terminal (usually unscannable from log)
   - `二维码已保存到 …/cache/qrcode.png` — this PNG is what you deliver to the user as `MEDIA:`
3. Read the WebUI token from JSON:
   ```bash
   python3 -c "import json; d=json.load(open('/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json')); print(d['token'])"
   ```
   Token is a 12-char hex string like `b5b7d03c4293`.
4. WebUI URL for the user: `http://<public-ip>:6099/webui?token=<TOKEN>`
5. User scans the QR (via WebUI is best, the cached PNG is fallback) to log in.
6. After login, `onebot11_<QQ>.json` is created. The user configures their bot connection (ws/http/reverse_ws) from the WebUI's "网络配置" section.

## OneBot connection modes (set via WebUI)

| Mode | When to use |
|---|---|
| `ws` (positive WS) | Bot framework connects TO NapCat — simplest, NapCat is server |
| `reverse_ws` | NapCat connects TO bot framework — needed when bot is behind NAT |
| `http` | Polling/POST APIs only, no events. Rarely used. |
| `http_post` | NapCat POSTs events to your HTTP endpoint |

For NoneBot/Koishi on the same machine, `ws` on `127.0.0.1:3001` (NapCat's default ws port) is the simplest config.

## Common downstream bot frameworks that connect to NapCat

- **NoneBot2** (Python, most popular for LLM bots)
- **Koishi** (Node.js, plugin-rich)
- **Hoshino** (older, NoneBot1 ecosystem)
- Any OneBot v11 client

## Account safety notes

- QQ accounts logged in via protocol frameworks **carry ban risk** — Tencent occasionally sweeps. Use a secondary account, not a main one.
- Frequent IP changes trigger device verification. Stable VPS = fewer login interruptions.
- After login, the device shows as a Linux PC in 手机QQ's "已登录设备" list.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Installer immediately prints help and exits 1 | Bad flag combo (e.g. `--confirm y` in Shell mode) | Remove the offending flag |
| WebUI port appears closed from internet | Tencent Cloud security group not opened | Add 6099/tcp in 腾讯云控制台 → 安全组 |
| Token shows as `***` everywhere | Working as designed (redaction) | Read directly from `webui.json` via Python |
| QR code in log is unreadable | Terminal font/encoding | Use the cached PNG at `cache/qrcode.png` |
| QQ window flickers on noVNC | Sharing DISPLAY=:99 with another app | Use `xvfb-run -a`, not `DISPLAY=:99` |
| `napcat start` says "QQ not installed" | Force-reinstalled but cache stale | `napcat rebuild` |

## Update / removal

- Update: `napcat update` (stops instance, fetches latest QQ + NapCat, restarts)
- Rebuild from scratch: `napcat rebuild`
- Uninstall: `napcat remove` (cleans `$HOME/Napcat`, removes systemd unit if set)
