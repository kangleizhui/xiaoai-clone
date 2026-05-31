# Volcano Engine Coding Plan — Model List & API Notes

## About This File

This covers the **Coding Plan** API (`/api/coding/v3`), NOT the regular Ark API (`/api/v3`). The two use **different** model names and endpoints.

## Model Names — Coding Plan

These are the Model Names you pass directly to the `model` field in Chat Completions. They use **dot** separators.

### Confirmed Working

| Model Name | Type | Notes |
|:-----------|:-----|:------|
| `deepseek-v4-pro` | Chat | Default, best quality |
| `deepseek-v4-flash` | Chat | Faster/cheaper |
| `deepseek-v3.2` | Chat | DeepSeek V3.2 |
| `doubao-seed-2.0-pro` | Chat | ByteDance flagship |
| `doubao-seed-2.0-lite` | Chat | Faster seed |
| `doubao-seed-2.0-code` | Code | Coding specialized |
| `doubao-seed-code` | Code | Earlier code model |
| `minimax-latest` | Chat | MiniMax M2.7 alias |
| `glm-5.1` | Chat | Zhipu AI |
| `kimi-k2.6` | Chat | Moonshot AI |

## Naming Differences

| Context | Format | Example |
|:--------|:-------|:--------|
| Coding Plan API | Dot-separated Model Name | `deepseek-v4-pro` |
| Regular Ark API | Hyphen-separated endpoint ID | `deepseek-v4-pro-260512` |
| Model catalog list | Raw endpoint IDs | `deepseek-v3-2-251201` |

**For Coding Plan, always use the Model Name format.**

## Config Patterns

### ~/.hermes/config.yaml — model section (top level)

```yaml
model:
  default: deepseek-v4-pro
  provider: custom    # NOT custom:volc
  base_url: https://ark.cn-beijing.volces.com/api/coding/v3
  api_key: ark-XXXXXXXXXX...
```

### ~/.hermes/config.yaml — model_catalog section

```yaml
model_catalog:
  providers:
    volc:
      base_url: https://ark.cn-beijing.volces.com/api/coding/v3
      api_key_env: VOLC_ARK_API_KEY
      models:
        - doubao-seed-2.0-code
        - doubao-seed-2.0-pro
        - doubao-seed-2.0-lite
        # ... etc (Model Names, not endpoint IDs)
```

## Docs References

- Coding Plan overview: https://www.volcengine.com/docs/82379/1925114?lang=zh
- Hermes Agent setup (Coding Plan): https://www.volcengine.com/docs/82379/2318283?lang=zh
- Coding Plan console: https://console.volcengine.com/ark

## API Key

Coding Plan API keys start with `ark-`. Set as env var `VOLC_ARK_API_KEY` in `.env`.
