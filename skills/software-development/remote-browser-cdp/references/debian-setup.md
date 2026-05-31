# Sample Deploy: noVNC + Chromium Remote Browser on Debian 13

## Environment
- OS: Debian 13 (trixie), x86_64
- Chromium: 148.0.7778.167
- noVNC: latest from git (github.com/novnc/noVNC)
- websockify: 0.13.0
- Server IP: 10.7.0.15 (private), 101.32.98.240 (public - Tencent Cloud)

## Architecture
```
Chromium (:9222) → Xvfb (:99) → x11vnc (:5900) → websockify/noVNC (:6080)
```

## Key Ports
| Port | Bind | Component |
|------|------|-----------|
| 9222 | 0.0.0.0 | CDP (DevTools Protocol) |
| 5900 | 127.0.0.1 | VNC (x11vnc) |
| 6080 | 0.0.0.0 | noVNC web UI |

## Firewall Setup
Both cloud security group AND server firewall must allow port 6080:

```bash
# UFW
ufw allow 6080/tcp
ufw allow 9222/tcp   # optional — remote CDP access
ufw reload

# If using iptables and default INPUT policy is DROP:
iptables -A INPUT -p tcp --dport 6080 -j ACCEPT
iptables -A INPUT -p tcp --dport 9222 -j ACCEPT
```

## Files Created
- `/root/start-remote-browser.sh` — startup script
- `/root/.chromium-remote/` — browser user data dir (auto-created)

## Commands Used

### Install deps
```bash
apt update && apt install -y xvfb x11vnc chromium git python3-pip
```

### Install noVNC + websockify
```bash
cd /opt && git clone https://github.com/novnc/noVNC.git
pip3 install websockify --break-system-packages
```

### Launch (with --remote-allow-origins=* for CDP websocket access)
```bash
bash /root/start-remote-browser.sh
```

**Note:** The startup script includes `--remote-allow-origins=*` so CDP WebSocket connections (e.g., from Python `websockets` library) won't get 403 Forbidden.

### Verify
```bash
curl -s http://127.0.0.1:9222/json/version
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:6080/vnc.html
ss -tlnp | grep -E '5900|6080|9222'
```

### Navigate via CDP
```python
import json, urllib.request, asyncio
pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
ws_url = pages[0]["webSocketDebuggerUrl"]

async def main():
    import websockets
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id":1,"method":"Page.navigate",
            "params":{"url":"https://creator.douyin.com/"}}))
        for _ in range(30):
            msg = json.loads(await ws.recv())
            if msg.get("method") == "Page.frameStoppedLoading":
                break
        await asyncio.sleep(2)
        await ws.send(json.dumps({"id":2,"method":"Runtime.evaluate",
            "params":{"expression":"document.title"}}))
        for _ in range(5):
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                print(msg["result"]["result"]["value"])
                break

asyncio.run(main())
```

### Screenshot via CDP
```python
import json, urllib.request, asyncio, base64
pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
ws_url = pages[0]["webSocketDebuggerUrl"]

async def main():
    import websockets
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id":1,"method":"Page.captureScreenshot",
            "params":{"format":"jpeg","quality":30}}))
        async for msg in ws:
            data = json.loads(msg)
            if data.get("id") == 1 and "result" in data:
                with open("/tmp/ss.jpg","wb") as f:
                    f.write(base64.b64decode(data["result"]["data"]))
                print("OK")
                return

asyncio.run(main())
```

### Clean restart
```bash
pkill -9 -f chromium; pkill -9 -f Xvfb; pkill -9 -f x11vnc; pkill -9 -f websockify
rm -rf /root/.chromium-remote
bash /root/start-remote-browser.sh
```

## Security Notes
- CDP port :9222 is exposed on 0.0.0.0 — anyone who can reach it can control the browser
- noVNC port :6080 has no password (`-nopw` flag)
- For production: add VNC password (`-passwd` flag), restrict CDP to localhost + SSH tunnel
- Tencent Cloud security group needs inbound rules for :6080 and :9222
