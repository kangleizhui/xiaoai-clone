# Volcano Ark Coding Plan — Vision (识图) Workaround

## Problem

Hermes' `vision_analyze` tool relies on an auxiliary vision model that may fail
silently for certain image formats or sizes. When it does, the model says
"I don't see any image attached" or "I'm a text-only AI."

## Solution: Multi-Provider Vision Fallback Chain

When Hermes' built-in `vision_analyze` fails (quota, unsupported format, etc.), try providers in order:

### Tier 1: kimi-k2.6 via Coding Plan API

`kimi-k2.6` supports multimodal (image + text) input via the Coding Plan API.
Other Coding Plan models like `doubao-seed-2.0-*` do **NOT** support vision
through the Coding Plan endpoint (they return "UnsupportedModel" error).

### Step 1: Compress large images

Base64 of raw phone photos (often 500KB+) will either:
- Fail with "Argument list too long" in terminal (shell limit)
- Time out over HTTP (payload too large)

Compress first:

```bash
convert input.jpg -resize 800x -quality 70 /tmp/vision-input.jpg
```

Target: under 150KB. Usually 90-100KB is fine and still readable.

### Step 2: Call via Python (NOT terminal curl)

Terminal curl cannot handle base64 images in command line — the shell argument
limit kicks in around 128KB of base64 data. Always use Python:

```python
import base64, json, urllib.request, os

# Read API key from .env
api_key = None
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        if line.startswith("VOLC_ARK_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

# Encode compressed image
with open("/tmp/vision-input.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "model": "kimi-k2.6",
    "stream": False,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "详细描述这张图片中的内容，用中文回答。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
        ]
    }]
}

req = urllib.request.Request(
    "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
)

with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode())
    print(data["choices"][0]["message"]["content"])
```

### Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong model | `"UnsupportedModel"` / 404 | Only `kimi-k2.6` supports vision in Coding Plan |
| Image too large in terminal | "Argument list too long" | Use Python, not terminal curl |
| Image too large in Python | Timeout (>60s) | Compress with `convert -resize 800x -quality 70` |
| Wrong base URL | Billed to regular Ark instead of Coding Plan | Must end with `/api/coding/v3` |

### Verified Working

- Image: 1272×2800 JPEG, compressed to 800px width, ~94KB
- Model: kimi-k2.6
- Latency: ~50 seconds for a detailed description
- Result: Full, accurate Chinese description of the image

## Tier 2: MiMo Omni via Token Plan API

When Coding Plan API is also rate-limited (HTTP 429), fall back to Xiaomi MiMo's
vision-capable model. This is a tertiary provider that is rarely rate-limited.

### Python Call

```python
import base64, json, urllib.request, os

api_key = None
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        if line.startswith("XIAOMI_TOKEN_PLAN_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

with open("/tmp/vision-input.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "model": "mimo-v2-omni",
    "stream": False,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "详细描述这张图片中的内容，用中文回答。"},
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

### Verified Working

- Image: 36900 bytes JPEG (already compressed from Tier 1)
- Model: mimo-v2-omni
- Latency: ~23 seconds
- Result: Full, accurate Chinese description of the image

### Full Fallback Chain

```
Hermes vision_analyze
  └─ 429/error → kimi-k2.6 Coding Plan (compress image first)
                    └─ 429/error → mio-v2-omni Token Plan
                                      └─ still failed → admit and ask user
```

> **Principle**: Don't give up after the first provider fails. Exhaust all available
> vision-capable providers before telling the user you can't see the image.