# 从 SkillHub 线上拉取原版 SKILL.md 作为修改基线

## 使用场景

用户对本地副本的"基线纯净性"有疑虑（"你修改的版本可能不对，重新下载我发的这个版本"），或本地仓库与线上发布版本已分叉若干个版本，必须以线上发布版为唯一可信基线时使用。

绝大多数情况下本地副本就是基线，**不要默认每次都拉网**。仅在以下情况触发本流程：

- 用户明确给了 SkillHub 详情页 URL 并要求"用这个版本"。
- 本地副本 `version:` 字段与线上展示版本不一致。
- 多个本地路径（如 `~/projects/<slug>/`、`~/.openclaw/workspace/skills/<slug>/`、备份目录）SKILL.md 之间已发生分叉，不知哪个是真。

## 关键 API 端点（api.skillhub.cn）

SkillHub 详情页本身是 SPA，HTML 里不包含 SKILL.md 全文；真实数据走 `api.skillhub.cn`：

```text
GET https://api.skillhub.cn/api/v1/skills/<slug>
GET https://api.skillhub.cn/api/v1/skills/<slug>/files?version=<ver>
GET https://api.skillhub.cn/api/v1/skills/<slug>/file?path=SKILL.md&version=<ver>
```

`/file?...` 接口返回 **302 重定向** 到腾讯云 COS 直链：

```text
https://skillhub-1388575217.cos.accelerate.myqcloud.com/skills/<slug>/<ver>/files/SKILL.md
```

`/files?version=<ver>` 返回文件清单，含 **官方 sha256**，校验下载完整性必须用它：

```json
{"count":1,"files":[{"path":"SKILL.md","sha256":"64ed1d4e...","size":26143}],"version":"1.0.18"}
```

## 标准下载 + 校验流程

```bash
SLUG="tencent-novnc-chromium-cdp"
VER="1.0.18"
mkdir -p /tmp/skillhub-original && cd /tmp/skillhub-original

# 1) 拿官方清单与 sha256
EXPECTED_SHA=$(curl -s "https://api.skillhub.cn/api/v1/skills/${SLUG}/files?version=${VER}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["files"][0]["sha256"])')
echo "expected sha256: $EXPECTED_SHA"

# 2) 直接命中 COS（避开 -L 在某些 shell 下被 & 触发 background 误判）
curl -s "https://skillhub-1388575217.cos.accelerate.myqcloud.com/skills/${SLUG}/${VER}/files/SKILL.md" \
  -o SKILL.md

# 3) 校验
ACTUAL_SHA=$(sha256sum SKILL.md | awk '{print $1}')
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] && echo "✅ 基线校验通过" || echo "❌ sha256 不匹配，停手"
```

## 坑 1：curl -L 与 shell 转义

直接 `curl -sL 'https://api.skillhub.cn/.../file?path=SKILL.md&version=1.0.18'` 在 hermes terminal 里可能被识别为含 `&` 后台命令、被工具层拦截。两种解决方法：

- **绕过重定向**：先用 `curl -s -o /dev/null -w '%{redirect_url}'` 拿到 302 的 Location（即 COS 直链），再直接 GET COS。
- **转义 &**：URL 写成 `'...path=SKILL.md\&version=1.0.18'`，注意外层是单引号时反斜杠也保留。

## 坑 2：HEAD 请求 405

`curl -sI` 对 `api.skillhub.cn/api/v1/skills/.../file` 返回 `405 Method Not Allowed`，**不是 API 挂了**——它只支持 GET。要看响应头用 `curl -sv -o /dev/null 2>&1 | grep -i '^<'`，或者直接 GET 一次。

## 坑 3：HTML 兜底页 ≠ 真数据

请求 `https://skillhub.cloud.tencent.com/api/skills/<slug>`（注意是前端域名 + `/api/skills/...`，缺 `/v1/`）会返回 SPA 的 HTML 首页（200 OK），看起来"成功"但内容是 `<!DOCTYPE html>...`。**判定法**：返回体前 20 字节包含 `<!DOCTYPE` 就是兜底页，必须改用 `api.skillhub.cn/api/v1/...`。

## 拿到基线后

1. **覆盖本地 projects/ 目录的 SKILL.md**，把它当唯一基线再开始 patch（不要在已被改过的本地副本上叠加）。
2. 校验后立刻 `cp` 到 `~/.openclaw/workspace/skills/<slug>/SKILL.md`（如果存在该镜像）保持两地一致。
3. 修改完成、版号 +1 后，重新打**纯净 zip**（根目录只含 SKILL.md，文件名带新版号），按 skill 主文档「Pure Zip Rule」。

## 反模式

- ❌ "我感觉本地版本就是线上版本"——感觉不算证据，sha256 才算。
- ❌ 拉了线上但不校验 sha256 就直接覆盖（COS 下载偶发截断）。
- ❌ 用浏览器渲染后的 DOM 文本反推 SKILL.md 内容（Markdown 渲染会丢空格/反引号）。
- ❌ 把"重新下载基线"做成默认动作。每次都拉网会拖慢节奏，用户没要求别拉。
