"""
CDP Utility functions for controlling a remote Chromium browser.

Usage:
    from cdp_utils import CdpBrowser
    
    browser = CdpBrowser("http://127.0.0.1:9222")
    info = browser.get_info()
    print(info["Browser"])
    
    browser.navigate("https://example.com")
    title = browser.get_title()
    print(f"Loaded: {title}")
    
    browser.screenshot("/tmp/ss.jpg", format="jpeg", quality=30)
"""

import json, urllib.request, asyncio, base64
from typing import Optional


class CdpBrowser:
    """Control a Chromium browser via Chrome DevTools Protocol."""

    def __init__(self, cdp_http: str = "http://127.0.0.1:9222"):
        self.cdp_http = cdp_http.rstrip("/")

    def get_info(self) -> dict:
        """Get browser version info."""
        resp = urllib.request.urlopen(f"{self.cdp_http}/json/version")
        return json.loads(resp.read())

    def list_pages(self) -> list[dict]:
        """List all open pages/tabs."""
        resp = urllib.request.urlopen(f"{self.cdp_http}/json")
        return json.loads(resp.read())

    def navigate(self, url: str, timeout: int = 15) -> str:
        """Navigate the active page to a URL. Returns the page title."""
        pages = self.list_pages()
        ws_url = pages[0]["webSocketDebuggerUrl"]
        title = asyncio.run(self._navigate_ws(ws_url, url, timeout))
        return title

    @staticmethod
    async def _navigate_ws(ws_url: str, url: str, timeout: int) -> str:
        import websockets
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "id": 1, "method": "Page.navigate", "params": {"url": url}
            }))
            # Wait for page to load
            for _ in range(timeout * 2):
                msg = json.loads(await ws.recv())
                if msg.get("method") == "Page.frameStoppedLoading":
                    break
            await asyncio.sleep(2)
            # Get title
            await ws.send(json.dumps({
                "id": 2, "method": "Runtime.evaluate",
                "params": {"expression": "document.title"}
            }))
            for _ in range(5):
                msg = json.loads(await ws.recv())
                if msg.get("id") == 2:
                    return msg["result"]["result"]["value"]
            return ""

    def screenshot(self, path: str = "/tmp/screenshot.jpg",
                   format: str = "jpeg", quality: int = 30):
        """Take a screenshot of the current page."""
        pages = self.list_pages()
        ws_url = pages[0]["webSocketDebuggerUrl"]
        asyncio.run(self._screenshot_ws(ws_url, path, format, quality))

    @staticmethod
    async def _screenshot_ws(ws_url: str, path: str,
                              format: str, quality: int):
        import websockets
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "id": 1, "method": "Page.captureScreenshot",
                "params": {"format": format, "quality": quality}
            }))
            async for msg in ws:
                data = json.loads(msg)
                if data.get("id") == 1 and "result" in data:
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data["result"]["data"]))
                    return

    def evaluate(self, js: str) -> str:
        """Run JavaScript in the page context and return the result."""
        pages = self.list_pages()
        ws_url = pages[0]["webSocketDebuggerUrl"]
        return asyncio.run(self._evaluate_ws(ws_url, js))

    @staticmethod
    async def _evaluate_ws(ws_url: str, js: str) -> str:
        import websockets
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "id": 1, "method": "Runtime.evaluate",
                "params": {"expression": js}
            }))
            async for msg in ws:
                data = json.loads(msg)
                if data.get("id") == 1 and "result" in data:
                    return data["result"].get("result", {}).get("value", "")

    def get_title(self) -> str:
        """Get the current page title."""
        return self.evaluate("document.title")

    def get_url(self) -> str:
        """Get the current page URL."""
        return self.evaluate("window.location.href")


# --- Quick CLI usage ---
if __name__ == "__main__":
    import sys
    b = CdpBrowser()
    info = b.get_info()
    print(f"Browser: {info['Browser']}")
    print(f"Protocol: {info['Protocol-Version']}")

    if len(sys.argv) > 1 and sys.argv[1] == "navigate":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://example.com"
        title = b.navigate(url)
        print(f"Navigated to: {title}")
        b.screenshot("/tmp/screenshot.jpg")
        print("Screenshot: /tmp/screenshot.jpg")
