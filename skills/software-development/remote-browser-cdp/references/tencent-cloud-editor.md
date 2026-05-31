# Tencent Cloud Developer Article Editor

Editing articles on `cloud.tencent.com/developer` via CDP.

## Navigation

- Article view: `https://cloud.tencent.com/developer/article/{id}`
- Edit URL: **NOT** `/article/{id}/edit` (returns 404). Must click the "编辑" button on the article page.
- Edit target URL after click: `https://cloud.tencent.com/developer/article/write-new/{id}`

## Login State Detection

Detect login by checking for logged-in indicators, NOT just the presence of "登录" text (Tencent Cloud shows "登录/注册" in some layouts even when logged in):

```javascript
// Reliable login check
var body = document.body.innerText;
var loggedIn = body.includes("退出登录") && body.includes("消息中心");
// Also check for avatar/dropdown
var hasUserMenu = !!document.querySelector("[class*=user-center], [class*=account]");
```

## Editor Structure

The editor uses **CodeMirror** (wrapping mode) with a hidden textarea:

| Element | Purpose |
|---------|---------|
| `textarea#code` | Contains the full markdown content |
| `.CodeMirror` | Visual editor layer (synced with textarea) |
| `input.cdc-article-editor__title-input` | Article title |

**To set content**, write to `textarea#code` AND trigger events so CodeMirror picks it up:

```javascript
var ta = document.getElementById("code");
ta.value = newContent;
ta.dispatchEvent(new Event("input", { bubbles: true }));
ta.dispatchEvent(new Event("change", { bubbles: true }));
// Also update CodeMirror if present
var cm = document.querySelector(".CodeMirror");
if (cm && cm.CodeMirror) {
    cm.CodeMirror.setValue(newContent);
}
```

## Publish Flow

1. Click "去发布" button (class: `cdc-btn--primary`). JavaScript `.click()` works.
2. A **drawer** opens (`.editor-publish-drawer__inner`) with publish settings.
3. Click "确认发布" in the drawer.
4. Article enters "审核中" status — "我们预计将在 20 分钟内完成审核".

The publish drawer contains:
- 文章来源 (原创/转载/翻译)
- 文章标签
- 专栏选择
- 摘要 (max 200 chars)
- 封面图
- 文章设置 (comments, auto-link)

## Mouse Click on React-bound Buttons

When `.click()` on the "编辑" button doesn't navigate, use `Input.dispatchMouseEvent`:

```python
# Find element position
rect = element.getBoundingClientRect()
x = rect.left + rect.width / 2
y = rect.top + rect.height / 2

cdp_call(ws, "Input.dispatchMouseEvent", {
    "type": "mousePressed", "x": x, "y": y,
    "button": "left", "clickCount": 1
})
cdp_call(ws, "Input.dispatchMouseEvent", {
    "type": "mouseReleased", "x": x, "y": y,
    "button": "left", "clickCount": 1
})
```

Note: Dispatch to the **current page tab**, not to a browser-level session.

## Pitfalls

1. **CSRF/redirect guard**: Direct navigation to `/article/{id}/edit` hits a 404 or redirect to community home. Always click the edit button on the article page.
2. **Draft auto-save**: Clicking "去发布" auto-saves a draft (URL gains `?draftId=xxx`). The publish drawer opens over the editor.
3. **Button state timing**: "存草稿" may show as `is-disabled` momentarily after auto-save. Wait 1-2s before reading button state.
4. **Login required**: All edit operations require a logged-in Tencent Cloud account. Check for "退出登录" text to confirm login state.
