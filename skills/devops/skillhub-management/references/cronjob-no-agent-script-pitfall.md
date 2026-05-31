# Cron Job `no_agent=True` Script Pitfall

## The problem

When creating a `no_agent=True` cron job, the `script` parameter takes a **relative filename** (e.g., `skillhub-download.sh`), NOT inline script code.

```python
# ❌ WRONG — treated as a file path, produces "Script not found"
cronjob(script="#!/bin/bash\necho hello", no_agent=True)

# ✅ RIGHT — write the script to ~/.hermes/scripts/ first, then reference by name
write_file("/root/.hermes/scripts/my-script.sh", "#!/bin/bash\necho hello")
cronjob(script="my-script.sh", no_agent=True)
```

## How it fails

Error message: `Script not found: /root/.hermes/scripts/#!/bin/bash ...`

The entire inline script body gets appended to the scripts directory path, producing a nonsense path.

## Absolute paths also fail

Even `cronjob(script="/root/.hermes/scripts/my-script.sh")` will fail with:
`Script path must be relative to ~/.hermes/scripts/`

Only relative filenames are accepted. The system auto-resolves them to `~/.hermes/scripts/`.

## Batch workflow

For updating a `no_agent=True` cron job: update the script file on disk first (via `write_file` or `patch`), then run `cronjob(action='update', script='same-filename.sh')`. No need to change the `script` parameter if the filename hasn't changed.
