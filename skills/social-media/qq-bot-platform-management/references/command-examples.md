# QQ Bot Command Examples

All 43 Hermes slash commands formatted for QQ bot platform 指令.

Format: `command_name | description` (no symbols in description — Chinese/English/numbers only)

```
new|新建会话
topic|管理私聊主题
retry|重发消息
undo|删除上轮对话
title|设置会话标题
branch|会话分支
compress|压缩上下文
rollback|恢复快照
stop|终止后台进程
approve|允许高危指令
deny|拒绝高危指令
background|后台执行
agents|查看任务
queue|排队执行
steer|插入消息
goal|管理任务目标
subgoal|管理附加要求
status|查看会话信息
whoami|查看权限
profile|查看配置
sethome|设置默认频道
resume|恢复历史会话
sessions|浏览历史会话
model|切换模型
codex-runtime|切换运行服务
personality|调用预设人设
footer|控制元数据展示
yolo|极速模式
reasoning|调整推理模式
fast|切换加速模式
voice|切换语音功能
curator|后台技能维护
kanban|多人协同看板
reload-mcp|重载MCP服务
reload-skills|刷新技能
commands|分页查看指令
help|查看帮助
restart|重启网关
usage|查看令牌用量
insights|查看使用统计
platform|管理服务节点
update|更新版本
debug|生成调试日志
```

## Derived Rules

From the user's original input (e.g., `新建会话（/reset）`, `后台执行（/bg、/btw）`):
1. Take only the Chinese text before `（`
2. Remove all symbols: `(` `)` `/` `、` `-`
3. The command name field gets the English word (no `/` — platform adds it)
4. The description field gets the cleaned Chinese text
