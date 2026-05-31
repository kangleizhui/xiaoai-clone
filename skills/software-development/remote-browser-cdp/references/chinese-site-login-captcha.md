# Chinese Website Login with Captcha

## Overview

Chinese websites commonly use **slider captchas** from ByteDance's VerifyCenter (`verify.zijieapi.com` / `rmc.bytedance.com/verifycenter/`) or Alibaba's risk control services before allowing automated actions like SMS code sending. This is particularly common on:

- **番茄小说** (fanqienovel.com) — ByteDance ecosystem
- **抖音** (douyin.com) — ByteDance ecosystem  
- **头条** (toutiao.com) — ByteDance ecosystem
- Various Chinese e-commerce and content platforms

The captcha **cannot be bypassed programmatically** — it requires human visual interaction (drag slider). The strategy is to use the remote browser (noVNC) and let the user solve the captcha manually.

## Typical Login Flow (SMS Code)

### Step-by-step

```
1. Navigate to site homepage
2. Click "登录" (login) button
   → May navigate to a separate login page URL (e.g., writer zone)
3. Switch to "验证码登录" (SMS code login) tab
4. Enter phone number
5. Check "我已阅读并同意用户协议" (I agree to terms) checkbox
6. Click "获取验证码" (get verification code)
   → CAPTCHA iframe appears (from verify.zijieapi.com)
7. User solves captcha via noVNC (drag slider)
8. SMS code is sent to phone
9. User provides code → enter it → click "登录/注册"
```

### Captcha Architecture

When "获取验证码" is clicked:
1. The page calls an API endpoint like `/passport/web/send_code/`
2. Before sending, it triggers a captcha request to `verify.zijieapi.com`
3. A cross-origin iframe loads the captcha UI (slider challenge)
4. The captcha sends back a verification ticket on successful solve
5. Only then does the SMS actually get sent

**HTTP traces to look for:**
- `rmc.bytedance.com/verifycenter/captcha/v2` — captcha iframe load
- `fanqienovel.com/passport/web/send_code/` — SMS send API
- `verify.zijieapi.com` — verification endpoint

### Using noVNC for Captcha Solving

1. Set up the remote browser stack (see main `remote-browser-cdp` skill)
2. **Open UFW/iptables for port 6080** — cloud security group alone is NOT enough if the server has its own firewall
3. Navigate to the login page (use **CDP directly** via WebSocket to `:9222`, NOT Hermes' `browser_navigate` — see pitfall below)
4. Fill in the form (phone, checkbox)
5. Click "获取验证码" — captcha iframe appears
6. Tell the user to open `http://<IP>:6080/vnc.html` in their browser
7. Ask the user to manually drag the slider to solve the captcha
8. Once solved, the SMS is sent — user shares the code
9. Enter code and submit

## QQ Open Platform Login (Tencent TCaptcha)

QQ Open Platform (`q.qq.com`) uses **Tencent TCaptcha** — identifiable by the iframe `tcaptcha_iframe_dy`. Unlike ByteDance's slider captcha that appears on SMS send, TCaptcha appears on **form submission** (after clicking "登录").

### Login Flow

```
1. Navigate to https://q.qq.com
2. Click "邮箱登录" tab (switches form to email mode; QQ 扫码 uses a different iframe)
3. Fill email + password (use native value setter for React-controlled inputs):
   Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'value');
   input.dispatchEvent(new Event('input', {bubbles: true}));
4. Click "登录" button — TCaptcha iframe appears (tcaptcha_iframe_dy)
5. User solves captcha via noVNC → page redirects to dashboard (#/apps)
```

### Key Observations

- **No captcha before submit**: The login form has no visible captcha until you click the button. After JS click/mouse click, a TCaptcha iframe (`id="tcaptcha_iframe_dy"`) appears.
- **Form fields disappear when captcha is active**: `document.querySelectorAll('input')` returns 0 visible inputs while TCaptcha is shown — the form is replaced/overlaid.
- **After captcha solve**: Page auto-redirects to `https://q.qq.com/#/apps` (dashboard). Check `document.title` — "QQ开放平台" confirms login; presence of "你好，<nickname>" in body text confirms authenticated state.
- **TCaptcha cannot be bypassed programmatically** — same constraint as ByteDance captchas.

## Hermes Browser Tool Notes

When using Hermes' built-in browser tools (`browser_navigate`, `browser_click`, `browser_snapshot`) instead of raw CDP:

### Snapshot returns "(empty page)" 

This commonly happens in two scenarios:

1. **Page navigation after click** — Clicking "登录" may navigate to a new page (e.g., from `fanqienovel.com` to `fanqienovel.com/author/...`). The snapshot tool may not immediately pick up the new page state.
   
   **Fix:** Call `browser_navigate` again to refresh the page handle, then take a new snapshot.

2. **Iframe/overlay appears** — A captcha iframe loads inside an overlay. The snapshot may report "(empty page)" because it can't serialize the cross-origin iframe content.
   
   **Fix:** Use `browser_console` with JS expressions to inspect the DOM:
   ```javascript
   // Check if iframe exists
   document.querySelectorAll('iframe').length
   
   // Check actual page structure
   document.body.innerHTML.substring(0, 2000)
   
   // Get page title (reflects actual navigation)
   document.title
   ```

### Element not responding to click

If a click on a `ref` from the snapshot doesn't trigger the expected behavior:

1. **Try `browser_console` with JS click:**
   ```javascript
   document.querySelector('.specific-class-name').click()
   ```

2. **Check for disabled state:**
   ```javascript
   document.querySelector('button').disabled
   ```

3. **For React SPAs, dispatch native events:**
   ```javascript
   var el = document.querySelector('div.slogin-form-input__button-text');
   var evt = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
   el.dispatchEvent(evt);
   ```

### Checking captcha presence

```javascript
// Check if a captcha iframe appeared
document.querySelectorAll('iframe[src*="verify"]').length > 0
// → true means captcha is showing

// Check all iframes
Array.from(document.querySelectorAll('iframe')).map(f => f.src)
```

## Common Pitfalls

1. **Button text doesn't change to countdown.** If "获取验证码" text stays the same after clicking, the captcha hasn't been solved yet — the SMS wasn't sent.

2. **Login button stays disabled.** The "登录/注册" button may remain disabled until the SMS code input has content AND the agreement checkbox is checked.

3. **Phone number lost after page navigation.** Some login flows redirect to a different URL. The input state from the previous page is lost. Always verify the page URL (via `browser_console` → `document.title` or `window.location.href`) before typing.

4. **Cross-origin iframe limits.** The captcha iframe is cross-origin, so you cannot inject JS into it or read its content programmatically. The captcha MUST be solved by a human via noVNC.

5. **Stealth/detection.** Running from a cloud VM's IP (especially outside China) may trigger additional bot detection. The `browser_snapshot` output may show `stealth_warning` messages. Residential proxies help but not available in all setups.

6. **CDP WebSocket 403 Forbidden.** When connecting to the CDP WebSocket from a Python script, Chrome may reject the connection if `--remote-allow-origins=*` was not set when starting Chromium. Error message: `Handshake status 403 Forbidden - ... Rejected an incoming WebSocket connection from the http://127.0.0.1:9222 origin.`

   **Fix:** Restart Chromium with `--remote-allow-origins=*`:
   ```bash
   pkill -9 -f chromium
   # restart with the flag — see startup script in main skill
   ```

7. **Hermes browser tools control a DIFFERENT browser.** When using both Hermes' built-in browser tools (`browser_navigate`, `browser_click`, `browser_snapshot`) AND a noVNC visible browser, be aware they are **separate Chromium instances**. The Hermes tools control a headless instance (`--headless=new`); the noVNC browser is a different instance on the X11 display. Always check both when the user reports seeing different content.

8. **CPU spike from unsolved captcha.** If the captcha iframe keeps rendering (user hasn't solved the slider yet), the Chromium renderer process can consume 35-40% CPU. Kill just the renderer process (not the whole browser) to free CPU.

## Verification Checklist

- [ ] noVNC accessible at `http://<IP>:6080/vnc.html`
- [ ] Phone number visible in input field after typing
- [ ] Agreement checkbox shows `checked=true` in snapshot
- [ ] After clicking "获取验证码", user sees captcha slider in noVNC
- [ ] User reports SMS received after solving captcha
- [ ] Code entered; "登录/注册" button becomes clickable
