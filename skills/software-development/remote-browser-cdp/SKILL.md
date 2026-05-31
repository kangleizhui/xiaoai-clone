---
name: remote-browser-cdp
description: "Use when setting up a remote Chromium browser with noVNC for visual access and CDP for programmatic control — install, configure, launch, navigate, screenshot."
version: 1.0.4
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [browser, cdp, noVNC, chromium, remote-browser, xvfb]
    related_skills: [node-inspect-debugger]
---

# Remote Browser with noVNC + CDP

## Overview

Set up a full remote browser stack on Linux: **Xvfb** (virtual display) → **Chromium** (browser with CDP) → **x11vnc** (VNC bridge) → **noVNC/websockify** (web-based VNC viewer).

The result gives you two access points:
- **Visual**: noVNC web UI at `http://<IP>:6080/vnc.html` — the user sees a real browser
- **Programmatic**: CDP WebSocket at `ws://<IP>:9223` — you control the browser programmatically

Data flow: `Chromium → Xvfb(:99) → x11vnc(:5900) → websockify(:6080) → user browser`

### ⚠️ CRITICAL: Two Chromium Instances — Do NOT Confuse Them

This remote browser is a **separate Chromium process** from Hermes Agent's internal headless browser. They are NOT the same browser.

| Instance | How to control | Where you can see it | CDP port |
|----------|---------------|---------------------|----------|
| **This remote browser** (noVNC) | Raw CDP WebSocket via Python + `websockets` | ✅ User sees via noVNC web UI | `:9223` |
| **Hermes internal browser** (headless) | `browser_navigate`, `browser_click`, `browser_snapshot` tools | ❌ Not visible to user | `:0` (random) |

**The `browser_*` Hermes tools DO NOT control the noVNC browser.** If you use `browser_navigate` while the user is looking at the noVNC browser, nothing happens on their end. If you read a page with `browser_snapshot` and the user says "that's not what I see", you're looking at the wrong browser.

**How to detect which is which:**
```bash
ps aux | grep -E "chromium.*--headless=new|chromium.*--window-size=1920" | grep -v grep
```
- One with `--headless=new` and `--remote-debugging-port=0` → **Hermes internal** (ignore for this skill)
- One with `--window-size=1920,1080` and `--remote-debugging-port=9222` → **this remote browser** (use CDP)

**Rule:** To control the noVNC browser, ALWAYS use raw CDP via Python WebSocket. Never use Hermes `browser_*` tools unless you explicitly intend the invisible headless browser.

## When to Use

- User asks to "set up a remote browser" or "make a browser I can see"
- User says "control this browser via CDP" or "use Chrome DevTools Protocol"
- You need a visible browser for a user to interact with while you script it
- User asks for screenshots of a browser in a headless server
- User asks about noVNC, Xvfb, x11vnc, websockify setup

**Don't use for:** standard Playwright/Puppeteer headless testing (where no visual access is needed), or Node.js debugging (use `node-inspect-debugger` skill instead).

## Related Task: Chinese Site Login with Captcha

Chinese websites (ByteDance ecosystem: 番茄小说, 抖音, 头条; Alibaba ecosystem) often require a **slider captcha** before actions like sending SMS verification codes. The captcha cannot be bypassed programmatically — use the remote browser's noVNC UI for the user to solve it visually.

See `references/chinese-site-login-captcha.md` for the full login flow, captcha architecture notes, and Hermes browser tool quirks.

## Architecture

| Component | Role | How to use it |
|-----------|------|---------------|
| **Xvfb** | Virtual framebuffer (display :99) | Provides a "screen" for Chromium |
| **Chromium** | Browser with CDP on :9223 | Control via CDP WebSocket |
| **x11vnc** | VNC server on :5900 | Bridges Xvfb to VNC protocol |
| **websockify/noVNC** | WebSocket proxy + viewer on :6080 | User opens this in their browser |

## Setup Steps

### Step 1: Install Dependencies

```bash
apt update && apt install -y xvfb x11vnc chromium git python3-pip
```

### Step 2: Install noVNC + websockify

```bash
cd /opt
git clone https://github.com/novnc/noVNC.git
pip3 install websockify --break-system-packages
```

### Step 3: Open Firewall Ports

Before starting, ensure both **cloud security group** and **server firewall** allow access:

```bash
# UFW (common on Debian/Ubuntu)
# 只放行 noVNC。9223（CDP 调试端口）不建议暴露到公网，不走防火墙。
ufw allow 6080/tcp    # noVNC web UI
ufw reload

# Also add inbound rules in your cloud provider's security group:
# - 6080 TCP (noVNC)
# - 9222 TCP (CDP, only if remote access needed)
```

If UFW is not installed, check `iptables -L -n` for the INPUT chain policy — if the default is DROP, ports won't be reachable from outside regardless of cloud firewall rules.

### Step 4: Generate noVNC Password

```bash
# Generate random password and store it
NOVNC_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 8)
echo -n "$NOVNC_PASS" > /root/.novnc_password
chmod 600 /root/.novnc_password
x11vnc -storepasswd "$NOVNC_PASS" /root/.vncpasswd
chmod 600 /root/.vncpasswd
echo "noVNC 访问密码: $NOVNC_PASS"
```

### Step 5: Create Startup Script

Create `/root/start-remote-browser.sh`:

```bash
#!/bin/bash
pkill -9 -f x11vnc 2>/dev/null
pkill -9 -f Xvfb 2>/dev/null
pkill -9 -f websockify 2>/dev/null
sleep 2

echo "[1/4] 启动虚拟显示器..."
Xvfb :99 -screen 0 1920x1080x24 &
sleep 1
export DISPLAY=:99

echo "[2/4] 启动 Chromium (CDP:9223)..."
chromium \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-session-crashed-bubble \
  --restore-last-session=false \
  --remote-debugging-port=9223 \
  --remote-debugging-address=0.0.0.0 \
  --remote-allow-origins=* \
  --window-size=1920,1080 \
  --start-maximized \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/root/.chromium-remote \
  about:blank &
sleep 3

echo "[3/4] 启动 x11vnc..."
x11vnc -display :99 -forever -rfbauth /root/.vncpasswd -quiet -listen 127.0.0.1 &
sleep 1

echo "[4/4] 启动 noVNC (端口:6080)..."
websockify --web /opt/noVNC 6080 127.0.0.1:5900 &
sleep 1

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "========================================"
echo "  ✅ 远程浏览器已就绪"
echo "  用户访问: http://${IP}:6080/vnc.html"
echo "  CDP: ws://${IP}:9223"
echo "========================================"
```

Make it executable: `chmod +x /root/start-remote-browser.sh`

### Step 6: Launch

```bash
bash /root/start-remote-browser.sh
```

### Step 7: Configure Auto-Start (systemd)

```bash
# Xvfb
cat > /etc/systemd/system/xvfb-remote.service <<'EOF'
[Unit]
Description=Xvfb virtual display :99
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -ac
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# x11vnc
cat > /etc/systemd/system/x11vnc-remote.service <<'EOF'
[Unit]
Description=x11vnc server on :99 (password protected)
After=xvfb-remote.service
Requires=xvfb-remote.service

[Service]
Type=simple
Environment=DISPLAY=:99
ExecStart=/usr/bin/x11vnc -display :99 -forever -shared -rfbauth /root/.vncpasswd -rfbport 5900 -quiet
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# noVNC
cat > /etc/systemd/system/novnc-remote.service <<'EOF'
[Unit]
Description=noVNC websockify on 6080
After=x11vnc-remote.service
Requires=x11vnc-remote.service

[Service]
Type=simple
ExecStart=/usr/local/bin/websockify --web=/opt/noVNC 6080 localhost:5900
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Chromium + CDP
CHROME_BIN=$(command -v chromium || command -v chromium-browser || command -v google-chrome-stable)
cat > /etc/systemd/system/chromium-remote.service <<EOF
[Unit]
Description=Chromium with CDP on :9223, display :99
After=xvfb-remote.service
Requires=xvfb-remote.service
StartLimitBurst=3
StartLimitInterval=120

[Service]
Type=simple
Environment=DISPLAY=:99
ExecStart=${CHROME_BIN} --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-session-crashed-bubble --restore-last-session=false --remote-debugging-port=9223 --remote-debugging-address=127.0.0.1 --remote-allow-origins=* --user-data-dir=/root/.chromium-remote --no-first-run --no-default-browser-check --window-size=1920,1080 --start-maximized about:blank
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now xvfb-remote.service x11vnc-remote.service novnc-remote.service chromium-remote.service
```

Verify:

```bash
systemctl is-active xvfb-remote x11vnc-remote novnc-remote chromium-remote
ss -tlnp | grep -E ':6080|:5900|:9223'
```


## Controlling the Browser via CDP

### Check available pages

```bash
curl -s http://127.0.0.1:9223/json | python3 -m json.tool
```

### Navigate to a URL (Python via websockets)

Use the Hermes venv (which has websockets installed):

```python
import json, urllib.request, asyncio

pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9223/json").read())
page = pages[0]
ws_url = page["webSocketDebuggerUrl"]

async def main():
    import websockets
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
            "params": {"url": "https://example.com"}}))
        # Wait for load
        for _ in range(30):
            msg = json.loads(await ws.recv())
            if msg.get("method") == "Page.frameStoppedLoading":
                break
        await asyncio.sleep(2)
        # Get current title
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
            "params": {"expression": "document.title"}}))
        for _ in range(5):
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                title = msg["result"]["result"]["value"]
                print(f"Loaded: {title}")
                break

asyncio.run(main())

### Navigate to a URL (Python via `websocket-client` — sync, no asyncio)

For terminal-based scripts (piped through `python3 << 'PYEOF'`), the sync `websocket-client` library is simpler:

```bash
pip install websocket-client --break-system-packages
```

```python
import json, http.client, websocket

conn = http.client.HTTPConnection("127.0.0.1", 9223)
conn.request("GET", "/json")
tabs = json.loads(conn.getresponse().read())
conn.close()

ws = websocket.create_connection(
    tabs[0]["webSocketDebuggerUrl"],
    header={"Origin": "http://127.0.0.1:9223"},  # Required to avoid 403!
    timeout=10
)

# Navigate
ws.send(json.dumps({"id": 1, "method": "Page.navigate",
    "params": {"url": "https://example.com"}}))
ws.recv()  # discard

import time; time.sleep(3)

# Evaluate JS
ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
    "params": {"expression": "document.title"}}))
resp = json.loads(ws.recv())
print(resp["result"]["result"]["value"])

# Get page text
ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
    "params": {"expression": "document.body.innerText.substring(0,3000)"}}))
resp = json.loads(ws.recv())
print(resp["result"]["result"]["value"][:1000])

ws.close()
```

**Important:** Always set `header={"Origin": "http://127.0.0.1:9223"}` — without it, Chrome returns a 403 Forbidden on the WebSocket handshake because of the `--remote-allow-origins=*` CORS check.

### Take a Screenshot

```python
import json, urllib.request, asyncio, base64

pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9223/json").read())
ws_url = pages[0]["webSocketDebuggerUrl"]

async def main():
    import websockets
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot",
            "params": {"format": "jpeg", "quality": 30}}))
        async for msg in ws:
            data = json.loads(msg)
            if data.get("id") == 1 and "result" in data:
                with open("/tmp/screenshot.jpg", "wb") as f:
                    f.write(base64.b64decode(data["result"]["data"]))
                print("Screenshot saved: /tmp/screenshot.jpg")
            return

asyncio.run(main())

**Sync version (websocket-client, no asyncio):**
```python
import json, http.client, websocket, base64

CDP_PORT = 9222  # verify: ss -tlnp | grep 922; may be 9223

conn = http.client.HTTPConnection("127.0.0.1", CDP_PORT)
conn.request("GET", "/json")
tabs = json.loads(conn.getresponse().read())
conn.close()

# Pick first real page (skip browser_ui / chrome:// tabs)
page = next((p for p in tabs if p["type"] == "page" and not p["url"].startswith("chrome://")), tabs[0])

ws = websocket.create_connection(
    page["webSocketDebuggerUrl"],
    header={"Origin": f"http://127.0.0.1:{CDP_PORT}"},
    timeout=30
)

ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot",
    "params": {"format": "jpeg", "quality": 30}}))

# Poll for response
for _ in range(10):
    resp = json.loads(ws.recv())
    if resp.get("id") == 1 and "result" in resp:
        with open("/tmp/screenshot.jpg", "wb") as f:
            f.write(base64.b64decode(resp["result"]["data"]))
        print("Saved: /tmp/screenshot.jpg")
        break

ws.close()
```

**Important**: When running from `execute_code` in Hermes, use `urllib.request` to read the CDP target list, then connect to the WebSocket. The Hermes venv (`/usr/local/lib/hermes-agent/venv/bin/python3`) has the `websockets` package installed. If running from system python, install it or set `sys.path` to point to the Hermes venv's site-packages.
**Important**: When running from `execute_code` in Hermes, use `urllib.request` to read the CDP target list, then connect to the WebSocket. The Hermes venv (`/usr/local/lib/hermes-agent/venv/bin/python3`) has the `websockets` package installed. If running from system python, install it or set `sys.path` to point to the Hermes venv's site-packages.

## Utility Script

See `references/cdp-utils.py` for reusable functions (navigate, screenshot, get page info).

## Cleaning Up

```bash
pkill -9 -f chromium
pkill -9 -f Xvfb
pkill -9 -f x11vnc
pkill -9 -f websockify
rm -rf /root/.chromium-remote   # fresh start next time
```

Or just run the startup script which auto-cleans before starting.

## Common Pitfalls

1. **noVNC page loads but shows blank/gray screen.** The Chromium start needs the `--window-size` flag to match Xvfb resolution. Check x11vnc is running (`ss -tlnp | grep 5900`). Verify password file exists (`/root/.vncpasswd`) — if missing, regenerate with Step 4.

2. **Running CDP WebSocket interactions — use `terminal()`, NOT `execute_code`.** 
   The `execute_code` sandbox does NOT have `websocket-client` installed (ModuleNotFoundError). Use `terminal()` with system Python instead:
   - **Sync (preferred for heredocs)**: `pip3 install websocket-client --break-system-packages`, then `python3 << 'PYEOF' ... PYEOF` with `import websocket` and `websocket.create_connection()`. No asyncio boilerplate needed.
   - **Async**: `pip3 install websockets --break-system-packages`, then `/usr/local/lib/hermes-agent/venv/bin/python3 << 'PYEOF' ... PYEOF` with `import websockets` and `async with websockets.connect(...)`.
   Both packages (`websocket-client` — sync, imported as `websocket`; `websockets` — async) are separate installs; typically only one is pre-installed on a given system. Check with `python3 -c "import websocket"` before assuming availability.

3. **CDP navigation times out.** The WebSocket connection may drop after large responses (screenshots >1MB). Handle screenshot responses with `async for` instead of positional `recv()` calls.

4. **DBus errors in Chromium output.** These are harmless in headless environments. The `ERROR:dbus/bus.cc` and `ERROR:google_apis/gcm/engine` messages can be ignored.

5. **Chromium user data dir conflicts.** If Chromium crashes on restart, delete the user data dir: `rm -rf /root/.chromium-remote`.

6. **Remote debugging address.** `--remote-debugging-address=0.0.0.0` exposes the CDP port to the network. Only use this if you need remote CDP access; for security, bind to `127.0.0.1` (default if omitted) and tunnel. **Do NOT expose port 9223 in firewall rules.**

7. **Screenshot quality.** JPEG quality=30 gives ~100-300KB files. For higher quality, use quality=80 or switch to PNG format (but PNG screenshots can exceed WebSocket message limits on large pages).

8. **Cleanup before restart.** Always `pkill -9` all processes before restarting. The previous Xvfb session on :99 will block a new one.

9. **Two Chromium instances: CDP vs Hermes browser tools.** Hermes Agent's built-in `browser_*` tools (`browser_navigate`, `browser_click`, `browser_snapshot`) use a **separate headless Chromium instance** (`--headless=new`, `--remote-debugging-port=0`). The visible noVNC browser (started by this skill) is a **completely different Chromium instance** with a real X11 display and CDP on `:9223`. This means:
   - **`browser_navigate` does NOT control the noVNC browser.** It navigates the Hermes-internal headless browser.
   - **CDP WebSocket (`ws://127.0.0.1:9223`) connects to the noVNC browser only.**
   - When the user says "I see X on noVNC" but `browser_snapshot` shows different content, you're looking at different browsers.
   - To control the noVNC browser programmatically, use raw CDP (Python via WebSocket to `:9223`), not the Hermes browser tools.
   - **Detection**: run `ps aux | grep chrom` — look for two Chromium processes, one with `--headless=new` (Hermes tools) and one without (noVNC browser). Check `curl -s http://127.0.0.1:<CDP_PORT>/json` for the noVNC instance's tabs (verify port first with `ss -tlnp | grep 922`).
   - **FIRST-RESPONSE RULE**: When the user says "I don't see that page on noVNC" after you navigated somewhere, your FIRST action must be: verify the actual CDP port with `ss -tlnp`, then re-navigate via CDP WebSocket. Do NOT try `browser_navigate` again — it controls the wrong browser.

10. **Captcha slider CPU spike.** Chinese site captcha iframes (ByteDance VerifyCenter) can keep rendering in an infinite loop when unsolved, consuming 35-40%+ CPU and making noVNC unresponsive.
    **Fix:** Kill the Chromium renderer process consuming high CPU (it's typically the renderer, not the browser process):
    ```bash
    ps aux --sort=-%cpu | head -5
    kill -9 <high-cpu-renderer-pid>
    ```
    The main browser stays alive; the page reloads on next navigation.

11. **Hermes browser_snapshot returns "(empty page)" after clicking.** This is NOT a blank page — it usually means one of two things:
   - **Page navigated to a new URL** (e.g., clicking "登录" redirected to a separate login page). Fix: call `browser_navigate` again to re-attach to the page, or use `browser_console` to check `document.title` and `window.location.href`.
   - **An iframe/overlay appeared** (e.g., captcha iframe from verify.zijieapi.com). The snapshot tool can't serialize cross-origin iframe content. Fix: use `browser_console` with JS expressions (`document.body.innerHTML.substring(0,2000)`, `document.querySelectorAll('iframe').length`) to inspect the actual DOM state. Or use `browser_vision` for a visual screenshot.
   See `references/chinese-site-login-captcha.md` for detailed workarounds.

12. **CDP WebSocket 403 "Origin not allowed".** First verify Chromium was started with `--remote-allow-origins=*`; old startup scripts may be missing it even if the skill template includes it. When using Python `websocket-client`, prefer `header=["Origin: http://127.0.0.1:9223"]` (or `suppress_origin=True` when appropriate) instead of a dict, because some versions can produce a duplicated Origin value such as `http://127.0.0.1:9223,http://127.0.0.1:9223`. For the async `websockets` library, pass the equivalent Origin header. If the error persists, patch the startup script and restart Chromium, not just the CDP client.

13. **CDP target selection: avoid Chrome internal tabs.** `/json` can return `browser_ui` targets such as `chrome://tab-search.top-chrome/`. Do not navigate or evaluate against these; the WebSocket may disconnect or behave oddly. Select a normal target with `type == "page"` and a non-`chrome://` URL, or create a new `about:blank` target via `PUT /json/new?about:blank` before navigating.

13b. **CDP port is NOT always 9223 — always verify first.** This skill's startup templates default to 9223, but the actual running instance may be on 9222 (as on this machine) or another port. Before ANY CDP operations, run:
   ```bash
   ss -tlnp | grep 922
   ```
   Then test: `curl -s http://127.0.0.1:<PORT>/json/version`. Getting "Connection refused" on 9223 means the instance is on a different port — try 9222. Also check with `ps aux | grep chromium | grep remote-debugging-port` to see the launch flag. Never assume the port; always verify.

14. **Partial stack recovery.** If `Xvfb`, `x11vnc`, and `websockify` are still running but Chromium/CDP died, you do not need to restart the entire stack. Start only Chromium on the existing display: `DISPLAY=:99 chromium --no-sandbox --disable-dev-shm-usage --disable-gpu --remote-debugging-port=9223 --remote-debugging-address=0.0.0.0 --remote-allow-origins='*' --window-size=1920,1080 --start-maximized --no-first-run --no-default-browser-check --user-data-dir=/root/.chromium-remote 'about:blank'`. Then verify `curl http://127.0.0.1:9223/json/version` and capture `DISPLAY=:99 import -window root /tmp/screenshot.png`.

15. **noVNC red error: `browserAsyncClipboardSupport` export missing.** This is usually caused by using a moving noVNC `master` checkout where Chrome caches one ES module version while websockify serves another. The most reliable fix is to pin noVNC to a stable release (tested: `v1.6.0`):
    ```bash
    pkill -TERM -f 'websockify --web /opt/noVNC 6080' || true
    cd /opt/noVNC
    git reset --hard
    git clean -fd
    git checkout v1.6.0
    websockify --web /opt/noVNC 6080 127.0.0.1:5900
    ```

16. **OOM kill + Restart=always death spiral (tabs multiply exponentially).** On low-memory servers (2H4G and below), Chromium may get OOM-killed. If `Restart=always` is set in the systemd unit, systemd restarts Chromium immediately. On restart, Chromium's `--user-data-dir` restores the previous session (all open tabs), while the `ExecStart` URL argument opens yet another tab. If OOM kills it again, the cycle repeats, doubling or tripling tabs each time. **Fix**: (a) Change `Restart=always` to `Restart=on-failure`. (b) Add a circuit breaker: `StartLimitBurst=3` and `StartLimitInterval=120` in `[Unit]`. (c) Add `--disable-session-crashed-bubble` and `--restore-last-session=false` to Chromium flags.

## Verification Checklist

- [ ] `curl -s http://127.0.0.1:9223/json/version` returns Chromium version info
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:6080/vnc.html` returns 200
- [ ] `ss -tlnp | grep -E '5900|6080|9223'` shows all three ports listening
- [ ] NoVNC page loads in user's browser at `http://<public-IP>:6080/vnc.html`
- [ ] noVNC password from `/root/.novnc_password` works
- [ ] CDP navigation succeeds and `document.title` returns the expected page
- [ ] systemd services are active: `systemctl is-active xvfb-remote x11vnc-remote novnc-remote chromium-remote`

## One-Shot Recipes

**"Set up the whole stack from scratch"**
```bash
apt update && apt install -y xvfb x11vnc chromium git python3-pip
cd /opt && git clone https://github.com/novnc/noVNC.git
pip3 install websockify --break-system-packages
# Then create and run the startup script above
```

**"Take a screenshot of the current page"** → use the Python snippet above.

**"Navigate to a URL"** → use the Python CDP navigate snippet above.

**"Restart everything clean"** → run the startup script again.

## Additional CDP Automation Patterns

### React / SPA Form Filling
React-controlled inputs ignore direct `.value` assignment. Use the native setter + event dispatch pattern (see `references/cdp-dom-interaction.md`). For Alpine.js forms, see `references/alpine-and-github.md`.

### Mouse Click via CDP
When JavaScript `.click()` doesn't trigger handlers (Vue `@click`, React synthetic events), use `Input.dispatchMouseEvent` with `mousePressed` + `mouseReleased` at the element's center coordinates.

**IMPORTANT — re-query position each time:** Elements move as content is added/removed. Always re-run `getBoundingClientRect()` before each click. Negative coordinates (`y < 0`) mean the element is scrolled above the viewport — use `scrollIntoView({block:'center'})` first.

### Vue SPA Shared-Form Pattern
Some Vue SPAs (QQ bot platform, Tencent Cloud editors) use a **shared form panel**: only one item's data is shown at a time. Clicking an item's header selects it and loads its data into the form. Pattern:
1. Click item N's header → form shows item N's data
2. Fill/change the form values
3. Click item N+1's header → form auto-switches to item N+1
4. Repeat for all items
5. Click "Save" ONCE at the end

### Reverse Image Search
Upload local images to Bing/Sogou/Yandex via CDP `DOM.setFileInputFiles`. See `references/reverse-image-search.md` for full per-engine recipes.

### Site-Specific Recipes
- **QQ机器人管理端 (功能配置/指令)** → `references/qq-bot-platform.md`
- **番茄小说作家后台** → `references/fanqienovel-writer.md`
- **腾讯云开发者社区编辑器** → `references/tencent-cloud-editor.md`
- **GitHub PAT extraction & Alpine.js forms** → `references/alpine-and-github.md`

### SPA Content Extraction
For fully client-rendered pages (ChatGPT/Claude share links, Notion), navigate the visible CDP browser, wait for hydration, then extract via `Runtime.evaluate`. See `scripts/extract_spa_content.py` for a drop-in helper.

### Completion Reply Template for noVNC Setup
When you install/start the noVNC + Chromium stack for a user, the final reply should actively include:
1. **Server sizing** — recommend at least 2 CPU / 4 GB RAM; warn that lower specs may cause white screens or OOM kills.
2. **noVNC URL** — prefer the server's public IPv4: `http://<public-ip>:6080/vnc.html`.
3. **Screenshot** — attach a current `DISPLAY=:99 import -window root` screenshot as media when the channel supports it.
4. **Port reminders** — `6080/tcp` is required; `5900/tcp` and `9222/tcp` are optional and should be source-restricted if exposed.
