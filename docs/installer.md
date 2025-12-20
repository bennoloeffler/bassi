# bassi macOS Installer

One-click installer for setting up bassi on a fresh macOS machine.

## Overview

The installer automates the complete setup of bassi, including all prerequisites, dependencies, and a Desktop launcher app.

## Files Location

All installer files are stored in Dropbox for easy distribution:

```
/Users/<username>/<Dropbox>/VundS/B_Org Shop/B_05_IT/B_0504_IT Infrastruktur/install-bassi-on-macOS/
├── install-bassi.command    # Double-clickable installer script
├── .env                     # Pre-configured secrets (API keys)
└── README.txt               # User instructions
```

**Note**: The Dropbox path varies by user (e.g., `VundS Dropbox/VundS/...` or `VS Dropbox/VundS/...`). The installer script self-locates using `$(dirname "$0")`.

## What Gets Installed

### System Tools (via Homebrew)
| Package | Purpose |
|---------|---------|
| `git` | Version control |
| `ripgrep` | Fast code search (used by Claude Code) |
| `imagemagick` | Image manipulation |
| `libheif` | HEIC image support |
| `node` | JavaScript runtime (for Claude Code) |
| `libpq` | PostgreSQL client libraries |
| `iterm2` | Better terminal (cask) |
| `visual-studio-code` | Code editor (cask) |

### Python Environment
- **uv** - Fast Python package manager
- **Python dependencies** - Via `uv sync` in bassi directory
- **Playwright browsers** - Chromium for web automation

### AI Tools
- **Claude Code** - Anthropic's CLI (`npm install -g @anthropic-ai/claude-code`)

### bassi Application
- **Repository** - Cloned to `~/projects/ai/bassi`
- **Configuration** - `.env` copied from Dropbox with user's email
- **Desktop Launcher** - `Start bassi.app` on Desktop

## Installation Flow

```
User double-clicks install-bassi.command
         │
         ▼
┌─────────────────────────────────┐
│ 1. Check Prerequisites          │
│    - macOS version              │
│    - Internet connection        │
│    - .env file exists           │
│    - Disk space (≥5GB)          │
│    - Stop running server        │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 2. Check Existing Installation  │
│    If bassi exists, ask:        │
│    • Update (keep changes)      │
│    • Clean Reinstall (delete)   │
│    • Cancel                     │
│    Also ask: keep .env?         │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 3. Install Homebrew             │
│    (if not present)             │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 4. Install brew packages        │
│    CLI tools + cask apps        │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 5. Install uv                   │
│    curl -LsSf .../uv... | sh    │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 6. Install Claude Code          │
│    npm install -g @anthropic-   │
│    ai/claude-code               │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 7. Ask user for email           │
│    (macOS dialog)               │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 8. Clone/Update bassi           │
│    - Fresh: git clone           │
│    - Update: git stash + pull   │
│    - Reinstall: delete + clone  │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 9. Configure .env               │
│    - Backup existing .env       │
│    - Copy from Dropbox          │
│    - Replace __USER_EMAIL__     │
│    (or keep existing if chosen) │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 10. Install Python dependencies │
│     uv sync + playwright install│
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 11. Create Desktop launcher     │
│     Start bassi.app with icon   │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 12. Claude Authentication       │
│     - Check for API key in .env │
│     - Ask: subscription/API/skip│
│     - Login or save API key     │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 13. Done! Show success dialog   │
└─────────────────────────────────┘
```

## Installation Modes

The installer is **idempotent** - it can be run multiple times safely.

### Fresh Install
- No existing bassi installation
- Clones repository, copies .env, installs everything

### Update
- Existing installation detected
- User chooses "Update"
- Stashes local git changes (if any)
- Pulls latest from GitHub
- Asks whether to keep existing .env or replace
- If replacing, creates backup: `.env.backup-YYYYMMDD-HHMMSS`

### Clean Reinstall
- Existing installation detected
- User chooses "Clean Reinstall"
- Confirms deletion warning
- Deletes entire bassi folder
- Fresh clone from GitHub

## Safety Features

| Check | Action |
|-------|--------|
| **Disk space** | Requires ≥5GB free, fails otherwise |
| **Running server** | Offers to stop server on port 8765 |
| **Existing installation** | Asks: Update / Reinstall / Cancel |
| **Existing .env** | Asks: Keep / Replace (with backup) |
| **Git uncommitted changes** | Warns user, stashes changes on update |
| **Git pull conflicts** | Warns but continues, manual resolution needed |
| **Claude authentication** | Offers subscription login, API key entry, or skip |

## Claude Authentication

At the end of installation, if no API key is found in `.env`, the user is asked:

1. **"I have subscription"** - Opens `claude login` in Terminal for browser-based login
2. **"I have API key"** - Prompts for API key (hidden input), saves to `.env`
3. **"Skip for now"** - User can configure later manually

If the Dropbox `.env` already has an active `ANTHROPIC_API_KEY`, this step is skipped.

## Application

The installer creates `/Applications/bassi.app` - a proper macOS app bundle.

Users can launch it via:
- **Applications folder** - Double-click "bassi"
- **Spotlight** - Cmd+Space → type "bassi"
- **Dock** - Drag from Applications to Dock for quick access

### App Bundle Structure
```
bassi.app/
├── Contents/
│   ├── Info.plist           # App metadata
│   ├── MacOS/
│   │   └── start-bassi      # Executable shell script
│   └── Resources/
│       └── icon.icns        # Purple robot icon
```

### Launcher Behavior
1. Checks if bassi is installed (`~/projects/ai/bassi`)
2. Checks if `.env` exists
3. If server already running on port 8765 → just opens browser
4. Otherwise → opens Terminal, runs `./run-agent-web.sh`, waits 4 seconds, opens browser

### Icon
Purple background with a simple robot face (eyes, pupils, mouth, antenna). Generated using Python/PIL during installation.

## Configuration

### .env Template (in Dropbox)
```env
# Pre-configured secrets - DO NOT SHARE

# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Microsoft 365 Integration
MS365_CLIENT_ID=...
MS365_TENANT_ID=...
MS365_CLIENT_SECRET=...

# User email - replaced by installer
MS365_USER=__USER_EMAIL__

# Agent Pool Configuration
AGENT_INITIAL_POOL_SIZE=1
AGENT_KEEP_IDLE_SIZE=1
AGENT_MAX_POOL_SIZE=4
```

The `__USER_EMAIL__` placeholder is replaced with the user's email address during installation.

### API Key Handling
The `ANTHROPIC_API_KEY` in the Dropbox `.env` can be:
- **Active** - Shared team key for all users
- **Commented out** - Each user provides their own key

If commented out, users need to either:
1. Set `ANTHROPIC_API_KEY` in their system environment
2. Edit `~/projects/ai/bassi/.env` and add their key

## Troubleshooting

### Installation Issues

**Log file**: `~/bassi-install.log`

Check the log for detailed error messages if installation fails.

### Common Problems

| Problem | Solution |
|---------|----------|
| "Permission denied" when running installer | Right-click → Open → Click "Open" in dialog |
| Homebrew installation hangs | Check internet connection, try again |
| "Command not found: uv" | Restart Terminal or run `source ~/.zshrc` |
| Server doesn't start | Check `~/bassi-install.log` and `/tmp/bassi-web.log` |

### Manual Start (if launcher fails)
```bash
cd ~/projects/ai/bassi
./run-agent-web.sh
# Then open http://localhost:8765 in browser
```

## Updating bassi

To update an existing installation:
```bash
cd ~/projects/ai/bassi
git pull
uv sync
```

Or re-run the installer - it will pull latest changes instead of cloning.

## Uninstallation

To remove bassi:
```bash
# Remove bassi
rm -rf ~/projects/ai/bassi

# Remove Desktop launcher
rm -rf ~/Desktop/Start\ bassi.app

# Remove log file
rm ~/bassi-install.log

# Optional: Remove Homebrew packages
brew uninstall git ripgrep imagemagick libheif node libpq
brew uninstall --cask iterm2 visual-studio-code

# Optional: Remove uv
rm -rf ~/.local/bin/uv ~/.local/bin/uvx

# Optional: Remove Claude Code
npm uninstall -g @anthropic-ai/claude-code
```

## Estimated Installation Time

| Component | Time |
|-----------|------|
| Homebrew (if not installed) | 2-5 min |
| Brew packages | 5-10 min |
| uv + Claude Code | 1-2 min |
| Python dependencies | 2-3 min |
| Playwright browsers | 2-3 min |
| **Total (fresh system)** | **15-20 min** |

Re-running on an already-configured system is much faster (~2-3 min).

## Security Notes

- The `.env` file contains API secrets - never commit to git
- Dropbox folder should be shared only with trusted team members
- Each user's email is stored in their local `.env`
- The installer does not transmit any data externally (except to install packages)

## Future Improvements

- [ ] First-run API key setup flow (dialog or web UI)
- [ ] Automatic updates check
- [ ] Health check on startup
- [ ] Support for multiple environments (dev/prod)
