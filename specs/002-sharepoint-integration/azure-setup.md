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
