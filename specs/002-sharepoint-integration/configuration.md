# SharePoint Configuration Reference

This document provides a comprehensive reference for all SharePoint-related environment variables and configuration options in NPD.

## Environment Variables

### Required Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHAREPOINT_ENABLED` | Yes | `false` | Feature flag to enable SharePoint storage. Set to `true` to use SharePoint instead of local filesystem. |
| `SHAREPOINT_SITE_URL` | Yes | - | Full URL to your SharePoint site. Example: `https://contoso.sharepoint.com/sites/NPD` |
| `SHAREPOINT_DRIVE_ID` | Yes | - | Document library drive ID from Microsoft Graph API. Starts with `b!`. |

### Optional Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHAREPOINT_BASE_FOLDER` | No | `/NPD/projects` | Base folder path in SharePoint where project documents are stored. |
| `SHAREPOINT_CLIENT_ID` | No* | - | Azure AD app client ID. Falls back to `AZURE_AD_CLIENT_ID` if not set. |
| `SHAREPOINT_CLIENT_SECRET` | No* | - | Azure AD app client secret. Falls back to `AZURE_AD_CLIENT_SECRET` if not set. |
| `SHAREPOINT_TENANT_ID` | No* | - | Azure AD tenant ID. Falls back to `AZURE_AD_TENANT_ID` if not set. |

*These variables are optional if you're reusing the main NPD Azure AD credentials. Set them only if using a separate app registration for SharePoint access.

## Credential Fallback Behavior

NPD uses a fallback chain for SharePoint credentials, allowing you to either:
1. Reuse existing Azure AD SSO credentials (simpler)
2. Use dedicated SharePoint credentials (more secure, isolated)

### Fallback Order

```
SHAREPOINT_CLIENT_ID     -> AZURE_AD_CLIENT_ID
SHAREPOINT_CLIENT_SECRET -> AZURE_AD_CLIENT_SECRET
SHAREPOINT_TENANT_ID     -> AZURE_AD_TENANT_ID
```

### Option 1: Reuse Azure AD Credentials (Recommended for Simplicity)

```bash
# SharePoint uses existing Azure AD settings
SHAREPOINT_ENABLED=true
SHAREPOINT_SITE_URL=https://contoso.sharepoint.com/sites/NPD
SHAREPOINT_DRIVE_ID=b!xxxxxxxxxxxxxxxxxxxxxxxxxx

# These are already set for Azure AD SSO
AZURE_AD_CLIENT_ID=your-app-client-id
AZURE_AD_CLIENT_SECRET=your-app-secret
AZURE_AD_TENANT_ID=your-tenant-id
```

### Option 2: Dedicated SharePoint Credentials (Recommended for Security)

```bash
# SharePoint has its own credentials
SHAREPOINT_ENABLED=true
SHAREPOINT_SITE_URL=https://contoso.sharepoint.com/sites/NPD
SHAREPOINT_DRIVE_ID=b!xxxxxxxxxxxxxxxxxxxxxxxxxx
SHAREPOINT_CLIENT_ID=sharepoint-app-client-id
SHAREPOINT_CLIENT_SECRET=sharepoint-app-secret
SHAREPOINT_TENANT_ID=your-tenant-id

# Azure AD SSO uses separate credentials
AZURE_AD_CLIENT_ID=sso-app-client-id
AZURE_AD_CLIENT_SECRET=sso-app-secret
AZURE_AD_TENANT_ID=your-tenant-id
```

## Configuration Validation

### Verify Configuration is Loaded

```python
# From backend directory
from app.config import get_settings

settings = get_settings()
print(f"SharePoint Enabled: {settings.sharepoint_enabled}")
print(f"SharePoint Site URL: {settings.sharepoint_site_url}")
print(f"SharePoint Drive ID: {settings.sharepoint_drive_id}")
print(f"SharePoint Base Folder: {settings.sharepoint_base_folder}")
print(f"SharePoint Configured: {settings.is_sharepoint_configured}")
```

### Configuration Check Script

```bash
# Quick check script
cd backend
python -c "
from app.config import get_settings
s = get_settings()
print('=== SharePoint Configuration ===')
print(f'Enabled: {s.sharepoint_enabled}')
print(f'Site URL: {s.sharepoint_site_url or \"NOT SET\"}')
print(f'Drive ID: {s.sharepoint_drive_id[:20] + \"...\" if s.sharepoint_drive_id else \"NOT SET\"}')
print(f'Base Folder: {s.sharepoint_base_folder}')
print(f'Client ID Set: {bool(s.sharepoint_client_id or s.azure_ad_client_id)}')
print(f'Client Secret Set: {bool(s.sharepoint_client_secret or s.azure_ad_client_secret)}')
print(f'Fully Configured: {s.is_sharepoint_configured}')
"
```

## Docker Compose Configuration

### Development Environment

```yaml
services:
  backend:
    environment:
      # SharePoint Integration (optional - uncomment to enable)
      # SHAREPOINT_ENABLED: "true"
      # SHAREPOINT_SITE_URL: "https://contoso.sharepoint.com/sites/NPD"
      # SHAREPOINT_DRIVE_ID: "b!xxxxxxxxxxxxxxxxxxxxxxxxxx"
      # SHAREPOINT_BASE_FOLDER: "/NPD/projects"
      # If using dedicated SharePoint credentials (otherwise falls back to AZURE_AD_*)
      # SHAREPOINT_CLIENT_ID: ""
      # SHAREPOINT_CLIENT_SECRET: ""
      # SHAREPOINT_TENANT_ID: ""
```

### Production Environment

```yaml
services:
  backend:
    environment:
      # SharePoint Integration
      SHAREPOINT_ENABLED: "true"
      SHAREPOINT_SITE_URL: "${SHAREPOINT_SITE_URL}"
      SHAREPOINT_DRIVE_ID: "${SHAREPOINT_DRIVE_ID}"
      SHAREPOINT_BASE_FOLDER: "/NPD/projects"
      # Use dedicated credentials in production
      SHAREPOINT_CLIENT_ID: "${SHAREPOINT_CLIENT_ID}"
      SHAREPOINT_CLIENT_SECRET: "${SHAREPOINT_CLIENT_SECRET}"
      SHAREPOINT_TENANT_ID: "${SHAREPOINT_TENANT_ID}"
```

### Complete .env Example

```bash
# =============================================================================
# SharePoint Integration Configuration
# =============================================================================

# Feature flag - set to "true" to enable SharePoint storage
SHAREPOINT_ENABLED=true

# SharePoint site URL (no trailing slash)
SHAREPOINT_SITE_URL=https://contoso.sharepoint.com/sites/NPD

# Document library drive ID (from Graph API, starts with "b!")
SHAREPOINT_DRIVE_ID=b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Base folder path for document organization
SHAREPOINT_BASE_FOLDER=/NPD/projects

# =============================================================================
# SharePoint Credentials (optional - falls back to Azure AD credentials)
# =============================================================================

# Use separate app registration for SharePoint (recommended for production)
SHAREPOINT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SHAREPOINT_CLIENT_SECRET=your-client-secret-here
SHAREPOINT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## Production Recommendations

### Secret Management

1. **Never commit secrets to version control**
   - Use environment variables or secret managers
   - Add `.env` files to `.gitignore`

2. **Use Azure Key Vault (Recommended)**
   ```bash
   # Store secrets in Key Vault
   az keyvault secret set --vault-name mykeyvault \
     --name sharepoint-client-secret \
     --value "your-secret-here"

   # Reference in app configuration
   SHAREPOINT_CLIENT_SECRET=@Microsoft.KeyVault(SecretUri=https://mykeyvault.vault.azure.net/secrets/sharepoint-client-secret)
   ```

3. **Rotate secrets regularly**
   - Azure AD client secrets have configurable expiry
   - Set calendar reminders before expiration
   - Create new secret before rotating out old one

### Network Security

1. **Use Private Endpoints** (if available)
   - Configure SharePoint private endpoints for Azure-hosted NPD
   - Reduces exposure to public internet

2. **IP Restrictions**
   - Consider Azure AD Conditional Access policies
   - Limit token issuance to known IP ranges

### Monitoring

1. **Enable Azure AD Sign-in Logs**
   - Monitor for unusual access patterns
   - Set up alerts for failed authentication attempts

2. **Application Insights** (if deployed to Azure)
   - Track SharePoint API call latency
   - Monitor for rate limiting (HTTP 429)

## Configuration Properties

The following properties are computed from configuration:

| Property | Description |
|----------|-------------|
| `is_sharepoint_configured` | Returns `True` if all required SharePoint settings are valid |

### is_sharepoint_configured Logic

SharePoint is considered configured when:
- `sharepoint_enabled` is `True`
- `sharepoint_site_url` is set (non-empty)
- `sharepoint_drive_id` is set (non-empty)
- Client credentials are available (either SharePoint-specific or Azure AD fallback)

```python
@property
def is_sharepoint_configured(self) -> bool:
    return bool(
        self.sharepoint_enabled
        and self.sharepoint_site_url
        and self.sharepoint_drive_id
        and (self.sharepoint_client_id or self.azure_ad_client_id)
        and (self.sharepoint_client_secret or self.azure_ad_client_secret)
    )
```

## Troubleshooting Configuration

### "SharePoint not configured" Error

Check that all required values are set:
```bash
# Verify environment variables
env | grep -E "SHAREPOINT_|AZURE_AD_" | sort
```

Common causes:
- `SHAREPOINT_ENABLED` not set to `true`
- Missing `SHAREPOINT_SITE_URL` or `SHAREPOINT_DRIVE_ID`
- No credentials (neither SharePoint-specific nor Azure AD fallback)

### Environment Variable Not Loading

1. Check `.env` file location (must be in `backend/` directory)
2. Verify no syntax errors in `.env` file
3. Clear settings cache if running interactively:
   ```python
   from app.config import get_settings
   get_settings.cache_clear()
   settings = get_settings()
   ```

## Related Documentation

- [Azure AD Setup](./azure-setup.md) - App registration and permissions
- [SharePoint Setup](./sharepoint-setup.md) - Site and library configuration
- [Migration Runbook](./migration-runbook.md) - Production migration steps
