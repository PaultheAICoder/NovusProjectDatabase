# GitHub Webhook Setup

This document describes how to configure GitHub webhooks for the Novus Project Database (NPD).

## Architecture

GitHub webhooks cannot reach private network IPs directly. We use [smee.io](https://smee.io) as a webhook proxy:

```
GitHub --> smee.io --> smee-client (local) --> http://localhost:6701/api/v1/webhooks/github
```

## Prerequisites

Before setting up the webhook, ensure:

1. **smee-client** is installed:
   ```bash
   npm install -g smee-client
   # Or use npx (no install needed): npx smee ...
   ```

2. **Environment variables** are set in `backend/.env`:
   - `GITHUB_WEBHOOK_SECRET` - For webhook signature verification
   - `GITHUB_API_TOKEN` - For GitHub API access (repo scope)

3. **Docker containers** are running:
   ```bash
   docker compose up -d
   ```

4. **Backend endpoint** is accessible:
   ```bash
   curl http://localhost:6701/api/v1/webhooks/github
   # Expected: {"status":"ok","service":"github-webhook"}
   ```

## Smee Channel Setup

1. Visit https://smee.io/new to create a new channel
2. Copy the channel URL (e.g., `https://smee.io/XXXXX`)
3. Save this URL - you will need it for:
   - The smee-client command
   - The GitHub webhook configuration

## Manual Testing

### Start Smee Forwarder

```bash
# Run smee forwarder (foreground)
npx smee -u https://smee.io/YOUR_CHANNEL --target http://localhost:6701/api/v1/webhooks/github

# Or run in background
nohup npx smee -u https://smee.io/YOUR_CHANNEL --target http://localhost:6701/api/v1/webhooks/github > /tmp/smee-npd.log 2>&1 &
```

### Verify Endpoint

```bash
# Test webhook health endpoint
curl http://localhost:6701/api/v1/webhooks/github

# Check Docker logs for webhook activity
docker logs npd-backend 2>&1 | grep -i webhook
```

## GitHub Webhook Configuration

### Create Webhook via GitHub CLI

```bash
# Read webhook secret from .env
cd /home/pbrown/Novus-db
WEBHOOK_SECRET=$(grep GITHUB_WEBHOOK_SECRET backend/.env | cut -d= -f2)

# Create the webhook
gh api repos/PaultheAICoder/NovusProjectDatabase/hooks --method POST \
  --input - <<EOF
{
  "name": "web",
  "active": true,
  "events": ["issues"],
  "config": {
    "url": "https://smee.io/YOUR_CHANNEL",
    "content_type": "json",
    "secret": "$WEBHOOK_SECRET"
  }
}
EOF
```

### Configure via GitHub Web UI

1. Go to https://github.com/PaultheAICoder/NovusProjectDatabase/settings/hooks
2. Click "Add webhook"
3. Configure:
   - **Payload URL**: `https://smee.io/YOUR_CHANNEL`
   - **Content type**: `application/json`
   - **Secret**: Your `GITHUB_WEBHOOK_SECRET` value
   - **Events**: Select "Issues" only
4. Click "Add webhook"

## Verification

### Test Webhook Delivery

```bash
# Get webhook ID (if you need it)
gh api repos/PaultheAICoder/NovusProjectDatabase/hooks --jq '.[].id'

# Send test ping (replace HOOK_ID with actual ID)
gh api repos/PaultheAICoder/NovusProjectDatabase/hooks/HOOK_ID/pings --method POST

# Check recent deliveries
gh api repos/PaultheAICoder/NovusProjectDatabase/hooks/HOOK_ID/deliveries --jq '.[0]'
```

### Verify Smee Forwarder

```bash
# If running as background process
tail -f /tmp/smee-npd.log

# If running as systemd service
sudo systemctl status npd-smee-webhook
sudo journalctl -u npd-smee-webhook -f
```

### End-to-End Test

1. Create a test issue on GitHub
2. Watch smee logs for the incoming webhook
3. Close the issue
4. Verify:
   - Smee forwards the webhook
   - NPD backend logs show webhook receipt
   - Email notification is sent (if configured)

## Systemd Service Setup

For persistent webhook forwarding, install the systemd service:

```bash
# Install services
sudo ./scripts/systemd/install-services.sh

# IMPORTANT: Edit the service to add your smee channel URL
sudo nano /etc/systemd/system/npd-smee-webhook.service
# Replace YOUR_CHANNEL with your actual smee.io channel URL

# Reload and start
sudo systemctl daemon-reload
sudo systemctl enable --now npd-smee-webhook.service

# Check status
sudo systemctl status npd-smee-webhook.service
```

## Troubleshooting

### Webhook Returns 502 Bad Gateway

**Cause**: The smee forwarder is not running.

**Solution**:
```bash
# Start smee manually
npx smee -u https://smee.io/YOUR_CHANNEL --target http://localhost:6701/api/v1/webhooks/github

# Or start the systemd service
sudo systemctl start npd-smee-webhook.service
```

### No Webhook Logs in App

**Causes & Solutions**:

1. **Smee not connected**: Check `cat /tmp/smee-npd.log`
2. **Channel mismatch**: Verify smee channel URL matches GitHub webhook config
3. **Container not running**: Check `docker ps | grep npd-backend`

### Email Not Sent on Issue Close

**Causes & Solutions**:

1. **Missing submitter info**: Issue body must contain `**Submitted by**: Name (email@example.com)`
2. **Email not configured**: Check `FEEDBACK_EMAIL` in `.env`
3. **Graph API not configured**: Verify Azure AD settings

```bash
# Check webhook health and email status
curl http://localhost:6701/api/v1/webhooks/github

# Check backend logs
docker logs npd-backend 2>&1 | grep -i webhook
```

### Signature Verification Failed

**Cause**: `GITHUB_WEBHOOK_SECRET` mismatch between GitHub and `.env`

**Solution**:
1. Generate new secret: `openssl rand -hex 32`
2. Update `backend/.env` with new secret
3. Update GitHub webhook with same secret
4. Restart Docker containers: `docker compose restart backend`

## Configuration Reference

| Setting | Location | Description |
|---------|----------|-------------|
| `GITHUB_WEBHOOK_SECRET` | `backend/.env` | Webhook signature verification |
| `GITHUB_API_TOKEN` | `backend/.env` | GitHub API access |
| `GITHUB_OWNER` | `backend/.env` | Repository owner (default: PaultheAICoder) |
| `GITHUB_REPO` | `backend/.env` | Repository name (default: NovusProjectDatabase) |

## Live Setup Checklist

### Step 1: Generate Secrets

```bash
# Generate webhook secret
openssl rand -hex 32
# Add to backend/.env as GITHUB_WEBHOOK_SECRET=<value>

# Generate cron secret (if not already set)
openssl rand -hex 32
# Add to backend/.env as CRON_SECRET=<value>
```

### Step 2: Create Smee Channel

1. Visit https://smee.io/new
2. Copy the channel URL
3. Update `npd-smee-webhook.service` with the URL

### Step 3: Create GitHub Webhook

```bash
cd /home/pbrown/Novus-db
source backend/.env
gh api repos/PaultheAICoder/NovusProjectDatabase/hooks --method POST \
  --input - <<EOF
{
  "name": "web",
  "active": true,
  "events": ["issues"],
  "config": {
    "url": "https://smee.io/YOUR_CHANNEL",
    "content_type": "json",
    "secret": "$GITHUB_WEBHOOK_SECRET"
  }
}
EOF
```

### Step 4: Install and Start Services

```bash
sudo ./scripts/systemd/install-services.sh
# Edit the smee service with your channel URL
sudo nano /etc/systemd/system/npd-smee-webhook.service
sudo systemctl daemon-reload
sudo systemctl enable --now npd-smee-webhook.service
sudo systemctl enable --now npd-email-monitor.timer
```

### Step 5: Verify

```bash
# Check services
sudo systemctl status npd-smee-webhook.service
sudo systemctl status npd-email-monitor.timer

# Test webhook
curl http://localhost:6701/api/v1/webhooks/github

# Check logs
tail -f /var/log/npd/email-monitor.log
```

## Related Documentation

- [Email Monitor Cron](./EMAIL-MONITOR-CRON.md) - Handles reply processing
- Webhook handler: `backend/app/api/webhooks.py`
