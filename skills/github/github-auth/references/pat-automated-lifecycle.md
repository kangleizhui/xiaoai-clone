# Automated PAT Lifecycle via Remote Browser CDP

When you need a one-shot Personal Access Token (e.g., to create a repo and push from a headless server) and the user has a noVNC + CDP browser stack available (see `remote-browser-cdp` skill), you can fully automate creation **and** revocation. This avoids leaving long-lived tokens on the server.

## When to use this

- Headless server, user is logged into GitHub.com in the visible browser
- One-shot push: create repo → push code → done; no need to keep the PAT
- User wants the agent to "just do it" rather than walk them through manual UI steps

## Step 1: Pre-fill the New Token form via URL params

GitHub's classic token form accepts `description` and `scopes` query params, so the user never has to click checkboxes:

```
https://github.com/settings/tokens/new?description=<name>&scopes=repo,delete_repo,workflow
```

Common scope combos:

| Goal                                       | Scopes                              |
| ------------------------------------------ | ----------------------------------- |
| Push to a private repo                     | `repo`                              |
| Create + push + later auto-cleanup the repo| `repo,delete_repo`                  |
| Same plus trigger GitHub Actions           | `repo,delete_repo,workflow`         |

## Step 2: Drive the form via CDP

### Sudo mode (2FA) gate — MUST clear before token form renders

GitHub requires **sudo mode** (re-authentication) before creating tokens, even if the user is already logged in. The sudo page shows a "Confirm access" dialog with two options:

1. **"Use GitHub Mobile"** — triggers a push notification. The page displays a 2-digit code (e.g. `37`); the user must select the matching number on their phone. Click the green button via CDP, then **pause and ask the user to confirm** (via `clarify` tool). After confirmation, the browser auto-advances.

2. **"Use your password"** — **MISLEADING**: this goes to the password RESET flow, not a sudo password entry. Do NOT click it.

**URL-prefill does NOT bypass sudo**. `/settings/tokens/new?description=X&scopes=repo` still hits the "Confirm access" page.

**Pattern**:
1. Navigate to `/settings/tokens/new`
2. Screenshot — if "Confirm access" appears, click "Use GitHub Mobile", then ask user to approve
3. After sudo clears, the token form renders

### Filling the Note field

GitHub requires non-empty Note. Direct `.value =` may not trigger validation. Use CDP `Input.insertText` after focusing:

```python
# Focus then insert
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
    "params": {"expression": "document.querySelector('input#token_description').focus()"}}))
await ws.recv()
await ws.send(json.dumps({"id": 2, "method": "Input.insertText",
    "params": {"text": "my-temp-token"}}))
```

### Clicking "Generate token"

```python
js = """
(() => {
    const btns = Array.from(document.querySelectorAll('button, input[type=submit]'));
    const target = btns.find(b => {
        const txt = (b.textContent || b.value || '').trim().toLowerCase();
        return txt === 'generate token' || txt.includes('generate token');
    });
    if (!target) return 'NOT_FOUND';
    target.scrollIntoView();
    target.click();
    return 'CLICKED';
})()
"""
```

### Extracting the generated token — CRITICAL PITFALL

After generation, element `#new-oauth-token` shows the token, but **textContent is truncated** — e.g. `ghp_wx...HtrA` where `...` is literal (GitHub masks the middle in the DOM). The full token is rendered visually but NOT accessible via `textContent`, `innerText`, `innerHTML`, `value`, or `data-*` attributes.

**Extraction strategies (ordered by reliability)**:

1. **Vision AI (recommended)**: Screenshot + vision analysis to OCR the full `ghp_` string. GitHub renders the full token visually even though DOM text is masked.

2. **Clipboard (often fails)**: Click copy button, then `navigator.clipboard.readText()`. Fails if document is not focused (common in CDP). `Browser.grantPermissions` for `clipboardReadWrite` doesn't fix the focus requirement.

3. **Ask the user**: Fallback — have user copy the token from their browser and paste in chat.

After click, screenshot the page and use a vision tool to extract the `ghp_…` string (it's only shown once).

## Step 3: Hand off to gh + git immediately

```bash
export GH_TOKEN="ghp_..."
echo "$GH_TOKEN" | gh auth login --with-token
gh auth status  # confirm

# Configure git
GH_USER=$(gh api user --jq .login)
GH_ID=$(gh api user --jq .id)
# user/emails requires user:email scope. If your PAT doesn't have it, use noreply:
NOREPLY="${GH_ID}+${GH_USER}@users.noreply.github.com"
git config --global user.name "$GH_USER"
git config --global user.email "$NOREPLY"
git config --global credential.helper store
echo "https://${GH_USER}:${GH_TOKEN}@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
```

**Pitfall:** when `GH_TOKEN` is in env, gh keeps using it instead of stored creds. That's fine for the immediate operations, but `unset GH_TOKEN` before testing "would this still work without env?" cases.

## Step 4: Revoke the PAT after use

Two-step CDP automation: click "Delete" on the token row, then click "I understand, delete this token" in the modal.

```python
# Step 4a: click the Delete button on the row matching the token description
js_delete = """
(() => {
    const rows = Array.from(document.querySelectorAll('.access-token, [class*="listgroup"], .Box-row'));
    for (const row of rows) {
        if (row.textContent.includes('YOUR_TOKEN_DESCRIPTION')) {
            const delBtn = row.querySelector('button[type=submit], summary, button.btn-danger, .btn-danger');
            if (delBtn) { delBtn.scrollIntoView(); delBtn.click(); return 'CLICKED'; }
        }
    }
    return 'NO_ROW';
})()
"""

# Step 4b: confirm in the modal
js_confirm = """
(() => {
    const btns = Array.from(document.querySelectorAll('button, input[type=submit]'));
    const target = btns.find(b => (b.textContent || b.value || '').toLowerCase().includes('i understand'));
    if (!target) return 'NOT_FOUND';
    target.click();
    return 'CONFIRMED';
})()
"""
```

Verify deletion with a screenshot + vision check that the token row is gone.

## Why bother revoking?

- The PAT string ends up in terminal logs, gh keyring, `~/.git-credentials`, and possibly chat history. Even if those are "private", the principle of least lifetime applies.
- `repo` scope on a leaked PAT = full account compromise for repos. Cheap to revoke, expensive to clean up after a leak.

## After revoke: scrub local copies

The revoke action only invalidates the token server-side. The string is still sitting in `~/.git-credentials` on disk. Truncate it as the last step:

```bash
> ~/.git-credentials   # truncate in place; preserves perms
```

This way a later `grep ghp_ ~/.git-credentials` doesn't resurface a dead-but-real-looking token and confuse a future session into trying to reuse it.

## Multi-cycle PAT pattern (more than one push per session)

If you have to push several times across a session (e.g. iterative README edits), don't try to keep one PAT alive: just mint → push → revoke → mint again for each cycle. Cost is ~15s of CDP automation per cycle plus one security-scan approval. The session that authored this skill did this 4 times in a row with no friction. Trying to reuse a PAT across iterations means leaving it on disk longer than necessary and re-explaining its existence to the user mid-session.

## Security scan warning

Hermes' security scanner flags PAT strings appearing in terminal commands as `[HIGH] GitHub PAT detected`. Expect approval prompts when you paste the token into commands. This is correct behavior — review and approve once per token.

## Alternative: use existing `~/.git-credentials` instead

If the user already has stored credentials from a prior session, extract the token rather than minting a new one — see the main SKILL.md "Extracting the Token from Git Credentials" section.
