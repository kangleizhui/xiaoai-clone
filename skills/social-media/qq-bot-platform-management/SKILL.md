---
name: qq-bot-platform-management
description: Manage bots on the QQ Open Platform (q.qq.com/qqbot) — configure features, commands, services, quick menus, and handle identity verification. Use when the user wants to add/edit bot commands, services, or other settings on the official QQ bot management dashboard.
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [qq, qq-bot, qq-platform, commands, cdp, browser]
---

# QQ Bot Platform Management

Manage official QQ bots on the QQ Open Platform (q.qq.com/qqbot). Uses CDP to control Chrome on a visible noVNC browser so the user can see and interact with the page (e.g., scan QR codes for identity verification).

## When to Use

- User asks to configure QQ bot commands (指令), services (服务), or quick menus (快捷菜单)
- User needs to add/edit features on the QQ bot management dashboard
- User asks to navigate to `q.qq.com/qqbot` or the bot's appid page
- Debugging QQ bot platform configuration issues

**Don't use for**: NapCat/real QQ account integration (use `napcat-onebot-hermes-integration` instead). This skill is for the official QQ Bot API platform.

## Architecture

The QQ bot platform is a React-based SPA at `https://q.qq.com/qqbot/`. All interaction is via CDP through the visible noVNC Chromium browser (see `remote-browser-cdp` skill for the browser stack).

Key pages (hash routes):
- `#/home?appid=<appid>` — Bot home/dashboard
- `#/developer/publish-config/function-config` — Function configuration (服务/指令/快捷菜单)
- `#/developer/sandbox` — Sandbox configuration

## Feature Configuration (功能配置)

The 功能配置 page has three sub-tabs managed by TDesign `t-tabs`:

| Tab | Purpose | Actions |
|-----|---------|---------|
| 服务 (Service) | Chatbot service settings | Add/edit AI service configuration |
| 指令 (Commands) | Slash commands users can type | Add command name + description |
| 快捷菜单 (Quick Menu) | Quick-access button menus | Add menu items |

### Adding Commands (指令)

**IMPORTANT — Two view modes**: The 功能配置 page has TWO modes for the 指令 tab:

1. **Read-only mode** (default): Commands display as collapsed `function-card` components. The card shows the command name (`/test`) and has a chevron to expand details. Buttons: "返回" and "重新配置". **No "+" button is visible in this mode.**

2. **Edit mode** (after clicking "重新配置"): Commands become draggable `command-item-wrap` items with forms. This is where the `+` button (`t-icon-add-circle` SVG, 28px) appears after each command item, and each item has a `t-icon-minus-circle` delete button. Buttons change to "取消" and "保存配置". Tabs become disabled (`t-is-disabled`) because the form is modal.

**To add commands, always click "重新配置" first** to enter edit mode. The "+" icon is NOT a text button — it's an SVG `<use href="#t-icon-add-circle">` inside the `command-contents__list` container.

**Maximum**: QQ platform limits commands to **24 total** (tooltip: "指令数量上限24条").

#### ⭐ Batch Workflow (THE correct way — do NOT save per-command)

The single biggest mistake is saving after each individual command fill. The correct workflow saves ONCE for all commands:

1. Click "重新配置" to enter edit mode
2. Click the `+` icon N times (via CDP `Input.dispatchMouseEvent`) to create all empty command rows **BEFORE filling anything** — query `+` position fresh before each click since it moves down as rows are added
3. **Fill each command by clicking its header** (via CDP mouse event) to switch the shared form to that command, then fill name + description. The form panel is SHARED — only ONE command's form is visible at a time. Clicking command N's header collapses the previous and shows command N's data
4. Click "保存配置" ONCE at the end — this triggers a single identity verification

**Why batch save is critical**: Each save triggers identity verification (QR code scan). If you save 24 times, the user scans 24 times, and intermediate verification dialogs cause saves to fail silently. The entire edit session is a single transaction.

**Form structure**: In edit mode, when a new command form appears, the fields are:

1. **指令名 prefix** (input[0]) — Pre-filled with `/`. **Do not type here.**
2. **指令名** (input[1]) — The command name. **English letters and numbers only.** (e.g., `new`, `model`, `status`). Placeholder: "请使用简练的词语作为指令名"
3. **指令介绍** (input[2]) — The description. **Chinese characters, English letters, and numbers ONLY.** No parentheses, slashes, or other symbols. Placeholder: "请输入指令介绍"

Additional fields (usually left at defaults):
- **权限菜单** — "所有人" (everyone)
- **使用场景** — QQ频道, 频道私信, QQ群, 消息列表. These are `usescene-item` DIVs, NOT native checkboxes. Three have `usescene-item-forbit` class (disabled: requires sandbox config). To enable: remove `forbit` class, then click to toggle `usescene-item-active`. Only "消息列表" has no `forbit` by default.
- **是否传参** — toggle for parameter support

**Checking usage scenarios** (optional — user may skip if sandbox not configured):
```python
js("""(function(){
    var items=document.querySelectorAll('.usescene-item');
    for(var i=0;i<items.length;i++){
        items[i].classList.remove('usescene-item-forbit');
        if(!items[i].classList.contains('usescene-item-active')){
            items[i].click();
        }
    }
})()""")
```

**Descriptor constraints**: The 指令介绍 field rejects symbols like `(` `)` `/` `、`. Strip everything after `（` and remove all non-alphanumeric symbols. Examples:

| User input | Corrected description |
|-----------|----------------------|
| `新建会话（/reset）` | `新建会话` |
| `后台执行（/bg、/btw）` | `后台执行` |
| `会话分支（/fork）` | `会话分支` |
| `切换模型（/provider）` | `切换模型` |

### CDP Interaction Patterns (QQ Bot Platform)

**CRITICAL**: The QQ bot platform is a Vue SPA with custom event bindings. Regular DOM `.click()` does NOT work on key elements — you MUST use CDP's `Input.dispatchMouseEvent` for:
- Clicking the `+` icon (`t-icon-add-circle`) to add new command rows
- Clicking command item headers to select/switch which command's form is shown

This is the #1 cause of "nothing happens" when clicking via `Runtime.evaluate`.

**Clicking the `+` icon** (adds a blank command row):
```python
# Get position, then dispatch
r = js("(function(){var s=document.querySelector('.t-icon-add-circle');var r=s.getBoundingClientRect();return JSON.stringify({x:r.left+r.width/2,y:r.top+r.height/2});})()")
pos = json.loads(r)
send({"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
send({"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
```

**Clicking a command header** (switches which command's form is displayed — only ONE form is visible at a time):
```python
# Scroll the target item into view first, then click
js(f"""(function(){{
    var items=document.querySelectorAll('.command-item-wrap');
    var h=items[{idx}].querySelector('.form-box-header');
    h.scrollIntoView({{block:'center'}});
    var rect=h.getBoundingClientRect();
    // dispatch mouse events at rect.left+width/2, rect.top+height/2
}})()""")
```

**NOTE**: Command items below the visible viewport MUST be scrolled into view (`scrollIntoView`) before clicking. The `config-content-config-body` div has `scrollHeight > clientHeight` when many commands exist.

### CDP Form Filling (QQ Bot Platform)

Use `websocket-client` (sync, imported as `websocket`) via `terminal()`. The form uses Vue-controlled inputs — use the native setter pattern:

```python
import json, time
from websocket import create_connection

WS_URL = "ws://127.0.0.1:9222/devtools/page/<PAGE_ID>"
ws = create_connection(WS_URL, timeout=15)

def js(expr):
    ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":expr}}))
    return json.loads(ws.recv())

# Fill command name (input[1]) and description (input[2])
js("""(function(){
    var ins=document.querySelectorAll('input.t-input__inner');
    var n=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    n.call(ins[1],'new');
    ins[1].dispatchEvent(new Event('input',{bubbles:true}));
    n.call(ins[2],'新建会话');
    ins[2].dispatchEvent(new Event('input',{bubbles:true}));
    return'OK';
})()""")

# Save
js("""(function(){
    var btns=document.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){if(btns[i].innerText.trim()==='保存配置'){btns[i].click()}}
})()""")

ws.close()
```

### Identity Verification (身份验证)

**Every save triggers a QR code identity verification dialog.** The user must scan a QR code with their mobile QQ app before changes are persisted. The dialog has:
- A canvas QR code inside `.common-qrcode-main canvas`
- "身份验证" title and "使用手机QQ扫码二维码验证身份" text
- "取消" and "确认" buttons

**Extracting the QR code:**
```python
js("""(function(){
    var canvas = document.querySelector('.common-qrcode-main canvas');
    if(!canvas) return 'NO_CANVAS';
    return canvas.toDataURL('image/png');
})()""")
# Save the data URL as a PNG and share with user
```

**Important**: The verification is per-save. Batch automation is impractical because each save requires a new QR scan. After the user scans, verify the dialog closed before proceeding.

## CDP Page Detection

The CDP browser may have multiple tabs. Find the right one:

```bash
curl -s http://127.0.0.1:9222/json/list | python3 -c "
import json, sys
for p in json.load(sys.stdin):
    print(f'{p[\"id\"]} | {p[\"type\"]:10s} | {p.get(\"title\",\"\")[:50]} | {p.get(\"url\",\"\")[:80]}')
"
```

Activate a specific page:
```python
import urllib.request
urllib.request.urlopen(f"http://127.0.0.1:9222/json/activate/{page_id}")
```

Navigate a page:
```python
js({"method": "Page.navigate", "params": {"url": "https://q.qq.com/qqbot/#/home?appid=1904088040"}})
```

## Checking Page State

After actions, verify the page content. These are useful CDP probes:

```python
# Check page visible text around 功能配置
js("""(function(){
    var t=document.body.innerText||'';
    var idx=t.indexOf('功能配置');
    return t.slice(idx,idx+300);
})()""")

# Check active tab
js("""(function(){
    var tabs=document.querySelectorAll('.t-tabs__nav-item');
    for(var i=0;i<tabs.length;i++){
        if(tabs[i].classList.contains('t-is-active')) return tabs[i].innerText.trim();
    }
})()""")

# List all visible buttons (READ the page this way)
js("""(function(){
    var btns=document.querySelectorAll('button');
    var n=[]; for(var i=0;i<btns.length;i++){
        if(btns[i].offsetHeight>0) n.push(btns[i].innerText.trim());
    }
    return JSON.stringify(n);
})()""")

# Check if identity verification dialog is showing
js("""(function(){
    var ds=document.querySelectorAll('.t-dialog__ctx');
    for(var i=0;i<ds.length;i++){
        if(ds[i].offsetHeight>0 && ds[i].innerText.indexOf('扫码')!==-1)
            return 'YES';
    }
    return 'NO';
})()""")

# Count commands in edit mode
js("""(function(){
    var items=document.querySelectorAll('.command-item-wrap');
    var res=[];
    for(var i=0;i<items.length;i++){
        var t=items[i].querySelector('.title span');
        var n=items[i].querySelector('.form-box-expand-name');
        res.push((t?t.innerText.trim():'?') + '=' + (n?n.innerText.trim():'?'));
    }
    return items.length + ' commands: ' + JSON.stringify(res);
})()""")

# Check if in edit mode vs read-only mode (by looking for add-circle icon)
js("""(function(){
    var add=document.querySelector('.t-icon-add-circle');
    return add ? 'EDIT_MODE' : 'READ_ONLY';
})()""")
```

## Pitfalls

1. **"添加指令" button disappears**: This happens when a dialog is overlaying the page or when you're in read-only mode. In read-only mode, commands are `function-card` components — click "重新配置" to enter edit mode where the `t-icon-add-circle` "+" icon appears. The "+" is an SVG icon, not a text button. If dialogs are overlaying, close all `.t-dialog` dialogs first.

2. **"指令配置内容不符合要求"**: This validation error means the description contains banned characters — only Chinese characters, English letters, and numbers are allowed. Remove all parentheses `（）`, slashes `/`, punctuation `、`, and other symbols. Strip aliases like `/reset`, `/fork`, `/provider` entirely from descriptions.

3. **Batch-add THEN save once**: The correct workflow is NOT to save after each command. Instead: (a) click "重新配置" to enter edit mode, (b) click the `+` icon 24 times to create all empty command rows FIRST, (c) fill each command's name and description by clicking its header to select it, (d) click "保存配置" ONCE at the end. This triggers only one identity verification for the entire batch. DON'T save after each individual command — that forces the user to scan 24 times and the repeated verification dialogs cause intermediate saves to fail silently.

4. **VNC vs screenshot QR codes**: Identity verification QR codes are time-sensitive. Always instruct the user to scan from the live VNC page (http://101.32.98.240:6080/vnc.html), NOT from a screenshot that may have an expired code. The CDP `canvas.toDataURL()` extraction is useful for debugging but the extracted image is already stale by the time it's delivered.

5. **Sticky "是否保存" dialog**: After any form interaction, a "是否需要保存已填写的服务？" dialog may persist and block the UI. Clicking "确认" triggers identity verification; clicking "取消" dismisses temporarily but the dialog often reappears. The cleanest escape is: click "确认" → user scans verification QR from VNC → dialog auto-closes on success.

6. **Form inputs appear empty after save attempt**: The React-controlled inputs may show old values. Always verify with `input.value` directly, not just visual rendering.

7. **CDP port variance**: The visible Chrome may be on port 9222 or 9223. Always verify with `ss -tlnp | grep 922` before connecting. The `remote-browser-cdp` skill's pitfall #13b covers this.

8. **Using wrong browser**: The Hermes internal `browser_*` tools control a separate headless Chromium. Always use raw CDP WebSocket to control the visible noVNC browser. See `remote-browser-cdp` skill pitfall #9.

9. **Command count limit**: QQ platform displays "指令数量上限24条" when the 指令 tab is in edit mode. Plan which 24 commands to add if the full list exceeds this limit.

10. **Scrolling required for command items**: When 20+ commands are in the list, items below the visible viewport return negative `y` coordinates from `getBoundingClientRect()`. Always call `scrollIntoView({block:'center'})` on the target item before dispatching mouse events at its coordinates.

11. **Only one form is visible at a time**: The form panel is shared across all command items. When you click command N's header, the form switches to show command N's data and the previous command collapses to `chevron-down`. After filling all commands, always verify the last command's values stuck by checking `input.t-input__inner` values directly.

12. **DOM `.click()` silent failure on Vue SPA**: The QQ bot platform uses Vue with custom event delegation. Calling `.click()` on elements returned by `querySelector()` often does nothing. Always use CDP `Input.dispatchMouseEvent` for the `+` icon and command headers. This is the single most common cause of "I clicked it but nothing happened."

13. **CDP WebSocket timeouts during rapid interaction**: The `websocket-client` connection times out (10-second default) when the page does heavy React re-renders from rapid clicks. Symptoms: `WebSocketTimeoutException` / `Connection timed out` mid-script. Recovery: (a) reconnect using the same page ID — Chrome CDP sessions survive disconnects, (b) check page state with `curl http://127.0.0.1:9222/json/list` first, (c) increase `create_connection(timeout=30)` for longer operations, (d) add explicit `time.sleep()` after DOM mutations to let the Vue render cycle complete before the next CDP call.

14. **Form values not persisting after fill**: Even when `input.value` returns the correct value, the Vue model may not register the change if the reactivity trigger is incomplete. The `Object.getOwnPropertyDescriptor` setter + `input` event works MOST of the time, but occasionally the value reverts. When this happens: (a) verify with `input.value` AFTER the fill, (b) try adding a `change` event too: `ins[1].dispatchEvent(new Event('change',{bubbles:true}))`, (c) if all else fails, use CDP `Input.dispatchKeyEvent` character-by-character to simulate keyboard input.

## Related Skills

- `remote-browser-cdp` — Setting up and controlling the visible noVNC Chromium browser
- `napcat-onebot-hermes-integration` — Real QQ account integration (separate from official bot API)
- `tencent-novnc-chromium-cdp` (if present) — CDP patterns for Tencent/Chinese web platforms
