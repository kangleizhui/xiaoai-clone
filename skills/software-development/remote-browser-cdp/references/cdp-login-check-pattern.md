# CDP Login Check Pattern

## Problem

You need to determine whether a user is logged into a web service (e.g., Douyin Creator Platform, Toutiao Writer) via CDP.

## Solution: 5-Heuristic Check

Instead of looking for a single indicator, run multiple checks via `Runtime.evaluate`:

```python
checks = [
    # 1. User avatar/info element exists
    'document.querySelector(".account-info") !== null || '
    'document.querySelector(".user-info") !== null || '
    'document.querySelector("[class*=user]") !== null',
    
    # 2. Current URL (login pages have different URLs)
    'window.location.href',
    
    # 3. Page body text (look for username, nickname, account info)
    'document.body.innerText.substring(0, 5000)',
    
    # 4. Cookies (passport_, session, token keywords)
    'document.cookie',
    
    # 5. Login button visibility
    'document.body.innerText.includes("登录") || document.body.innerText.includes("Login")',
]

for i, expr in enumerate(checks):
    await ws.send(json.dumps({"id": i+1, "method": "Runtime.evaluate",
        "params": {"expression": expr}}))
```

## Interpretation

| check_1 | check_5 | body text | Cookies | Verdict |
|---------|---------|-----------|---------|---------|
| True | False | Shows nickname/avatar | Has passport_/session cookies | ✅ **Logged in** |
| False | True | Shows login form | No session cookies | ❌ **Not logged in** |
| True | True | Mixed | Has some cookies | ⚠️ **Ambiguous** — inspect deeper |

## Full Example (Douyin)

```python
async with websockets.connect(ws_url) as ws:
    checks = [
        'document.querySelector(".account-info") !== null || '
        'document.querySelector(".user-info") !== null || '
        'document.querySelector("[class*=user]") !== null || '
        'document.querySelector("[class*=avatar]") !== null',
        'window.location.href',
        'document.body.innerText.substring(0, 5000)',
        'document.cookie',
        'document.body.innerText.includes("登录") || '
        'document.body.innerText.includes("Login")',
    ]
    for i, expr in enumerate(checks):
        await ws.send(json.dumps({"id": i+1, "method": "Runtime.evaluate",
            "params": {"expression": expr}}))

    results = {}
    for i in range(len(checks)):
        async for msg in ws:
            data = json.loads(msg)
            if data.get("id") == i+1 and "result" in data:
                r = data["result"]["result"]
                results[f"check_{i+1}"] = r["value"] if r["type"] == "string" else str(r)
                break
    
    if results.get("check_1") == "True" and results.get("check_5") == "False":
        print("✅ User is logged in")
    elif results.get("check_5") == "True":
        print("❌ User is NOT logged in")
    else:
        print("⚠️ Status ambiguous, inspect manually")
```

## Key Insight

The most reliable single indicator is **check_1=True AND check_5=False** — user elements exist AND no login button is visible. Cookie inspection confirms the conclusion.
