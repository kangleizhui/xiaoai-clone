# CDP Screenshot Tips

## The "Message too large" Problem

When taking screenshots via CDP WebSocket, large pages produce PNG screenshots
that can exceed the 1MB WebSocket message limit, causing:
```
websockets.exceptions.ConnectionClosedError: sent 1009 (message too big)
```

## Fixes

### 1. Use JPEG with quality=30 (recommended)
JPEG compression at quality 30 produces ~100-300KB files vs 1-5MB for PNG.

```python
await ws.send(json.dumps({
    "id": 1,
    "method": "Page.captureScreenshot",
    "params": {"format": "jpeg", "quality": 30}
}))
```

### 2. Use async for instead of positional recv
When the response might be large, iterate with `async for msg in ws:`
instead of `await ws.recv()` to handle streaming:

```python
async with websockets.connect(ws_url) as ws:
    await ws.send(json.dumps({
        "id": 1,
        "method": "Page.captureScreenshot",
        "params": {"format": "jpeg", "quality": 30}
    }))
    async for msg in ws:
        data = json.loads(msg)
        if data.get("id") == 1 and "result" in data:
            import base64
            with open("/tmp/screenshot.jpg", "wb") as f:
                f.write(base64.b64decode(data["result"]["data"]))
            print("OK")
            return
```

### 3. Increase websocket max_size
If you must use PNG, increase the WebSocket limit:
```python
async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
```
But JPEG is more reliable.

## 4. Alternative: ImageMagick Screenshot via X11

When CDP screenshot fails or times out (e.g., on very large pages or unstable WebSocket connections), use ImageMagick's `import` command to capture the X11 display directly:

```bash
# Install
apt-get install -y imagemagick

# Capture the full X11 display (:99)
DISPLAY=:99 import -window root /tmp/screenshot.png
```

**When to use this instead of CDP:**
- CDP screenshot returns "message too big" despite JPEG compression
- WebSocket connection to CDP is unstable or timing out
- You need a screenshot of the entire X11 desktop (not just the browser tab)
- The browser page contains cross-origin iframes that CDP can't capture

**Limitations:**
- Needs `imagemagick` installed (`apt-get install -y imagemagick`)
- Can only capture what's visible on the virtual display (no off-screen content)
- Slower than CDP (~1-2 seconds vs ~200ms)
- Only works with X11 display (not headless Chromium)
- File is saved to the server filesystem, not returned as base64 — share with user via `MEDIA:/path/to/file` in your response
