# 番茄小说 (Fanqienovel) Writer Platform — CDP Automation Reference

> Domain-specific reference for operating the 番茄小说 writer backend via CDP.

## URL Map

| Page | URL Pattern |
|------|-------------|
| Writer Dashboard | `https://fanqienovel.com/main/writer/` |
| Book Management | `https://fanqienovel.com/main/writer/book-manage` |
| Create New Book | `https://fanqienovel.com/main/writer/create` |
| Chapter Manager | `https://fanqienovel.com/main/writer/chapter-manage/{book_id}&{book_name}?type=1` |
| Chapter Editor | `https://fanqienovel.com/main/writer/{book_id}/publish/{chapter_id}?enter_from=newchapter_1` |

## Creating a New Book

Navigate to `/main/writer/create`. Fill the form fields:

```javascript
// Book name (max 15 chars)
nativeInputValueSetter.call(nameInput, '腹黑仙途');
nameInput.dispatchEvent(new Event('input', {bubbles: true}));

// Target audience: 女频 (value=0) or 男频 (value=1)
document.querySelector('input[name="pindao"][value="0"]').checked = true;
document.querySelector('input[name="pindao"][value="0"]')
  .dispatchEvent(new Event('change', {bubbles: true}));

// Protagonist name (max 5 chars)
nativeInputValueSetter.call(protInput, '苏瑶');
protInput.dispatchEvent(new Event('input', {bubbles: true}));

// Description (50-500 chars)
nativeTextAreaSetter.call(textarea, 'description...');
textarea.dispatchEvent(new Event('input', {bubbles: true}));
```

Submit: `document.querySelector('button').find(b => b.textContent.includes('立即创建'))?.click()`

## Writing a Chapter

### Input fields

```javascript
// Chapter number
nativeInputValueSetter.call(numInput, '1');
numInput.dispatchEvent(new Event('input', {bubbles: true}));

// Chapter title
nativeInputValueSetter.call(titleInput, '灭门之夜');
titleInput.dispatchEvent(new Event('input', {bubbles: true}));
```

### ProseMirror content editor

The chapter content editor is a ProseMirror instance. See the `remote-browser-cdp` skill's `references/cdp-dom-interaction.md` for full patterns. Key takeaways:

1. **Clear existing content**: `editor.focus(); document.execCommand('selectAll'); document.execCommand('delete');`
2. **Insert large UTF-8 content**: Base64 encode in Python, store in `window.__hermesB64`, decode with `atob()` + `TextDecoder('utf-8')`, then `document.execCommand('insertHTML', false, html)` with `<p>` tags.
3. **Do NOT use `Input.insertText`** CDP method — it only inserts the first paragraph.
4. **Do NOT use `Runtime.callFunctionOn`** with large string args — it times out. Use global variables.

### Saving a draft

```javascript
// Find and click save
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === '存草稿') {
        buttons[i].click();
        break;
    }
}
```

### Handling version conflict dialog

When saving triggers a "版本冲突" (version conflict) modal with "选择云端版本" and "继续编辑本地" buttons:

```javascript
// Keep local changes
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === '继续编辑本地') {
        buttons[i].click();
        break;
    }
}
// Then click save again
```

### Verifying successful save

Check for success toast messages:

```javascript
Array.from(document.querySelectorAll('[class*=success],[class*=toast]'))
    .map(el => el.textContent.trim())
    .filter(t => t.length > 0 && t.length < 100)
```

### Detecting save success

The platform shows a "保存成功" toast after successful save. The URL may also change to include `?enter_from=modifydraft` after saving a draft.

## Book Info Query

After creating a book, the URL changes to:
`https://fanqienovel.com/main/writer/book-info/{book_id}?type=1`

The book_id can be extracted from this URL.

## Finding Interactive Elements

The writer backend uses Arco Design components. Buttons have class `arco-btn`. Common button texts:
- 存草稿 (save draft)
- 下一步 (next step)
- 立即创建 (create now)
- 继续编辑本地 (keep local edits - conflict dialog)
- 选择云端版本 (use cloud version - conflict dialog)
