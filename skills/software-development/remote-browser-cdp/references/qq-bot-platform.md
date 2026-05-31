# QQ Bot Platform — CDP Automation Patterns

> Site: `https://q.qq.com/qqbot/#/developer/publish-config/function-config`
> Route after login: click "开发" sidebar → "功能配置" → "指令" tab

## Two Views: Read-Only vs Edit Mode

| Mode | Buttons visible | DOM structure | How to enter |
|------|----------------|---------------|-------------|
| **Read-only** | "返回" + "重新配置" | `function-card-wrap` > `function-card-main` | Default after page load |
| **Edit** | "取消" + "保存配置" | `command-item-wrap` > `form-box` | Click "重新配置" |

To detect which mode: check for `document.querySelector('.command-item-wrap')` vs `document.querySelector('.function-card-wrap')`.

## Command (指令) Configuration — Full Workflow

### Step 1: Enter Edit Mode

Click **"重新配置"** button. This switches from read-only to edit mode. After this:
- Buttons change to "取消" + "保存配置"
- `command-item-wrap` elements appear (existing commands as editable rows)
- `t-icon-add-circle` SVG appears after the last command row

**Important:** The "+" button ONLY appears after clicking "重新配置". Do NOT try to find it in read-only mode — it doesn't exist there.

### Step 2: Add Command Rows

Click the **`t-icon-add-circle`** SVG (28px, class `add-icon add-icon-margin`) N times to create N empty command rows.

**CRITICAL: Use CDP `Input.dispatchMouseEvent`, NOT DOM `.click()`.**  
Vue event listeners don't fire from DOM clicks on this element. Do:
```python
# Get position each time (it moves as rows are added)
pos = js("(function(){var s=document.querySelector('.t-icon-add-circle');var r=s.getBoundingClientRect();return JSON.stringify({x:r.left+r.width/2,y:r.top+r.height/2});})()")
send({"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos.x,"y":pos.y,"button":"left","clickCount":1}})
send({"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos.x,"y":pos.y,"button":"left","clickCount":1}})
```

Re-query the position each time — the list grows and the "+" moves down.

**Limit: 24 commands total.**

### Step 3: Fill Commands

The form is **shared** — only one command's data is shown at a time. The command whose header you clicked is the "active" one:

```python
def click_item(idx):
    """Click command row header to select it for editing, scrolling if needed."""
    js(f"""
    (function(){{
        var items=document.querySelectorAll('.command-item-wrap');
        var h=items[{idx}].querySelector('.form-box-header');
        h.scrollIntoView({{block:'center'}});
        var r=h.getBoundingClientRect();
        return JSON.stringify({{x:r.left+r.width/2,y:r.top+r.height/2}});
    }})()
    """)
    # CDP mouse click at returned x,y
    ...

def fill(cmd, desc):
    """Fill the currently active form's inputs."""
    js(f"""(function(){{
        var ins=document.querySelectorAll('input.t-input__inner');
        var d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
        d.set.call(ins[1],'{cmd}');
        ins[1].dispatchEvent(new Event('input',{{bubbles:true}}));
        d.set.call(ins[2],'{desc}');
        ins[2].dispatchEvent(new Event('input',{{bubbles:true}}));
    }})()""")

# Fill all commands one by one
for idx, (cmd, desc) in enumerate(commands):
    click_item(idx)
    fill(cmd, desc)
```

**Form fields:**

| # | Placeholder | What to fill | Notes |
|---|------------|-------------|-------|
| 0 | 请输入 | `/` auto-filled | Don't touch |
| 1 | 请使用简练的词语作为指令名 | English word (e.g. `new`) | No `/` prefix |
| 2 | 请输入指令介绍 | Chinese description | **Only 中英文字符和数字** — strip `（）/、` |

**Description cleaning rule:** Take everything before the first `（`.  
Examples: `新建会话（/reset）` → `新建会话`, `后台执行（/bg、/btw）` → `后台执行`

### Step 4: Save Once

**Click "保存配置" ONCE after ALL commands are filled.** Do NOT save after each command — identity verification triggers every save, and each verification requires a fresh QR scan.

### Step 5: Identity Verification

1. "保存配置" triggers QR-code identity verification modal
2. Tell user to open VNC (`http://<IP>:6080/vnc.html`) and scan the **live** QR
3. QR codes in screenshots expire quickly — user MUST scan the live VNC screen
4. After scan, the dialog auto-closes and save completes
5. A "提交成功" toast may appear briefly

## CDP Mouse Click Pattern

When DOM `.click()` doesn't work (Vue/React event handlers), use:
```python
# Get element center
js("(function(){var el=...;var r=el.getBoundingClientRect();return JSON.stringify({x:r.left+r.width/2,y:r.top+r.height/2});})()")

# Click
send({"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1}})
send({"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1}})
```

## Scrolling

Elements may be off-screen. Before clicking, use `scrollIntoView({block:'center'})`:
```js
var el = document.querySelectorAll('.command-item-wrap')[idx];
el.querySelector('.form-box-header').scrollIntoView({block:'center'});
```

## Dialog Loop Problem

The page can get stuck in a dialog loop:
1. "是否保存已填写的服务？" dialog (取消/确认)
2. If verification doesn't complete before dialog re-triggers, cycle repeats

**Fix:** Close all dialogs, click "确认" to accept, then handle the identity verification that appears. If truly stuck, `Page.reload` and start fresh.

## Usage Scenarios (使用场景)

Custom `usescene-item` elements, NOT standard checkboxes. May show `usescene-item-forbit` (disabled) if sandbox QQ channel isn't configured. Default selection ("所有人" + all scenarios) is usually fine.

## Key Selectors Reference

| Element | Selector |
|---------|----------|
| Edit mode entry | `button` with text "重新配置" |
| "+" add button | `svg.t-icon-add-circle.add-icon.add-icon-margin` |
| Command row | `.command-item-wrap` |
| Row header (click to select) | `.command-item-wrap .form-box-header` |
| Form inputs | `input.t-input__inner` |
| Save button | `button` with text "保存配置" |
| Identity verification modal | `.t-dialog__ctx` containing "扫码" |
| Read-only command card | `.function-card-wrap`
