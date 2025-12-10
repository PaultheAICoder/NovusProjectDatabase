# Email Monitor Cron Job

## Overview

The email monitor cron job polls the feedback email inbox every 5 minutes to check for replies to issue resolution notifications. It processes user responses to determine if they verified a fix or requested additional changes.

## Quick Start

### Installation

```bash
cd /home/pbrown/Novus-db/scripts/systemd
sudo ./install-services.sh
```

### Uninstallation

```bash
cd /home/pbrown/Novus-db/scripts/systemd
sudo ./uninstall-services.sh
```

### Manual Trigger

```bash
# Read CRON_SECRET from .env
CRON_SECRET=$(grep CRON_SECRET /home/pbrown/Novus-db/backend/.env | cut -d= -f2)

# Trigger email monitor
curl -X GET "http://localhost:6701/api/v1/cron/email-monitor" \
  -H "Authorization: Bearer $CRON_SECRET"
```

## Architecture

### Components

1. **Systemd Timer**: `/etc/systemd/system/npd-email-monitor.timer`
   - Triggers every 5 minutes
   - Survives reboots (Persistent=true)
   - Starts 1 minute after boot

2. **Systemd Service**: `/etc/systemd/system/npd-email-monitor.service`
   - Executes curl request to the email monitor API
   - Logs output to `/var/log/npd/email-monitor.log`

3. **API Endpoint**: `GET /api/v1/cron/email-monitor`
   - Protected by CRON_SECRET bearer token
   - Polls email inbox via Microsoft Graph API
   - Updates Feedback database records

### Flow Diagram

```
systemd timer (5 min)
       |
       v
systemd service (curl)
       |
       v
/api/v1/cron/email-monitor
       |
       v
Microsoft Graph API (poll inbox)
       |
       v
Feedback table (update records)
```

## Configuration

### Environment Variables

| Variable | Location | Description |
|----------|----------|-------------|
| `CRON_SECRET` | `backend/.env` | Bearer token for API authentication |
| `FEEDBACK_EMAIL` | `backend/.env` | Shared mailbox to poll |
| `AZURE_AD_*` | `backend/.env` | Graph API credentials |

### Changing the Poll Interval

Edit `/etc/systemd/system/npd-email-monitor.timer`:

```ini
[Timer]
OnUnitActiveSec=5min  # Change this value
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart npd-email-monitor.timer
```

## Operations

### Check Timer Status

```bash
# View timer status
sudo systemctl status npd-email-monitor.timer

# List all timers with next run time
sudo systemctl list-timers | grep npd
```

### Check Service Status

```bash
# View last execution status
sudo systemctl status npd-email-monitor.service

# View logs
tail -f /var/log/npd/email-monitor.log
```

### Manual Trigger via Systemd

```bash
sudo systemctl start npd-email-monitor.service
```

### Stop/Disable

```bash
# Stop timer (until next reboot)
sudo systemctl stop npd-email-monitor.timer

# Disable timer (survives reboot)
sudo systemctl disable npd-email-monitor.timer
```

## API Response Format

The email monitor endpoint returns JSON:

```json
{
  "status": "success",
  "emails_checked": 10,
  "processed": 2,
  "verified": 1,
  "changes_requested": 1,
  "skipped": 8,
  "errors": [],
  "timestamp": "2025-12-09T21:45:00.000Z"
}
```

## External Scheduler Options

If you prefer not to use systemd, here are alternative scheduling options:

### Option 1: cron-job.org (Recommended for Simplicity)

1. Sign up at https://cron-job.org
2. Create a new job:
   - **URL**: `https://your-domain/api/v1/cron/email-monitor`
   - **Method**: GET
   - **Schedule**: Every 5 minutes
   - **Headers**: `Authorization: Bearer YOUR_CRON_SECRET`

### Option 2: Linux Crontab

```bash
# Edit crontab
crontab -e

# Add entry (every 5 minutes)
*/5 * * * * curl -sS -X GET "http://localhost:6701/api/v1/cron/email-monitor" -H "Authorization: Bearer $(cat /home/pbrown/Novus-db/backend/.env | grep CRON_SECRET | cut -d= -f2)" >> /var/log/npd/email-monitor.log 2>&1
```

### Option 3: AWS EventBridge

1. Create an EventBridge rule with rate expression: `rate(5 minutes)`
2. Target: API Gateway or Lambda proxy to your endpoint
3. Include Authorization header in the request

## Troubleshooting

### Timer Not Running

```bash
# Check if timer is enabled
sudo systemctl is-enabled npd-email-monitor.timer

# Check for errors
sudo journalctl -u npd-email-monitor.timer -n 50

# Verify service file syntax
sudo systemd-analyze verify npd-email-monitor.service
```

### Service Failing

```bash
# Check service status and exit code
sudo systemctl status npd-email-monitor.service

# Check full logs
sudo journalctl -u npd-email-monitor.service -n 100

# Check network connectivity
curl http://localhost:6701/api/v1/health
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | CRON_SECRET mismatch | Verify secret in service matches .env |
| Connection refused | Backend not running | Check `docker ps \| grep npd-backend` |
| Timeout | Backend slow/hung | Check backend health, increase TimeoutSec |
| Empty log | Service not triggered | Check `systemctl list-timers` for next trigger |

### Debugging Steps

1. **Verify the endpoint works manually**:
   ```bash
   CRON_SECRET=$(grep CRON_SECRET /home/pbrown/Novus-db/backend/.env | cut -d= -f2)
   curl -s -w "\nHTTP_CODE:%{http_code}\n" \
     -H "Authorization: Bearer $CRON_SECRET" \
     "http://localhost:6701/api/v1/cron/email-monitor"
   ```

2. **Check systemd journal**:
   ```bash
   sudo journalctl -u npd-email-monitor.service --since "1 hour ago"
   ```

3. **Verify Docker backend is running**:
   ```bash
   docker ps | grep npd-backend
   curl http://localhost:6701/api/v1/health
   ```

## Log Files

| File | Description |
|------|-------------|
| `/var/log/npd/email-monitor.log` | Execution logs |
| `journalctl -u npd-email-monitor.service` | Systemd service logs |
| `journalctl -u npd-email-monitor.timer` | Timer trigger logs |

## Security Considerations

1. **CRON_SECRET** should be a strong random value:
   ```bash
   openssl rand -hex 32
   ```

2. **Log files** may contain email metadata
   - Ensure `/var/log/npd/` has appropriate permissions

3. **Service isolation**
   - Service runs as `pbrown` user, not root
   - Only performs HTTP requests

## File Locations

### Source Files (Project)

```
/home/pbrown/Novus-db/scripts/systemd/
  - npd-email-monitor.service     # systemd service file
  - npd-email-monitor.timer       # systemd timer file
  - install-services.sh           # installation script
  - uninstall-services.sh         # uninstallation script
```

### Installed Files (System)

```
/etc/systemd/system/
  - npd-email-monitor.service
  - npd-email-monitor.timer

/var/log/npd/
  - email-monitor.log
```

## Related Documentation

- [Webhook Setup](./WEBHOOK-SETUP.md) - GitHub webhook configuration
- Cron handler: `backend/app/api/cron.py`
- Email service: `backend/app/services/graph_email_service.py`
