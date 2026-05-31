# Worked Example: Hermes Dashboard behind Nginx Basic Auth on BT Panel

Real session, May 2026. User wanted `hermes dashboard` accessible from public IP, but Hermes's dashboard has no built-in auth and the user was understandably uncomfortable with "anyone clicking the URL gets in".

## Goal architecture

```
Browser (you)
   ↓  http://<public-IP>:9120  + Basic Auth (admin / <password>)
   ↓
[Cloud security group] — 9120 allowed
   ↓
[Nginx :9120]  ← /www/server/panel/vhost/nginx/hermes-dashboard.conf
   ↓  reverse proxy + Host-header rewrite
   ↓
[Hermes Dashboard :9119]  ← systemd, bound to 127.0.0.1 only
```

## Step-by-step

### 1. Stop any insecure existing instance

If the dashboard was previously run with `--insecure --host 0.0.0.0`, kill it first:

```bash
hermes dashboard --stop
# or: pkill -f "hermes dashboard"
ss -tlnp | grep 9119  # confirm gone
```

### 2. systemd unit (dashboard bound to 127.0.0.1 only)

```bash
cat > /etc/systemd/system/hermes-dashboard.service <<'EOF'
[Unit]
Description=Hermes Agent Web Dashboard (localhost only, reverse-proxied by nginx)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
Environment=HOME=/root
Environment=HERMES_HOME=/root/.hermes
ExecStart=/usr/local/bin/hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/hermes-dashboard.log
StandardError=append:/var/log/hermes-dashboard.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now hermes-dashboard
systemctl is-active hermes-dashboard   # → active
ss -tlnp | grep 9119                    # → 127.0.0.1:9119 only
```

Note `--skip-build` — without it, dashboard tries to `npm run build` on startup which can fail or hang. Pre-built dist already ships with Hermes.

### 3. htpasswd (BT Panel nginx paths)

```bash
apt-get install -y apache2-utils

# Random strong password
PW=$(python3 -c "import secrets,string; a=string.ascii_letters+string.digits+'!@#%*-_+='; print(''.join(secrets.choice(a) for _ in range(16)))")
echo "Password: $PW"   # SAVE THIS — not shown again

htpasswd -bc /www/server/nginx/conf/.hermes_dashboard_htpasswd admin "$PW"
chmod 640 /www/server/nginx/conf/.hermes_dashboard_htpasswd
chown root:www /www/server/nginx/conf/.hermes_dashboard_htpasswd
```

### 4. nginx vhost (BT Panel auto-include path)

```bash
cat > /www/server/panel/vhost/nginx/hermes-dashboard.conf <<'EOF'
# Hermes Dashboard reverse proxy + HTTP Basic Auth
# Public :9120 -> internal 127.0.0.1:9119, requires user/password
server {
    listen 9120 default_server;
    server_name _;

    auth_basic "Hermes Dashboard - Login Required";
    auth_basic_user_file /www/server/nginx/conf/.hermes_dashboard_htpasswd;

    location / {
        proxy_pass http://127.0.0.1:9119;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        # CRITICAL: Hermes Dashboard validates Host header against its bind addr.
        # Without this rewrite, public IP requests return:
        #   {"detail":"Invalid Host header. Dashboard requests must use
        #    the hostname the server was bound to."}
        proxy_set_header Host 127.0.0.1:9119;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

nginx -t && nginx -s reload
```

### 5. Verify in layers

```bash
# Layer 1: dashboard listening locally
curl -s -o /dev/null -w "Local 9119: HTTP %{http_code}\n" http://127.0.0.1:9119/
# → HTTP 200

# Layer 2: nginx rejects unauth
curl -s -o /dev/null -w "Local 9120 no auth: HTTP %{http_code}\n" http://127.0.0.1:9120/
# → HTTP 401

# Layer 3: nginx accepts auth (local)
curl -s -o /dev/null -w "Local 9120 with auth: HTTP %{http_code}\n" -u admin:"$PW" http://127.0.0.1:9120/
# → HTTP 200

# Layer 4: public IP with auth
curl -s --max-time 5 -o /dev/null -w "Public 9120 with auth: HTTP %{http_code}\n" -u admin:"$PW" http://<PUBLIC-IP>:9120/
# → HTTP 200
```

If layer 4 returns **HTTP 400**: missing `proxy_set_header Host 127.0.0.1:9119;` line. Hermes is rejecting the Host header.
If layer 4 returns **HTTP 000 (timeout)**: cloud security group not allowing port 9120, or `ufw` is active and blocking it.

## Three-layer firewall debugging order

When public access fails, check in this order — each layer is more painful to debug than the last:

```bash
# 1. App is listening?
ss -tlnp | grep <port>

# 2. Local works?
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:<port>/

# 3. Public IP self-access works? (if yes → only client-side issue)
curl -s --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://<public-IP>:<port>/

# 4. Host firewall (ufw)
ufw status | grep <port>

# 5. Cloud security group (Tencent/Aliyun/AWS console — last to check, hardest to see)
```

## Pitfalls hit during this real session

1. **Hermes Dashboard has no built-in auth**, deliberately — the `--insecure` flag warns you. Don't try to find a `--token` or `--password` flag, there isn't one. Use a reverse proxy.

2. **`--insecure --host 0.0.0.0`** exposes the dashboard with NO auth. Anyone scanning the port gets your API keys and full session history. Never use this in production without a reverse proxy layer doing auth.

3. **Hermes Dashboard's Host validation** triggers BEFORE the proxy headers reach the app, returning the `Invalid Host header` 400. Took 5 minutes to debug; fix is a single `proxy_set_header Host 127.0.0.1:9119;` line.

4. **`nginx -s reload` failed** with `kill(<pid>) failed (3: No such process)` — old pid file stale. Recovery: run nginx binary directly (`/www/server/nginx/sbin/nginx`) which starts fresh from config.

5. **`nginx -t` reported OK** even when the vhost was in the wrong directory — because nginx only validates files it actually includes. Wrong directory = silent ignore.

6. **`apache2-utils` not preinstalled** on Debian 13 Tencent Cloud images. `htpasswd` command missing until installed.

7. **htpasswd file group** must be readable by nginx worker. On BT Panel default nginx, worker user is `www` (not `nginx` or `www-data`). Check with `grep ^user /www/server/nginx/conf/nginx.conf`.

## Maintenance commands

```bash
# Change password
htpasswd /www/server/nginx/conf/.hermes_dashboard_htpasswd admin

# Add a second user
htpasswd /www/server/nginx/conf/.hermes_dashboard_htpasswd <newuser>

# Change public port (edit vhost, reload)
sed -i 's/listen 9120/listen 9121/' /www/server/panel/vhost/nginx/hermes-dashboard.conf
nginx -s reload
# Don't forget to also update cloud security group + (if any) ufw rule

# Disable temporarily (mv out of include dir)
mv /www/server/panel/vhost/nginx/hermes-dashboard.conf{,.disabled}
nginx -s reload

# Tail dashboard logs
tail -f /var/log/hermes-dashboard.log

# Restart dashboard if config or version changes
systemctl restart hermes-dashboard
```
