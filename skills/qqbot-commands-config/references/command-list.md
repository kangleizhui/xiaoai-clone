# Hermes Agent QQ 机器人指令清单

24条斜杠指令，QQ开放平台「功能配置 → 指令」配置用。

| # | 指令名 | 指令介绍 | 备注 |
|---|--------|----------|------|
| 1 | new | 新建会话 | /new |
| 2 | topic | 管理私聊主题 | /topic |
| 3 | retry | 重发消息 | /retry |
| 4 | undo | 删除上轮对话 | /undo |
| 5 | title | 设置会话标题 | /title |
| 6 | branch | 会话分支 | /branch, /fork |
| 7 | compress | 压缩上下文 | /compress |
| 8 | rollback | 恢复快照 | /rollback |
| 9 | stop | 终止后台进程 | /stop |
| 10 | approve | 允许高危指令 | /approve |
| 11 | deny | 拒绝高危指令 | /deny |
| 12 | background | 后台执行 | /background, /bg, /btw |
| 13 | agents | 查看任务 | /agents, /tasks |
| 14 | queue | 排队执行 | /queue, /q |
| 15 | steer | 插入消息 | /steer |
| 16 | goal | 管理任务目标 | /goal |
| 17 | subgoal | 管理附加要求 | /subgoal |
| 18 | status | 查看会话信息 | /status |
| 19 | whoami | 查看权限 | /whoami |
| 20 | profile | 查看配置 | /profile |
| 21 | sethome | 设置默认频道 | /sethome, /set-home |
| 22 | resume | 恢复历史会话 | /resume |
| 23 | sessions | 浏览历史会话 | /sessions |
| 24 | model | 切换模型 | /model, /provider |

## Python 格式

```python
CMDS = [
    ("new","新建会话"),("topic","管理私聊主题"),("retry","重发消息"),
    ("undo","删除上轮对话"),("title","设置会话标题"),("branch","会话分支"),
    ("compress","压缩上下文"),("rollback","恢复快照"),("stop","终止后台进程"),
    ("approve","允许高危指令"),("deny","拒绝高危指令"),("background","后台执行"),
    ("agents","查看任务"),("queue","排队执行"),("steer","插入消息"),
    ("goal","管理任务目标"),("subgoal","管理附加要求"),("status","查看会话信息"),
    ("whoami","查看权限"),("profile","查看配置"),("sethome","设置默认频道"),
    ("resume","恢复历史会话"),("sessions","浏览历史会话"),("model","切换模型"),
]
```
