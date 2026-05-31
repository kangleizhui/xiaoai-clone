---
name: qqbot-commands-config
description: "通过 CDP 浏览器自动化配置 QQ 机器人斜杠指令（功能配置 → 指令）。适用于已登录的 QQ 开放平台管理后台。"
version: 1.0.0
author: Hermes Agent
category: platforms
---

# QQ 机器人斜杠指令配置

在 QQ 开放平台（q.qq.com/qqbot）的「功能配置 → 指令」页面，通过 CDP（Chrome DevTools Protocol）批量添加斜杠指令。

## 前提条件

- Chrome 已通过 CDP 启动（`--remote-debugging-port=9222`）
- 已登录 QQ 开放平台，机器人管理后台页面已打开
- 需要手机 QQ 扫码验证身份（每步保存都要扫）
- 指令上限 **24 条**，格式 `/指令名`
- 指令名和介绍仅支持中英文字符和数字
- 标准指令清单见 [references/command-list.md](references/command-list.md)

## 完整流程

### 1. 进入编辑模式

```
页面按钮: 「返回」「重新配置」 → 点「重新配置」
进入后按钮变为: 「取消」「保存配置」
出现 t-icon-add-circle 加号图标
```

### 2. 批量添加指令行

用 CDP `Input.dispatchMouseEvent` 点击 `t-icon-add-circle`：

```python
from websocket import create_connection
ws = create_connection("ws://127.0.0.1:9222/devtools/page/<PAGE_ID>", timeout=10)

def click_plus():
    r = send_eval(ws, """
        (function(){
            var s=document.querySelector('.t-icon-add-circle');
            var r=s.getBoundingClientRect();
            return JSON.stringify({x:r.left+r.width/2, y:r.top+r.height/2});
        })()
    """)
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})

# 点 N 次凑满所需条数
for i in range(24):
    click_plus()
    time.sleep(0.4)
```

**注意**: 每次点 `+` 号后图标位置会下移，需要重新 `getBoundingClientRect()` 获取最新位置。

### 3. 逐条填写指令

```python
def click_item(idx):
    """点击第 idx 条指令的标题以选中它"""
    r = send_eval(ws, f"""
        (function(){{
            var items=document.querySelectorAll('.command-item-wrap');
            var h=items[{idx}].querySelector('.form-box-header');
            h.scrollIntoView({{block:'center'}});
            var rect=h.getBoundingClientRect();
            return JSON.stringify({{x:rect.left+rect.width/2, y:rect.top+rect.height/2}});
        }})()
    """)
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})

def fill_form(cmd, desc):
    """填入指令名和介绍"""
    send_eval(ws, f"""
        (function(){{
            var ins=document.querySelectorAll('input.t-input__inner');
            var d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
            d.set.call(ins[1],'{cmd}');
            ins[1].dispatchEvent(new Event('input',{{bubbles:true}}));
            d.set.call(ins[2],'{desc}');
            ins[2].dispatchEvent(new Event('input',{{bubbles:true}}));
        }})()
    """)

# 逐条填
for idx, (cmd, desc) in enumerate(cmds):
    click_item(idx)
    fill_form(cmd, desc)
```

**注意**: 表单是**共享**的，同时只有一条指令的表单可见。点不同指令的标题会切换表单上下文。`input.t-input__inner` 共 3 个：`[0]`=前缀`/`（只读），`[1]`=指令名，`[2]`=指令介绍。

### 4. 勾选「消息列表」使用场景

```python
def check_msg_list():
    send_eval(ws, """
        (function(){
            var items=document.querySelectorAll('.usescene-item');
            for(var i=0;i<items.length;i++){
                if(!items[i].classList.contains('usescene-item-forbit')){
                    if(!items[i].classList.contains('usescene-item-active')){
                        items[i].click();
                    }
                }
            }
        })()
    """)
```

- 4 个场景：QQ频道、频道私信、QQ群、消息列表
- 前 3 个有 `usescene-item-forbit` 类（需沙箱配置，不可选）
- 只有「消息列表」可以选，点击切换 `usescene-item-active`
- **必须勾选才能保存**

### 5. 保存（CDP 鼠标真点）

```python
def click_save():
    r = send_eval(ws, """
        (function(){
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].innerText.trim()=='保存配置' && btns[i].offsetHeight>0){
                    var rect=btns[i].getBoundingClientRect();
                    return JSON.stringify({x:rect.left+rect.width/2, y:rect.top+rect.height/2});
                }
            }
            return 'NO';
        })()
    """)
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
```

**关键**: 必须用 `Input.dispatchMouseEvent`，不能用 JS `.click()`——后者不会触发 Vue 的提交事件。

### 6. 扫码验证

保存后弹出「身份验证」弹窗，含二维码 canvas（`.common-qrcode-main canvas`）。用户在 VNC 页面直接扫实时二维码。

```python
# 导出二维码图片给用户
b64 = send_eval(ws, "(function(){var c=document.querySelector('.common-qrcode-main canvas');return c?c.toDataURL('image/png'):'NO';})()")
```

验证通过后弹窗自动消失，页面回到只读模式（按钮变为「返回」「重新配置」）。

## 验证结果

只读模式下检查 `.function-card__expand-name span`：

```python
cards = send_eval(ws, """
    (function(){
        var cards=document.querySelectorAll('.function-card__expand-name span');
        var r=[];
        for(var i=0;i<cards.length;i++) r.push(cards[i].innerText.trim());
        return r.join('|');
    })()
""")
```

## 关键：一次性批量模式

**不要在编辑过程中点保存！** 正确做法：

1. 点「重新配置」进入编辑模式
2. 点 `+` 号凑满条数
3. 逐条填指令名 + 介绍
4. 逐条勾选「消息列表」
5. **最后一次性点「保存配置」**

如果中途保存，会触发身份验证 → 验证后退出编辑模式 → 又要重新点「重新配置」进入，效率极低。

## 完整代码骨架

```python
from websocket import create_connection, WebSocketTimeoutException
import json, time, base64

WS = "ws://127.0.0.1:9222/devtools/page/<PAGE_ID>"

def send(ws, msg):
    ws.send(json.dumps(msg))
    return json.loads(ws.recv())

def js(ws, expr):
    send(ws, {"id":1,"method":"Runtime.evaluate","params":{"expression":expr}})
    return json.loads(ws.recv()).get("result",{}).get("result",{}).get("value","")

def click_plus(ws):
    """点击 + 号添加一条空指令行"""
    r = js(ws, """(function(){
        var s=document.querySelector('.t-icon-add-circle');
        if(!s) return 'NO_ICON';
        var r=s.getBoundingClientRect();
        return JSON.stringify({x:r.left+r.width/2, y:r.top+r.height/2});
    })()""")
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})

def click_item(ws, idx):
    """展开第 idx 条指令（切换表单上下文）"""
    r = js(ws, f"""(function(){{
        var items=document.querySelectorAll('.command-item-wrap');
        var h=items[{idx}].querySelector('.form-box-header');
        h.scrollIntoView({{block:'center'}});
        var rect=h.getBoundingClientRect();
        return JSON.stringify({{x:rect.left+rect.width/2,y:rect.top+rect.height/2}});
    }})()""")
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    time.sleep(0.3)

def fill_form(ws, cmd, desc):
    """填入指令名(index 1)和介绍(index 2)"""
    js(ws, f"""(function(){{
        var ins=document.querySelectorAll('input.t-input__inner');
        if(ins.length<3) return;
        var d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
        d.set.call(ins[1],'{cmd}'); ins[1].dispatchEvent(new Event('input',{{bubbles:true}}));
        d.set.call(ins[2],'{desc}'); ins[2].dispatchEvent(new Event('input',{{bubbles:true}}));
    }})()""")

def check_msg_list(ws):
    """勾选「消息列表」"""
    js(ws, """(function(){
        var items=document.querySelectorAll('.usescene-item');
        for(var i=0;i<items.length;i++){
            if(!items[i].classList.contains('usescene-item-forbit')){
                if(!items[i].classList.contains('usescene-item-active')) items[i].click();
            }
        }
    })()""")

def click_save(ws):
    """CDP鼠标真点保存按钮"""
    r = js(ws, """(function(){
        var btns=document.querySelectorAll('button');
        for(var i=0;i<btns.length;i++){
            if(btns[i].innerText.trim()=='保存配置' && btns[i].offsetHeight>0){
                var rect=btns[i].getBoundingClientRect();
                return JSON.stringify({x:rect.left+rect.width/2,y:rect.top+rect.height/2});
            }
        }
        return 'NO';
    })()""")
    pos = json.loads(r)
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
    send(ws, {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":pos["x"],"y":pos["y"],"button":"left","clickCount":1}})
```

## 常见坑

1. **`+` 号只在「重新配置」模式下出现** —— 只读模式（「返回」「重新配置」）下 `t-icon-add-circle` 不在 DOM 中，必须先点「重新配置」
2. **JS `.click()` 对保存按钮无效** —— 必须用 `Input.dispatchMouseEvent`，Vue 组件绑定了原生鼠标事件
3. **`+` 号位置动态变化** —— 每点一次要重新 `getBoundingClientRect()` 取坐标
4. **表单是共享的** —— 只有当前展开指令的输入框可见，点不同标题切换上下文。`input.t-input__inner`：[0]=前缀`/`(只读)，[1]=指令名，[2]=指令介绍
5. **消息列表必须勾选** —— 否则保存不会触发验证弹窗（静默失败）
6. **指令上限 24 条** —— QQ 平台硬限制，超出部分无法添加
7. **备注仅支持中英文+数字** —— 去掉括号`（）`、斜杠`/`、顿号`、`等符号
8. **CDP 连接可能超时** —— 长时间未操作会断开，需要 `try/except` 重连
9. **不要逐条保存** —— 一次编辑完所有指令，最后一次性保存，避免反复进出编辑模式
10. **验证通过后自动退出编辑模式** —— 回到只读状态，需要再次点击「重新配置」才能继续编辑
