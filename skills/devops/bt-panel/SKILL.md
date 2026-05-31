---
name: bt-panel
description: "Install and manage 宝塔面板 (BT Panel) on Debian/Ubuntu — web-based Linux server management panel with app store, file manager, database manager, and monitoring."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [bt-panel, baota, server-management, panel, devops]
    related_skills: []
---

# 宝塔面板 (BT Panel) Installation & Management

## Overview

宝塔面板 (BT Panel) is a popular web-based Linux server management panel. It provides a GUI for managing websites, databases, FTP, cron jobs, firewalls, and monitoring.

- **Official site**: https://www.bt.cn
- **Default port**: Randomized per install (commonly 33890, 25260, 13007, etc.)
- **Language**: Chinese UI (primary), English available

## When to Use

- User asks to "install 宝塔" or "install BT Panel"
- User provides the one-line install command
- You need to manage a Linux server via web UI for less technical users

## Prerequisites

- **Clean/fresh system** — BT Panel warns against installing on systems with existing services
- **Debian 10+ / Ubuntu 20.04+ / CentOS 7+** (tested on Debian 13)
- **Root access** — the installer requires root
- **curl or wget** — for downloading the install script

## Installation

### Standard Install (with confirmation code)

```bash
curl -sSO https://download.bt.cn/install/install_panel.sh
bash install_panel.sh <confirmation_code>
```

### Auto-confirm Install (for non-interactive environments)

On Debian systems, the installer may show prompts. Pipe `echo "y"` to handle confirmation:

```bash
echo "y" | bash -c "$(curl -fsSL https://download.bt.cn/install/install_panel.sh)" <confirmation_code>
```

### Installation Process

The installer:
1. Updates apt and upgrades bash
2. Installs Ruby (required for the panel's internal tooling)
3. Installs curl-dev and build dependencies
4. Downloads and compiles Python 3.7 (internal venv at `/www/server/panel/pyenv/`)
5. Installs Python dependencies (flask, gevent, pymongo, cryptography, etc.)
6. Downloads the panel.zip (~43MB) to `/www/server/panel/`
7. Sets up init scripts at `/etc/init.d/bt`
8. Starts Bt-Panel and Bt-Tasks services

**Typical duration:** 3-8 minutes depending on network speed.

## Post-Installation

### Login Information

The installer outputs access URLs and credentials at the end:

```
外网面板地址: http://<public-IP>:<random-port>/<path>
内网面板地址: http://<private-IP>:<random-port>/<path>
username: <random-username>
password: <random-password>
```

Save these immediately — the password is auto-generated.

### Security Group Configuration

If the panel is behind a cloud firewall (Tencent Cloud, Alibaba Cloud, AWS):

```
需要放行 <port> 端口
```

Add an inbound TCP rule for the randomized panel port.

## BT CLI Commands

```bash
bt              # Show interactive menu
bt 1            # Restart panel
bt 6            # Stop panel
bt 9            # Enable/disable SSL
bt 14           # View current panel info (URL, username, password)
bt 5            # Modify username
/etc/init.d/bt start|stop|restart
```

## Key Paths

| Path | Purpose |
|------|---------|
| `/www/server/panel/` | Panel installation directory |
| `/www/server/panel/pyenv/` | Python 3.7 virtual environment |
| `/www/server/panel/data/` | Configuration and databases |
| `/etc/init.d/bt` | Init script |
| `/www/server/` | Websites, databases, other server software |

## Common Pitfalls

1. **Installer hangs or runs forever.** On Debian 13, the `apt-get install` step may prompt for confirmation. Use the `echo "y"` pipe trick above.

2. **`--force-yes` deprecation warning.** The installer script uses `--force-yes` which is deprecated in newer Debian versions. This is harmless — the install completes successfully despite the warning `W: --force-yes is deprecated`.

3. **libpcre3-dev not found on Debian 13.** The package `libpcre3-dev` was replaced by `libpcre2-dev` in newer Debian. The installer logs `Unable to locate package libpcre3-dev` but proceeds without it. This is safe — the missing package only affects specific PHP compilation scenarios.

4. **Port randomized each install.** Unlike the old BT Panel (fixed port 8888), the current installer randomizes the web port. The port is shown in the final output banner.

5. **Envoy proxy (sidecar) conflict.** On some cloud VMs (e.g. Tencent Cloud with YunJing agent), port 8888 may be reserved. The randomized port avoids this naturally.

6. **Cannot access from public IP.** The most common issue. Fix: cloud console → security group → inbound rule → allow TCP on the panel port.

7. **The install script exits without installing.** This usually means the confirmation code is missing or expired. Re-run with `bash install_panel.sh <correct_code>`.

## Verification Checklist

- [ ] `bt 14` returns panel address, username, and password
- [ ] Panel web UI loads at `http://<IP>:<port>/<path>`
- [ ] Login with the random username/password succeeds
- [ ] Software store loads and shows available apps

## Manual Nginx Reverse Proxy on BT Panel

BT Panel ships its own nginx (at `/www/server/nginx/`) — **do not assume standard `/etc/nginx` paths**. When the user wants to expose a localhost-only service (Hermes Dashboard, Jupyter, Grafana, any backend UI) safely to the internet with auth, drop a vhost file into the panel's include dir and reload.

### Key paths

| What | Where |
|------|-------|
| nginx binary | `/usr/bin/nginx` (symlink) or `/www/server/nginx/sbin/nginx` |
| Main config | `/www/server/nginx/conf/nginx.conf` |
| **Auto-included vhost dir** | `/www/server/panel/vhost/nginx/*.conf` ← drop new vhosts HERE |
| htpasswd / cert files | `/www/server/nginx/conf/` (alongside main config) |
| nginx worker user | `www` (check with `grep ^user /www/server/nginx/conf/nginx.conf`) |

### Pattern: vhost + HTTP Basic Auth + Host-header rewrite

```bash
# 1. Install htpasswd if missing
apt-get install -y apache2-utils

# 2. Create password file (owner root, group nginx worker user)
htpasswd -bc /www/server/nginx/conf/.<service>_htpasswd <user> '<password>'
chmod 640 /www/server/nginx/conf/.<service>_htpasswd
chown root:www /www/server/nginx/conf/.<service>_htpasswd

# 3. Write vhost
cat > /www/server/panel/vhost/nginx/<service>.conf <<'EOF'
server {
    listen <public_port> default_server;
    server_name _;

    auth_basic "<Service Name> - Login Required";
    auth_basic_user_file /www/server/nginx/conf/.<service>_htpasswd;

    location / {
        proxy_pass http://127.0.0.1:<internal_port>;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        # CRITICAL: rewrite Host to match the bind address of the upstream,
        # otherwise apps with Host-header validation (Hermes Dashboard, Django, Jupyter)
        # will return 400 "Invalid Host header"
        proxy_set_header Host 127.0.0.1:<internal_port>;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

# 4. Test + reload
nginx -t && nginx -s reload
```

### Pitfalls specific to BT Panel nginx

1. **Wrong vhost path = silent no-op.** Files in `/etc/nginx/conf.d/` are NOT loaded. They MUST go to `/www/server/panel/vhost/nginx/`. `nginx -t` will still say OK because it only validates included files.

2. **`nginx -s reload` may fail with `kill(<pid>) failed (3: No such process)`** if a previous reload left a stale pid file. Fix: `systemctl restart nginx` OR call `/etc/init.d/nginx restart` OR just invoke `/www/server/nginx/sbin/nginx` directly to start fresh.

3. **`htpasswd` not installed by default.** Install via `apt-get install -y apache2-utils` (Debian/Ubuntu).

4. **htpasswd file permission.** If nginx worker (`www`) can't read it, all auth requests fail silently. `chmod 640` + `chown root:www` is the safe combo. Verify with `sudo -u www cat /www/server/nginx/conf/.<service>_htpasswd`.

5. **Host-header validation 400.** Apps that pin themselves to `127.0.0.1` for safety (Hermes Dashboard is a prime example — it explicitly returns `{"detail":"Invalid Host header. Dashboard requests must use the hostname the server was bound to."}`) reject reverse-proxied requests unless `proxy_set_header Host 127.0.0.1:<port>` is set. Forgetting this is the #1 cause of "Basic Auth works locally but public IP returns 400".

6. **Dual firewall trap.** BT Panel does NOT manage `ufw`. If `ufw` is active, you also need `ufw allow <port>/tcp` on top of the cloud security group. Three layers total: cloud security group → ufw → app bind address.

7. **BT Panel UI can manage sites, but it does NOT show vhosts you drop manually.** They still work, just don't appear in 网站 list. That's expected — manual vhosts are for non-website services (dashboards, APIs, proxies).

See `references/nginx-reverse-proxy.md` for a full worked example (Hermes Dashboard on port 9120 with Basic Auth).

## Reference: Sample Install (Debian 13, Tencent Cloud)

- OS: Debian 13 (trixie), x86_64
- Installer: bt.cn install_panel.sh
- Duration: ~3 minutes
- Result port: 25260
- Username: ehbutyhn / Password: 196af12b (randomized)
- Security group: inbound TCP 25260 required
