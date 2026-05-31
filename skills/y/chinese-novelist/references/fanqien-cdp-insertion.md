# Fanqien Novel (番茄小说) ProseMirror Content Insertion via CDP

> Technique for inserting large Chinese text into 番茄小说's ProseMirror editor using CDP (Chrome DevTools Protocol). Developed through iterative trial-and-error during novel upload sessions.

## Problem

The 番茄小说 writer backend uses **ProseMirror** as its rich text editor (`div.ProseMirror[contenteditable]`). Standard CDP text insertion methods fail:

| Method | Result |
|--------|--------|
| `Input.insertText` | Only inserts the first paragraph; rest is lost |
| `execCommand('insertText')` | Same — ProseMirror intercepts and only processes first block |
| Setting `innerHTML` directly | ProseMirror syncs from internal state; changes are overwritten |
| Clipboard paste event dispatch | Unreliable with large UTF-8 text |

## Working Solution

The reliable approach is a 4-step CDP pipeline:

### Step 1: Encode content as UTF-8 base64 in Python

```python
import base64

with open('chapter.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Strip markdown artifacts
content = content.replace('# Chapter Title\n\n', '')
content = content.strip()

# UTF-8 safe base64 encoding
b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
```

### Step 2: Inject base64 string into page via CDP Runtime.evaluate

```python
cdp_call(ws, "Runtime.evaluate", {
    "expression": "window.__hermesB64 = '" + b64 + "';",
    "returnByValue": False
}, session_id=session_id)
```

The base64 string can be 40K+ chars — JavaScript handles this fine.

### Step 3: Decode and insert via JavaScript (UTF-8 safe)

```javascript
(function() {
    var editor = document.querySelector('.ProseMirror');
    if (!editor) return 'no editor';
    editor.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');

    // UTF-8 safe base64 decode using TextDecoder
    var binary = atob(window.__hermesB64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    var decoder = new TextDecoder('utf-8');
    var text = decoder.decode(bytes);

    // Convert to ProseMirror-compatible HTML
    // Double newlines → paragraph breaks
    // Single newlines → line breaks
    var paras = text.split('\\n\\n');
    var html = '<p>' + paras.map(function(p) {
        return p.replace(/\\n/g, '<br>');
    }).join('</p><p>') + '</p>';

    document.execCommand('insertHTML', false, html);
    return 'ok: len=' + editor.textContent.length;
})()
```

### Step 4: Save draft and handle version conflicts

```javascript
// Click '存草稿' button
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === '存草稿') {
        buttons[i].click();
        break;
    }
}

// If version conflict dialog appears ('版本冲突提示'):
// Click '继续编辑本地' to keep local changes, then save again
// The conflict has two options:
//   '选择云端版本' — overwrites local with cloud version (LOSES changes)
//   '继续编辑本地' — keeps local edits (CORRECT choice)
```

## Key Pitfalls

### Pitfall 1: `atob` does not handle UTF-8
Using plain `atob(b64)` on UTF-8 base64 produces mojibake (garbled Chinese characters). MUST use `Uint8Array` + `TextDecoder('utf-8')`.

### Pitfall 2: `callFunctionOn` with large arguments times out
Runtime.callFunctionOn with large string arguments (>5000 chars) frequently times out. Use `Runtime.evaluate` with a pre-set global variable instead.

### Pitfall 3: ProseMirror strips raw text
ProseMirror expects structured HTML input. Raw text or `\n`-delimited text is not properly split into paragraphs. Always convert to `<p>...</p>` blocks.

### Pitfall 4: Editor must be focused first
`execCommand` calls may silently fail if the ProseMirror editor is not focused. Always call `editor.focus()` first.

## CDP Setup Prerequisites

```python
import json, websocket

WS_URL = "ws://127.0.0.1:9222/devtools/browser/<browser-id>"
TAB_ID = "<tab-id>"  # from Target.getTargets

ws = websocket.create_connection(WS_URL, timeout=15)

# Attach to target
resp = cdp_call(ws, "Target.attachToTarget", {
    "targetId": TAB_ID, "flatten": True
})
session_id = resp["result"]["sessionId"]

# Enable domains
cdp_call(ws, "Runtime.enable", session_id=session_id)
cdp_call(ws, "DOM.enable", session_id=session_id)
```

## Full Python Example

See `scripts/fanqien-upload-chapter.py` for a complete standalone script.
