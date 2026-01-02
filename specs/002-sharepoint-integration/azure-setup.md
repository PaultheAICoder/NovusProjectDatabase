# Azure AD App Registration for SharePoint Integration

This guide documents the Azure AD configuration required for SharePoint integration.

## Prerequisites

- Azure AD tenant with admin access
- SharePoint Online site provisioned
- NPD Azure AD app registration (existing)

## Option A: Extend Existing NPD App Registration (Recommended)

If you already have an Azure AD app for NPD authentication, you can add SharePoint permissions to it.

### Step 1: Add API Permissions

1. Go to Azure Portal > Azure Active Directory > App registrations
2. Select your NPD application
3. Go to "API permissions"
4. Click "Add a permission" > "Microsoft Graph"
5. Select "Delegated permissions" and add:
   - `Files.ReadWrite.All` - For user-context file operations
6. For background jobs, select "Application permissions" and add:
   - `Sites.ReadWrite.All` - For app-only file access
7. Click "Grant admin consent" for your organization

### Step 2: Note the Drive ID

1. Use Graph Explorer (https://developer.microsoft.com/graph/graph-explorer)
2. Sign in with an account that has access to your SharePoint site
3. Run: `GET https://graph.microsoft.com/v1.0/sites/{site-hostname}:/sites/{site-name}:/drive`
4. Note the `id` field - this is your `SHAREPOINT_DRIVE_ID`

Example:
```
GET https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com:/sites/NPD:/drive
```

## Option B: Create Separate App Registration

Use this if you want to isolate SharePoint permissions from the main NPD app.

### Step 1: Create New App Registration

1. Go to Azure Portal > Azure Active Directory > App registrations
2. Click "New registration"
3. Name: "NPD SharePoint Integration"
4. Supported account types: "Accounts in this organizational directory only"
5. Redirect URI: Leave blank (not needed for client credentials flow)
6. Click "Register"

### Step 2: Create Client Secret

1. Go to "Certificates & secrets"
2. Click "New client secret"
3. Description: "NPD SharePoint Integration"
4. Expiry: Choose based on your security policy
5. Click "Add"
6. **Copy the secret value immediately** - it won't be shown again

### Step 3: Add API Permissions

Same as Option A, Step 1.

### Step 4: Configure NPD

Set these environment variables:
```bash
SHAREPOINT_CLIENT_ID=<new-app-client-id>
SHAREPOINT_CLIENT_SECRET=<new-app-secret>
SHAREPOINT_TENANT_ID=<tenant-id>  # Same as AZURE_AD_TENANT_ID
```

## Required Permissions Summary

| Permission | Type | Purpose |
|------------|------|---------|
| `Files.ReadWrite.All` | Delegated | User-context file upload/download |
| `Sites.ReadWrite.All` | Application | Background job file processing |

## Security Recommendations

1. **Principle of Least Privilege**: Start with delegated permissions only. Add application permissions only if background processing is needed.

2. **Secret Rotation**: Set calendar reminders for client secret expiry. Rotate secrets before they expire.

3. **Audit Logging**: Enable Azure AD sign-in logs to monitor SharePoint API access.

4. **Conditional Access**: Consider applying Conditional Access policies to the SharePoint app registration.

## Verification

After configuration, verify connectivity:

```bash
# Set environment variables
export SHAREPOINT_ENABLED=true
export SHAREPOINT_SITE_URL="https://contoso.sharepoint.com/sites/NPD"
export SHAREPOINT_DRIVE_ID="b!xxxxx"

# Test configuration is loaded
python -c "from app.config import get_settings; s = get_settings(); print(f'SharePoint configured: {s.is_sharepoint_configured}')"
```

## Production Deployment Considerations

### Secret Management

1. **Azure Key Vault Integration**
   - Store `SHAREPOINT_CLIENT_SECRET` in Azure Key Vault
   - Use managed identity for Key Vault access when deployed to Azure
   - Reference secrets using Key Vault URI syntax

2. **Secret Rotation Schedule**
   - Azure AD client secrets can be configured with 6 month, 12 month, or 24 month expiry
   - Set calendar reminders 2 weeks before expiration
   - Create new secret before rotating out old one (zero-downtime rotation)
   - Update NPD configuration with new secret
   - Verify connectivity, then delete old secret

3. **Rotation Procedure**
   ```bash
   # 1. Create new secret in Azure Portal (don't delete old one yet)
   # 2. Update environment variable
   export SHAREPOINT_CLIENT_SECRET="new-secret-value"

   # 3. Restart NPD backend
   docker compose restart backend

   # 4. Verify connectivity
   python -m app.scripts.migrate_to_sharepoint --dry-run

   # 5. Only after verification, delete old secret in Azure Portal
   ```

### Monitoring Recommendations

1. **Azure AD Sign-in Logs**
   - Enable diagnostic settings for Azure AD
   - Send logs to Log Analytics workspace
   - Create alerts for:
     - Failed authentications
     - Unusual access patterns
     - Access from unexpected locations

2. **Microsoft Graph API Metrics**
   - Monitor API call volume
   - Track response times
   - Alert on rate limiting (HTTP 429)

3. **NPD Application Logs**
   - Log SharePoint operations with structured logging
   - Include correlation IDs for request tracing
   - Monitor error rates for SharePoint operations

### Conditional Access Policies

Consider applying Conditional Access policies to the SharePoint app registration:

1. **IP-based Restrictions**
   - Allow access only from known NPD deployment IP ranges
   - Useful for production deployments with static IPs

2. **Device Compliance** (if applicable)
   - Require compliant devices for delegated access
   - Not applicable for application-only access

3. **Sign-in Risk**
   - Block high-risk sign-ins
   - Require MFA for medium-risk sign-ins

### High Availability

1. **Token Caching**
   - NPD caches access tokens to reduce authentication calls
   - Tokens are refreshed before expiry
   - No manual intervention required

2. **Retry Logic**
   - NPD implements exponential backoff for transient failures
   - Rate limit responses (429) are handled automatically
   - Configurable retry limits

## Troubleshooting Common Issues

### Token Acquisition Failures

**Symptom**: "Failed to acquire token" or "Authentication failed" errors

**Possible Causes & Solutions**:

1. **Invalid credentials**
   ```bash
   # Verify client ID and secret are correct
   # Check for copy/paste errors (trailing spaces, etc.)
   echo "Client ID: $SHAREPOINT_CLIENT_ID"
   echo "Client Secret length: ${#SHAREPOINT_CLIENT_SECRET}"
   ```

2. **Expired client secret**
   - Check secret expiration in Azure Portal
   - Create new secret if expired
   - Update NPD configuration

3. **Missing admin consent**
   - Go to Azure Portal > App registrations > Your app > API permissions
   - Check for "Granted for" status
   - Click "Grant admin consent" if needed

4. **Incorrect tenant ID**
   - Verify tenant ID matches your Azure AD tenant
   - Find correct ID in Azure Portal > Azure Active Directory > Overview

### Permission Denied Errors

**Symptom**: "Access denied" or "403 Forbidden" when accessing files

**Possible Causes & Solutions**:

1. **Missing Site.ReadWrite.All permission**
   - Verify application permission is added
   - Ensure admin consent is granted

2. **App not added to SharePoint site**
   - Add the app's service principal to site permissions
   - Grant at least "Edit" permission level

3. **Incorrect site URL or drive ID**
   - Verify site URL format (no trailing slash)
   - Re-query drive ID via Graph Explorer

### Rate Limiting Responses

**Symptom**: HTTP 429 "Too Many Requests" errors

**Possible Causes & Solutions**:

1. **High request volume**
   - Reduce batch size during migration
   - Add delays between operations
   - Spread migration over longer period

2. **Retry-After header**
   - Check response headers for `Retry-After` value
   - Wait specified time before retrying

3. **Optimize API calls**
   - Use batch requests where supported
   - Cache responses when appropriate

## Health Check Integration

NPD exposes health check endpoints that include SharePoint status:

```bash
# Check overall health (includes SharePoint if configured)
curl http://localhost:6701/api/v1/health

# Expected response includes:
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "sharepoint": "healthy"  # Only if SHAREPOINT_ENABLED=true
  }
}
```

### Custom Health Check

For custom monitoring, you can call the configuration check directly:

```python
from app.config import get_settings

settings = get_settings()
if settings.sharepoint_enabled:
    if settings.is_sharepoint_configured:
        print("SharePoint: Configured")
    else:
        print("SharePoint: MISCONFIGURED - check credentials")
else:
    print("SharePoint: Disabled")
```

## Related Documentation

- [SharePoint Site Setup](./sharepoint-setup.md) - Site and library configuration
- [Configuration Reference](./configuration.md) - All environment variables
- [Migration Runbook](./migration-runbook.md) - Production migration steps
- [Rollback Procedure](./rollback.md) - How to disable SharePoint if needed
