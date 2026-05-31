# QQbot Media and noVNC SkillHub Package Notes

This reference records concrete details from maintaining the `tencent-novnc-chromium-cdp` SkillHub package.

## Package Shape

The user expects SkillHub upload packages to be clean:

```text
zip root/
└── SKILL.md
```

No `references/`, README, GitHub docs, generated screenshots, or helper scripts should be included unless explicitly requested.

## noVNC Deployment Reminders

For a noVNC + Chromium + CDP deployment skill, the pre-run reminder should include:

- Server recommendation: at least 2 CPU / 4 GB RAM (`2H4G`).
- Required port: `6080/tcp` for noVNC web access.
- Optional advanced ports: `5900/tcp` for raw VNC and `9222/tcp` for Chromium CDP. These should not be publicly exposed by default; if opened, restrict source IP.
- Estimated time: normally 5-15 minutes; slow networks, low-end servers, or first-time dependency installation may take 20-30 minutes.
- Progress behavior: check deployment state every 30 seconds, auto-fix common issues when safe, and send a short progress update about once per minute.

## Completion Feedback

When deployment succeeds, the executing Agent should return:

- noVNC URL: `http://<server-ip>:6080/vnc.html`
- browser status, ideally after opening `https://www.baidu.com/`
- screenshot proof
- port reminder for `6080/tcp`
- warning that CDP `9222/tcp` is for Agent/local control and should not be public

## QQbot Screenshot Rule

QQbot/QQ channel image delivery is special:

1. Screenshot must be copied to:

```bash
mkdir -p ~/.openclaw/media/qqbot
cp /tmp/remote-browser.png ~/.openclaw/media/qqbot/remote-browser.png
```

2. Reply with:

```text
<qqmedia>/root/.openclaw/media/qqbot/remote-browser.png</qqmedia>
```

3. For non-QQbot channels, regular media paths are fine:

```text
MEDIA:/tmp/remote-browser.png
```

## Update Log Example

```markdown
## v1.1.0 更新日志

- 新增 QQbot/QQ 通道发图适配：图片必须放到 `~/.openclaw/media/qqbot/`，并使用 `<qqmedia>...</qqmedia>` 标签发送。
- 保留普通通道发图方式：非 QQbot 通道继续使用 `MEDIA:/tmp/remote-browser.png`。
- 保留部署进度提醒：安装过程中每 30 秒检查一次状态，每分钟汇报一次部署进度。
- 保留部署完成反馈：自动打开百度页面，发送 noVNC 地址、截图和端口提醒。
```
