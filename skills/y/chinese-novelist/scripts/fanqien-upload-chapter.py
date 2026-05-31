#!/usr/bin/env python3
"""
Upload a chapter markdown file to Fanqien Novel (番茄小说) ProseMirror editor via CDP.

Usage:
    python3 fanqien-upload-chapter.py <chapter_file.md> [--ws-url WS_URL] [--tab-id TAB_ID]

Requires:
    - Chromium running with --remote-debugging-port=9222
    - Fanqien writer page already open and logged in on the target tab
    - websocket-client: pip install websocket-client
"""

import json, websocket, time, base64, sys, argparse

def cdp_call(ws, method, params=None, session_id=None, timeout=15):
    msg_id = int(time.time() * 1000000) % 1000000
    msg = {"id": msg_id, "method": method}
    if params: msg["params"] = params
    if session_id: msg["sessionId"] = session_id
    ws.send(json.dumps(msg))
    ws.settimeout(timeout)
    start = time.time()
    while time.time() - start < timeout:
        try:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                return data
        except:
            pass
    return None


def find_fanqien_tab(ws_url):
    """Find the tab with fanqienovel.com open."""
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Target.getTargets"}))
    ws.settimeout(5)
    raw = ws.recv()
    data = json.loads(raw)
    ws.close()

    targets = data.get("result", {}).get("targetInfos", [])
    for t in targets:
        if "fanqienovel.com" in t.get("url", ""):
            return t["targetId"], t["url"]
    return None, None


def upload_chapter(ws_url, tab_id, content):
    """
    Upload chapter content to Fanqien ProseMirror editor.
    Returns (success: bool, editor_length: int).
    """
    ws = websocket.create_connection(ws_url, timeout=15)
    resp = cdp_call(ws, "Target.attachToTarget", {
        "targetId": tab_id, "flatten": True
    })
    if not resp or "result" not in resp:
        ws.close()
        return False, 0, "Failed to attach to target"

    session_id = resp["result"]["sessionId"]
    cdp_call(ws, "Runtime.enable", session_id=session_id)
    cdp_call(ws, "DOM.enable", session_id=session_id)
    time.sleep(0.5)

    # Strip markdown title
    if content.startswith("# "):
        content = content.split("\n\n", 1)[-1] if "\n\n" in content else content
    content = content.strip()

    # Base64 encode (UTF-8 safe)
    b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    print(f"  Content: {len(content)} chars → {len(b64)} chars base64")

    # Step 1: Inject base64 into page
    cdp_call(ws, "Runtime.evaluate", {
        "expression": "window.__hermesB64 = '" + b64 + "';",
        "returnByValue": False
    }, session_id=session_id)
    time.sleep(0.3)

    # Step 2: Clear and insert
    insert_script = """
(function() {
    var editor = document.querySelector('.ProseMirror');
    if (!editor) return 'ERROR: no editor';
    editor.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');

    var binary = atob(window.__hermesB64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    var text = new TextDecoder('utf-8').decode(bytes);

    var paras = text.split('\\n\\n');
    var html = '<p>' + paras.map(function(p) {
        return p.replace(/\\n/g, '<br>');
    }).join('</p><p>') + '</p>';

    document.execCommand('insertHTML', false, html);
    return 'OK: ' + editor.textContent.length;
})()
"""
    r = cdp_call(ws, "Runtime.evaluate", {
        "expression": insert_script,
        "returnByValue": True
    }, session_id=session_id)
    result = r.get("result", {}).get("result", {}).get("value", "?") if r else "?"
    print(f"  Insert: {result}")

    time.sleep(1)

    # Step 3: Save draft
    save_script = """
(function() {
    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.trim() === '存草稿') {
            buttons[i].click();
            return 'SAVED';
        }
    }
    return 'NO_SAVE_BTN';
})()
"""
    r2 = cdp_call(ws, "Runtime.evaluate", {
        "expression": save_script,
        "returnByValue": True
    }, session_id=session_id)
    save = r2.get("result", {}).get("result", {}).get("value", "?") if r2 else "?"
    print(f"  Save: {save}")

    time.sleep(2)

    # Step 4: Handle version conflict
    conflict_script = """
(function() {
    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.trim() === '继续编辑本地') {
            buttons[i].click();
            return 'CONFLICT_RESOLVED';
        }
    }
    return 'NO_CONFLICT';
})()
"""
    r3 = cdp_call(ws, "Runtime.evaluate", {
        "expression": conflict_script,
        "returnByValue": True
    }, session_id=session_id)
    conflict = r3.get("result", {}).get("result", {}).get("value", "?") if r3 else "?"
    print(f"  Conflict: {conflict}")

    # If conflict was resolved, save again
    if "CONFLICT" in str(conflict):
        time.sleep(1)
        r4 = cdp_call(ws, "Runtime.evaluate", {
            "expression": save_script,
            "returnByValue": True
        }, session_id=session_id)
        save2 = r4.get("result", {}).get("result", {}).get("value", "?") if r4 else "?"
        print(f"  Re-save: {save2}")
        time.sleep(2)

    # Step 5: Verify
    time.sleep(1)
    r5 = cdp_call(ws, "Runtime.evaluate", {
        "expression": "document.querySelector('.ProseMirror').textContent.length",
        "returnByValue": True
    }, session_id=session_id)
    final_len = r5.get("result", {}).get("result", {}).get("value", 0) if r5 else 0

    # Check success toast
    toast = cdp_call(ws, "Runtime.evaluate", {
        "expression": "(function(){var all=document.querySelectorAll('*');for(var i=0;i<all.length;i++){if(all[i].textContent.trim()==='保存成功')return true;}return false;})()",
        "returnByValue": True
    }, session_id=session_id)
    success = toast.get("result", {}).get("result", {}).get("value", False) if toast else False
    print(f"  Final length: {final_len} | Success toast: {success}")

    ws.close()
    return success, final_len, None


def main():
    parser = argparse.ArgumentParser(description="Upload chapter to Fanqien Novel via CDP")
    parser.add_argument("file", help="Chapter markdown file to upload")
    parser.add_argument("--ws-url", default=None, help="CDP WebSocket URL (auto-discover from :9222)")
    parser.add_argument("--tab-id", default=None, help="Tab ID (auto-discover fanqien tab)")
    args = parser.parse_args()

    # Read content
    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    # Auto-discover CDP and tab
    ws_url = args.ws_url or "ws://127.0.0.1:9222/devtools/browser/"

    if not args.ws_url:
        # Discover browser ID
        import requests
        try:
            resp = requests.get("http://127.0.0.1:9222/json/version", timeout=5)
            ws_url = resp.json().get("webSocketDebuggerUrl", ws_url)
        except:
            pass

    tab_id = args.tab_id
    if not tab_id:
        tab_id, page_url = find_fanqien_tab(ws_url)
        if not tab_id:
            print("Error: No Fanqien tab found. Open fanqienovel.com writer page first.")
            sys.exit(1)
        print(f"Found Fanqien tab: {page_url[:80]}")

    success, length, error = upload_chapter(ws_url, tab_id, content)
    if error:
        print(f"Error: {error}")
        sys.exit(1)

    if success:
        print(f"\n✓ Uploaded successfully! Editor now has {length} characters.")
    else:
        print(f"\n✗ Upload may have failed. Editor length: {length}")
        sys.exit(1)


if __name__ == "__main__":
    main()
