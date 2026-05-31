# CDP DOM Interaction Patterns

Techniques for finding, clicking, typing into, and reading elements on pages controlled via Chrome DevTools Protocol (CDP).

## Prerequisites

All snippets assume:
```python
import json, urllib.request, asyncio, base64
import sys
sys.path.insert(0, '/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages')
import websockets

pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
ws_url = pages[0]["webSocketDebuggerUrl"]
```

## 1. Finding Elements by Text Content

### Find a button/link by exact text
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    Array.from(document.querySelectorAll('*')).filter(el => 
        el.children.length === 0 && el.textContent.trim() === '登录'
    ).map(el => ({
        tag: el.tagName,
        className: el.className?.substring(0,100),
        x: el.getBoundingClientRect().x,
        y: el.getBoundingClientRect().y,
        w: el.getBoundingClientRect().width,
        h: el.getBoundingClientRect().height
    }))
    """
}}))
```

### Find all input fields and buttons
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (() => {
        const results = [];
        document.querySelectorAll('input').forEach(el => {
            const r = el.getBoundingClientRect();
            results.push({
                type: 'INPUT',
                placeholder: el.placeholder,
                name: el.name,
                className: el.className?.substring(0,60),
                visible: r.width > 0 && r.height > 0
            });
        });
        document.querySelectorAll('button').forEach(el => {
            results.push({
                type: 'BUTTON',
                text: el.textContent?.trim()?.substring(0,30),
                className: el.className?.substring(0,60),
            });
        });
        return JSON.stringify(results);
    })()
    """
}}))
```

## 2. Clicking Elements

### Click by class name
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    document.querySelector('.slogin-user-avatar__buttons__item').click()
    """
}}))
```

### Click by text content (scan all elements)
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (() => {
        const all = document.querySelectorAll('*');
        for(const el of all) {
            if(el.children.length === 0 && el.textContent.trim() === '登录') {
                el.click();
                return 'clicked';
            }
        }
        return 'not found';
    })()
    """
}}))
```

## 3. Typing into Input Fields (React/SPA apps)

React and other SPA frameworks intercept native input events. A standard `el.value = '...'` won't trigger the framework's change detection. Use the **nativeInputValueSetter** trick:

```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (() => {
        const input = document.querySelector('input[placeholder="手机号"]');
        if(!input) return 'not found';
        // Get native setter to bypass React's synthetic event wrapper
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSetter.call(input, '16607657595');
        // Dispatch both input and change events for the framework to pick up
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return 'ok';
    })()
    """
}}))
```

### After typing, verify input value
```python
await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
    "expression": "document.querySelector('input[placeholder=\"手机号\"]').value"
}}))
```

## 4. Reading Page Content

### Get full visible text (first N chars)
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "document.body.innerText.substring(0, 3000)"
}}))
```

### Check for specific text on page
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "document.body.innerText.includes('登录') ? 'login page' : 'no login text'"
}}))
```

### Get HTML snippet for debugging
```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "document.body.innerHTML.substring(0, 5000)"
}}))
```

## 5. Rich Text Editor (ProseMirror / contenteditable) Interaction

Many web platforms (fanqienovel writer backend, Medium, etc.) use ProseMirror or similar contenteditable editors. The editable element is usually a div with `class="ProseMirror"` and `contentEditable`.

### 5.1 Finding the editor element

```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "document.querySelectorAll('[contenteditable]').length"
}}))

# Or find all editable elements with details
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    Array.from(document.querySelectorAll('[contenteditable], textarea')).map(el => ({
        tag: el.tagName,
        class: (el.className || '').substring(0, 60),
        id: el.id || '',
        textLength: (el.textContent || el.value || '').length,
        visible: el.getBoundingClientRect().width > 0
    }))
    """
}}))
```

### 5.2 Inserting HTML content into ProseMirror (innerHTML approach)

For short content (< 2000 chars), `innerHTML` + `input` event usually works:

```python
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (() => {
        const pm = document.querySelector('.ProseMirror');
        if(!pm) return 'ProseMirror not found';
        pm.innerHTML = '<p>Paragraph 1</p><p>Paragraph 2</p>';
        pm.dispatchEvent(new Event('input', {bubbles: true}));
        return 'inserted, len=' + pm.textContent.length;
    })()
    """
}}))
```

**NOTE:** For long content, `innerHTML` may not trigger ProseMirror's internal state sync reliably. The word counter and save button may not update. Use `execCommand('insertHTML')` instead (see 5.4).

### 5.3 Inserting Large UTF-8 Content (Base64 + TextDecoder + execCommand)

This is the **most reliable pattern** for long Chinese/UTF-8 content (tested with 10K+ chars). Uses three steps:

#### Step 1: Store content as base64 in a global variable

```python
import base64

with open('/path/to/chapter.md', 'r', encoding='utf-8') as f:
    content = f.read()

b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')

ws.send(json.dumps({
    "id": 1, "method": "Runtime.evaluate",
    "params": {"expression": "window.__hermesB64 = '" + b64 + "';"}
}))
# Wait for response
resp = json.loads(ws.recv())
```

**Why base64?** Passing multi-byte UTF-8 text directly in a JS string literal via `Runtime.evaluate` causes mojibake (Chinese chars become garbage). Base64 encoding keeps the text ASCII-safe for transit.

**Why a global variable?** `Runtime.callFunctionOn` with large string arguments (10K+) frequently times out over WebSocket. Storing data in a global variable via `Runtime.evaluate`, then referencing it from a second call, avoids this entirely.

#### Step 2: Clear the editor

```python
ws.send(json.dumps({
    "id": 2, "method": "Runtime.evaluate",
    "params": {"expression": """
    (function() {
        var editor = document.querySelector('.ProseMirror');
        if (!editor) return 'no editor';
        editor.focus();
        document.execCommand('selectAll');
        document.execCommand('delete');
        return 'cleared, len=' + editor.textContent.length;
    })()
    """}
}))
```

#### Step 3: Decode UTF-8 and insert via execCommand

```python
ws.send(json.dumps({
    "id": 3, "method": "Runtime.evaluate",
    "params": {"expression": """
    (function() {
        var editor = document.querySelector('.ProseMirror');
        if (!editor) return 'no editor';
        editor.focus();
        document.execCommand('selectAll');
        document.execCommand('delete');

        // Decode UTF-8 base64 properly
        try {
            var binary = atob(window.__hermesB64);
            var bytes = new Uint8Array(binary.length);
            for (var i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            var decoder = new TextDecoder('utf-8');
            var text = decoder.decode(bytes);
        } catch(e) {
            return 'decode error: ' + e.message;
        }

        // Convert newlines to HTML for ProseMirror
        // double newline = paragraph break, single newline = line break within paragraph
        var paras = text.split('\\n\\n');
        var html = '<p>' + paras.map(function(p) {
            return p.replace(/\\n/g, '<br>');
        }).join('</p><p>') + '</p>';

        var success = document.execCommand('insertHTML', false, html);
        return 'insertHTML=' + success + ' textLen=' + editor.textContent.length;
    })()
    """}
}))
```

**Why `execCommand('insertHTML')` instead of `innerHTML`?** ProseMirror has an internal state machine. Setting `innerHTML` directly can cause a mismatch between the DOM and ProseMirror's state — the displayed text looks correct, but `editor.textContent.length` and the word counter stay at 0 or a small number. `execCommand('insertHTML')` goes through ProseMirror's input pipeline and correctly updates both DOM and internal state.

**Why `TextDecoder('utf-8')`?** `atob()` alone decodes bytes as Latin-1, not UTF-8. Chinese characters will display as garbled multi-byte fragments without the `TextDecoder` step.

### 5.4 Verifying content insertion

Check the page's own character/word counter if available:

```python
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "document.querySelector('.publish-header-count')?.textContent"
}}))
```

Or check the editor directly:

```python
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": "(function(){var e=document.querySelector('.ProseMirror');return {len: e.textContent.length, start: e.textContent.substring(0,50)};})()"
}}))
```

### 5.5 Finding and clicking save/submit buttons

```python
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (function() {
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var t = buttons[i].textContent.trim();
            if (t === '存草稿' || t === '保存' || t.includes('发布')) {
                buttons[i].click();
                return 'clicked: ' + t;
            }
        }
        return 'not found';
    })()
    """
}}))
```

### 5.6 Handling version conflict / save conflict dialogs

Many platforms detect simultaneous editing. When saving triggers a "版本冲突" (version conflict) dialog with choices like "选择云端版本" / "继续编辑本地":

```python
# Click "继续编辑本地" to keep your changes
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (function() {
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var t = buttons[i].textContent.trim();
            if (t === '继续编辑本地') {
                buttons[i].click();
                return 'kept local: ' + t;
            }
            if (t === '选择云端版本') {
                buttons[i].click();
                return 'using cloud: ' + t;
            }
        }
        return 'no conflict dialog buttons';
    })()
    """
}}))
```

After resolving the conflict, click save again:

```python
time.sleep(2)
ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
    "expression": """
    (function() {
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim() === '存草稿') {
                buttons[i].click();
                return 'saved';
            }
        }
        return 'save button not found';
    })()
    """
}}))
```

Then check for a success toast:

```python
ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {
    "expression": """
    Array.from(document.querySelectorAll('[class*=success],[class*=toast],[class*=message]'))
        .map(el => el.textContent.trim())
        .filter(t => t.length > 0 && t.length < 100)
    """
}}))
```

### 5.7 Finding all interactive elements on a page

When you need to discover what buttons and inputs are available (useful for unfamiliar pages):

```python
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
    "expression": """
    (function() {
        var buttons = document.querySelectorAll('button, a, [role=button], .arco-btn, .btn');
        var result = [];
        for (var i = 0; i < buttons.length; i++) {
            var b = buttons[i];
            var rect = b.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && rect.width < 500) {
                result.push({
                    tag: b.tagName,
                    text: (b.textContent || '').trim().substring(0, 30),
                    class: (b.className || '').substring(0, 80),
                    id: b.id || '',
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height)
                });
            }
        }
        return result;
    })()
    """
}}))
```

### Common ProseMirror pitfalls

- **`textContent` doesn't work**: Inserting plain text loses paragraph structure. Always use `innerHTML` with `<p>` tags or `execCommand('insertHTML')`.
- **Missing `input` event**: The editor's word counter won't update unless you dispatch an `input` event after setting innerHTML. With `execCommand('insertHTML')` this happens automatically.
- **Multiple ProseMirror instances**: Some pages have one for title and one for body. Find the right one by checking parent container class or text content length.
- **`Input.insertText` CDP method only inserts one paragraph**: Chrome DevTools' `Input.insertText` will only produce a single `<p>` element in ProseMirror, losing all paragraph breaks after the first one. Always use the JavaScript `execCommand('insertHTML')` pattern for multi-paragraph content.
- **`Runtime.callFunctionOn` times out with large string args**: If you pass a function and a large string argument via `callFunctionOn`, the WebSocket connection can time out waiting for the response. Always store large data in a global variable first via `Runtime.evaluate`, then call a function that reads that variable.
- **ProseMirror's trailing break**: ProseMirror always adds a `<br class="ProseMirror-trailingBreak">` at the end of an empty paragraph. This is expected — don't try to remove it.
- **Special characters in JS strings**: Backticks, dollar signs, and template literal syntax inside your content will break `Runtime.evaluate` JS expressions. Base64 encoding avoids ALL escaping issues.

## 6. Combining: Full Login Flow Pattern

A complete login flow for a Chinese web platform (React-based, phone + SMS code):

```python
import json, urllib.request, asyncio, base64
sys.path.insert(0, '/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages')
import websockets

pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
ws_url = pages[0]["webSocketDebuggerUrl"]

async def login(phone, code):
    async with websockets.connect(ws_url) as ws:
        # 1. Check current page and find login button
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": """
            (() => {
                const all = document.querySelectorAll('*');
                for(const el of all) {
                    if(el.children.length === 0 && el.textContent.trim() === '登录')
                        { el.click(); return 'clicked login'; }
                }
                return 'login not found';
            })()
            """
        }}))
        for _ in range(5):
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1: break
        
        await asyncio.sleep(2)
        
        # 2. Enter phone number
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
            "expression": f"""
            (() => {{
                const input = document.querySelector('input[placeholder*="手机"]');
                if(!input) return 'no phone input';
                const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                s.call(input, '{phone}');
                input.dispatchEvent(new Event('input', {{bubbles:true}}));
                input.dispatchEvent(new Event('change', {{bubbles:true}}));
                return 'phone set: ' + input.value;
            }})()
            """
        }}))
        for _ in range(5):
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                print(msg["result"]["result"]["value"])
                break
        
        # 3. If code provided, enter it and click submit
        if code:
            await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {
                "expression": f"""
                (() => {{
                    const input = document.querySelector('input[placeholder*="验证码"]');
                    if(!input) return 'no code input';
                    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    s.call(input, '{code}');
                    input.dispatchEvent(new Event('input', {{bubbles:true}}));
                    input.dispatchEvent(new Event('change', {{bubbles:true}}));
                    return 'code set: ' + input.value;
                }})()
                """
            }}))
            for _ in range(5):
                msg = json.loads(await ws.recv())
                if msg.get("id") == 3: break
            
            # Click submit button
            await ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {
                "expression": """
                (() => {
                    const all = document.querySelectorAll('button');
                    for(const btn of all) {
                        const t = btn.textContent.trim();
                        if(t.includes('登录') || t.includes('注册')) {
                            btn.click();
                            return 'clicked ' + t;
                        }
                    }
                    return 'no submit button';
                })()
                """
            }}))
            for _ in range(5):
                msg = json.loads(await ws.recv())
                if msg.get("id") == 4:
                    print(msg["result"]["result"]["value"])
                    break

asyncio.run(login("16607657595", None))  # No code = just enter phone
```

## Common Pitfalls

1. **React synthetic events**: Setting `element.value = '...'` alone doesn't trigger React's onChange. Always use the nativeInputValueSetter + dispatchEvent pattern above.

2. **Page transitions after click**: Login clicks often trigger navigation or modal popups. Always `await asyncio.sleep(2)` before looking for the next element.

3. **Hidden/clipped elements**: Some login pages have hidden inputs (e.g., hidden checkbox for "agree to terms") that are not visible. Check `getBoundingClientRect().width > 0` before interacting.

4. **Multiple tabs/pages**: Login via OAuth or redirect may open a new tab. Check `curl -s http://127.0.0.1:9222/json` to see all pages — the first one may not be the login page anymore.

5. **Cross-origin iframes**: CDP can't directly access elements inside cross-origin iframes. You may need to switch frame context with `Page.navigate` to the iframe's src URL.

6. **IIFE required in `Runtime.evaluate`**: Top-level `return` statements cause `SyntaxError: Illegal return statement`. Always wrap expressions in an IIFE: `(function(){ ... })()` — not a bare arrow function with `return`.

7. **Vue `v-if` leaves `<!--v-if-->` placeholders**: When a Vue component conditionally hides an element with `v-if`, the DOM shows `<!--v-if-->` with NO fallback content. The element is NOT in the DOM at all — searching for it will fail. This is different from `v-show` which keeps the element in DOM with `display:none`. Indicators: an `item-header-right-state` div containing only `<!--v-if-->` means action buttons exist but haven't rendered because their Vue condition isn't met. You may need to resolve page state (close dialogs, complete auth flows) before the condition evaluates to true.

8. **Sync `websocket-client` for heredoc scripts**: When running CDP from `terminal()` with `python3 << 'PYEOF'`, prefer the sync `websocket-client` library (`import websocket; ws = websocket.create_connection(...)`) over async `websockets`. Avoids `asyncio.run()` boilerplate and threading issues in terminal-based scripts.
