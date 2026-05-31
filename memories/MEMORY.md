邮箱：QQ邮箱${OWNER_QQ_EMAIL} himalaya ~/.config/himalaya/。邮件模板v3.0.0 Apple风（纯蓝顶条+纯黑标题+圆角卡片+胶囊状态，无渐变无emoji）。skill: email-notify-owner。
§
小说创作偏好：都市现实情感（坦克风格）——普通底层男主（非富二代），第一人称男性视角，现实主义，慢节奏细节描写，虐心带黑色幽默。标题偏好"渣男口吻"（漫不经心但句句扎心）。上次创作《你好，顾欣欣》（深圳外卖骑手×旧情人重逢，男主贵州/女主云南）。
§
火山 Coding Plan：provider=custom, base_url=https://ark.cn-beijing.volces.com/api/coding/v3, api_key=VOLC_ARK_API_KEY(.env)。默认deepseek-v4-pro。context_length: deepseek-v4-pro/flash=1024k, kimi-k2.6=256k, doubao-seed-2.0-*=256k, minimax-m2.7=200k, glm-5.1=200k, deepseek-v3.2=128k。只用/api/coding/v3不用/api/v3。识图备用链：Hermes vision_analyze→kimi-k2.6 Coding Plan(compress 800x quality70)→小米mimo-v2-omni直调token-plan API。别在第一层失败就放弃，穷尽所有provider。
§
本机NapCat：林知予${BOT_QQ}，主人${OWNER_QQ}。QQ开放平台机器人"Hermes Agent（爱马仕）"appid=1904088040（管理后台q.qq.com/qqbot），${BOT_QQ}@qq.com登录密码${QQ_PASSWORD}，昵称"配角"超级管理员，开发者ID=${DEV_ID}。
§
小米MiMo Token Plan: provider=custom:xiaomi-token-plan, base=token-plan-cn.xiaomimimo.com/v1, 默认mimo-v2.5-pro 1M, key_env=XIAOMI_TOKEN_PLAN_API_KEY。8模型:mimo-v2.5-pro(1M), mimo-v2.5(1M+全模态), mimo-v2-pro(1M), mimo-v2-omni(256K), 4个TTS(8K)。辅助识图=mimo-v2.5。火山Coding Plan保留用于kimi-k2.6。
§
Cron job `no_agent=True` 时，`script` 参数必须是 `~/.hermes/scripts/` 下的文件名（如 `my-task.sh`），不能传内联代码，也不能传绝对路径。先 write_file 再传文件名。
§
小米 MiMo Token Plan 密钥已于 2026-05-27 更新（新 key 在 .env 的 XIAOMI_TOKEN_PLAN_API_KEY）。
§
用户想对接 Grok/xAI 大模型 API。但 console.x.ai 和 accounts.x.ai 均被 Cloudflare/CAPTCHA 拦截本服务器 IP，CDP 浏览器无法访问。用户需在自己设备上登录获取 API Key 后交给助手配置。
§
技能编辑铁律：删小节内容必须同步删标题（不留空壳）。QQbot截图须写完整bash(mkdir -p+cp)不能只文字描述——Agent不会自动执行文字。优化后模拟Agent跑部署流程验证顺序。tencent-novnc-chromium-cdp v1.0.36 914行。
§
改 SkillHub 技能包追加规则⑥：打完 zip 后必须在同一条消息里用 MEDIA: 标签立刻发送，不能说"包在 /tmp/xxx"让用户自己去找。QQ 通道：发文件用 MEDIA: 路径，发图用 <qqmedia> 标签。
§
QQ机器人管理后台 q.qq.com/qqbot appid=1904088040，指令上限24条。CDP自动化技能: platforms/qq-bot-platform-cdp。
§
用户有第二个QQ开放平台机器人，appid=102898221，同样在 q.qq.com/qqbot 管理。使用同一账号${BOT_QQ}@qq.com登录。
§
QQ开放平台两个bot：
- appid=1904088040 "Hermes Agent（爱马仕）" — /personality /yolo /reasoning /fast /voice
- appid=102898221 "OpenClaw Agent（小龙虾）" — /kill /export /think /debug /usage
两者指令配置独立（需用新tab打开切换，同tab切URL不刷新）。小龙虾bot之前只支持2条指令，但现在可加到24条。