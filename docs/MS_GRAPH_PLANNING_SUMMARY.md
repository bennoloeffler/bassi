# MS Graph Server - Planning Complete ✅

**Date**: 2025-01-22
**Status**: Research & Planning Phase Complete - Ready for Implementation

## Executive Summary

I have completed comprehensive research, analysis, and planning for implementing the MS Graph MCP Server to integrate Microsoft 365 (email and calendar) into bassi. This document provides a quick reference to all deliverables.

## What Was Accomplished

### 1. ✅ Architecture Analysis
- Analyzed existing MCP server patterns in the codebase
- Identified integration points in `bassi/agent.py`
- Confirmed consistent patterns across `bash_server.py` and `web_search_server.py`
- Designed MS Graph Server to follow the same patterns

### 2. ✅ Microsoft Graph API Research
- Researched authentication flows (Device Code, Interactive Browser, Client Secret)
- **Selected Device Code Flow** as optimal for CLI personal assistant
- Identified required Python packages: `msgraph-sdk`, `azure-identity`, `msal-extensions`
- Documented all required API permissions and scopes

### 3. ✅ Tool Design
Designed 4 MCP tools following existing patterns:
- `mcp__ms365__read_emails` - Read emails from inbox
- `mcp__ms365__send_email` - Send emails
- `mcp__ms365__read_calendar` - Read calendar events
- `mcp__ms365__create_event` - Create calendar events

### 4. ✅ Azure/O365 Backend Requirements
Created detailed step-by-step guide for Azure portal setup:
- App registration process
- Permission configuration (7 specific permissions documented)
- Public client flow enablement
- Configuration in bassi

### 5. ✅ Implementation Plan
Created 4-phase implementation plan:
- **Phase 1**: Foundation (authentication, structure)
- **Phase 2**: Email tools
- **Phase 3**: Calendar tools
- **Phase 4**: Polish, testing, documentation

### 6. ✅ Documentation
Created comprehensive documentation:
- Feature design document: `docs/features_concepts/ms_graph_server.md` (600+ lines)
- Implementation guide: `docs/ms_graph_implementation_guide.md` (practical checklist)
- Updated Azure setup: `docs/features_concepts/azure_ad_setup.md`

## Deliverables

### Primary Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| **MS Graph Server Design** | `docs/features_concepts/ms_graph_server.md` | Complete technical design, API research, code examples |
| **Implementation Guide** | `docs/ms_graph_implementation_guide.md` | Step-by-step implementation checklist |
| **Azure AD Setup** | `docs/features_concepts/azure_ad_setup.md` | Azure portal configuration guide |

### Key Decisions Made

1. **Authentication Flow**: Device Code Flow
   - Best for CLI applications
   - User-friendly (one-time setup with browser)
   - Tokens cached for future use

2. **Permissions**: Delegated (not Application)
   - Acts on behalf of signed-in user
   - More secure for personal assistant use case
   - Aligns with bassi's vision

3. **Dependencies**:
   ```bash
   uv add msgraph-sdk azure-identity msal-extensions
   ```

4. **Configuration Approach**:
   - Store `client_id` and `tenant_id` in config
   - No client secret needed (device code flow)
   - Token cache in `~/.cache/bassi/`

## What You Need to Do in Azure Portal

### Quick Steps (5-10 minutes)

1. **Register App**: https://portal.azure.com/ → Azure AD → App registrations → New
   - Name: `bassi-personal-assistant`
   - Account types: Personal + Organizational
   - Redirect: `http://localhost` (Public client)

2. **Copy IDs**:
   - Application (client) ID
   - Directory (tenant) ID

3. **Add Permissions**: API permissions → Microsoft Graph → Delegated
   - ☑️ User.Read
   - ☑️ offline_access
   - ☑️ Mail.Read
   - ☑️ Mail.ReadWrite
   - ☑️ Mail.Send
   - ☑️ Calendars.Read
   - ☑️ Calendars.ReadWrite

4. **Grant Consent**: Click "Grant admin consent"

5. **Enable Public Client**: Authentication → Advanced → Allow public client flows → Yes

### Configuration

Add to `~/.config/bassi/config.json`:

```json
{
  "ms365_client_id": "YOUR_CLIENT_ID_FROM_AZURE",
  "ms365_tenant_id": "common"
}
```

## Implementation Roadmap

### Phase 1: Foundation (Day 1)
- Install dependencies
- Create `bassi/mcp_servers/ms_graph_server.py`
- Implement authentication helper
- Register in `bassi/agent.py`

### Phase 2: Email Tools (Day 2)
- Implement `read_emails` tool
- Implement `send_email` tool
- Test with real API

### Phase 3: Calendar Tools (Day 3)
- Implement `read_calendar` tool
- Implement `create_event` tool
- Test with real API

### Phase 4: Polish (Day 4)
- Error handling
- Documentation
- Integration testing

**Total Estimated Time**: 4 days

## Technical Architecture

```
User Query → bassi CLI → BassiAgent
                            ↓
                     MCP Server Registry
                            ↓
                    ms_graph_server.py
                   (4 tools: email + calendar)
                            ↓
                  msgraph-sdk-python
                  + azure-identity
                            ↓
                   Device Code Flow
                   (first time: browser auth)
                   (later: cached token)
                            ↓
              Microsoft Graph API
         (https://graph.microsoft.com)
              ↓                    ↓
          Mail API           Calendar API
     (Outlook/Exchange)
```

## Example Usage (After Implementation)

```bash
./run-agent.sh

# First time - authentication
> show me my recent emails

  To sign in, open: https://microsoft.com/devicelogin
  Enter code: A1B2C3D4

  [User opens browser, signs in]

  ✓ Authenticated! Showing your recent emails...

# Subsequent uses - no re-auth needed
> what's on my calendar today?
> send a test email to myself
> create a meeting tomorrow at 2pm
```

## Required Azure Permissions Summary

| Permission | Type | Purpose |
|------------|------|---------|
| User.Read | Delegated | Read user profile |
| offline_access | Delegated | Token refresh |
| Mail.Read | Delegated | Read emails |
| Mail.ReadWrite | Delegated | Modify emails |
| Mail.Send | Delegated | Send emails |
| Calendars.Read | Delegated | Read calendar |
| Calendars.ReadWrite | Delegated | Modify calendar |

**All are Delegated** (not Application) - acts on behalf of signed-in user.

## Security Considerations

### ✅ Best Practices Followed
- Device Code Flow (user consent required)
- Delegated permissions (not app-only)
- Minimal permission set
- Token caching in user directory
- No secrets in code/config (client secret not needed)

### 🔒 User Responsibilities
- Never commit `config.json` with real IDs to git
- Keep Azure client ID private
- Review permissions before granting
- Use personal app registration (don't share)

## References

### Documentation Created
- `docs/features_concepts/ms_graph_server.md` - Full design (600+ lines)
- `docs/ms_graph_implementation_guide.md` - Implementation checklist
- `docs/features_concepts/azure_ad_setup.md` - Azure portal guide

### External Resources
- Microsoft Graph SDK: https://github.com/microsoftgraph/msgraph-sdk-python
- Graph API Reference: https://learn.microsoft.com/en-us/graph/api/overview
- Device Code Flow: https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code
- Permissions Reference: https://learn.microsoft.com/en-us/graph/permissions-reference

### Code Examples
All code examples included in `docs/features_concepts/ms_graph_server.md`:
- Authentication setup
- Reading emails
- Sending emails
- Reading calendar
- Creating events
- Error handling patterns

## Next Steps

### Immediate Action Required (You)
1. **Azure Portal Setup** (5-10 min)
   - Follow: `docs/features_concepts/azure_ad_setup.md`
   - Complete steps 1-5 above
   - Copy client ID to bassi config

### Implementation (After Azure Setup)
2. **Begin Phase 1**
   - Follow: `docs/ms_graph_implementation_guide.md`
   - Install dependencies
   - Create server file
   - Test authentication

3. **Iterate Through Phases**
   - Complete each phase
   - Test thoroughly
   - Document any issues

## Questions Answered

### Why Device Code Flow?
- **Best for CLI apps** - no need for local web server
- **User-friendly** - one-time browser authentication
- **Secure** - user consent required, tokens cached
- **Standard** - recommended by Microsoft for browserless apps

### Why Not Client Secret?
- Client secrets are for **daemon apps** (no user interaction)
- bassi is a **personal assistant** (acts on behalf of user)
- Device code flow is more appropriate for personal use

### Why Delegated (not Application) Permissions?
- **Delegated**: Acts as the user (personal assistant model)
- **Application**: Acts as the app (automation/service model)
- bassi should act **on behalf of the user**, not independently

### Will I Need to Re-Authenticate?
- **First time**: Yes, via device code flow (browser)
- **Subsequent uses**: No, token cached and auto-refreshed
- **Token expired**: Delete cache, re-authenticate

## Vision Alignment

This implementation completes:
- ✅ **Iteration 3**: Read emails, save drafts (from vision.md)
- ✅ **Iteration 4**: Read calendar (from vision.md)

Enables future iterations:
- Iteration 5: Save conversations (email integration helpful)
- Iteration 6: Scheduled tasks (calendar integration helpful)

## Success Criteria

### Definition of Done
- [ ] User can authenticate via device code flow
- [ ] User can read recent emails
- [ ] User can send emails
- [ ] User can view calendar events
- [ ] User can create calendar events
- [ ] Tokens cached for future use
- [ ] Error messages are user-friendly
- [ ] Documentation updated

### Acceptance Test
```bash
> show me my recent 5 emails
✓ Shows 5 emails with subjects, senders, dates

> what's on my calendar tomorrow?
✓ Shows tomorrow's events with times, locations

> send a test email to myself
✓ Email sent confirmation, appears in inbox

> create a 30-minute meeting at 3pm tomorrow
✓ Event created, appears in calendar
```

## Final Notes

### ✅ What's Ready
- Complete technical design
- Azure portal instructions
- Implementation plan with code examples
- Testing strategy
- Documentation

### 🚀 Ready to Implement
Everything needed to implement the MS Graph Server is documented and ready. The architecture follows existing patterns, making implementation straightforward.

### 📋 Next Action
**You**: Complete Azure portal setup (5-10 minutes)
**Then**: Begin Phase 1 implementation following the checklist

---

**Status**: Planning Complete - Ready for Implementation
**Estimated Implementation Time**: 4 days (can be done iteratively)
**Risk Level**: Low (well-researched, follows existing patterns)

For questions during implementation, refer to:
- `docs/features_concepts/ms_graph_server.md` - Technical details
- `docs/ms_graph_implementation_guide.md` - Step-by-step guide
