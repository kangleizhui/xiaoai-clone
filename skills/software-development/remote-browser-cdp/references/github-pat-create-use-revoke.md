# GitHub PAT Create → Use → Revoke (via visible CDP browser)

When the user is **already logged into GitHub** in the visible noVNC browser but the agent needs to perform git/gh API operations, the cleanest pattern is:

1. Create a short-lived PAT (via the visible browser → user's existing session)
2. Use it immediately for the operation (gh CLI / git push / API call)
3. Revoke it via the same visible browser

This avoids storing long-lived credentials, never asks the user for their password, and leaves no token in `~/.git-credentials` after the session.

## When to use this pattern

- User has logged into github.com in the visible Chromium (noVNC)
- Agent needs to: create a repo, push commits, change repo settings, manage releases
- Agent does NOT need: long-lived auth (use `gh auth login` interactively for that)

## Full recipe

### Step 1: Navigate to token creation page (pre-fills description + scopes)

```bash
/usr/local/lib/hermes-agent/venv/bin/python3 << 'PYEOF'
import json, asyncio, urllib.request
import websockets

async def main():
    targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
    page = next((t for t in targets if t.get("type") == "page"), None)
    async with websockets.connect(page["webSocketDebuggerUrl"]) as ws:
        # URL params pre-fill the form: description + comma-separated scopes
        await ws.send(json.dumps({
            "id": 1, "method": "Page.navigate",
            "params": {"url": "https://github.com/settings/tokens/new?description=<task-name>&scopes=repo,delete_repo,workflow"}
        }))
        await ws.recv()

asyncio.run(main())
PYEOF
sleep 3
```

Scope cheat sheet:
- `repo` — push, create repos, read/write code
- `delete_repo` — delete repos (only if needed)
- `workflow` — modify .github/workflows files
- `read:org` — list org membership (needed for some `gh` commands)

### Step 2: Click "Generate token" (the form is already filled via URL params)

```bash
/usr/local/lib/hermes-agent/venv/bin/python3 << 'PYEOF'
import json, asyncio, urllib.request
import websockets

async def main():
    targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
    page = next((t for t in targets if t.get("type") == "page"), None)
    async with websockets.connect(page["webSocketDebuggerUrl"]) as ws:
        js = """(() => {
            const btn = Array.from(document.querySelectorAll('button,input[type=submit]'))
                .find(b => (b.textContent||b.value||'').trim().toLowerCase()==='generate token');
            if (!btn) return 'NOT_FOUND';
            btn.scrollIntoView(); btn.click();
            return 'CLICKED';
        })()"""
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        print(json.loads(await ws.recv()).get("result", {}).get("result", {}).get("value"))

asyncio.run(main())
PYEOF
sleep 4
```

### Step 3: Extract token via screenshot + vision_analyze

```bash
DISPLAY=:99 import -window root /tmp/gh_token.png
```

Then `vision_analyze(image_url="/tmp/gh_token.png", question="What is the ghp_ token shown?")`.

The vision model reliably reads `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` from the green confirmation box.

### Step 4: Configure git + gh + do the work

```bash
TOKEN="ghp_xxx..."

# gh CLI (will warn about env-var auth — that's fine for short-lived use)
echo "$TOKEN" | GH_TOKEN="" gh auth login --with-token

# git via stored credentials (works for HTTPS push)
echo "https://<github-username>:${TOKEN}@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

# Username from gh; email use the noreply form (avoids leaking real email)
GH_USER=$(gh api user --jq .login)
GH_ID=$(gh api user --jq .id)
git config --global user.name "$GH_USER"
git config --global user.email "${GH_ID}+${GH_USER}@users.noreply.github.com"
git config --global init.defaultBranch main

# Now do the work: create repo, push, etc.
gh repo create <name> --public --description "..."
cd <project> && git push -u origin main
```

### Step 5: Revoke token immediately (same browser, same session)

```bash
/usr/local/lib/hermes-agent/venv/bin/python3 << 'PYEOF'
import json, asyncio, urllib.request
import websockets

async def main():
    targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
    page = next((t for t in targets if t.get("type") == "page"), None)
    async with websockets.connect(page["webSocketDebuggerUrl"]) as ws:
        # Go to token list
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
            "params": {"url": "https://github.com/settings/tokens"}}))
        await ws.recv()
        await asyncio.sleep(3)

        # Click the Delete button next to the row matching description
        js1 = """(() => {
            for (const row of document.querySelectorAll('.access-token, .Box-row')) {
                if (row.textContent.includes('<task-name>')) {
                    const b = row.querySelector('button.btn-danger, button[type=submit], .btn-danger');
                    if (b) { b.scrollIntoView(); b.click(); return 'DEL'; }
                }
            }
            return 'NO_ROW';
        })()"""
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
            "params": {"expression": js1, "returnByValue": True}}))
        print("Del:", json.loads(await ws.recv()).get("result", {}).get("result", {}).get("value"))
        await asyncio.sleep(2)

        # Confirm in modal
        js2 = """(() => {
            const t = Array.from(document.querySelectorAll('button'))
                .find(b => (b.textContent||'').toLowerCase().includes('i understand'));
            if (!t) return 'NO_MODAL'; t.click(); return 'CONFIRMED';
        })()"""
        await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
            "params": {"expression": js2, "returnByValue": True}}))
        print("Confirm:", json.loads(await ws.recv()).get("result", {}).get("result", {}).get("value"))

asyncio.run(main())
PYEOF

# Clean local credentials
> ~/.git-credentials
unset GH_TOKEN
```

## Pitfalls

1. **Run safety scanner will flag the token in every command.** This is expected — `ghp_*` matches the GitHub PAT regex. User auto-approves after seeing the pattern. Don't try to hide the token (don't use env-var indirection just to fool the scanner); be open about it being intentional.

2. **Each token must have a unique description.** If you re-run the same flow, increment a counter (`hermes-qq-bot-push-2`, `push-3`, ...) so the revoke step's CSS selector matches the right row. Without uniqueness, the JS finds the first row containing the substring and may delete the wrong token.

3. **`gh auth login --with-token` reads from stdin.** Use `echo "$TOKEN" | gh auth login --with-token` — NOT `gh auth login --with-token <<< "$TOKEN"` if `$TOKEN` contains special chars. Also, gh will complain if `GH_TOKEN` env var is set; either unset it first or accept the env-var mode (which works fine).

4. **Email field needs `user:email` scope OR use noreply.** Default `repo` scope doesn't grant access to `/user/emails`. Use `<numeric-id>+<username>@users.noreply.github.com` — GitHub recognizes this format and attributes commits correctly.

5. **The git push uses the credential helper file, not gh.** Even after `gh auth login`, `git push` over HTTPS reads from `~/.git-credentials` (because of `credential.helper store`). Both must be set.

6. **Revoke right after the operation completes, not at session end.** The token text is in tool-call logs and may persist in session storage. Shorter exposure window = better.

7. **Pre-filling scopes via URL params has a quirk.** GitHub auto-collapses redundant scopes (e.g., if you request `repo,delete_repo`, the saved scopes are just `repo` because `repo` includes everything except the explicit `delete_repo`). The blue notice "Only the minimum set of necessary scopes has been saved" appears — this is fine, your token still works.

## Variants

- **Fine-grained tokens** (`/settings/personal-access-tokens/new`) — more granular but the form is more complex; the URL param pre-fill doesn't work the same way. Stick with classic for short-lived agent operations.

- **OAuth device flow** — better for long-lived agent auth, but requires user interaction at github.com/login/device. Use this for `gh auth login` without `--with-token`.

- **SSH key + deploy key** — best for repo-specific automation that runs forever (CI). Overkill for a one-off agent task.
