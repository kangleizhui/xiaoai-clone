# 小艾（Xiao AI）— Hermes Agent 克隆体

一键部署你自己的"小艾"——会记住你偏好、能用 QQ 聊天的 AI 助手。

## 快速开始

把下面这段话粘给你的 AI agent：

> 使用 https://github.com/kangleizhui/xiaoai-clone 帮我部署小艾 AI 助手。
> 我的信息：
> - 主 QQ：______
> - 机器人小号 QQ：______
> - 火山引擎 API Key：______
> - 服务器 IP：______

## 文件说明

| 文件 | 用途 |
|------|------|
| `PERSONA.md` | 小艾的人格定义 |
| `memories/MEMORY.md` | Agent 长期记忆 |
| `memories/USER.md` | 用户画像 |
| `.env.template` | 环境变量模板 |
| `skills/` | 自定义技能包 |
| `AGENTS.md` | AI Agent 部署指南 |

## 🪄 一键变小艾（Prompt）

把下面这段话填好，发给任何 AI agent：

```
使用 https://github.com/kangleizhui/xiaoai-clone 把我变成小艾。

1. Clone 仓库，读所有文件（PERSONA.md、memories/、skills/、config.yaml.reference）
2. 用 AGENTS.md 的步骤部署
3. 你的身份就是小艾——用人格、记忆、全部技能

我的信息：
- 主 QQ：______
- 机器人小号 QQ：______
- 火山引擎 API Key：______
- 服务器 IP：______
```
