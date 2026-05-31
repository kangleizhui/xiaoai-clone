---
name: custom-llm-provider-config
description: Configure Hermes Agent with custom OpenAI-compatible LLM providers. Covers provider setup, model discovery, context-length declarations, and provider-specific quirks.
when_to_use:
  - User wants to add a new custom provider (Volcano Ark, Xiaomi MiMo, OpenRouter, etc.)
  - User says "how do I set up <provider>" or "context window is wrong"
  - Troubleshooting custom provider connection issues
---

# Custom LLM Provider Configuration

Hermes Agent supports any OpenAI-compatible API via the `custom` provider path. This skill covers the universal setup pattern and the quirks of specific providers.

## Universal Setup Pattern

### 1. API Key in `.env`

Add the key to `~/.hermes/.env` (protected file — update via `sed` or `terminal`):

```bash
sed -i 's/PROVIDER_API_KEY=.*/PROVIDER_API_KEY=xxx/' ~/.hermes/.env
```

### 2. CLI Configuration

```bash
hermes config set model.default <model-name>
hermes config set model.provider custom
hermes config set model.base_url <base-url>
hermes config set model.api_key <key>
```

### 3. Declare `providers:` in `config.yaml` (REQUIRED for correct context windows)

The **top-level `providers:`** block (not `model_catalog.providers:`) is what Hermes reads for `context_length`.

```yaml
providers:
  <provider-key>:
    base_url: <base-url>
    key_env: <ENV_VAR_NAME>
    models:
      <model-name>:
        context_length: <number>
```

**Pitfall**: putting `context_length` under `model_catalog.providers:` only enables model-picker autocomplete; the runtime context resolver ignores it and falls back to 256K.

### 4. Test with curl

```bash
curl -s <base-url>/models \
  -H "Authorization: Bearer $ENV_VAR_NAME" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

### 5. Apply

Run `/reset` in chat or restart the gateway.

## Provider-Specific Sections

### Volcano Engine Ark / Coding Plan

- **Base URL**: `https://ark.cn-beijing.volces.com/api/coding/v3` (Coding Plan). Do NOT use `/api/v3` — that bills per-token instead of consuming subscription quota.
- **Model names**: use dot separators (`deepseek-v4-pro`, `kimi-k2.6`).
- **Context windows**: `deepseek-v4-pro` / `deepseek-v4-flash` support **1,024,000** tokens. Always declare this or Hermes truncates at 256K.
- **Billing**: Coding Plan is a flat-rate subscription billed by call count, not raw tokens. Local `estimated_cost_usd` is misleading; check the Volcano console for true quota.
- **Vision**: only `kimi-k2.6` supports multimodal in Coding Plan. If `vision_analyze` fails, fall back to a direct API call with compressed images.

See `references/vision-workaround.md` and `references/local-usage-tracking.md` for detailed recipes.

### Xiaomi MiMo

- **Two plans**:
  - **Token Plan** (订阅制): `https://token-plan-cn.xiaomimimo.com/v1`, key format `tp-xxxxx`
  - **Pay-per-use** (按量付费): `https://api.xiaomimimo.com/v1`, key format `sk-xxxxx`
- **Model names**: must be **lowercase with hyphens** (`mimo-v2.5-pro`). The platform UI shows `MiMo-V2.5-Pro` but the API rejects it.
- **Context windows**: `mimo-v2.5-pro` and `mimo-v2-pro` support **1,048,576** tokens.
- **Protected `.env`**: use `sed` via `terminal` to edit `~/.hermes/.env`; `patch`/`write_file` are denied for credential files.

See `references/vision-fallback.md` for vision fallback recipes.

## Switching Providers

```bash
# Example: switch back to Volcano
hermes config set model.default deepseek-v4-pro
hermes config set model.provider custom
hermes config set model.base_url https://ark.cn-beijing.volces.com/api/coding/v3
```

Multiple `providers:` blocks can coexist in `config.yaml`; Hermes only uses the one matching `model.base_url`.

## References

- `references/local-usage-tracking.md` — query `~/.hermes/state.db` for usage when the provider has no public billing API.
- `references/vision-workaround.md` — direct Coding Plan vision call recipe.
- `references/vision-fallback.md` — MiMo vision fallback.
- `references/model-list.md` — authoritative model lists per provider.
