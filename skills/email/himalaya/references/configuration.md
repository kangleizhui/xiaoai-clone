# Himalaya Configuration Reference

Configuration file location: `~/.config/himalaya/config.toml`

## Minimal IMAP + SMTP Setup

```toml
[accounts.default]
email = "user@example.com"
display-name = "Your Name"
default = true

# IMAP backend for reading emails
backend.type = "imap"
backend.host = "imap.example.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "user@example.com"
backend.auth.type = "password"
backend.auth.raw = "your-password"

# SMTP backend for sending emails
message.send.backend.type = "smtp"
message.send.backend.host = "smtp.example.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "user@example.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.raw = "your-password"

# Folder aliases — required whenever server folder names differ
# from himalaya's canonical names. See "Folder Aliases" below.
folder.aliases.inbox = "INBOX"
folder.aliases.sent = "Sent"
folder.aliases.drafts = "Drafts"
folder.aliases.trash = "Trash"
```

## Password Options

### Raw password (testing only, not recommended)

```toml
backend.auth.raw = "your-password"
```

### Password from command (recommended)

```toml
backend.auth.cmd = "pass show email/imap"
# backend.auth.cmd = "security find-generic-password -a user@example.com -s imap -w"
```

### System keyring (requires keyring feature)

```toml
backend.auth.keyring = "imap-example"
```

Then run `himalaya account configure <account>` to store the password.

## Gmail Configuration

```toml
[accounts.gmail]
email = "you@gmail.com"
display-name = "Your Name"
default = true

backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "you@gmail.com"
backend.auth.type = "password"
backend.auth.cmd = "pass show google/app-password"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "you@gmail.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "pass show google/app-password"

# Gmail folder mapping. Without these, save-to-Sent fails after
# SMTP delivery succeeds (Gmail's Sent folder is `[Gmail]/Sent Mail`,
# not `Sent`), and `himalaya message send` exits non-zero. Any
# caller that retries on that error will re-run SMTP — duplicate
# emails to recipients. Always include this block for Gmail.
folder.aliases.inbox = "INBOX"
folder.aliases.sent = "[Gmail]/Sent Mail"
folder.aliases.drafts = "[Gmail]/Drafts"
folder.aliases.trash = "[Gmail]/Trash"
```

**Note:** Gmail requires an App Password if 2FA is enabled.

## iCloud Configuration

```toml
[accounts.icloud]
email = "you@icloud.com"
display-name = "Your Name"

backend.type = "imap"
backend.host = "imap.mail.me.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "you@icloud.com"
backend.auth.type = "password"
backend.auth.cmd = "pass show icloud/app-password"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.mail.me.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "you@icloud.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "pass show icloud/app-password"
```

**Note:** Generate an app-specific password at appleid.apple.com

## QQ Mail / 163 / Chinese providers (must disable save-copy)

```toml
[accounts.qq]
email = "12345678@qq.com"
display-name = "Your Name"
default = true

backend.type = "imap"
backend.host = "imap.qq.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "12345678@qq.com"
backend.auth.type = "password"
backend.auth.cmd = "cat /root/.config/himalaya/.qq_authcode"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.qq.com"
message.send.backend.port = 465
message.send.backend.encryption.type = "tls"
message.send.backend.login = "12345678@qq.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "cat /root/.config/himalaya/.qq_authcode"

folder.aliases.inbox = "INBOX"
folder.aliases.sent = "Sent Messages"
folder.aliases.drafts = "Drafts"
folder.aliases.trash = "Deleted Messages"

# CRITICAL — see "save-copy pitfall" below
message.send.save-copy = false
```

**Auth notes:**
- QQ Mail requires an **authorization code** (授权码), NOT your QQ login
  password. Enable IMAP/SMTP in QQ Mail settings → Account → "POP3/IMAP/SMTP
  service" to generate a 16-char code. Store it in a 600-permission file and
  reference via `backend.auth.cmd = "cat /path/to/authcode"`.
- Port choice: QQ Mail SMTP supports both `465` (TLS, `encryption.type = "tls"`)
  and `587` (STARTTLS, `encryption.type = "start-tls"`). 465 is more reliable
  from mainland-China VPS — some networks block 587.
- 163, Sina, Sohu, NetEase Mail all use the same auth-code model and exhibit
  the same `save-copy` pitfall described below.

### save-copy pitfall (QQ Mail, 163, others)

After SMTP delivery succeeds, himalaya tries to APPEND a copy to the Sent
folder via IMAP and read back the returned UID (`APPENDUID` response).
QQ Mail / 163 successfully save the message but **do not return a UID**.
himalaya treats the missing UID as an error and exits with code 1:

```
Error:
   0: cannot find UID of appended IMAP message
```

**The email IS delivered to the recipient**, and QQ's SMTP server
*automatically* writes a copy to the server-side Sent folder regardless.
The agent's local-save retry is the only thing that fails.

**Fix — disable client-side save-copy:**

```toml
message.send.save-copy = false
```

This makes `himalaya template send` exit 0 on real success. Without it,
any cron / CI / agent caller that retries on non-zero exit will re-send
the email, producing duplicates to recipients.

Symptom signature (use this to recognize the bug in trace logs):

```
INFO email::email::message::send::smtp: sending smtp message       ← OK
INFO email::email::message::add::imap: adding imap message to ...  ← fails here
Error: cannot find UID of appended IMAP message
```

## Folder Aliases

Map himalaya's canonical folder names (`inbox`, `sent`, `drafts`,
`trash`) to whatever the server actually calls them. Use the
v1.2.0 `folder.aliases.X` syntax (plural, dotted keys, directly
under `[accounts.NAME]`):

```toml
[accounts.default]
# ... other account config ...

folder.aliases.inbox = "INBOX"
folder.aliases.sent = "Sent"
folder.aliases.drafts = "Drafts"
folder.aliases.trash = "Trash"
```

The equivalent TOML sub-section form also works in v1.2.0:

```toml
[accounts.default.folder.aliases]
inbox = "INBOX"
sent = "Sent"
drafts = "Drafts"
trash = "Trash"
```

> **Don't use the singular `alias` form.** Pre-v1.2.0 docs showed
> `[accounts.NAME.folder.alias]` (singular). v1.2.0 silently
> ignores that sub-section — TOML parses without error, but the
> alias resolver never reads it. Every lookup then falls through
> to the canonical name. On Gmail (where `sent` is actually
> `[Gmail]/Sent Mail`) this means save-to-Sent fails *after* SMTP
> delivery succeeds, and `himalaya message send` exits non-zero.
> Any caller (agent, script, user) that retries on that error
> code will re-run the send — including SMTP — producing duplicate
> emails to recipients. Always use `folder.aliases.X` (plural).

## Multiple Accounts

```toml
[accounts.personal]
email = "personal@example.com"
default = true
# ... backend config ...

[accounts.work]
email = "work@company.com"
# ... backend config ...
```

Switch accounts with `--account`:

```bash
himalaya --account work envelope list
```

## Notmuch Backend (local mail)

```toml
[accounts.local]
email = "user@example.com"

backend.type = "notmuch"
backend.db-path = "~/.mail/.notmuch"
```

## OAuth2 Authentication (for providers that support it)

```toml
backend.auth.type = "oauth2"
backend.auth.client-id = "your-client-id"
backend.auth.client-secret.cmd = "pass show oauth/client-secret"
backend.auth.access-token.cmd = "pass show oauth/access-token"
backend.auth.refresh-token.cmd = "pass show oauth/refresh-token"
backend.auth.auth-url = "https://provider.com/oauth/authorize"
backend.auth.token-url = "https://provider.com/oauth/token"
```

## Additional Options

### Signature

```toml
[accounts.default]
signature = "Best regards,\nYour Name"
signature-delim = "-- \n"
```

### Downloads directory

```toml
[accounts.default]
downloads-dir = "~/Downloads/himalaya"
```

### Editor for composing

Set via environment variable:

```bash
export EDITOR="vim"
```
