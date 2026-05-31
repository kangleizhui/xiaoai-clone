# BT CLI Cheatsheet

```
bt           # Interactive menu (numbered options)
bt 1         # Restart panel
bt 2         # Stop panel
bt 3         # Start panel
bt 5         # Modify username
bt 6         # Modify password
bt 8         # Modify panel port
bt 9         # Enable/disable SSL
bt 14        # Display current panel info
bt 22        # Show system logs
/etc/init.d/bt start|stop|restart   # Service control
```

## Quick Info Retrieval

```bash
# Get username, password, and URL
bt 14

# Check if panel is running
ss -tlnp | grep "$(cat /www/server/panel/data/port.pl 2>/dev/null)"

# View installation log
cat /tmp/btpanel-install.log 2>/dev/null
```
