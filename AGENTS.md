# AGENTS.md — 给小艾克隆体的部署指南

> 你（AI）正在帮用户部署"小艾"——一个跑在 QQ 上的 AI 助手。
> 本质是 Hermes Agent + 小艾人格 + 长期记忆 + QQ 机器人接入。

## 部署步骤

### 1. 安装 Hermes Agent
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

### 2. Clone 这个 repo
```bash
cd ~ && git clone https://github.com/kangleizhui/xiaoai-clone.git
cd xiaoai-clone
```

### 3. 填入配置
```bash
cp .env.template ~/.hermes/.env
# 编辑 ~/.hermes/.env，填入真实的 API Key 和密码
nano ~/.hermes/.env
```

### 4. 部署文件
```bash
cp PERSONA.md ~/.hermes/PERSONA.md
cp memories/MEMORY.md ~/.hermes/memories/MEMORY.md
cp memories/USER.md ~/.hermes/memories/USER.md
cp -r skills/* ~/.hermes/skills/
cp scripts/* ~/.hermes/scripts/
```

### 5. 配置 config.yaml
参考 `config.yaml.reference`，根据自己的 providers 调整。

### 6. 启动
```bash
hermes gateway install
hermes gateway start
```

## 关键信息
- 火山引擎 base_url 必须用 `/api/coding/v3`，不能用 `/api/v3`
- NapCat 需配置 WebSocket 反连 `ws://127.0.0.1:3001/onebot/v11/ws`
- 有 visible 浏览器时用 CDP terminal 命令操作，不用内置 browser_* 工具
