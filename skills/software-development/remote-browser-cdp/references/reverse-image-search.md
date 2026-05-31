# CDP Reverse Image Search — 通过 CDP 浏览器反向搜图

## 概述

通过 CDP 控制 Chromium 浏览器，将本地图片上传到反向图片搜索引擎（Bing、搜狗、Yandex 等），获取相似图片结果。

## 核心思路

1. 启动本地 HTTP 服务器托管图片（避免 base64 传大文件）
2. 导航到搜索引擎的图片搜索页
3. 用 `DOM.querySelector` + `DOM.setFileInputFiles` 注入图片到 `<input type="file">`
4. 等待结果，用 `Runtime.evaluate` 提取页面内容

## 前置：启动本地 HTTP 服务器

```bash
cd /path/to/image/dir && python3 -m http.server 9876 &
```

图片 URL 形如：`http://<server-ip>:9876/image.jpg`

## 各引擎对比

| 引擎 | 文件上传 | 结果质量 | 备注 |
|------|----------|----------|------|
| **Bing** | ✅ id=`sb_fileinput` | ⭐⭐⭐ 最好 | 直接给出分类+来源链接 |
| **搜狗** | ✅ `input[type="file"]` | ⭐⭐ 一般 | 显示相似图片但有"人物识别"等标签，点击后不见得有用 |
| **Yandex** | URL 直传 | ⭐⭐ 一般 | 支持 `?url=` 参数但需要手动选搜索区域 |
| **Google Lens** | URL 直传 | ❌ | 触发 CAPTCHA（`google.com/sorry`） |
| **百度** | 上传被拒 | ❌ | API 上传返回 `{"status":1,"msg":"Reject"}` |

**推荐顺序：Bing > 搜狗 > Yandex**（Bing 最省心）

## Bing 图片搜索（首选）

### 步骤

```python
import json, time, urllib.request, websocket

# 连接 CDP
tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
page = next(t for t in tabs if t.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], 
    header=['Origin: http://127.0.0.1:9222'], timeout=30)

msg_id = [0]
def call(method, params=None):
    msg_id[0] += 1
    ws.send(json.dumps({'id': msg_id[0], 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == msg_id[0]:
            return msg

call('Page.enable')
call('Runtime.enable')
call('DOM.enable')

# 1. 导航到 Bing 图片
call('Page.navigate', {'url': 'https://www.bing.com/images'})
time.sleep(3)

# 2. 点击相机按钮（"Search using an image"）
call('Runtime.evaluate', {
    'expression': '''
(function() {
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        var t = all[i].getAttribute('title') || all[i].getAttribute('aria-label') || '';
        if (t.includes('Search using an image')) { all[i].click(); return 'clicked'; }
    }
    return 'not found';
})()
''',
    'returnByValue': True,
})
time.sleep(2)

# 3. 注入图片到文件输入框
doc = call('DOM.getDocument', {'depth': 0})
root_id = doc['result']['root']['nodeId']
res = call('DOM.querySelector', {'nodeId': root_id, 'selector': '#sb_fileinput'})
node_id = res['result']['nodeId']
call('DOM.setFileInputFiles', {'files': ['/path/to/image.jpg'], 'nodeId': node_id})
time.sleep(10)

# 4. 提取结果
res = call('Runtime.evaluate', {
    'expression': '({title: document.title, url: location.href, text: document.body.innerText.substring(0, 2000)})',
    'returnByValue': True,
})
print(res['result']['result']['value']['text'])
```

### Bing 结果格式

搜索结果页面 title 形如 `"<分类> - Search"`，文本中包含来源链接（Pixabay、Shutterstock、Pexels、Pinterest 等）。

## 搜狗图片搜索（备选）

```python
# 导航
call('Page.navigate', {'url': 'https://pic.sogou.com/'})
time.sleep(4)

# 点击"以图搜图"按钮 (id="cameraIco")
call('Runtime.evaluate', {
    'expression': 'document.getElementById("cameraIco").click();',
    'returnByValue': True,
})
time.sleep(2)

# 找文件输入框并注入
doc = call('DOM.getDocument', {'depth': 0})
root_id = doc['result']['root']['nodeId']
res = call('DOM.querySelector', {'nodeId': root_id, 'selector': 'input[type="file"]'})
node_id = res['result']['nodeId']
call('DOM.setFileInputFiles', {'files': ['/path/to/image.jpg'], 'nodeId': node_id})
time.sleep(8)
```

搜狗结果页会显示"相似图片"和"人物识别"/"找高清大图"标签，但点击标签后的结果有限。

## Yandex 图片搜索（URL 方式）

Yandex 支持通过 URL 参数直接传入图片，无需文件上传：

```python
url = f'https://yandex.com/images/search?rpt=imageview&url=http://<server-ip>:9876/image.jpg'
call('Page.navigate', {'url': url})
time.sleep(5)
```

注意：Yandex 加载图片后会提示"Move the frames to select the search area"——通常需要手动交互。

## 常见问题

### 图片注入后无反应
- 确认 `DOM.setFileInputFiles` 的 nodeId 正确
- 等待足够时间（8-10s），部分搜索引擎上传后需要 AJAX 处理
- 检查 `<input type="file">` 的 `accept` 属性是否匹配图片格式

### 文件输入框找不到
- 部分搜索引擎在点击相机按钮后才动态创建文件输入框
- 先 click，再 querySelector

### Google 触发 CAPTCHA
- Google Lens（`lens.google.com/uploadbyurl?url=...`）会重定向到 `google.com/sorry`
- 无解，需人工验证

### 百度拒绝上传
- `graph.baidu.com/upload` 返回 `{"status":1,"msg":"Reject"}`
- 可能需要特定的 Referer/Cookie，CDP 自动化场景不适用
