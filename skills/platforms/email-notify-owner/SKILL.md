---
name: email-notify-owner
description: "执行大动作后必须给主人邮箱发 HTML 邮件汇报（QQ邮箱 himalaya，Apple 产品风）"
version: 3.0.0
author: xiaoai
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [notification, email, qq, himalaya, audit, changelog]
---

# 给主人发通知邮件（HTML / Apple 风）

主人（2556208918@qq.com）要求：每次小艾做"大动作"，必须发邮件汇报。

主人对邮件视觉有强偏好，**必须用 Apple 产品风的 HTML 模板**发送。风格演进历史：v1.0 "AI 风卡片"（emoji 太多、配色饱和）→ 被否决 → v2.0 changelog/工程师日志风 → 主人觉得不好看了 → **v3.0 Apple 产品风**（当前）。完整由来与色板/字体/红线见 `references/style-guide.md`。

## 触发条件（任意一条命中就必须发）

1. **同步/push 到 GitHub**（包括 sync.sh、git push、新建 repo）
2. **安装/卸载系统服务**（apt install、systemd unit 增删、新装 CLI）
3. **修改 systemd / nginx / cron 配置**
4. **修改 ~/.hermes/ 重要配置**（config.yaml、PERSONA.md、memories/）
5. **部署新服务或大改现有服务**（端口/认证/反代/数据库）
6. **执行不可逆操作**（rm -rf、drop table、delete repo、force push）

**不需要发**：纯查询、读文件、临时 cd、cat、ls、写小说章节、聊天回复。

## 发送流程

1. 复制模板 `templates/notify-changelog.html` 到一个临时文件（如 `/tmp/notify.html`）。
2. 替换占位符（见模板顶部注释里的清单：`__SUBJECT_TAIL__` / `__TIMESTAMP__` / `__LOG_TYPE__` / `__TITLE__` / `__ONELINE_DESC__` / `__DIFF_ROWS__` / `__META_ROWS__` / `__STATUS_*__` / `__EXIT_CODE__` / `__DURATION__` / `__ROLLBACK_CMD__` / `__LOG_NUM__`）。
3. 用 `himalaya` 发 HTML 邮件：

```bash
SUBJECT="[小艾日志] <一句话概括>"
BODY_HTML=$(cat /tmp/notify.html)

cat << EOF | himalaya template send
From: 2556208918@qq.com
To: 2556208918@qq.com
Subject: ${SUBJECT}
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

${BODY_HTML}
EOF
```

主题前缀**统一 `[小艾日志]`**（不是 `[小艾通知]`，那是 v1.0 旧风格）。

## 模板风格红线（违反一条就回去返工）

- ❌ **渐变色**（标题、顶栏、背景）→ 用户原话："太AI感了"，一律用纯色
- ❌ emoji 满天飞 / 多张圆角卡片堆叠 / 紫色配色 → 被定性为 "AI 风"
- ❌ 大留白 + 全细体 + 一根灰线 + 单一红强调 → 被定性为 "太极简"
- ✅ Apple 产品风：白底 + 纯蓝细顶条（3px `#0071e3`）+ 纯黑大标题（`#1d1d1f`）
- ✅ 圆角 16px 卡片 + 柔和阴影（`box-shadow:0 2px 12px rgba(0,0,0,0.06)`）
- ✅ 状态用圆角胶囊（`border-radius:20px`），不用方块徽章
- ✅ diff 标记：`+ NEW` 绿 `#34c759` / `~ MOD` 蓝 `#0071e3` / `- DEL` 红 `#ff375f`
- ✅ 代码块：深色圆角（`#1d1d1f` 底），等宽字体
- ✅ emoji 数量 ≤ 0（`●` `+` `~` `↑` `$` 是 ASCII 字符不算 emoji）
- ✅ 一封邮件只发一件事，多个动作发多封

## 配置依赖（已就绪）

- 配置文件：`~/.config/himalaya/config.toml`
- 授权码：`/root/.config/himalaya/.qq_authcode`（600 权限）
- 关键参数：`message.send.save-copy = false`（不加会发件成功但报错退出 1）

## 执行时机

- **每次大动作完成后立即发**，不要攒一封"今日汇总"。
- 失败也要发，主题前加 `[FAIL]`，模板里 `STATUS=FAIL`、`EXIT=<码>`，写清楚卡在哪步。
- 一个会话连续多个独立动作 → 多封独立邮件（每封 `/log #NNN` 编号递增）。

## 反模式

- ❌ 只在 QQ 回复，不发邮件（主人可能没看 QQ）
- ❌ 用纯文本邮件应付（v1.0 模板已过期）
- ❌ 邮件里只写"已完成"，不填 DIFF/META/ROLLBACK 块
- ❌ 一个会话连续 5 个动作只发最后一封（每个大动作单独一封）
- ❌ 用空主题或随便写"测试"（主题必须能让主人一眼看懂干了啥）
- ❌ 用渐变色做标题/顶栏/强调（用户明确反感："太AI感了"）
- ❌ 偷工减料用 Google Fonts / web font（QQ 邮箱客户端剥掉后字体回退会丑爆）

## 文件清单

- `templates/notify-changelog.html` — 主模板（必须用这个）
- `references/style-guide.md` — 完整色板/字体/红线/历史否决版本说明
