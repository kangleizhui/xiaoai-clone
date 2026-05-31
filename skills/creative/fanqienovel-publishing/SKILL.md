---
name: fanqienovel-publishing
description: |-
  在番茄小说(fanqienovel.com)作家后台发布和管理小说的完整工作流。
  配合 chinese-novelist 技能使用——chinese-novelist 负责创作内容，本技能负责发布操作。
  包括：创建书籍、填写章节、处理ProseMirror编辑器、保存草稿、管理章节。
metadata:
  trigger: 番茄小说、fanqienovel、发布小说、创建章节、存草稿
  depends_on: chinese-novelist
---

# 番茄小说发布工作流

## 重要前提

这条技能操作的是**visible 浏览器**（Xvfb :99, CDP port 9222, 用户数据目录 /root/.chromium-remote），
和 Hermes 内部 headless 浏览器（browser_navigate/click 工具）是**两个不同的浏览器实例**。
用户通过 noVNC 能看到 visible 浏览器的画面。

所有操作都通过 `terminal` → CDP (http://127.0.0.1:9222/json) → WebSocket 发指令。

## 前置条件

- 用户已在 番茄小说 登录（作家后台）
- Python websocket-client 已安装：`pip install websocket-client --break-system-packages`
- noVNC 端口 6080 已在防火墙放行

## 通用 CDP 操作函数模板

> **使用 `flatten: True` + `sessionId` 模式**。
> 旧版直接 `tabs[0].webSocketDebuggerUrl` + `Page.navigate` 模式在 React SPA 页面
> （如番茄作家后台）不稳定——`Target.attachToTarget` 配合 `flatten=True` 能正确处理
> iframe 和动态路由。

```python
import json, time, websocket

def cdp_call(ws, method, params=None, session_id=None, timeout=10):
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
        except websocket.WebSocketTimeoutException:
            pass
    return None

# 1. 先获取标签页列表
ws = websocket.create_connection(
    "ws://127.0.0.1:9222/devtools/browser/<browserId>", timeout=15
)
resp = cdp_call(ws, "Target.getTargets")
targets = resp["result"]["targetInfos"]
# 找到番茄作家后台标签页
tab = next(t for t in targets if "fanqienovel.com" in t["url"])
tab_id = tab["targetId"]

# 2. 连接到标签页
resp = cdp_call(ws, "Target.attachToTarget",
    {"targetId": tab_id, "flatten": True})
session_id = resp["result"]["sessionId"]

# 3. 启用 Runtime（每次 attach 后必须重新启用）
cdp_call(ws, "Runtime.enable", session_id=session_id)

# 4. 执行 JS
r = cdp_call(ws, "Runtime.evaluate", {
    "expression": "...",
    "returnByValue": True
}, session_id=session_id)
result = r.get("result",{}).get("result",{}).get("value","")

# 5. 导航（用 JS location.href 替代 Page.navigate）
cdp_call(ws, "Runtime.evaluate", {
    "expression": "window.location.href = 'https://fanqienovel.com/main/writer/'",
    "returnByValue": False
}, session_id=session_id)
time.sleep(5)  # 等待 React SPA 渲染完成

ws.close()
```

## 关键API 与 URL 模式

### 页面路径
| 功能 | URL |
|------|-----|
| 作家后台首页 | `/main/writer/` |
| 作品管理 | `/main/writer/book-manage` |
| 章节管理(bk_id) | `/main/writer/chapter-manage/{bookId}?type=1` |
| 创建作品 | `/main/writer/create` |
| 创建章节(bk_id) | `/main/writer/{bookId}/publish/?enter_from=newchapter` |
| 编辑章节(bk_id,ch_id) | `/main/writer/{bookId}/publish/{chapterId}?enter_from=newchapter` |
| 作品信息编辑 | `/main/writer/book-info/{bookId}?type=1` |

### Book ID
新作品创建后从 URL 中获取：`/main/writer/book-info/{bookId}?type=1`

## 创建新书

1. 从作家专区首页导航：`/writer/zone/` → 点击"工作台"按钮 → 进入 `/main/writer/?enter_from=author_zone`
2. 在页面上找到"创建新书"区域——它**不是独立页面**，而是作家首页上的一个卡片/区块
3. "创建新书"下有"小说"和"短故事"两个选项——点"小说"
4. 用 `nativeInputValueSetter` 填入 React 表单字段（直接 `.value=` 会被框架忽略）
5. 选择目标读者（女频=0, 男频=1）
6. 填写主角名、作品简介
7. 点击"立即创建"按钮
8. 创建成功后从 URL 中提取 book_id：`/main/writer/book-info/{bookId}?type=1`

**⚠️ 注意**：`/main/writer/create` 路径存在但 React 路由可能不匹配。
推荐走 `工作台 → 创建新书 → 小说` 的点击路径，而不是直接导航 URL。

```javascript
// React表单填值模板（必须用 nativeInputValueSetter）
var ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
var ta_ns = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;

// 书名
var input = document.querySelector('input[placeholder="请输入作品名称"]');
ns.call(input, '腹黑仙途');
input.dispatchEvent(new Event('input', {bubbles: true}));

// 主角名
var prot = document.querySelector('input[placeholder="请输入主角名1"]');
ns.call(prot, '苏瑶');
prot.dispatchEvent(new Event('input', {bubbles: true}));

// 目标读者（女频）
document.querySelector('input[name="pindao"][value="0"]').checked = true;

// 简介
var ta = document.querySelector('textarea');
ta_ns.call(ta, '作品简介文字');
ta.dispatchEvent(new Event('input', {bubbles: true}));

// 点击创建
document.querySelector('button').find(b => b.textContent.includes('立即创建'))?.click();
```

## 创建章节并填写内容

### 设置章节号和标题

```javascript
var ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
var inputs = document.querySelectorAll('input.serial-input');

// 章节号（第一个无placeholder的input）
var ni = Array.from(inputs).find(i => !i.placeholder);
ns.call(ni, '1');
ni.dispatchEvent(new Event('input', {bubbles: true}));

// 标题
var ti = Array.from(inputs).find(i => i.placeholder === '请输入标题');
ns.call(ti, '灭门之夜');
ti.dispatchEvent(new Event('input', {bubbles: true}));
```

## 写入正文（ProseMirror 编辑器）

番茄小说的编辑器基于 **ProseMirror**。编辑器元素为：
```
div.serial-editor-content div.ProseMirror[contenteditable]
```

### 短内容（<2000 字）— innerHTML 方式

```javascript
var pm = document.querySelector('.serial-editor-content .ProseMirror');
pm.innerHTML = '<p>段落1</p><p>段落2</p>...';
pm.dispatchEvent(new Event('input', {bubbles: true}));
```

**注意**：
- 内容必须是 HTML 格式，用 `<p>` 包裹每个段落
- 写入后必须 dispatch `input` 事件，否则字数统计不更新
- 追加内容：`pm.innerHTML = pm.innerHTML + '<p>新增段落</p>';`

### 长内容（2000+ 字，含中文字符）— 推荐 base64 + execCommand 方式

**⚠️ 为什么不能直接用 innerHTML？** ProseMirror 有内部状态机。直接设置 innerHTML 会导致 DOM 和内部状态不同步——文字显示对了，但字数统计和保存按钮不更新。exexCommand('insertHTML') 经过 ProseMirror 的输入管道，正确更新 DOM 和内部状态。

**⚠️ 为什么不能直接用 Input.insertText？** Chrome DevTools 的 Input.insertText CDP 方法在 ProseMirror 中只插入第一个段落，所有后续换行会丢失。

**⚠️ 为什么用 base64？** 直接把中文文本嵌入 JS 字符串会导致乱码。Base64 编码保证 ASCII-safe 传输。atob() 解码后必须用 TextDecoder('utf-8') 正确处理多字节字符。

**⚠️ 为什么存全局变量？** Runtime.callFunctionOn 传大字符串参数（10K+）会 WebSocket 超时。先用 Runtime.evaluate 存为全局变量，再在第二次调用中读取。

完整三步模式：

#### Step 1: Python 端 — 读取内容并 base64 编码
```python
import base64
with open('/path/to/chapter.md', 'r', encoding='utf-8') as f:
    content = f.read()
b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
```

#### Step 2: CDP — 注入 base64 到页面全局变量 + 清空编辑器
```python
# 存 base64 到全局变量
resp = cdp_call(ws, "Runtime.evaluate", {
    "expression": "window.__hermesB64 = '" + b64 + "';",
    "returnByValue": False
}, session_id=session_id)
time.sleep(0.3)

# 清空编辑器
resp = cdp_call(ws, "Runtime.evaluate", {
    "expression": """
(function() {
    var editor = document.querySelector('.ProseMirror');
    editor.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');
    return 'cleared';
})()
""",
    "returnByValue": True
}, session_id=session_id)
time.sleep(0.5)
```

#### Step 3: CDP — 解码并插入
```python
resp = cdp_call(ws, "Runtime.evaluate", {
    "expression": """
(function() {
    var editor = document.querySelector('.ProseMirror');
    editor.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');

    // 解码 UTF-8 base64
    var binary = atob(window.__hermesB64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    var decoder = new TextDecoder('utf-8');
    var text = decoder.decode(bytes);

    // 双换行=段落，单换行=段内换行
    var paras = text.split('\\n\\n');
    var html = '<p>' + paras.map(function(p) {
        return p.replace(/\\n/g, '<br>');
    }).join('</p><p>') + '</p>';

    var success = document.execCommand('insertHTML', false, html);
    return 'ok: textLen=' + editor.textContent.length;
})()
""",
    "returnByValue": True
}, session_id=session_id)
```

### 检查字数

```javascript
document.querySelector('.publish-header-count')?.textContent
// 返回数字字符串，如 "5996"
```

### 保存草稿

```javascript
Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('存草稿'))?.click();
```

保存后页面显示"已保存到云端"。

## 章节管理

### 新建章节
1. 导航到章节管理页：`/main/writer/chapter-manage/{bookId}?type=1`
2. 点击"新建章节"链接：`document.querySelector('a').find(a => a.textContent.includes('新建章节'))?.click()`
3. 或直接导航到：`/main/writer/{bookId}/publish/?enter_from=newchapter`

## 已知陷阱

| 问题 | 原因 | 解决 |
|------|------|------|
| **React 表单填值无效** | React 控制 input.value，直接赋值被忽略 | 必须用 `Object.getOwnPropertyDescriptor` 获取 native setter |
| **创建新书按钮无效** | 按钮事件绑定在 React 虚拟 DOM 上 | 直接导航到 `/main/writer/create`，或通过 CDP dispatchEvent |
| **编辑器内容不保存** | ProseMirror 需要 input 事件触发 | 设置 innerHTML 后必须 dispatch `new Event('input', {bubbles: true})` |
| **滑块验证码** | 反爬机制，点击"获取验证码"触发 | 需要用户通过 noVNC 手动滑动，或在可信环境使用 |
| **WebSocket 403** | Chrome CDP 安全限制 | 启动 Chromium 时加 `--remote-allow-origins=*` |
| **两个浏览器实例混淆** | Hermes 内部 headless + visible 浏览器 | 始终操作 CDP port 9222 的那个，不用 browser_navigate 等工具 |
| **Target.attachToTarget 超时** | 在直接 attach 到 React SPA 的 iframe 时可能超时 | 用 `flatten: True`，并确保先 `Target.getTargets` 拿到正确的 targetId |
| **存草稿→版本冲突弹窗** | 云端版本和本地缓存不一致 | 点"继续编辑本地" → 再次点"存草稿" → 确认"保存成功" |

## 删除草稿/章节

### 步骤
1. 导航到章节管理页：`/main/writer/chapter-manage/{bookId}?type=1`
2. 点击"草稿箱"标签页切换
3. 找到要删除章节行的删除图标（`.icon-delete`，每行一个）
4. 按从上到下的顺序点击删除图标（第1个=顶行，第2个=第二行...）
5. 确认弹窗中点击"删除"按钮

```javascript
// 切换到草稿箱
Array.from(document.querySelectorAll('div, span')).find(el => el.textContent.trim() === '草稿箱')?.click();

// 删除第N个草稿（0-indexed）
Array.from(document.querySelectorAll('.icon-delete'))[N].click();
// 等待弹窗出现
Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '删除').click();
```

**陷阱**：删除弹窗中有"取消"和"删除"两个按钮——要点"删除"不是"确定"。而且"新增读者纠错功能"的弹窗可能会干扰，需要先关掉它（点"我知道了"）。

## 创建多章的工作流（逐章发布）

当需要创建第N+1章时：

1. 导航到章节管理页
2. 点击"新建章节"按钮/链接（或直接导航到 `{bookId}/publish/?enter_from=newchapter`）
3. 填写章节号、标题、正文
4. 存草稿
5. 重复

```javascript
// 从章节管理页新建章节
// 先导航到章节管理
// Page.navigate -> /main/writer/chapter-manage/{bookId}?type=1
// 然后点击新建章节链接
Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('新建章节'))?.click();
// 或直接导航到 publish URL
// Page.navigate -> /main/writer/{bookId}/publish/?enter_from=newchapter
```

**注意**：第一次进入 publish 页面会分配一个新的 chapterId，后面修改草稿用 modifydraft 参数。

## 扩充章节字数到目标值

当章节字数不足目标（如~6000字）时：

1. 导航到章节编辑页（modifydraft）
2. 获取当前 ProseMirror 内容
3. 追加新段落
4. 保存

```javascript
// 追加内容到现有章节
var pm = document.querySelector('.serial-editor-content .ProseMirror');
pm.innerHTML = pm.innerHTML + '<p>新增内容...</p>';
pm.dispatchEvent(new Event('input', {bubbles: true}));
// 检查字数
document.querySelector('.publish-header-count')?.textContent;
```

## 字数目标

- 通常每章目标：~6000字
- 检查方式：`document.querySelector('.publish-header-count')?.textContent`
- 不足时追加内容，超额时下一章缩减

### 保存草稿并处理版本冲突

```javascript
// 1. 点击存草稿
Array.from(document.querySelectorAll('button'))
    .find(el => el.textContent.includes('存草稿'))?.click();

// 2. 检查版本冲突弹窗（"选择云端版本" / "继续编辑本地"）
// 点"继续编辑本地"保留本地修改
Array.from(document.querySelectorAll('button'))
    .find(b => b.textContent.trim() === '继续编辑本地')?.click();

// 3. 再次点击存草稿
Array.from(document.querySelectorAll('button'))
    .find(el => el.textContent.includes('存草稿'))?.click();

// 4. 确认保存成功
document.body.innerText.includes('保存成功')
```

### 删除书籍/作品

番茄小说作家后台没有直接的"删除"按钮。需要找到"作品设置"或"废弃作品"入口。

```javascript
// 方案1：导航到作品设置页（如果已知book_id）
// window.location.href = '/main/writer/book-info/{bookId}?type=1'

// 方案2：从章节管理页找设置入口
// 先导航到 /main/writer/chapter-manage/{bookId}?type=1
// 然后找"作品设置"或"更多"按钮

// 方案3：冻结/下架
// 在作品管理页找"冻结"或"停止连载"或"下架"选项
```

- [ ] 确认在 visible 浏览器（CDP:9222）上操作
- [ ] 创建新书时用 nativeInputValueSetter 填React表单
- [ ] 章节编辑器用 ProseMirror.innerHTML 写入
- [ ] 写入后 dispatch input 事件
- [ ] 保存草稿后确认"已保存到云端"提示
- [ ] 检查字数是否符合要求（~6000字/章）
- [ ] 更新本地 02-写作计划.json
