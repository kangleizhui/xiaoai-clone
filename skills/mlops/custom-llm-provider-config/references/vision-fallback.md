# MiMo Omni — Vision Fallback 识图兜底方案

## 场景

Hermes 内置的 `vision_analyze` 工具可能因配额耗尽（`AccountQuotaExceeded` 429）或其他原因失败。此时可以用 `mimo-v2-omni` 或 `mimo-v2.5`（两者均支持多模态 vision）通过 Xiaomi Token Plan API 直接识图。

## 调用方式

### Step 1: 压缩图片（重要）

原始手机截图动辄 500KB+，base64 后更大，易超时。先压缩：

```bash
convert input.jpg -resize 800x -quality 70 /tmp/vision-input.jpg
```

目标 < 150KB，通常 36-100KB 足够识别。

### Step 2: Python 调用 MiMo API

```python
import base64, json, urllib.request, os

# 从 .env 读取 Token Plan API key
api_key = None
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        if line.startswith("XIAOMI_TOKEN_PLAN_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

# 编码图片
with open("/tmp/vision-input.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "model": "mimo-v2-omni",  # 或 mimo-v2.5
    "stream": False,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "详细描述这张图片中的内容。用中文回答。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
        ]
    }]
}

req = urllib.request.Request(
    "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
)

with urllib.request.urlopen(req, timeout=90) as resp:
    data = json.loads(resp.read().decode())
    print(data["choices"][0]["message"]["content"])
```

### Model 选择

| Model | Vision | 延迟 | 适用 |
|-------|--------|------|------|
| `mimo-v2-omni` | ✅ Omni-modal | ~20-30s | 首选 |
| `mimo-v2.5` | ✅ text+image | ~15-25s | 备选 |

## 注意事项

- **不要用 execute_code 调用**（sandbox 没有 `websocket` 模块限制，但此处用 urllib 不依赖 websocket，可以）
- **图片必须先压缩**，否则 API 可能超时
- **Base URL 是 `token-plan-cn.xiaomimimo.com/v1`**，不是 `api.xiaomimimo.com/v1`
- **模型名小写**：`mimo-v2-omni` 正确，`MiMo-V2-Omni` 错误
- 与火山 Coding Plan kimi-k2.6 不同，MiMo 不需要 `/api/coding/v3` 路径
