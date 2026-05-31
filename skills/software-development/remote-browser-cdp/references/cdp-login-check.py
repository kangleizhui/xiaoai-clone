"""
CDP Login Status Detection
Use to check if a user is logged into a web app via CDP.
Requires: websockets package (Hermes venv has it)
"""

import json, urllib.request, asyncio

def get_ws_url():
    pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
    return pages[0]["webSocketDebuggerUrl"]

async def main():
    import websockets
    ws_url = get_ws_url()
    async with websockets.connect(ws_url) as ws:
        checks = [
            ("document.querySelector('.user-info, .account-info, [class*=avatar]') !== null", "user_element"),
            ("window.location.href", "url"),
            ("document.body.innerText.substring(0, 5000)", "body_text"),
            ("document.cookie", "cookies"),
            ("document.body.innerText.includes('\u767b\u5f55') || document.body.innerText.includes('Login')", "has_login"),
        ]
        for i, (expr, name) in enumerate(checks, 1):
            await ws.send(json.dumps({"id": i, "method": "Runtime.evaluate", "params": {"expression": expr}}))
        results = {}
        for i in range(1, len(checks) + 1):
            async for msg in ws:
                data = json.loads(msg)
                if data.get("id") == i and "result" in data:
                    r = data["result"]["result"]
                    results[checks[i-1][1]] = r["value"][:2000] if r["type"] == "string" else r["value"]
                    break
        has_user = results.get("user_element") == True
        has_login = results.get("has_login") == True
        print(f"URL: {results.get('url', '?')}")
        print(f"User element: {has_user} | Login button: {has_login}")
        if has_user and not has_login:
            print("STATUS: Logged in")
        elif has_login and not has_user:
            print("STATUS: Not logged in")
        else:
            print("STATUS: Unknown")

if __name__ == "__main__":
    asyncio.run(main())
