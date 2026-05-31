# 番茄小说作家后台自动化

## 书号格式
- 书号是 19 位数字，如 `7642400637614817854`
- 编辑页 URL：`https://fanqienovel.com/main/writer/{book_id}/publish/`
- 创建页 URL：`https://fanqienovel.com/main/writer/create`

## 创建新书
1. 导航到 `/main/writer/create`
2. 用 React 兼容方式填表（见 SKILL.md 技法1）：
   - 书名：`input[placeholder="请输入作品名称"]`
   - 男频/女频：`input[type="radio"]` 第一个
   - 主角名：`input[placeholder^="请输入主角名"]`
   - 简介：`textarea[placeholder*="作品简介"]`
   - 标签：需要交互 Arco Select 组件（点击后选下拉选项），可尝试跳过
3. 点击"立即创建"按钮

**Pitfall：** "立即创建"有时不会触发页面跳转。检查 `localStorage` 中是否出现 `authorWebDraft_{book_id}` 来确认是否创建成功。书号可从该 key 中提取。

## 章节编辑
- 章节号输入框：72px 宽，位于 `(566, 240)` 附近
- 章节标题输入框：`input[placeholder="请输入标题"]`，位于 `(696, 240)`
- 正文编辑器：`.ProseMirror` 类元素，位于 `x=532`

## 保存草稿
- 对于已有章节：顶部有"存草稿"按钮
- 对于新创建的首章：可能只有"下一步"按钮
- 保存成功会弹窗显示"保存成功"
- 如出现"版本冲突提示"对话框，先点"继续编辑本地"，再重新点"存草稿"

## 本地草稿持久化
- 草稿储存在 `localStorage`，key 格式：`authorWebDraft_{book_id}`
- 即使书未创建成功，草稿也可能已保存
- 目前经过排查，发现"立即创建"实际上并未成功——因为并没有显示该书

## 已有书籍
- 历史书籍 ID 可在 localStorage 中找到：
  - `authorWebDraft_7642399629786481214` — 旧书《腹黑仙途》第1章
  - `authorWebDraft_7642400637614817854` — 本次尝试的《你好，顾欣欣》草稿（7856字）
