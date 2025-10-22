# Azure AD Setup for O365 Integration

## Overview

To use bassi with Office 365 (email and calendar), you need to create an Azure AD application and configure authentication.

## Prerequisites

- Azure account with Office 365 access
- Admin rights to register applications in Azure AD
- Microsoft 365 mailbox and calendar

## Step-by-Step Setup

### 1. Register Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Configure the application:
   - **Name**: `bassi-personal-assistant` (or your choice)
   - **Supported account types**: Single tenant or Personal Microsoft accounts
   - **Redirect URI**: Leave empty (device code flow)
5. Click **Register**

### 2. Get Application IDs

After registration, note down:
- **Application (client) ID**: Copy this value
- **Directory (tenant) ID**: Copy this value

### 3. Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Description: `bassi-secret`
4. Expiration: Choose duration (e.g., 6 months, 12 months, or 24 months)
5. Click **Add**
6. **IMPORTANT**: Copy the secret VALUE immediately (it won't be shown again!)

### 4. Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions** (for personal use)
5. Add these permissions:

**Email Permissions:**
- `Mail.Read` - Read user mail
- `Mail.ReadWrite` - Read and write access to user mail
- `Mail.Send` - Send mail as a user

**Calendar Permissions:**
- `Calendars.Read` - Read user calendars
- `Calendars.ReadWrite` - Read and write user calendars

**Optional (for advanced features):**
- `User.Read` - Sign in and read user profile
- `offline_access` - Maintain access to data

6. Click **Add permissions**
7. Click **Grant admin consent** (if you have admin rights)

### 5. Configure bassi

Add the credentials to your `.env` file:

```bash
# Azure AD / O365 Configuration
MS365_CLIENT_ID=your-application-client-id-here
MS365_CLIENT_SECRET=your-client-secret-value-here
MS365_TENANT_ID=common  # or your specific tenant ID
```

### 6. Test Connection

Run bassi and try an email or calendar command:

```bash
uv run bassi

# In bassi:
> show my recent emails
> what's on my calendar today?
```

### 7. First-Time Authentication

The first time you use O365 features:

1. The Softeria MCP server will initiate device code authentication
2. You'll see a URL and code in the terminal
3. Open the URL in your browser
4. Enter the code
5. Sign in with your Microsoft account
6. Grant the requested permissions
7. Return to bassi - authentication complete!

The token will be cached securely for future use.

## Troubleshooting

### "API key not configured" Error

- Check that your `.env` file has the correct values
- Ensure environment variables are loaded (restart bassi)
- Verify the client ID and secret are correct

### "Permission denied" Error

- Verify you granted admin consent in Azure AD
- Check that all required permissions are added
- Some permissions require admin approval

### "Token expired" Error

- The authentication token has expired
- Delete cached tokens (usually in OS keychain/credential store)
- Re-authenticate when prompted

### "Cannot find module" Error

- Ensure Node.js is installed: `node --version`
- Install Softeria MCP server: `npx -y @softeria/ms-365-mcp-server`

## Security Notes

- **Never commit secrets** to version control
- Add `.env` to `.gitignore`
- Use environment variables or secure vaults
- Rotate secrets periodically
- Use minimal required permissions
- Review granted permissions regularly

## Alternative: Personal Account Mode

If you don't want to create an Azure AD app, you can use the Softeria server's built-in device code flow:

1. Remove `MS365_CLIENT_ID`, `MS365_CLIENT_SECRET` from `.env`
2. The server will use Microsoft's default public client
3. You'll authenticate via device code flow
4. Limited to personal accounts only (not organizational)

## Resources

- [Azure AD App Registration](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [Microsoft Graph Permissions](https://docs.microsoft.com/en-us/graph/permissions-reference)
- [Softeria MCP Server Docs](https://github.com/Softeria/ms-365-mcp-server)
- [Device Code Flow](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code)
