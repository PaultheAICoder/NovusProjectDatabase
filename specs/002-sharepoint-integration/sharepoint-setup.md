# SharePoint Site and Library Setup Guide

This guide documents how to create and configure a SharePoint site and document library for NPD document storage.

## Prerequisites

- Microsoft 365 subscription with SharePoint Online
- SharePoint administrator access (or Site Collection Administrator for existing sites)
- Azure AD app registration completed (see [azure-setup.md](./azure-setup.md))

## Step 1: Create or Identify SharePoint Site

### Option A: Create a New Site (Recommended for NPD)

1. Navigate to SharePoint Admin Center:
   - Go to https://admin.microsoft.com
   - Select "Admin centers" > "SharePoint"
   - Or directly: https://{tenant}-admin.sharepoint.com

2. Create a new site:
   - Click "Sites" > "Active sites" > "Create"
   - Select "Team site (no Microsoft 365 group)" - This provides simpler permissions management
   - Configure site settings:
     - **Site name**: `NPD` or `NovusProjectDatabase`
     - **Site address**: `npd` (results in `https://{tenant}.sharepoint.com/sites/npd`)
     - **Primary administrator**: Your admin account
     - **Language**: English (or appropriate)
     - **Time zone**: Your organization's time zone

3. Click "Finish" and wait for site provisioning (typically 1-2 minutes)

### Option B: Use an Existing Site

If using an existing site:
1. Ensure you have at least Site Collection Administrator permissions
2. Verify sufficient storage quota for expected document volume
3. Note the full site URL for configuration

## Step 2: Create Document Library

1. Navigate to your SharePoint site:
   ```
   https://{tenant}.sharepoint.com/sites/npd
   ```

2. Create the document library:
   - Click the gear icon (Settings) > "Site contents"
   - Click "New" > "Document library"
   - Configure library settings:
     - **Name**: `Documents`
     - **Description**: "NPD project documents storage"

3. Configure library settings (optional but recommended):
   - Go to Library Settings > "Versioning settings"
   - Enable versioning if document history is needed:
     - "Create major versions" - Yes
     - "Keep the following number of major versions" - 500 (or as needed)
   - Go to Library Settings > "Advanced settings"
     - "Allow management of content types" - No (keep simple)

## Step 3: Get Drive ID via Microsoft Graph Explorer

The Drive ID is required for API access to the document library.

1. Sign in to Graph Explorer:
   - Navigate to https://developer.microsoft.com/graph/graph-explorer
   - Sign in with an account that has access to the SharePoint site

2. Request the Drive ID:
   - Run the following query (replace with your tenant and site name):
   ```
   GET https://graph.microsoft.com/v1.0/sites/{tenant}.sharepoint.com:/sites/{site-name}:/drive
   ```

   Example:
   ```
   GET https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com:/sites/npd:/drive
   ```

3. Locate the Drive ID in the response:
   ```json
   {
     "@odata.context": "...",
     "id": "b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
     "driveType": "documentLibrary",
     "name": "Documents",
     "owner": { ... }
   }
   ```

   The `id` field (e.g., `b!xxxxxx...`) is your `SHAREPOINT_DRIVE_ID`.

4. Save this ID - you'll need it for NPD configuration.

### Alternative: Get Drive ID via PowerShell

```powershell
# Install Microsoft Graph PowerShell module if not already installed
Install-Module Microsoft.Graph -Scope CurrentUser

# Connect and authenticate
Connect-MgGraph -Scopes "Sites.Read.All"

# Get site ID first
$site = Get-MgSite -SiteId "{tenant}.sharepoint.com:/sites/npd"

# Get default drive (document library)
$drive = Get-MgSiteDrive -SiteId $site.Id
Write-Host "Drive ID: $($drive.Id)"
```

## Step 4: Create Base Folder Structure

NPD expects a specific folder structure in SharePoint.

### Option A: Manual Creation

1. Navigate to the Documents library
2. Create a folder named `NPD`:
   - Click "New" > "Folder"
   - Name: `NPD`
3. Inside `NPD`, create a subfolder named `projects`:
   - Navigate into the `NPD` folder
   - Click "New" > "Folder"
   - Name: `projects`

The final structure should be:
```
Documents/
  NPD/
    projects/
```

### Option B: Verification via Graph Explorer

Verify folders exist:
```
GET https://graph.microsoft.com/v1.0/drives/{drive-id}/root:/NPD/projects:/children
```

If this returns successfully (even with an empty array), the folder structure exists.

### Folder Naming Convention

NPD will automatically create subfolders within `projects/` for each project:
```
Documents/
  NPD/
    projects/
      project-uuid-1/
        document1.pdf
        document2.docx
      project-uuid-2/
        report.xlsx
```

## Step 5: Configure Permissions

The Azure AD app registration must have access to the SharePoint site.

### Grant App Access to Site

1. Navigate to your SharePoint site
2. Click the gear icon > "Site permissions"
3. Click "Share site" or "Add members"
4. In the search box, search for your Azure AD app by name:
   - If using existing NPD app: Search for your app registration name
   - If using separate SharePoint app: Search for "NPD SharePoint Integration"
5. Select the app and assign appropriate permission level:
   - **Edit** permission is required for read/write access
   - Note: Apps appear under "Site members" or you may need to invite via email

### Alternative: Grant via Admin Center

For application permissions (Sites.ReadWrite.All):

1. Go to SharePoint Admin Center
2. Select "Sites" > "Active sites"
3. Select your NPD site
4. Click "Permissions" > "Advanced permissions settings"
5. Add the service principal to the Site Owners or Site Members group

### Verify Permissions via Graph

Test that your app can access the site:
```bash
# Get an access token (using client credentials flow)
curl -X POST "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id={client-id}" \
  -d "client_secret={client-secret}" \
  -d "scope=https://graph.microsoft.com/.default" \
  -d "grant_type=client_credentials"

# Use the token to list drive contents
curl "https://graph.microsoft.com/v1.0/drives/{drive-id}/root/children" \
  -H "Authorization: Bearer {access-token}"
```

## Verification Checklist

After completing setup, verify the following:

### Manual Verification

- [ ] SharePoint site is accessible at expected URL
- [ ] Documents library exists
- [ ] `/NPD/projects` folder structure created
- [ ] Drive ID captured and stored securely
- [ ] Azure AD app can access the site (test via Graph Explorer)

### NPD Configuration Verification

Run the following commands to verify NPD can connect:

```bash
# Set environment variables
export SHAREPOINT_ENABLED=true
export SHAREPOINT_SITE_URL="https://{tenant}.sharepoint.com/sites/npd"
export SHAREPOINT_DRIVE_ID="{your-drive-id}"

# If using separate credentials
export SHAREPOINT_CLIENT_ID="{client-id}"
export SHAREPOINT_CLIENT_SECRET="{client-secret}"
export SHAREPOINT_TENANT_ID="{tenant-id}"

# Test configuration is loaded (from backend directory)
cd backend
python -c "from app.config import get_settings; s = get_settings(); print(f'SharePoint configured: {s.is_sharepoint_configured}')"
```

Expected output:
```
SharePoint configured: True
```

### Connection Test

Once NPD is configured, you can test the connection:

```bash
# Run dry-run migration to verify connectivity
python -m app.scripts.migrate_to_sharepoint --dry-run
```

If successful, you should see:
```
Found X documents to migrate
DRY RUN MODE - No changes will be made
...
```

## Troubleshooting

### "Access Denied" or "Unauthorized" Errors

1. Verify the Azure AD app has been granted admin consent for required permissions
2. Ensure the app has been added to the SharePoint site permissions
3. Check that client secret has not expired
4. Verify tenant ID, client ID, and client secret are correct

### "Site Not Found" Errors

1. Verify the site URL is correct (no trailing slash)
2. Ensure the site exists and is not archived/deleted
3. Check site URL format: `https://{tenant}.sharepoint.com/sites/{site-name}`

### "Drive Not Found" Errors

1. Verify the drive ID is correct (should start with `b!`)
2. Ensure the document library exists and is named correctly
3. Try re-querying the drive ID via Graph Explorer

### Folder Creation Failures

1. Verify the app has Edit or Full Control permissions
2. Check that the parent folder path exists (`/NPD`)
3. Ensure there are no naming conflicts

## Next Steps

After completing SharePoint setup:

1. Configure NPD environment variables (see [configuration.md](./configuration.md))
2. Run migration from local storage (see [migration-runbook.md](./migration-runbook.md))
3. Verify document upload/download via NPD UI

## Related Documentation

- [Azure AD App Registration](./azure-setup.md) - Azure AD configuration
- [Configuration Reference](./configuration.md) - All environment variables
- [Migration Runbook](./migration-runbook.md) - Production migration steps
- [Rollback Procedure](./rollback.md) - How to disable SharePoint if needed
