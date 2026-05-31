#!/usr/bin/env python3
"""
Extract content from a JS-rendered SPA page via CDP.

Use this when curl returns an empty shell because the page is fully client-side
rendered (ChatGPT shares, Notion pages, Next.js SPAs, etc.) AND the Hermes
internal browser_navigate/snapshot tools can't see the post-hydration DOM.

Prereqs:
  - Visible Chromium running on DISPLAY=:99 with --remote-debugging-port=9222
  - websockets pip package installed
  - Page already navigated to the target URL (and 8-12s elapsed for hydration)

Usage:
  # 1) launch (background, then sleep)
  DISPLAY=:99 chromium --remote-debugging-port=9222 \\
      --user-data-dir=/root/.chromium-remote --no-sandbox \\
      --disable-dev-shm-usage --window-size=1920,1080 \\
      "https://chatgpt.com/share/<id>"
  sleep 10

  # 2) find page ws url
  PAGE_WS=$(curl -s http://127.0.0.1:9222/json | python3 -c "
import json, sys
for t in json.load(sys.stdin):
    if t.get('type')=='page' and 'YOUR-DOMAIN' in t.get('url',''):
        print(t['webSocketDebuggerUrl']); break")

  # 3) extract
  python3 extract_spa_content.py "$PAGE_WS"

Customize SELECTORS for your target page.
"""
import json
import sys
import asyncio

try:
    import websockets
except ImportError:
    print("pip install websockets", file=sys.stderr)
    sys.exit(1)

WS_URL = sys.argv[1] if len(sys.argv) > 1 else None
if not WS_URL:
    print("Usage: extract_spa_content.py <page_ws_url>", file=sys.stderr)
    sys.exit(1)

# Customize for your target site. Each selector returns (role, text) pairs.
# Defaults below match ChatGPT share pages.
SELECTORS_JS = r"""
(function() {
    // ChatGPT share page
    const turns = document.querySelectorAll('[data-message-author-role]');
    if (turns.length > 0) {
        return {
            kind: 'chatgpt',
            messages: Array.from(turns).map(t => ({
                role: t.getAttribute('data-message-author-role'),
                text: t.innerText
            }))
        };
    }
    // Generic article / blog
    const article = document.querySelector('article');
    if (article) {
        return { kind: 'article', text: article.innerText };
    }
    // Fallback: body text (capped)
    return { kind: 'fallback', text: document.body.innerText.substring(0, 30000) };
})()
"""

# JS that dismisses common interrupters (cookie banners, restore-tabs, modals)
PREPARE_JS = r"""
(function() {
    const labels = ['accept','reject','got it','agree','dismiss','close','no thanks','x'];
    document.querySelectorAll('button').forEach(b => {
        const t = (b.innerText || '').trim().toLowerCase();
        if (labels.some(l => t === l || t.includes(l))) {
            try { b.click(); } catch(e) {}
        }
    });
    // Scroll to bottom to trigger lazy-load
    window.scrollTo(0, document.body.scrollHeight);
    const main = document.querySelector('main') || document.body;
    main.scrollTop = main.scrollHeight;
})()
"""

async def main():
    # max_size=50MB: ChatGPT transcripts can blow past 1 MB default
    async with websockets.connect(WS_URL, max_size=50_000_000) as ws:
        msg_id = 0
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            cid = msg_id
            await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == cid:
                    return resp.get("result", {})

        # Dismiss banners / scroll to bottom
        await send("Runtime.evaluate", {"expression": PREPARE_JS})
        await asyncio.sleep(2)

        # Extract
        result = await send("Runtime.evaluate", {
            "expression": SELECTORS_JS,
            "returnByValue": True,
        })
        value = result.get("result", {}).get("value", {})
        print(json.dumps(value, ensure_ascii=False, indent=2))

asyncio.run(main())
