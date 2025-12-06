/**
 * Bassi Web UI Client - Streaming-First Architecture
 *
 * Key Features:
 * - Real-time markdown rendering as text streams in
 * - Smooth animations and transitions
 * - Perfect event stream visualization
 * - Responsive, polished UI
 *
 * Architecture:
 * - Event-driven state machine
 * - Incremental markdown parsing with marked.js
 * - DOM diffing for smooth updates
 * - Optimized for streaming UX
 */

class BassiWebClient {
    constructor() {
        // WebSocket connection
        this.ws = null
        this.isConnected = false
        this.reconnectAttempts = 0
        this.maxReconnectAttempts = 5
        this.isIntentionalDisconnect = false  // Track intentional disconnects (session switch)

        // State
        this.blocks = new Map()              // id -> DOM element
        this.boxStates = new Map()           // id -> custom state ('expanded'|'collapsed'|null)
        this.textBuffers = new Map()         // id -> accumulated text
        this.currentMessage = null           // Current assistant message container
        this.totalCost = 0                   // Cumulative cost
        this.verboseLevel = this.loadVerboseLevel()
        this.isAgentWorking = false          // Track if agent is processing
        this.sessionCapabilities = null      // Capabilities from init system message
        this.sessionId = null                // Current session ID from WebSocket connection

        // Autocomplete state (supports both /commands and @files)
        this.commandRegistry = []            // All available commands
        this.autocompletePanel = null        // Autocomplete panel DOM element
        this.autocompleteVisible = false     // Is panel visible
        this.autocompleteSelectedIndex = -1  // Currently selected item index
        this.autocompleteItems = []          // Filtered items for current input
        this.autocompleteMode = null         // 'command' | 'file' | null
        this.autocompleteCommands = []       // Filtered commands (for backward compat)
        this.fileAtPosition = -1             // Position of @ in input when showing file autocomplete

        // Streaming markdown renderer
        this.markdownRenderer = null
        this.renderDebounceTimers = new Map()  // id -> timer

        // File handling (using file sidebar, not chips)
        this.pendingFiles = []                   // Files waiting for session ID
        this.sessionFiles = []                   // All files in current session (from API)
        this.dragCounter = 0                     // Track drag enter/leave events

        // DOM elements
        this.conversationEl = document.getElementById('conversation')
        this.messageInput = document.getElementById('message-input')
        this.sendButton = document.getElementById('send-button')
        this.stopButton = document.getElementById('stop-button')
        this.verboseLevelSelect = document.getElementById('verbose-level')
        this.statusIndicator = document.getElementById('status-indicator')
        this.connectionStatus = document.getElementById('connection-status')
        this.serverStatus = document.getElementById('server-status')
        this.statusText = document.getElementById('status-text')

        this.fileInput = document.getElementById('file-input')
        this.uploadButton = document.getElementById('upload-button')

        // File elements (removed old file chips - now using file sidebar)

        // Session sidebar elements
        this.sessionSidebar = document.getElementById('session-sidebar')
        this.sessionSidebarToggle = document.getElementById('session-sidebar-toggle')
        this.sessionSidebarControls = this.sessionSidebarToggle?.parentElement  // Container for toggle + new session buttons
        this.sessionList = document.getElementById('session-list')
        this.sessionSearch = document.getElementById('session-search')
        this.newSessionButton = document.getElementById('new-session-button')
        this.sessionSidebarOpen = false
        this.allSessions = []  // All sessions from API
        this.filteredSessions = []  // Sessions after search filter

        // File sidebar elements
        this.fileSidebar = document.getElementById('file-sidebar')
        this.fileSidebarToggle = document.getElementById('file-sidebar-toggle')
        this.fileSidebarControls = this.fileSidebarToggle?.parentElement
        this.fileSidebarList = document.getElementById('file-sidebar-list')
        this.fileSidebarUploadBtn = document.getElementById('file-sidebar-upload-btn')
        this.fileSidebarCount = document.getElementById('file-sidebar-count')
        this.fileSidebarSize = document.getElementById('file-sidebar-size')
        this.fileSidebarOpen = false

        // Connection count indicator
        this.connectionCountEl = document.getElementById('connection-count-value')
        this.connectionCountContainer = document.getElementById('connection-count')
        this.connectionCountInterval = null

        this.init()
    }

    init() {
        // Setup marked.js for markdown rendering
        if (typeof marked !== 'undefined') {
            this.markdownRenderer = marked
            // Configure marked for streaming
            marked.setOptions({
                breaks: true,
                gfm: true,
                highlight: (code, lang) => {
                    if (typeof Prism !== 'undefined' && Prism.languages[lang]) {
                        return Prism.highlight(code, Prism.languages[lang], lang)
                    }
                    return code
                }
            })
        }

        // Setup event listeners
        this.sendButton.addEventListener('click', () => {
            this.sendMessage()
        })

        this.stopButton.addEventListener('click', () => {
            this.stopAgent()
        })

        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                this.sendMessage()
            }
        })

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto'
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px'
        })

        // Handle image paste
        this.messageInput.addEventListener('paste', (e) => {
            this.handlePaste(e)
        })

        // Handle drag & drop for files
        this.setupDragAndDrop()

        if (this.verboseLevelSelect) {
            this.verboseLevelSelect.value = this.verboseLevel
            this.verboseLevelSelect.addEventListener('change', (e) => {
                this.setVerboseLevel(e.target.value)
            })
        }

        // Set initial verbose level CSS class
        this.conversationEl.classList.add(`verbose-${this.verboseLevel}`)

        // File upload button
        console.log('🔍 Upload button:', this.uploadButton)
        console.log('🔍 File input:', this.fileInput)
        if (this.uploadButton && this.fileInput) {
            this.uploadButton.addEventListener('click', (e) => {
                e.preventDefault()
                e.stopPropagation()
                console.log('📎 Upload button clicked!')
                this.fileInput.click()
            })

            this.fileInput.addEventListener('change', async (e) => {
                console.log('📁 File selected:', e.target.files)
                await this.handleFileSelect(e)
            })
        } else {
            console.error('❌ Upload button or file input not found!')
        }

        // Initialize settings
        this.initSettings()

        // Initialize autocomplete
        this.initAutocomplete()

        // Initialize session sidebar
        this.initSessionSidebar()

        // Initialize file sidebar
        this.initFileSidebar()

        // PHASE 1: Eager capability loading - load in parallel on startup
        this.loadCapabilities().then(() => {
            console.log('✅ Capabilities loaded on startup')
            this.rebuildCommandRegistry()
        }).catch(err => {
            console.warn('⚠️ Failed to load capabilities on startup:', err)
        })

        // Connect WebSocket
        this.connect()

        // Start connection count polling
        this.startConnectionCountPolling()
    }

    // ========== Connection Count Indicator ==========

    startConnectionCountPolling() {
        // Poll every 3 seconds
        this.connectionCountInterval = setInterval(() => {
            this.updateConnectionCount()
        }, 3000)

        // Initial fetch
        this.updateConnectionCount()
    }

    async updateConnectionCount() {
        try {
            const response = await fetch('/health')
            const data = await response.json()

            const count = data.active_connections || 0

            if (this.connectionCountEl) {
                this.connectionCountEl.textContent = count

                // Update styling for multiple connections
                if (this.connectionCountContainer) {
                    if (count > 1) {
                        this.connectionCountContainer.classList.add('multiple')
                    } else {
                        this.connectionCountContainer.classList.remove('multiple')
                    }
                }
            }
        } catch (error) {
            // Silent fail - don't spam console
        }
    }

    // ========== Session File Management ==========

    async loadSessionFiles() {
        /**
         * Load all files for the current session from the API.
         */
        if (!this.sessionId) {
            console.log('⚠️ Cannot load session files: no session ID')
            return
        }

        try {
            const response = await fetch(`/api/sessions/${this.sessionId}/files`)

            if (!response.ok) {
                console.error('❌ Failed to load session files:', response.status)
                return
            }

            const data = await response.json()
            // Backend returns flat array, not {files: [...]}
            this.sessionFiles = Array.isArray(data) ? data : (data.files || [])

            console.log('📁 Session files loaded:', this.sessionFiles.length)

            // Update file sidebar (files are shown in sidebar, not chips)
            this.renderFileSidebar()
        } catch (error) {
            console.error('❌ Error loading session files:', error)
        }
    }

    getMimeType(filename) {
        /**
         * Get MIME type from filename extension.
         */
        const ext = filename.toLowerCase().split('.').pop()
        const mimeTypes = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'svg': 'image/svg+xml',
            'bmp': 'image/bmp',
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'json': 'application/json',
            'csv': 'text/csv'
        }
        return mimeTypes[ext] || 'application/octet-stream'
    }

    formatFileSize(bytes) {
        /**
         * Format file size in human-readable format.
         */
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return Math.round(bytes / Math.pow(k, i) * 10) / 10 + ' ' + sizes[i]
    }

    // ========== Settings ==========

    initSettings() {
        const settingsButton = document.getElementById('settings-button')
        const settingsModal = document.getElementById('settings-modal')
        const settingsClose = document.getElementById('settings-close')
        const thinkingToggle = document.getElementById('thinking-toggle')
        const globalBypassToggle = document.getElementById('global-bypass-toggle')
        const thinkingIcon = document.getElementById('thinking-icon')
        const permissionsIcon = document.getElementById('permissions-icon')

        // Load thinking preference from localStorage
        const showThinking = localStorage.getItem('showThinking')
        if (showThinking === 'false') {
            thinkingToggle.checked = false
            document.body.classList.add('hide-thinking')
            this.updateThinkingIcon(false)
        } else {
            // Default to true
            thinkingToggle.checked = true
            document.body.classList.remove('hide-thinking')
            this.updateThinkingIcon(true)
        }

        // Load global bypass setting from backend
        this.loadGlobalBypassSetting()

        // Load model settings from backend
        this.loadModelSettings()

        // Model icon click opens settings
        const modelIcon = document.getElementById('model-icon')
        if (modelIcon) {
            modelIcon.addEventListener('click', () => {
                settingsModal.style.display = 'flex'
            })
        }

        // Model level radio buttons
        const modelRadios = document.querySelectorAll('input[name="model-level"]')
        modelRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                const level = parseInt(e.target.value, 10)
                this.updateModelLevel(level)
            })
        })

        // Auto-escalate toggle
        const autoEscalateToggle = document.getElementById('auto-escalate-toggle')
        if (autoEscalateToggle) {
            autoEscalateToggle.addEventListener('change', (e) => {
                this.updateAutoEscalate(e.target.checked)
            })
        }

        // Open settings modal (from gear button or status icons)
        const openSettingsModal = () => {
            settingsModal.style.display = 'flex'
        }

        if (settingsButton) {
            settingsButton.addEventListener('click', openSettingsModal)
        }

        // Status icons also open settings modal
        if (thinkingIcon) {
            thinkingIcon.addEventListener('click', openSettingsModal)
        }
        if (permissionsIcon) {
            permissionsIcon.addEventListener('click', openSettingsModal)
        }

        // Close settings modal
        const closeModal = () => {
            settingsModal.style.display = 'none'
        }

        if (settingsClose) {
            settingsClose.addEventListener('click', closeModal)
        }

        // Close modal when clicking outside
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                closeModal()
            }
        })

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && settingsModal.style.display === 'flex') {
                closeModal()
            }
        })

        // Handle thinking toggle
        if (thinkingToggle) {
            thinkingToggle.addEventListener('change', (e) => {
                // Guard: Block thinking toggle during agent work
                // Reason: Changing thinking mode disconnects and reconnects the session
                if (this.isAgentWorking) {
                    console.log('⚠️ Blocking thinking toggle - agent is working')
                    this.showNotification('Cannot change thinking mode while Claude is working', 'warning')
                    // Revert toggle to previous state
                    e.target.checked = !e.target.checked
                    return
                }

                const showThinking = e.target.checked

                // Save preference to localStorage
                localStorage.setItem('showThinking', showThinking.toString())

                // Toggle body class to show/hide thinking blocks
                if (showThinking) {
                    document.body.classList.remove('hide-thinking')
                    console.log('✅ Thinking blocks enabled')
                } else {
                    document.body.classList.add('hide-thinking')
                    console.log('❌ Thinking blocks disabled')
                }

                // Update the status icon
                this.updateThinkingIcon(showThinking)

                // Send config change to backend
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'config_change',
                        thinking_mode: showThinking
                    }))
                    console.log(`🔄 Sent thinking mode update to backend: ${showThinking}`)
                }
            })
        }

        // Handle global bypass toggle
        if (globalBypassToggle) {
            globalBypassToggle.addEventListener('change', async (e) => {
                const enabled = e.target.checked
                await this.updateGlobalBypass(enabled)
            })
        }
    }

    // Update thinking icon state (brain icon)
    updateThinkingIcon(enabled) {
        const thinkingIcon = document.getElementById('thinking-icon')
        if (thinkingIcon) {
            if (enabled) {
                thinkingIcon.classList.add('active')
                thinkingIcon.title = 'Show Thinking Process: ON'
            } else {
                thinkingIcon.classList.remove('active')
                thinkingIcon.title = 'Show Thinking Process: OFF'
            }
        }
    }

    // Update permissions icon state (lock icon)
    updatePermissionsIcon(unlocked) {
        const permissionsIcon = document.getElementById('permissions-icon')
        if (permissionsIcon) {
            if (unlocked) {
                permissionsIcon.classList.add('unlocked')
                permissionsIcon.title = 'Allow All Tools: ON (unlocked)'
            } else {
                permissionsIcon.classList.remove('unlocked')
                permissionsIcon.title = 'Allow All Tools: OFF (locked)'
            }
        }
    }

    async loadGlobalBypassSetting() {
        // Load global bypass setting from backend
        try {
            const response = await fetch('/api/settings/global-bypass')
            if (response.ok) {
                const data = await response.json()
                const toggle = document.getElementById('global-bypass-toggle')
                if (toggle) {
                    toggle.checked = data.enabled
                    console.log(`🔐 Global bypass loaded: ${data.enabled}`)
                }
                // Update the permissions icon
                this.updatePermissionsIcon(data.enabled)
            }
        } catch (error) {
            console.error('Failed to load global bypass setting:', error)
        }
    }

    async updateGlobalBypass(enabled) {
        // Update global bypass setting on backend
        try {
            const response = await fetch('/api/settings/global-bypass', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled })
            })

            if (response.ok) {
                // Update the permissions icon
                this.updatePermissionsIcon(enabled)

                // Notify WebSocket to update agent permission mode
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'permission_change',
                        bypass_permissions: enabled
                    }))
                    console.log(`🔐 Notified agent of permission change: bypass=${enabled}`)
                }

                this.showNotification(
                    enabled
                        ? '🔓 All tools allowed - agent runs autonomously'
                        : '🔐 Tool permissions managed - agent will ask before using tools',
                    'success'
                )

                console.log(`✅ Global bypass updated: ${enabled}`)

                // Suggest refresh if session is active
                if (this.sessionId) {
                    this.showNotification(
                        'Start a new session for changes to take effect',
                        'info'
                    )
                }
            } else {
                throw new Error('Failed to update setting')
            }
        } catch (error) {
            console.error('Failed to update global bypass:', error)

            // Revert toggle on error
            const toggle = document.getElementById('global-bypass-toggle')
            if (toggle) {
                toggle.checked = !enabled
            }

            this.showNotification(
                'Failed to update permission setting',
                'error'
            )
        }
    }

    // ========== Model Settings ==========

    async loadModelSettings() {
        // Load model settings from backend
        try {
            const response = await fetch('/api/settings/model')
            if (response.ok) {
                const data = await response.json()
                this.currentModelLevel = data.model_level
                this.autoEscalate = data.auto_escalate

                // Update radio buttons
                const radioBtn = document.querySelector(`input[name="model-level"][value="${data.model_level}"]`)
                if (radioBtn) {
                    radioBtn.checked = true
                }

                // Update auto-escalate toggle
                const autoEscalateToggle = document.getElementById('auto-escalate-toggle')
                if (autoEscalateToggle) {
                    autoEscalateToggle.checked = data.auto_escalate
                }

                // Update model icon
                this.updateModelIcon(data.model_level, data.model_info?.name)

                console.log(`🤖 Model settings loaded: level=${data.model_level}, auto_escalate=${data.auto_escalate}`)
            }
        } catch (error) {
            console.error('Failed to load model settings:', error)
        }
    }

    updateModelIcon(level, modelName) {
        const modelIcon = document.getElementById('model-icon')
        if (!modelIcon) return

        // Remove all model classes
        modelIcon.classList.remove('model-haiku', 'model-sonnet', 'model-opus')

        // Add correct class based on level
        const modelClasses = { 1: 'model-haiku', 2: 'model-sonnet', 3: 'model-opus' }
        const modelNames = { 1: 'Haiku 4.5', 2: 'Sonnet 4.5', 3: 'Opus 4.5' }
        modelIcon.classList.add(modelClasses[level] || 'model-haiku')

        // Update badge
        const badge = modelIcon.querySelector('.model-level-badge')
        if (badge) {
            badge.textContent = level
        }

        // Update tooltip
        modelIcon.title = `Model: ${modelName || modelNames[level]}`
    }

    async updateModelLevel(level) {
        // Guard: Block model changes while agent is working
        if (this.isAgentWorking) {
            this.showNotification('Cannot change model while agent is working', 'warning')
            // Revert radio button to current level
            if (this.currentModelLevel) {
                const radioBtn = document.querySelector(`input[name="model-level"][value="${this.currentModelLevel}"]`)
                if (radioBtn) radioBtn.checked = true
            }
            return
        }

        // Update model level on backend
        try {
            const response = await fetch('/api/settings/model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_level: level })
            })

            if (response.ok) {
                const data = await response.json()
                this.currentModelLevel = data.model_level
                this.updateModelIcon(data.model_level, data.model_info?.name)

                // Notify WebSocket about model change
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'model_change',
                        model_level: data.model_level
                    }))
                    console.log(`🤖 Notified agent of model change: level=${data.model_level}`)
                }

                this.showNotification(
                    `Model changed to ${data.model_info?.name || 'level ' + level}`,
                    'success'
                )
                console.log(`✅ Model level updated: ${level}`)
            } else {
                throw new Error('Failed to update model')
            }
        } catch (error) {
            console.error('Failed to update model level:', error)
            this.showNotification('Failed to update model', 'error')

            // Revert radio button
            if (this.currentModelLevel) {
                const radioBtn = document.querySelector(`input[name="model-level"][value="${this.currentModelLevel}"]`)
                if (radioBtn) radioBtn.checked = true
            }
        }
    }

    async updateAutoEscalate(enabled) {
        // Guard: Block auto-escalate changes while agent is working
        if (this.isAgentWorking) {
            this.showNotification('Cannot change auto-escalate while agent is working', 'warning')
            // Revert toggle
            const toggle = document.getElementById('auto-escalate-toggle')
            if (toggle) toggle.checked = !enabled
            return
        }

        // Update auto-escalate setting on backend
        try {
            const response = await fetch('/api/settings/model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auto_escalate: enabled })
            })

            if (response.ok) {
                this.autoEscalate = enabled
                console.log(`✅ Auto-escalate updated: ${enabled}`)
            } else {
                throw new Error('Failed to update auto-escalate')
            }
        } catch (error) {
            console.error('Failed to update auto-escalate:', error)

            // Revert toggle
            const toggle = document.getElementById('auto-escalate-toggle')
            if (toggle) toggle.checked = !enabled
        }
    }

    handleModelChanged(data) {
        // Handle model_changed event from WebSocket (e.g., auto-escalation)
        const { model_level, model_name, reason } = data

        this.currentModelLevel = model_level
        this.updateModelIcon(model_level, model_name)

        // Update radio button
        const radioBtn = document.querySelector(`input[name="model-level"][value="${model_level}"]`)
        if (radioBtn) radioBtn.checked = true

        // Show notification for auto-escalation
        if (reason === 'auto_escalation') {
            this.showNotification(
                `Model upgraded to ${model_name} after consecutive failures`,
                'info'
            )
            // Also add a system message to the conversation
            this.addSystemMessage(`Model automatically upgraded to ${model_name} after 3 consecutive errors`)
        }

        console.log(`🤖 Model changed: level=${model_level}, reason=${reason}`)
    }

    addSystemMessage(text) {
        // Add a system message to the conversation
        const message = document.createElement('div')
        message.className = 'message system-message'
        message.innerHTML = `
            <div class="message-content">
                <div class="system-text">${text}</div>
            </div>
        `
        this.conversationEl.appendChild(message)
        this.scrollToBottom()
    }

    showNotification(message, type = 'info') {
        // Show a toast notification to the user
        // Create notification element
        const notification = document.createElement('div')
        notification.className = `notification notification-${type}`
        notification.textContent = message

        // Style
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
            max-width: 300px;
            font-size: 14px;
        `

        document.body.appendChild(notification)

        // Remove after 4 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out'
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification)
                }
            }, 300)
        }, 4000)
    }

    // ========== Autocomplete Panel ==========

    initAutocomplete() {
        // Build command registry (will be updated when capabilities load)
        this.buildCommandRegistry()

        // Create autocomplete panel structure
        this.autocompletePanel = document.createElement('div')
        this.autocompletePanel.id = 'autocomplete-panel'
        this.autocompletePanel.className = 'autocomplete-panel hidden'
        document.body.appendChild(this.autocompletePanel)

        // Add input event listener for autocomplete trigger
        this.messageInput.addEventListener('input', (e) => {
            this.handleAutocompleteInput(e)
        })

        // Add keydown event listener for navigation
        this.messageInput.addEventListener('keydown', (e) => {
            if (this.autocompleteVisible) {
                this.handleAutocompleteKeydown(e)
            }
        })

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (this.autocompleteVisible &&
                !this.autocompletePanel.contains(e.target) &&
                e.target !== this.messageInput) {
                this.hideAutocomplete()
            }
        })
    }

    buildCommandRegistry() {
        // Built-in commands
        const builtinCommands = [
            { type: 'builtin', name: '/help', description: 'Show all available capabilities' },
            { type: 'builtin', name: '/agents', description: 'Show all available agents' },
            { type: 'builtin', name: '/skills', description: 'Show all available skills' },
            { type: 'builtin', name: '/commands', description: 'Show all available commands' },
            { type: 'builtin', name: '/tools', description: 'Show all MCP tools' },
            { type: 'builtin', name: '/permissions', description: 'Show active tool permissions' },
            { type: 'builtin', name: '/clear', description: 'Clear conversation UI' }
        ]

        // User commands from capabilities (will be added when capabilities load)
        const userCommands = []
        if (this.sessionCapabilities && this.sessionCapabilities.slash_commands) {
            this.sessionCapabilities.slash_commands.forEach(cmd => {
                const cmdName = typeof cmd === 'string' ? cmd : cmd.name
                const cmdDesc = typeof cmd === 'string' ? '' : (cmd.description || '')
                userCommands.push({
                    type: 'user',
                    name: cmdName.startsWith('/') ? cmdName : '/' + cmdName,
                    description: cmdDesc
                })
            })
        }

        this.commandRegistry = [...builtinCommands, ...userCommands]
    }

    rebuildCommandRegistry() {
        // PHASE 4: Rebuild command registry when capabilities change
        this.buildCommandRegistry()

        // If autocomplete is visible and in command mode, refresh it
        if (this.autocompleteVisible && this.autocompleteMode === 'command') {
            const currentQuery = this.messageInput.value.startsWith('/')
                ? this.messageInput.value.substring(1).toLowerCase()
                : ''
            this.showCommandAutocomplete(currentQuery)
        }

        console.log('🔄 Command registry rebuilt:', this.commandRegistry.length, 'commands')
    }

    handleAutocompleteInput(e) {
        const value = this.messageInput.value
        const cursorPos = this.messageInput.selectionStart

        // === Command autocomplete (/ at start) ===
        if (value === '/') {
            this.showCommandAutocomplete('')
            return
        }
        if (value.startsWith('/') && !value.includes(' ')) {
            const query = value.substring(1).toLowerCase()
            this.showCommandAutocomplete(query)
            return
        }

        // === File autocomplete (@ anywhere) ===
        // Find the @ closest to cursor
        const beforeCursor = value.substring(0, cursorPos)
        const lastAtPos = beforeCursor.lastIndexOf('@')

        if (lastAtPos >= 0) {
            // Check if @ is valid (start of word: beginning or after space)
            const charBefore = lastAtPos > 0 ? beforeCursor[lastAtPos - 1] : ' '
            if (charBefore === ' ' || charBefore === '\n' || lastAtPos === 0) {
                // Get query after @ (until cursor)
                const query = beforeCursor.substring(lastAtPos + 1)
                // Only show if no space in query (still typing the ref)
                if (!query.includes(' ')) {
                    this.showFileAutocomplete(query, lastAtPos)
                    return
                }
            }
        }

        // Hide autocomplete if conditions aren't met
        if (this.autocompleteVisible) {
            this.hideAutocomplete()
        }
    }

    handleAutocompleteKeydown(e) {
        if (!this.autocompleteVisible || this.autocompleteItems.length === 0) {
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                this.autocompleteSelectedIndex =
                    (this.autocompleteSelectedIndex + 1) % this.autocompleteItems.length
                this.renderAutocomplete()
                break

            case 'ArrowUp':
                e.preventDefault()
                this.autocompleteSelectedIndex =
                    this.autocompleteSelectedIndex <= 0
                        ? this.autocompleteItems.length - 1
                        : this.autocompleteSelectedIndex - 1
                this.renderAutocomplete()
                break

            case 'Enter':
                if (this.autocompleteSelectedIndex >= 0) {
                    e.preventDefault()
                    this.selectAutocompleteItem(this.autocompleteSelectedIndex)
                }
                break

            case 'Tab':
                e.preventDefault()
                if (this.autocompleteSelectedIndex >= 0) {
                    this.selectAutocompleteItem(this.autocompleteSelectedIndex)
                } else if (this.autocompleteItems.length > 0) {
                    // Tab with no selection: complete to first match
                    this.selectAutocompleteItem(0)
                }
                break

            case 'Escape':
                e.preventDefault()
                this.hideAutocomplete()
                break
        }
    }

    selectAutocompleteItem(index) {
        const item = this.autocompleteItems[index]
        if (this.autocompleteMode === 'command') {
            this.selectCommand(item.name)
        } else if (this.autocompleteMode === 'file') {
            this.selectFile(item)
        }
    }

    selectFile(file) {
        // Insert @ref at the @ position, replacing what was typed
        const value = this.messageInput.value
        const beforeAt = value.substring(0, this.fileAtPosition)
        const afterCursor = value.substring(this.messageInput.selectionStart)

        // Build the new value with @ref
        const ref = `@${file.ref}`
        this.messageInput.value = beforeAt + ref + ' ' + afterCursor.trimStart()

        // Position cursor after the inserted ref
        const newCursorPos = beforeAt.length + ref.length + 1
        this.messageInput.setSelectionRange(newCursorPos, newCursorPos)

        this.hideAutocomplete()
        this.messageInput.focus()
    }

    showCommandAutocomplete(query) {
        // Rebuild registry if capabilities have loaded
        if (this.sessionCapabilities && this.commandRegistry.length === 6) {
            this.buildCommandRegistry()
        }

        // Filter commands
        this.autocompleteCommands = this.filterCommands(query)
        this.autocompleteItems = this.autocompleteCommands
        this.autocompleteMode = 'command'

        if (this.autocompleteItems.length === 0) {
            this.hideAutocomplete()
            return
        }

        // Reset selection
        this.autocompleteSelectedIndex = -1

        // Position panel above input
        this.positionAutocompletePanel()

        // Render and show
        this.renderAutocomplete()
        this.autocompletePanel.classList.remove('hidden')
        this.autocompleteVisible = true
    }

    showFileAutocomplete(query, atPosition) {
        // Store @ position for insertion
        this.fileAtPosition = atPosition

        // Filter files from current session
        this.autocompleteItems = this.filterFiles(query)
        this.autocompleteMode = 'file'

        if (this.autocompleteItems.length === 0) {
            this.hideAutocomplete()
            return
        }

        // Reset selection
        this.autocompleteSelectedIndex = -1

        // Position panel above input
        this.positionAutocompletePanel()

        // Render and show
        this.renderAutocomplete()
        this.autocompletePanel.classList.remove('hidden')
        this.autocompleteVisible = true
    }

    positionAutocompletePanel() {
        const inputRect = this.messageInput.getBoundingClientRect()
        this.autocompletePanel.style.left = inputRect.left + 'px'
        this.autocompletePanel.style.bottom = (window.innerHeight - inputRect.top + 10) + 'px'
        this.autocompletePanel.style.width = inputRect.width + 'px'
    }

    hideAutocomplete() {
        this.autocompletePanel.classList.add('hidden')
        this.autocompleteVisible = false
        this.autocompleteSelectedIndex = -1
        this.autocompleteCommands = []
        this.autocompleteItems = []
        this.autocompleteMode = null
        this.fileAtPosition = -1
    }

    filterCommands(query) {
        if (!query) {
            return this.commandRegistry
        }

        const lowerQuery = query.toLowerCase()

        // Filter using prefix and substring matching
        return this.commandRegistry.filter(cmd => {
            const cmdName = cmd.name.toLowerCase().substring(1) // Remove leading "/"
            const cmdDesc = cmd.description.toLowerCase()

            // Prefix match (higher priority)
            if (cmdName.startsWith(lowerQuery)) {
                return true
            }

            // Substring match in name or description
            return cmdName.includes(lowerQuery) || cmdDesc.includes(lowerQuery)
        })
    }

    filterFiles(query) {
        // Return files from sessionFiles that match query
        if (!this.sessionFiles || this.sessionFiles.length === 0) {
            return []
        }

        if (!query) {
            return this.sessionFiles
        }

        const lowerQuery = query.toLowerCase()

        // Filter by ref name (without @)
        return this.sessionFiles.filter(file => {
            const ref = (file.ref || '').toLowerCase()
            return ref.startsWith(lowerQuery) || ref.includes(lowerQuery)
        })
    }

    renderAutocomplete() {
        let html = ''

        if (this.autocompleteMode === 'command') {
            html = this.autocompleteItems.map((cmd, index) => {
                const isSelected = index === this.autocompleteSelectedIndex
                const icon = cmd.type === 'builtin' ? '🔧' : '💻'

                return `
                    <div class="autocomplete-item ${isSelected ? 'selected' : ''}"
                         data-index="${index}">
                        <span class="autocomplete-icon">${icon}</span>
                        <div class="autocomplete-content">
                            <div class="autocomplete-name">${this.escapeHtml(cmd.name)}</div>
                            ${cmd.description ? `<div class="autocomplete-desc">${this.escapeHtml(cmd.description)}</div>` : ''}
                        </div>
                    </div>
                `
            }).join('')
        } else if (this.autocompleteMode === 'file') {
            html = this.autocompleteItems.map((file, index) => {
                const isSelected = index === this.autocompleteSelectedIndex
                const icon = this.getFileIcon(file.file_type || file.type)

                return `
                    <div class="autocomplete-item ${isSelected ? 'selected' : ''}"
                         data-index="${index}">
                        <span class="autocomplete-icon">${icon}</span>
                        <div class="autocomplete-content">
                            <div class="autocomplete-name">@${this.escapeHtml(file.ref)}</div>
                            <div class="autocomplete-desc">${this.escapeHtml(file.size_human || this.formatFileSize(file.size))}</div>
                        </div>
                    </div>
                `
            }).join('')
        }

        this.autocompletePanel.innerHTML = html

        // Add click handlers
        this.autocompletePanel.querySelectorAll('.autocomplete-item').forEach((item, index) => {
            item.addEventListener('click', () => {
                this.selectAutocompleteItem(index)
            })
        })

        // Scroll selected into view
        if (this.autocompleteSelectedIndex >= 0) {
            const selected = this.autocompletePanel.children[this.autocompleteSelectedIndex]
            if (selected) {
                selected.scrollIntoView({ block: 'nearest' })
            }
        }
    }

    getFileIcon(fileType) {
        const icons = {
            'image': '🖼️',
            'document': '📄',
            'pdf': '📑',
            'spreadsheet': '📊',
            'text': '📝',
            'code': '💻',
            'archive': '📦',
            'audio': '🎵',
            'video': '🎬'
        }
        return icons[fileType] || '📎'
    }

    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B'
        const units = ['B', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(1024))
        return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
    }

    // ========== @Reference Parsing ==========

    extractFileReferences(text) {
        // Extract @filename references from text
        // Matches @word where word contains alphanumeric, underscore, dot, hyphen
        const pattern = /@([\w.\-]+)/g
        const matches = []
        let match

        while ((match = pattern.exec(text)) !== null) {
            matches.push({
                ref: match[1],
                fullMatch: match[0],
                index: match.index
            })
        }

        return matches
    }

    validateFileReferences(text) {
        // Extract @references and check if they exist in session files
        const refs = this.extractFileReferences(text)
        const validRefs = []
        const invalidRefs = []

        for (const ref of refs) {
            const file = this.sessionFiles.find(f => f.ref === ref.ref)
            if (file) {
                validRefs.push({ ...ref, file })
            } else {
                invalidRefs.push(ref)
            }
        }

        return { validRefs, invalidRefs }
    }

    highlightFileReferences(text) {
        // Return text with @references wrapped in spans for styling
        // Used for display in chat messages
        if (!this.sessionFiles || this.sessionFiles.length === 0) {
            return this.escapeHtml(text)
        }

        let result = this.escapeHtml(text)
        const refs = this.extractFileReferences(text)

        // Sort by index descending to replace from end (avoids index shifting)
        refs.sort((a, b) => b.index - a.index)

        for (const ref of refs) {
            const file = this.sessionFiles.find(f => f.ref === ref.ref)
            const escapedRef = this.escapeHtml(ref.fullMatch)
            const escapedRefEscaped = escapedRef.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

            if (file) {
                // Valid reference - highlight in green
                result = result.replace(
                    new RegExp(escapedRefEscaped),
                    `<span class="file-ref valid" title="${this.escapeHtml(file.path || file.ref)}">${escapedRef}</span>`
                )
            } else {
                // Invalid reference - highlight in red
                result = result.replace(
                    new RegExp(escapedRefEscaped),
                    `<span class="file-ref invalid" title="File not found">${escapedRef}</span>`
                )
            }
        }

        return result
    }

    selectCommand(commandName) {
        this.messageInput.value = commandName
        this.hideAutocomplete()
        this.messageInput.focus()
    }

    // ========== WebSocket Connection ==========

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        let wsUrl = `${protocol}//${window.location.host}/ws`

        // Append session_id query parameter if resuming session
        if (this.sessionId) {
            wsUrl += `?session_id=${encodeURIComponent(this.sessionId)}`
            console.log(`🔄 Resuming session: ${this.sessionId}`)
        }

        console.log('🔌 Connecting to WebSocket:', wsUrl)
        this.updateConnectionStatus('connecting')

        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
            console.log('✅ WebSocket connected')
            console.log('🔷 [FRONTEND] WebSocket connection established, waiting for messages...')
            this.isConnected = true
            this.reconnectAttempts = 0
            this.updateConnectionStatus('connected')

            // Show loading while SDK initializes
            this.showServerStatus('🔌 Initializing Claude Agent SDK...')
        }

        this.ws.onclose = () => {
            console.log('❌ WebSocket disconnected')
            this.isConnected = false

            // Don't update status or reconnect if this was intentional (session switch)
            if (this.isIntentionalDisconnect) {
                console.log('🔄 Intentional disconnect (session switch) - not reconnecting')
                this.isIntentionalDisconnect = false
                return
            }

            this.updateConnectionStatus('disconnected')

            // Auto-reconnect with exponential backoff
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000)
                this.reconnectAttempts++
                console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
                setTimeout(() => this.connect(), delay)
            }
        }

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error)
            this.updateConnectionStatus('error')
        }

        this.ws.onmessage = (event) => {
            console.log('🔷 [FRONTEND] Received raw WebSocket message:', event.data)
            try {
                const data = JSON.parse(event.data)
                console.log('🔷 [FRONTEND] Parsed message:', data)
                this.handleMessage(data)
            } catch (e) {
                console.error('❌ [FRONTEND] Failed to parse message:', e)
                console.error('❌ [FRONTEND] Raw data:', event.data)
            }
        }
    }

    updateConnectionStatus(status) {
        if (!this.connectionStatus) return

        const statusConfig = {
            connecting: { text: 'Connecting...', class: 'status-connecting', icon: '🔄' },
            connected: { text: 'Connected', class: 'status-connected', icon: '✅' },
            disconnected: { text: 'Disconnected', class: 'status-disconnected', icon: '❌' },
            error: { text: 'Error', class: 'status-error', icon: '⚠️' }
        }

        const config = statusConfig[status] || statusConfig.disconnected

        this.connectionStatus.textContent = `${config.icon} ${config.text}`
        this.connectionStatus.className = `connection-status ${config.class}`

        // Enable/disable input
        this.sendButton.disabled = status !== 'connected'
        this.messageInput.disabled = status !== 'connected'
    }

    // ========== Server Status Indicator ==========

    showServerStatus(message) {
        console.log('🔷 [FRONTEND] Showing status:', message)
        if (this.serverStatus && this.statusText) {
            this.statusText.textContent = message
            this.serverStatus.style.display = 'flex'
        }
    }

    hideServerStatus() {
        console.log('🔷 [FRONTEND] Hiding status')
        if (this.serverStatus) {
            this.serverStatus.style.display = 'none'
        }
    }

    // ========== Message Sending ==========

    sendMessage() {
        const content = this.messageInput.value.trim()
        if (!content || !this.isConnected) return

        const lowerContent = content.toLowerCase()

        // Intercept meta-commands (handle locally, don't send to server)
        if (lowerContent === '/help') {
            this.addUserMessage(content)
            this.showDynamicHelp()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/agents') {
            this.addUserMessage(content)
            this.showAgents()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/skills') {
            this.addUserMessage(content)
            this.showSkills()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/commands') {
            this.addUserMessage(content)
            this.showCommands()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/tools') {
            this.addUserMessage(content)
            this.showTools()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/clear') {
            this.addUserMessage(content)
            this.clearConversation()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        if (lowerContent === '/permissions') {
            this.addUserMessage(content)
            this.showPermissions()
            this.messageInput.value = ''
            this.messageInput.style.height = 'auto'
            return
        }

        // Determine message type based on agent state
        const messageType = this.isAgentWorking ? 'hint' : 'user_message'

        // Build content blocks (multimodal support)
        const contentBlocks = []

        // Add text if present
        if (content) {
            contentBlocks.push({
                type: 'text',
                text: content
            })
        }


        // Process @references in message - add images/PDFs as content blocks
        // Text files are handled via system context (Claude uses Read tool)
        const { validRefs } = this.validateFileReferences(content)
        for (const ref of validRefs) {
            const file = ref.file
            if (file.file_type === 'image' && file.data) {
                // Image with base64 data
                contentBlocks.push({
                    type: 'image',
                    source: {
                        type: 'base64',
                        media_type: file.mime_type || 'image/png',
                        data: file.data
                    }
                })
            } else if (file.file_type === 'pdf' && file.data) {
                // PDF as document block with base64 data
                contentBlocks.push({
                    type: 'document',
                    source: {
                        type: 'base64',
                        media_type: 'application/pdf',
                        data: file.data
                    }
                })
            }
            // Text files: Claude uses Read tool via path in system context
        }

        // Must have at least text, image, or file
        if (contentBlocks.length === 0) {
            return
        }

        // Prepare message content (backward compatible)
        // If only text, send as string for backward compatibility
        // If multimodal (text+image or image-only), send as content blocks array
        const messageContent = contentBlocks.length === 1 && contentBlocks[0].type === 'text'
            ? content  // Simple text-only (backward compatible)
            : contentBlocks  // Multimodal content blocks

        // Add to UI with appropriate styling
        if (messageType === 'hint') {
            this.addHintMessage(content)
            // Reset currentMessage so agent's continuation appears BELOW hint
            this.currentMessage = null
            this.blocks.clear()
            this.textBuffers.clear()
        } else {
            // Display user message with @referenced files
            const referencedFiles = validRefs.map(r => r.file)
            this.addUserMessageWithImages(content, [], referencedFiles)
            // Reset currentMessage for new conversation
            this.currentMessage = null
            this.blocks.clear()
            this.textBuffers.clear()
        }

        // Send to server
        this.ws.send(JSON.stringify({
            type: messageType,
            content: messageContent
        }))

        console.log(`📤 Sent ${messageType}:`, contentBlocks.length === 1 ? 'text-only' : `${contentBlocks.length} blocks`)

        // Close sidebars when starting chat
        this.closeSessionSidebar()
        this.closeFileSidebar()

        // Clear input and reset height
        this.messageInput.value = ''
        this.messageInput.style.height = 'auto'

        // If this was a regular message, set agent working
        if (messageType === 'user_message') {
            this.setAgentWorking(true)
        }
        // If it was a hint, agent is already working - keep working state
    }

    stopAgent() {
        console.log('🛑 Stopping agent...')

        // Send interrupt to server
        this.ws.send(JSON.stringify({
            type: 'interrupt'
        }))

        // Update UI immediately
        this.setAgentWorking(false)
    }

    handlePaste(e) {
        const items = e.clipboardData?.items
        if (!items) return

        // Look for images in clipboard
        let foundImage = false
        for (let item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault()
                foundImage = true

                const file = item.getAsFile()
                if (file) {
                    this.addImageToMessage(file)
                }
            }
        }

        // If no image, let default paste behavior handle text
        if (foundImage) {
            console.log('📷 Image pasted from clipboard')
        }
    }

    async addImageToMessage(file) {
        // Validate size (5MB limit)
        if (file.size > 5 * 1024 * 1024) {
            alert('Image too large. Maximum size is 5MB per image.')
            return
        }

        // Upload to server first
        const uploadResult = await this.uploadFile(file)
        if (!uploadResult) return

        // File chips are updated automatically by loadSessionFiles() in uploadFile()
    }


    // === Drag & Drop Handlers ===

    setupDragAndDrop() {
        const dropZone = document.body

        dropZone.addEventListener('dragenter', (e) => this.handleDragEnter(e))
        dropZone.addEventListener('dragover', (e) => this.handleDragOver(e))
        dropZone.addEventListener('dragleave', (e) => this.handleDragLeave(e))
        dropZone.addEventListener('drop', (e) => this.handleDrop(e))
    }

    handleDragEnter(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter++

        if (this.dragCounter === 1) {
            // Show drop overlay
            this.showDropOverlay()
        }
    }

    handleDragOver(e) {
        e.preventDefault()
        e.stopPropagation()
    }

    handleDragLeave(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter--

        if (this.dragCounter === 0) {
            // Hide drop overlay
            this.hideDropOverlay()
        }
    }

    async handleDrop(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter = 0
        this.hideDropOverlay()

        const files = e.dataTransfer?.files
        if (!files || files.length === 0) return

        console.log(`📁 ${files.length} file(s) dropped`)

        // Process each file
        for (const file of files) {
            await this.processDroppedFile(file)
        }
    }

    showDropOverlay() {
        let overlay = document.getElementById('drop-overlay')
        if (!overlay) {
            overlay = document.createElement('div')
            overlay.id = 'drop-overlay'
            overlay.className = 'drop-overlay'
            overlay.innerHTML = `
                <div class="drop-overlay-content">
                    <div class="drop-overlay-icon">📁</div>
                    <div class="drop-overlay-text">Drop files here</div>
                    <div class="drop-overlay-hint">Images, PDFs, and Documents</div>
                </div>
            `
            document.body.appendChild(overlay)
        }
        overlay.style.display = 'flex'
    }

    hideDropOverlay() {
        const overlay = document.getElementById('drop-overlay')
        if (overlay) {
            overlay.style.display = 'none'
        }
    }

    async processDroppedFile(file) {
        console.log(`📄 Processing: ${file.name} (${file.type}, ${(file.size / 1024).toFixed(1)} KB)`)

        const fileType = this.getFileType(file)

        if (fileType === 'image') {
            // Handle images (small, base64 inline)
            await this.addImageToMessage(file)
        } else if (fileType === 'pdf') {
            // Handle PDFs (upload to server, then base64 encode)
            await this.addPDFToMessage(file)
        } else if (fileType === 'document') {
            // Handle other documents (upload to server, file reference)
            await this.addDocumentToMessage(file)
        } else {
            alert(`Unsupported file type: ${file.type || 'unknown'}`)
        }
    }

    getFileType(file) {
        const type = file.type.toLowerCase()
        const name = file.name.toLowerCase()

        // Images
        if (type.startsWith('image/')) {
            if (['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'].includes(type)) {
                return 'image'
            }
        }

        // PDFs
        if (type === 'application/pdf' || name.endsWith('.pdf')) {
            return 'pdf'
        }

        // Documents
        const docExtensions = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.md']
        if (docExtensions.some(ext => name.endsWith(ext))) {
            return 'document'
        }

        return 'unknown'
    }

    async addPDFToMessage(file) {
        // Validate size (32MB limit for PDFs)
        if (file.size > 32 * 1024 * 1024) {
            alert('PDF too large. Maximum size is 32MB.')
            return
        }

        // Upload to server first
        const uploadResult = await this.uploadFile(file)
        if (!uploadResult) return

        // File chips are updated automatically by loadSessionFiles() in uploadFile()
    }

    async addDocumentToMessage(file) {
        // Validate size (100MB limit for documents)
        if (file.size > 100 * 1024 * 1024) {
            alert('Document too large. Maximum size is 100MB.')
            return
        }

        // Upload to server
        const uploadResult = await this.uploadFile(file)
        if (!uploadResult) return

        // File chips are updated automatically by loadSessionFiles() in uploadFile()
    }

    async handleFileSelect(event) {
        /**
         * Handle file selection from file input button.
         */
        const files = event.target.files
        if (!files || files.length === 0) return

        console.log(`📁 ${files.length} file(s) selected via button`)

        // If session isn't ready yet, queue files for later processing
        if (!this.sessionId) {
            console.log('⏳ Session not ready, queueing files...')
            for (const file of files) {
                this.pendingFiles.push(file)
            }
            event.target.value = ''
            return
        }

        // Process each file (upload + add to staging)
        for (const file of files) {
            await this.processDroppedFile(file)
        }

        // Clear file input so same file can be selected again
        event.target.value = ''
    }

    async uploadFile(file) {
        try {
            // Validate session ID is available
            if (!this.sessionId) {
                throw new Error('Session not initialized. Please wait for connection.')
            }

            const formData = new FormData()
            formData.append('file', file)
            formData.append('session_id', this.sessionId)

            console.log(`📤 Uploading file to session ${this.sessionId.substring(0, 8)}...`)

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                throw new Error(errorData.error || `Upload failed: ${response.statusText}`)
            }

            const result = await response.json()
            console.log(`✅ File uploaded: ${result.path}`)

            // Reload session files to update the file list
            await this.loadSessionFiles()

            return result

        } catch (error) {
            console.error('File upload failed:', error)
            alert(`Failed to upload file: ${error.message}`)
            return null
        }
    }

    // ========== File Area Management (New Staging System) ==========

    getFileIcon(filename) {
        /**
         * Get emoji icon for file type based on extension.
         *
         * Args:
         *     filename: Name of the file
         *
         * Returns:
         *     String emoji icon
         */
        const ext = filename.toLowerCase().split('.').pop()

        const iconMap = {
            // Images
            'png': '🖼️',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'gif': '🖼️',
            'webp': '🖼️',
            'svg': '🖼️',

            // Documents
            'pdf': '📄',
            'doc': '📝',
            'docx': '📝',
            'txt': '📝',
            'md': '📝',

            // Spreadsheets
            'xls': '📊',
            'xlsx': '📊',
            'csv': '📊',

            // Presentations
            'ppt': '📽️',
            'pptx': '📽️',

            // Archives
            'zip': '📦',
            'tar': '📦',
            'gz': '📦',
            '7z': '📦',

            // Code
            'py': '🐍',
            'js': '📜',
            'ts': '📜',
            'html': '🌐',
            'css': '🎨',
            'json': '📋',
            'yaml': '📋',
            'yml': '📋'
        }

        return iconMap[ext] || '📎'
    }

    formatFileSize(bytes) {
        /**
         * Format file size in human-readable format.
         *
         * Args:
         *     bytes: File size in bytes
         *
         * Returns:
         *     Formatted string (e.g., "1.5 MB")
         */
        if (bytes === 0) return '0 Bytes'

        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))

        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
    }


    // ========== File Staging Area (New Design) ==========

    getFileIcon(filename) {
        /**
         * Get appropriate emoji icon for file type.
         */
        const ext = filename.toLowerCase().split('.').pop()

        // Images
        if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) {
            return '🖼️'
        }
        // PDFs
        if (ext === 'pdf') {
            return '📕'
        }
        // Documents
        if (['doc', 'docx'].includes(ext)) {
            return '📘'
        }
        // Spreadsheets
        if (['xls', 'xlsx', 'csv'].includes(ext)) {
            return '📗'
        }
        // Presentations
        if (['ppt', 'pptx'].includes(ext)) {
            return '📙'
        }
        // Text files
        if (['txt', 'md', 'log'].includes(ext)) {
            return '📝'
        }
        // Code files
        if (['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'cpp', 'c', 'h', 'css', 'html', 'json', 'xml', 'yaml', 'yml'].includes(ext)) {
            return '💻'
        }
        // Archives
        if (['zip', 'tar', 'gz', 'rar', '7z'].includes(ext)) {
            return '📦'
        }
        // Default
        return '📄'
    }

    fileToDataUrl(file) {
        /**
         * Convert a File object to a data URL for preview.
         */
        return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = reject
            reader.readAsDataURL(file)
        })
    }

    showPreviewTooltip(file, chipElement) {
        /**
         * Show a preview tooltip when hovering over a file chip (Claude.ai style).
         */
        // Remove existing tooltip
        this.hidePreviewTooltip()

        const tooltip = document.createElement('div')
        tooltip.className = 'file-preview-tooltip'
        tooltip.id = 'file-preview-tooltip'

        // Add preview image for image files
        if (file.type === 'image' && file.data) {
            // Reconstruct data URL from base64 data
            const dataUrl = `data:${file.media_type};base64,${file.data}`
            const previewImg = document.createElement('img')
            previewImg.src = dataUrl
            previewImg.alt = file.filename
            tooltip.appendChild(previewImg)
        } else {
            // Show file icon for non-images
            const iconDiv = document.createElement('div')
            iconDiv.className = 'tooltip-file-icon'
            iconDiv.textContent = this.getFileIcon(file.filename)
            tooltip.appendChild(iconDiv)
        }

        // Add filename and size info
        const infoDiv = document.createElement('div')
        infoDiv.className = 'tooltip-file-info'
        infoDiv.textContent = `${file.filename} (${this.formatFileSize(file.size)})`
        tooltip.appendChild(infoDiv)

        // Position tooltip above the chip
        document.body.appendChild(tooltip)
        const chipRect = chipElement.getBoundingClientRect()
        const tooltipRect = tooltip.getBoundingClientRect()

        // Center horizontally above chip
        const left = chipRect.left + (chipRect.width / 2) - (tooltipRect.width / 2)
        const top = chipRect.top - tooltipRect.height - 8  // 8px gap

        tooltip.style.left = Math.max(10, left) + 'px'  // Keep on screen
        tooltip.style.top = Math.max(10, top) + 'px'

        this.currentTooltip = tooltip
    }

    hidePreviewTooltip() {
        /**
         * Hide the file preview tooltip.
         */
        if (this.currentTooltip) {
            this.currentTooltip.remove()
            this.currentTooltip = null
        }
    }

    setAgentWorking(working) {
        this.isAgentWorking = working

        if (working) {
            // Agent is working - show stop button, keep everything else simple
            this.messageInput.disabled = false  // Keep input enabled

            // Show stop button
            this.stopButton.style.display = 'inline-block'

            // Keep send button enabled for hints
            this.sendButton.disabled = false

            // Show status indicator
            this.showServerStatus('🤖 Claude is thinking...')
        } else {
            // Agent is idle - hide stop button
            this.messageInput.disabled = false

            // Hide stop button
            this.stopButton.style.display = 'none'

            // 🔧 BUG FIX: NEVER disable send button when agent is idle
            // The button should always be enabled when connected
            // Input validation happens in sendMessage() method
            this.sendButton.disabled = false

            // Hide status indicator
            this.hideServerStatus()
        }
    }

    addUserMessage(content) {
        const messageEl = document.createElement('div')
        messageEl.className = 'user-message message-fade-in'
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="user-icon">👤</span>
                <span class="user-name">You</span>
            </div>
            <div class="message-content">${this.highlightFileReferences(content)}</div>
        `
        this.conversationEl.appendChild(messageEl)

        // Force scroll after user message with delay for DOM rendering
        // Wait for fade-in animation (300ms) + extra buffer (50ms)
        console.log('💬 [USER] User message appended, scheduling scroll in 350ms...')
        setTimeout(() => {
            console.log('⏰ [USER] 350ms timeout fired, calling forceScrollToBottom...')
            this.forceScrollToBottom()
        }, 350)
    }

    addUserMessageWithImages(content, images, files = []) {
        const messageEl = document.createElement('div')
        messageEl.className = 'user-message message-fade-in'

        // Build message HTML
        let messageHtml = `
            <div class="message-header">
                <span class="user-icon">👤</span>
                <span class="user-name">You</span>
            </div>
        `

        // Add text content if present (with @reference highlighting)
        if (content) {
            messageHtml += `<div class="message-content">${this.highlightFileReferences(content)}</div>`
        }

        // Add images if present
        if (images && images.length > 0) {
            messageHtml += '<div class="message-images">'
            for (const img of images) {
                messageHtml += `
                    <img src="data:${img.media_type};base64,${img.data}"
                         alt="${img.filename}"
                         class="message-image"
                         title="${img.filename} (${(img.size / 1024).toFixed(1)} KB)">
                `
            }
            messageHtml += '</div>'
        }

        // NOTE: Files are NOT displayed in the message bubble
        // They only appear as chips in the input wrapper before sending
        // This prevents files from "flowing up" into the conversation history
        // Files are still attached to the message and sent to Claude

        messageEl.innerHTML = messageHtml
        this.conversationEl.appendChild(messageEl)

        // Force scroll after user message with delay for DOM rendering
        // Wait for fade-in animation (300ms) + extra buffer (50ms)
        setTimeout(() => this.forceScrollToBottom(), 350)
    }

    addHintMessage(content) {
        const hintMsg = document.createElement('div')
        hintMsg.className = 'message hint-message message-fade-in'
        hintMsg.innerHTML = `
            <div class="message-header">
                <span class="hint-icon">💡</span>
                <span class="hint-label">HINT</span>
            </div>
            <div class="message-content">${this.highlightFileReferences(content)}</div>
        `
        this.conversationEl.appendChild(hintMsg)

        // Delay scroll for DOM rendering
        // Wait for fade-in animation (300ms) + extra buffer (50ms)
        setTimeout(() => this.forceScrollToBottom(), 350)
    }

    addSystemMessage(message, temporary = false) {
        // PHASE 2: Helper for system/loading messages
        const messageEl = document.createElement('div')
        messageEl.className = 'system-message message-fade-in'
        if (temporary) {
            messageEl.dataset.temporary = 'true'
        }
        messageEl.innerHTML = `
            <div class="system-header">
                <span class="system-icon">ℹ️</span>
                <span class="system-title">System</span>
            </div>
            <div class="system-content">${this.escapeHtml(message)}</div>
        `
        this.conversationEl.appendChild(messageEl)

        // Delay scroll for DOM rendering
        // Wait for fade-in animation (300ms) + extra buffer (50ms)
        setTimeout(() => this.forceScrollToBottom(), 350)
        return messageEl
    }

    removeTemporaryMessages() {
        // PHASE 2: Remove temporary loading messages
        const tempMessages = this.conversationEl.querySelectorAll('[data-temporary="true"]')
        tempMessages.forEach(msg => msg.remove())
    }

    handleUserMessageEcho(msg) {
        // Server echoing user's message - check if we already showed it
        // This is for conversation history replay or multi-client sync
        const lastMessage = this.conversationEl.lastElementChild

        // If the last message is already a user message with same content, skip
        if (lastMessage &&
            lastMessage.classList.contains('user-message') &&
            lastMessage.querySelector('.message-content')?.textContent === msg.content) {
            console.log('User message already shown, skipping echo')
            return
        }

        // Otherwise add it (for history replay scenarios)
        this.addUserMessage(msg.content)
    }

    // ========== Message Handling (Core) ==========

    async handleMessage(msg) {
        console.log('📨 Received:', msg.type, msg.id || '', msg)
        console.log('🔷 [FRONTEND] Handling message type:', msg.type)

        switch (msg.type) {
            case 'connected':
                // NOTE: Backend sends both chat_id (new) and session_id (backward compat)
                // We use session_id for now, can migrate to chat_id later
                const chatId = msg.chat_id || msg.session_id
                console.log('🔷 [FRONTEND] Got "connected" event, Chat ID:', chatId)

                // Store session ID for file uploads and session management
                // (internally this is now the chat_id, but we keep the variable name)
                this.sessionId = chatId
                console.log('✅ [FRONTEND] Chat ID stored:', this.sessionId)

                // Load any existing session files (for resumed sessions)
                this.loadSessionFiles()

                // Refresh session list to include this new session
                this.loadSessions()

                // Only clear and show welcome if conversation is empty
                // (If switching sessions, conversation already has loaded history)
                const hasMessages = this.conversationEl.children.length > 0
                if (!hasMessages) {
                    console.log('🔷 [FRONTEND] New session - showing welcome message')
                    this.conversationEl.innerHTML = ''
                    this.showWelcomeMessage()
                } else {
                    console.log(`🔷 [FRONTEND] Session has ${this.conversationEl.children.length} messages - keeping history`)
                }

                // Hide loading status - agent is ready
                this.hideServerStatus()

                // Process any files that were queued while waiting for session ID
                if (this.pendingFiles.length > 0) {
                    console.log(`🔄 Processing ${this.pendingFiles.length} queued file(s)...`)
                    const filesToProcess = [...this.pendingFiles]
                    this.pendingFiles = []
                    for (const file of filesToProcess) {
                        await this.processDroppedFile(file)
                    }
                }
                break

            case 'user_message_echo':
                // Server echoing user's message for history/replay
                // Only add if not already present (avoid duplication)
                this.handleUserMessageEcho(msg)
                break

            case 'text_delta':
                this.handleTextDelta(msg)
                break

            case 'tool_start':
                this.handleToolStart(msg)
                break

            case 'tool_end':
                this.handleToolEnd(msg)
                break

            case 'thinking':
                this.handleThinking(msg)
                break

            case 'message_complete':
                this.handleMessageComplete(msg)
                break

            case 'usage':
                this.handleUsage(msg)
                break

            case 'interrupted':
                this.handleInterrupted(msg)
                break

            case 'status':
                // Show server status updates
                if (msg.message) {
                    this.showServerStatus(msg.message)
                }
                this.handleStatus(msg)
                break

            case 'error':
                this.handleError(msg)
                break

            case 'system_message':
            case 'system':
                this.handleSystemMessage(msg)
                break

            case 'assistant_message':
                this.handleAssistantMessage(msg)
                break

            case 'question':
                this.handleQuestion(msg)
                break

            case 'session_renamed':
                // Session was auto-named by LLM
                console.log(`🏷️  Session renamed: ${msg.new_name}`)

                // Reload session list to show new name
                if (this.sessionList) {
                    this.loadSessions()
                }
                break

            case 'permission_request':
                // Agent requesting permission to use a tool
                this.handlePermissionRequest(msg)
                break

            case 'model_changed':
                // Model was changed (e.g., auto-escalation)
                this.handleModelChanged(msg)
                break

            default:
                console.warn('Unknown message type:', msg.type)
        }
    }

    // ========== Welcome Message ==========

    showWelcomeMessage() {
        const welcomeEl = document.createElement('div')
        welcomeEl.className = 'welcome-message message-fade-in'
        welcomeEl.innerHTML = `
            <div class="welcome-container">
                <div class="welcome-hero">
                    <div class="welcome-icon-wrapper">
                        <div class="welcome-icon">🤖</div>
                        <div class="welcome-glow"></div>
                    </div>
                    <h1 class="welcome-title">Bassi</h1>
                    <p class="welcome-tagline">Benno's AI Assistant</p>
                </div>

                <div class="welcome-divider"></div>

                <div class="welcome-content">
                    <p class="welcome-description">
                        Powered by <strong>Claude</strong>, I can do almost everything on your computer, the web and office 365.
                    </p>

                    <div class="welcome-quick-start">
                        <div class="quick-start-item">
                            <span class="qs-icon">💬</span>
                            <span class="qs-text">Ask me anything</span>
                        </div>
                        <div class="quick-start-item">
                            <span class="qs-icon">📝</span>
                            <span class="qs-text">Type <code>/help</code> for capabilities</span>
                        </div>
                        <div class="quick-start-item">
                            <span class="qs-icon">⚙️</span>
                            <span class="qs-text">Driven by MCP servers</span>
                        </div>
                    </div>
                </div>
            </div>
        `
        this.conversationEl.appendChild(welcomeEl)

        // Use setTimeout to ensure DOM is rendered before scrolling
        // Wait for fade-in animation (300ms) + extra buffer (50ms)
        console.log('💬 [WELCOME] Welcome message appended, scheduling scroll in 350ms...')
        setTimeout(() => {
            console.log('⏰ [WELCOME] 350ms timeout fired, calling forceScrollToBottom...')
            this.forceScrollToBottom()
        }, 350)
    }

    async loadCapabilities() {
        /**
         * Fetch session capabilities via REST API.
         *
         * Capabilities are lazily loaded on first /help command
         * and cached in memory for subsequent requests.
         */
        console.log('📡 Fetching capabilities from /api/capabilities...')

        try {
            const response = await fetch('/api/capabilities')

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`)
            }

            this.sessionCapabilities = await response.json()

            // Make globally accessible for debugging
            window.bassiCapabilities = this.sessionCapabilities

            console.log('✅ Capabilities loaded:', {
                tools: this.sessionCapabilities.tools?.length,
                mcp_servers: this.sessionCapabilities.mcp_servers?.length,
                slash_commands: this.sessionCapabilities.slash_commands?.length,
                skills: this.sessionCapabilities.skills?.length,
                agents: this.sessionCapabilities.agents?.length
            })
        } catch (error) {
            console.error('❌ Failed to load capabilities:', error)
            this.sessionCapabilities = null
        }
    }

    async showDynamicHelp() {
        // Lazy load capabilities if not already loaded
        if (!this.sessionCapabilities) {
            await this.loadCapabilities()
        }

        if (!this.sessionCapabilities) {
            // Still not loaded after fetch - show error
            const helpEl = document.createElement('div')
            helpEl.className = 'assistant-message message-fade-in'
            helpEl.innerHTML = `
                <div class="message-header">
                    <span class="assistant-icon">🤖</span>
                    <span class="assistant-name">Bassi</span>
                </div>
                <div class="message-content">
                    <div class="text-block">
                        <p>Could not load session capabilities. Please check the server connection.</p>
                    </div>
                </div>
            `
            this.conversationEl.appendChild(helpEl)
            this.scrollToBottom()
            return
        }

        const caps = this.sessionCapabilities

        // Safely extract arrays with defaults
        const tools = caps.tools || []
        const mcpServers = caps.mcp_servers || []
        const slashCommands = caps.slash_commands || []
        const skills = caps.skills || []
        const agents = caps.agents || []

        // Group tools by category
        const mcpTools = tools.filter(t => t.startsWith('mcp__'))
        const builtinTools = tools.filter(t => !t.startsWith('mcp__'))

        // Group MCP tools by server
        const toolsByServer = {}
        mcpTools.forEach(tool => {
            // Format: mcp__servername__toolname
            const parts = tool.split('__')
            if (parts.length >= 3) {
                const serverName = parts[1]
                const toolName = parts.slice(2).join('__')
                if (!toolsByServer[serverName]) {
                    toolsByServer[serverName] = []
                }
                toolsByServer[serverName].push(toolName)
            }
        })

        const helpHTML = `
            <div class="message-header">
                <span class="assistant-icon">📚</span>
                <span class="assistant-name">Help</span>
            </div>
            <div class="message-content">
                <div class="help-content">
                    <h2>Bassi V3 - Available Capabilities</h2>

                    <div class="help-section">
                        <h3>📡 MCP Servers (${mcpServers.length})</h3>
                        <div class="capability-list">
                            ${mcpServers.map(s => {
                                const serverTools = toolsByServer[s.name] || []
                                const toolsHTML = serverTools.length > 0 ? `
                                    <details class="server-tools-collapse">
                                        <summary>Click to view ${serverTools.length} tools</summary>
                                        <div class="tools-grid">
                                            ${serverTools.map(t => `
                                                <code class="tool-tag clickable"
                                                      data-tool="${t}"
                                                      data-server="${s.name}"
                                                      title="Click for details">
                                                    ${t}
                                                </code>
                                            `).join('')}
                                        </div>
                                    </details>
                                ` : '<p class="no-tools">No tools available</p>'

                                return `
                                    <div class="capability-item server-item">
                                        <div class="server-header">
                                            <span class="cap-badge ${s.status}">${s.status}</span>
                                            <strong>${s.name}</strong>
                                        </div>
                                        ${toolsHTML}
                                    </div>
                                `
                            }).join('')}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>🛠️ Built-in Tools (${builtinTools.length})</h3>
                        <div class="tools-grid">
                            ${builtinTools.slice(0, 20).map(t => `<code class="tool-tag">${t}</code>`).join('')}
                            ${builtinTools.length > 20 ? `<span class="tool-more">...and ${builtinTools.length - 20} more</span>` : ''}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>💻 Slash Commands (${slashCommands.length})</h3>
                        <div class="commands-list">
                            ${slashCommands.map(c => {
                                let cmdName = typeof c === 'string' ? c : c.name
                                // Remove leading slash if present (avoid //)
                                if (cmdName.startsWith('/')) {
                                    cmdName = cmdName.substring(1)
                                }
                                return `<code class="command-tag clickable"
                                             data-command="${cmdName}"
                                             title="Click for details">/${cmdName}</code>`
                            }).join(' ')}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>🎯 Skills (${skills.length})</h3>
                        <div class="skills-list">
                            ${skills.map(s => {
                                const skillName = typeof s === 'string' ? s : s.name || s
                                return `<span class="skill-badge clickable"
                                              data-skill="${skillName}"
                                              title="Click for details">${skillName}</span>`
                            }).join(' ')}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>🤖 Agents (${agents.length})</h3>
                        <div class="agents-list">
                            ${agents.map(a => {
                                const agentName = typeof a === 'string' ? a : a.name || a
                                return `<span class="agent-badge clickable"
                                              data-agent="${agentName}"
                                              title="Click for details">${agentName}</span>`
                            }).join(' ')}
                        </div>
                    </div>
                </div>
            </div>
        `

        const helpEl = document.createElement('div')
        helpEl.className = 'assistant-message message-fade-in'
        helpEl.innerHTML = helpHTML
        this.conversationEl.appendChild(helpEl)

        // Add click handlers for clickable elements
        helpEl.querySelectorAll('.tool-tag.clickable').forEach(tag => {
            tag.addEventListener('click', (e) => {
                const tool = e.target.dataset.tool
                const server = e.target.dataset.server
                this.showToolDetails(tool, server)
            })
        })

        helpEl.querySelectorAll('.command-tag.clickable').forEach(tag => {
            tag.addEventListener('click', (e) => {
                const cmd = e.target.dataset.command
                this.showCommandDetails(cmd)
            })
        })

        helpEl.querySelectorAll('.skill-badge.clickable').forEach(tag => {
            tag.addEventListener('click', (e) => {
                const skill = e.target.dataset.skill
                this.showSkillDetails(skill)
            })
        })

        helpEl.querySelectorAll('.agent-badge.clickable').forEach(tag => {
            tag.addEventListener('click', (e) => {
                const agent = e.target.dataset.agent
                this.showAgentDetails(agent)
            })
        })

        this.scrollToBottom()
    }

    async showAgents() {
        // PHASE 2: Show loading indicator
        let loadingMsg = null
        if (!this.sessionCapabilities) {
            loadingMsg = this.addSystemMessage('⏳ Loading agents...', true)
            await this.loadCapabilities()
        }

        if (loadingMsg) {
            this.removeTemporaryMessages()
        }

        if (!this.sessionCapabilities) {
            this.addSystemMessage('Could not load session capabilities.')
            return
        }

        const agents = this.sessionCapabilities.agents || []

        const html = `
            <div class="message-header">
                <span class="assistant-icon">🤖</span>
                <span class="assistant-name">Available Agents</span>
            </div>
            <div class="message-content">
                <div class="help-content">
                    <h2>🤖 Available Agents (${agents.length})</h2>
                    <div class="help-section">
                        <div class="agents-list">
                            ${agents.length > 0 ? agents.map(a => {
                                const agentName = typeof a === 'string' ? a : a.name || a
                                return `<span class="agent-badge">${agentName}</span>`
                            }).join(' ') : '<p>No agents available</p>'}
                        </div>
                    </div>
                </div>
            </div>
        `

        const el = document.createElement('div')
        el.className = 'assistant-message message-fade-in'
        el.innerHTML = html
        this.conversationEl.appendChild(el)
        this.scrollToBottom()
    }

    async showSkills() {
        // PHASE 2: Show loading indicator
        let loadingMsg = null
        if (!this.sessionCapabilities) {
            loadingMsg = this.addSystemMessage('⏳ Loading skills...', true)
            await this.loadCapabilities()
        }

        if (loadingMsg) {
            this.removeTemporaryMessages()
        }

        if (!this.sessionCapabilities) {
            this.addSystemMessage('Could not load session capabilities.')
            return
        }

        const skills = this.sessionCapabilities.skills || []

        const html = `
            <div class="message-header">
                <span class="assistant-icon">🎯</span>
                <span class="assistant-name">Available Skills</span>
            </div>
            <div class="message-content">
                <div class="help-content">
                    <h2>🎯 Available Skills (${skills.length})</h2>
                    <div class="help-section">
                        <div class="skills-list">
                            ${skills.length > 0 ? skills.map(s => {
                                const skillName = typeof s === 'string' ? s : s.name || s
                                return `<span class="skill-badge">${skillName}</span>`
                            }).join(' ') : '<p>No skills available</p>'}
                        </div>
                    </div>
                </div>
            </div>
        `

        const el = document.createElement('div')
        el.className = 'assistant-message message-fade-in'
        el.innerHTML = html
        this.conversationEl.appendChild(el)
        this.scrollToBottom()
    }

    async showCommands() {
        // PHASE 2: Show loading indicator
        let loadingMsg = null
        if (!this.sessionCapabilities) {
            loadingMsg = this.addSystemMessage('⏳ Loading commands...', true)
            await this.loadCapabilities()
        }

        if (loadingMsg) {
            this.removeTemporaryMessages()
        }

        if (!this.sessionCapabilities) {
            this.addSystemMessage('Could not load session capabilities.')
            return
        }

        const slashCommands = this.sessionCapabilities.slash_commands || []
        const builtinCommands = ['/help', '/agents', '/skills', '/commands', '/tools', '/clear']

        const html = `
            <div class="message-header">
                <span class="assistant-icon">💻</span>
                <span class="assistant-name">Available Commands</span>
            </div>
            <div class="message-content">
                <div class="help-content">
                    <h2>💻 Available Commands</h2>

                    <div class="help-section">
                        <h3>Built-in Commands (${builtinCommands.length})</h3>
                        <div class="commands-list">
                            ${builtinCommands.map(c => `<code class="command-tag">${c}</code>`).join(' ')}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>User Commands (${slashCommands.length})</h3>
                        <div class="commands-list">
                            ${slashCommands.length > 0 ? slashCommands.map(c => {
                                let cmdName = typeof c === 'string' ? c : c.name
                                if (cmdName.startsWith('/')) {
                                    cmdName = cmdName.substring(1)
                                }
                                return `<code class="command-tag">/${cmdName}</code>`
                            }).join(' ') : '<p>No user commands available</p>'}
                        </div>
                    </div>
                </div>
            </div>
        `

        const el = document.createElement('div')
        el.className = 'assistant-message message-fade-in'
        el.innerHTML = html
        this.conversationEl.appendChild(el)
        this.scrollToBottom()
    }

    async showTools() {
        // PHASE 2: Show loading indicator
        let loadingMsg = null
        if (!this.sessionCapabilities) {
            loadingMsg = this.addSystemMessage('⏳ Loading tools...', true)
            await this.loadCapabilities()
        }

        if (loadingMsg) {
            this.removeTemporaryMessages()
        }

        if (!this.sessionCapabilities) {
            this.addSystemMessage('Could not load session capabilities.')
            return
        }

        const tools = this.sessionCapabilities.tools || []
        const mcpServers = this.sessionCapabilities.mcp_servers || []

        const mcpTools = tools.filter(t => t.startsWith('mcp__'))
        const builtinTools = tools.filter(t => !t.startsWith('mcp__'))

        // Group MCP tools by server
        const toolsByServer = {}
        mcpTools.forEach(tool => {
            const parts = tool.split('__')
            if (parts.length >= 3) {
                const serverName = parts[1]
                const toolName = parts.slice(2).join('__')
                if (!toolsByServer[serverName]) {
                    toolsByServer[serverName] = []
                }
                toolsByServer[serverName].push(toolName)
            }
        })

        const html = `
            <div class="message-header">
                <span class="assistant-icon">🔌</span>
                <span class="assistant-name">Available Tools</span>
            </div>
            <div class="message-content">
                <div class="help-content">
                    <h2>🔌 Available Tools</h2>

                    <div class="help-section">
                        <h3>🛠️ Built-in Tools (${builtinTools.length})</h3>
                        <div class="tools-grid">
                            ${builtinTools.slice(0, 20).map(t => `<code class="tool-tag">${t}</code>`).join('')}
                            ${builtinTools.length > 20 ? `<span class="tool-more">...and ${builtinTools.length - 20} more</span>` : ''}
                        </div>
                    </div>

                    <div class="help-section">
                        <h3>📡 MCP Servers (${mcpServers.length})</h3>
                        <div class="capability-list">
                            ${mcpServers.map(s => {
                                const serverTools = toolsByServer[s.name] || []
                                const toolsHTML = serverTools.length > 0 ? `
                                    <details class="server-tools-collapse">
                                        <summary>Click to view ${serverTools.length} tools</summary>
                                        <div class="tools-grid">
                                            ${serverTools.map(t => `<code class="tool-tag">${t}</code>`).join('')}
                                        </div>
                                    </details>
                                ` : '<p class="no-tools">No tools available</p>'

                                return `
                                    <div class="capability-item server-item">
                                        <div class="server-header">
                                            <span class="cap-badge ${s.status}">${s.status}</span>
                                            <strong>${s.name}</strong>
                                        </div>
                                        ${toolsHTML}
                                    </div>
                                `
                            }).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `

        const el = document.createElement('div')
        el.className = 'assistant-message message-fade-in'
        el.innerHTML = html
        this.conversationEl.appendChild(el)
        this.scrollToBottom()
    }

    async showPermissions() {
        // Show loading indicator
        const loadingMsg = this.addSystemMessage('⏳ Loading permissions...', true)

        try {
            const response = await fetch('/api/settings/permissions')
            const data = await response.json()

            this.removeTemporaryMessages()

            if (!response.ok) {
                this.addSystemMessage('Could not load permissions.')
                return
            }

            let html

            if (data.global_bypass) {
                // Case 1: Global bypass enabled - no restrictions
                html = `
                    <div class="message-header">
                        <span class="assistant-icon">🔓</span>
                        <span class="assistant-name">Permissions</span>
                    </div>
                    <div class="message-content">
                        <div class="help-content">
                            <h2>🔓 PERMISSIONS: NO RESTRICTIONS</h2>

                            <div class="help-section">
                                <p>Global bypass is <strong>ENABLED</strong> - all tools run without asking.</p>
                                <p style="color: var(--text-secondary); margin-top: 1em;">
                                    To enable permission checks, toggle the "brain" icon in the UI
                                    or disable global bypass in settings.
                                </p>
                            </div>
                        </div>
                    </div>
                `
            } else {
                // Case 2/3: Permission checks active
                const sessionPerms = data.session_permissions || []
                const persistentPerms = data.persistent_permissions || []
                const oneTimePerms = data.one_time_permissions || {}

                const hasAnyPermissions = sessionPerms.length > 0 ||
                                         persistentPerms.length > 0 ||
                                         Object.keys(oneTimePerms).length > 0

                let permissionsHtml

                if (hasAnyPermissions) {
                    // Case 2: Has some permissions
                    let sectionsHtml = ''

                    if (sessionPerms.length > 0) {
                        sectionsHtml += `
                            <div class="help-section">
                                <h3>📍 THIS SESSION ONLY <span style="color: var(--text-secondary); font-weight: normal;">(cleared on disconnect)</span></h3>
                                <div class="tools-grid">
                                    ${sessionPerms.map(t => `<span class="permission-chip"><code class="tool-tag">${t}</code><button class="permission-delete" onclick="window.bassiClient.deletePermission('session', '${t}')" title="Remove this permission">×</button></span>`).join('')}
                                </div>
                            </div>
                        `
                    }

                    if (persistentPerms.length > 0) {
                        sectionsHtml += `
                            <div class="help-section">
                                <h3>💾 ALL SESSIONS <span style="color: var(--text-secondary); font-weight: normal;">(persistent, saved to config)</span></h3>
                                <div class="tools-grid">
                                    ${persistentPerms.map(t => `<span class="permission-chip"><code class="tool-tag">${t}</code><button class="permission-delete" onclick="window.bassiClient.deletePermission('persistent', '${t}')" title="Remove this permission">×</button></span>`).join('')}
                                </div>
                            </div>
                        `
                    }

                    if (Object.keys(oneTimePerms).length > 0) {
                        sectionsHtml += `
                            <div class="help-section">
                                <h3>⏱️ ONE-TIME <span style="color: var(--text-secondary); font-weight: normal;">(pending, will be consumed on next use)</span></h3>
                                <div class="tools-grid">
                                    ${Object.entries(oneTimePerms).map(([t, count]) =>
                                        `<span class="permission-chip"><code class="tool-tag">${t} (${count} use${count > 1 ? 's' : ''} remaining)</code><button class="permission-delete" onclick="window.bassiClient.deletePermission('one_time', '${t}')" title="Remove this permission">×</button></span>`
                                    ).join('')}
                                </div>
                            </div>
                        `
                    }

                    sectionsHtml += `
                        <p style="color: var(--text-secondary); margin-top: 1.5em; font-style: italic;">
                            Any tool NOT listed above will prompt for permission.
                        </p>
                    `

                    permissionsHtml = sectionsHtml
                } else {
                    // Case 3: No specific permissions (clean state)
                    permissionsHtml = `
                        <div class="help-section">
                            <p>No specific tool permissions granted yet.</p>
                            <p>Each tool use will prompt for your approval.</p>

                            <div style="margin-top: 1.5em; padding: 1em; background: var(--bg-secondary); border-radius: 8px;">
                                <strong>Permission options when prompted:</strong>
                                <ul style="margin: 0.5em 0 0 1.5em; padding: 0;">
                                    <li><strong>One-time:</strong> Allow just this invocation</li>
                                    <li><strong>Session:</strong> Allow for this browser session</li>
                                    <li><strong>Persistent:</strong> Allow forever (saved to config)</li>
                                    <li><strong>Global:</strong> Disable all permission checks</li>
                                </ul>
                            </div>
                        </div>
                    `
                }

                html = `
                    <div class="message-header">
                        <span class="assistant-icon">🔐</span>
                        <span class="assistant-name">Permissions</span>
                    </div>
                    <div class="message-content">
                        <div class="help-content">
                            <h2>🔐 PERMISSIONS: ACTIVE</h2>
                            <p style="color: var(--text-secondary); margin-bottom: 1em;">
                                Global bypass: <strong>OFF</strong> (tools require permission)
                            </p>
                            ${permissionsHtml}
                        </div>
                    </div>
                `
            }

            const el = document.createElement('div')
            el.className = 'assistant-message message-fade-in'
            el.innerHTML = html
            this.conversationEl.appendChild(el)
            this.scrollToBottom()
        } catch (error) {
            this.removeTemporaryMessages()
            this.addSystemMessage(`Error loading permissions: ${error.message}`)
        }
    }

    async deletePermission(scope, toolName) {
        try {
            const response = await fetch(
                `/api/settings/permissions/${scope}/${encodeURIComponent(toolName)}`,
                { method: 'DELETE' }
            )
            if (response.ok) {
                // Refresh the permissions display
                this.showPermissions()
            } else {
                const data = await response.json()
                this.addSystemMessage(`Failed to remove permission: ${data.detail || toolName}`)
            }
        } catch (error) {
            this.addSystemMessage(`Error removing permission: ${error.message}`)
        }
    }

    clearConversation() {
        // Show confirmation in UI
        const confirmEl = document.createElement('div')
        confirmEl.className = 'assistant-message message-fade-in'
        confirmEl.innerHTML = `
            <div class="message-header">
                <span class="assistant-icon">🗑️</span>
                <span class="assistant-name">Clear Conversation</span>
            </div>
            <div class="message-content">
                <div class="text-block">
                    <p>Conversation cleared. The chat history has been removed from the UI.</p>
                    <p><em>Note: The backend conversation context is still preserved.</em></p>
                </div>
            </div>
        `

        // Clear the conversation UI
        this.conversationEl.innerHTML = ''
        this.conversationEl.appendChild(confirmEl)

        // Reset state
        this.currentMessage = null
        this.blocks.clear()
        this.textBuffers.clear()

        this.scrollToBottom()
    }

    showToolDetails(toolName, serverName) {
        // Create modal with tool details
        const modal = document.createElement('div')
        modal.className = 'tool-modal-overlay'
        modal.innerHTML = `
            <div class="tool-modal">
                <div class="tool-modal-header">
                    <h3>🔧 ${toolName}</h3>
                    <button class="tool-modal-close">&times;</button>
                </div>
                <div class="tool-modal-body">
                    <p><strong>Server:</strong> ${serverName}</p>
                    <p><strong>Full name:</strong> <code>mcp__${serverName}__${toolName}</code></p>
                    <div class="tool-description">
                        ${this.getToolDescription(toolName, serverName)}
                    </div>
                </div>
            </div>
        `

        this.showModal(modal)
    }

    getToolDescription(toolName, serverName) {
        // Tool descriptions are not provided by the Agent SDK init message.
        // The SDK only sends tool names (strings), not schemas or descriptions.
        //
        // MCP servers DO have tool schemas with descriptions, but we would need to:
        // 1. Query each MCP server via the tools/list RPC method
        // 2. Parse and store the tool schemas
        // 3. Match tools to their schemas by name
        //
        // TODO: Implement MCP server tool schema fetching
        // For now, show a helpful message

        return `
            <p><em>Tool descriptions are not currently available.</em></p>
            <p>This tool is provided by the <strong>${serverName}</strong> MCP server.</p>
            <div style="margin-top: 12px; padding: 12px; background: rgba(255, 193, 7, 0.1); border-left: 3px solid #ffc107; border-radius: 4px;">
                <p style="margin: 0; font-size: 0.9rem;">
                    <strong>Note:</strong> The Claude Agent SDK only provides tool names, not descriptions.
                    Tool schemas with descriptions exist in the MCP server but require additional querying.
                </p>
            </div>
        `
    }

    showCommandDetails(cmdName) {
        // Find command in capabilities
        const caps = this.sessionCapabilities
        if (!caps || !caps.slash_commands) return

        const command = caps.slash_commands.find(c =>
            (typeof c === 'string' ? c : c.name) === cmdName
        )

        const modal = document.createElement('div')
        modal.className = 'tool-modal-overlay'

        let description = '<p><em>No description available</em></p>'
        let argumentHint = ''

        if (command && typeof command === 'object') {
            description = `<p>${command.description || 'No description available'}</p>`
            if (command.argumentHint) {
                argumentHint = `<p><strong>Arguments:</strong> <code>${command.argumentHint}</code></p>`
            }
        }

        modal.innerHTML = `
            <div class="tool-modal">
                <div class="tool-modal-header">
                    <h3>💻 /${cmdName}</h3>
                    <button class="tool-modal-close">&times;</button>
                </div>
                <div class="tool-modal-body">
                    <p><strong>Type:</strong> Slash Command</p>
                    ${argumentHint}
                    <div class="tool-description">
                        ${description}
                    </div>
                </div>
            </div>
        `

        this.showModal(modal)
    }

    showSkillDetails(skillName) {
        const modal = document.createElement('div')
        modal.className = 'tool-modal-overlay'

        modal.innerHTML = `
            <div class="tool-modal">
                <div class="tool-modal-header">
                    <h3>🎯 ${skillName}</h3>
                    <button class="tool-modal-close">&times;</button>
                </div>
                <div class="tool-modal-body">
                    <p><strong>Type:</strong> Skill (Claude Code Plugin)</p>
                    <div class="tool-description">
                        <p><em>Skill descriptions are loaded from SKILL.md files but not exposed via the Agent SDK.</em></p>
                        <p>Skills are automatically loaded when needed - you don't need to call them directly.</p>
                    </div>
                </div>
            </div>
        `

        this.showModal(modal)
    }

    showAgentDetails(agentName) {
        const modal = document.createElement('div')
        modal.className = 'tool-modal-overlay'

        modal.innerHTML = `
            <div class="tool-modal">
                <div class="tool-modal-header">
                    <h3>🤖 ${agentName}</h3>
                    <button class="tool-modal-close">&times;</button>
                </div>
                <div class="tool-modal-body">
                    <p><strong>Type:</strong> Agent</p>
                    <div class="tool-description">
                        <p><em>Agent descriptions are not provided by the Agent SDK.</em></p>
                        <p>Agents are specialized sub-processes for complex, multi-step tasks.</p>
                        <p>Use the Task tool to launch agents when needed for your work.</p>
                    </div>
                </div>
            </div>
        `

        this.showModal(modal)
    }

    showModal(modal) {
        document.body.appendChild(modal)

        // Close on click outside or close button
        modal.addEventListener('click', (e) => {
            if (e.target === modal || e.target.classList.contains('tool-modal-close')) {
                modal.remove()
            }
        })

        // Close on Escape key
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                modal.remove()
                document.removeEventListener('keydown', escHandler)
            }
        }
        document.addEventListener('keydown', escHandler)
    }

    // ========== Text Delta Handler (Streaming Markdown) ==========

    handleTextDelta(msg) {
        // Ensure we have an assistant message container
        if (!this.currentMessage) {
            this.currentMessage = document.createElement('div')
            this.currentMessage.className = 'assistant-message message-fade-in'
            this.currentMessage.innerHTML = `
                <div class="message-header">
                    <span class="assistant-icon">🤖</span>
                    <span class="assistant-name">Bassi</span>
                    <span class="typing-indicator">●</span>
                </div>
                <div class="message-content"></div>
            `
            this.conversationEl.appendChild(this.currentMessage)
            this.blocks.clear()
            this.textBuffers.clear()
        }

        const contentEl = this.currentMessage.querySelector('.message-content')

        // Get or create text block
        let textBlock = this.blocks.get(msg.id)
        if (!textBlock) {
            textBlock = document.createElement('div')
            textBlock.id = msg.id
            textBlock.className = 'text-block'
            contentEl.appendChild(textBlock)
            this.blocks.set(msg.id, textBlock)
            this.textBuffers.set(msg.id, '')
        }

        // Accumulate text
        const currentBuffer = this.textBuffers.get(msg.id) || ''
        const newBuffer = currentBuffer + msg.text
        this.textBuffers.set(msg.id, newBuffer)

        // Render markdown immediately (streaming!)
        this.renderMarkdownStreaming(textBlock, newBuffer)

        // During streaming, force scroll to show new content (use smooth for better UX)
        // Delay scroll to let DOM render (especially for markdown + code highlighting)
        setTimeout(() => this.forceScrollToBottomSmooth(), 50)
    }

    renderMarkdownStreaming(element, markdown) {
        if (!this.markdownRenderer) {
            // Fallback: plain text
            element.textContent = markdown
            return
        }

        try {
            // Parse markdown
            const html = this.markdownRenderer.parse(markdown)
            element.innerHTML = html

            // Highlight code blocks
            if (typeof Prism !== 'undefined') {
                element.querySelectorAll('pre code').forEach(codeBlock => {
                    // Auto-detect language from class
                    const className = codeBlock.className
                    const match = className.match(/language-(\w+)/)
                    const lang = match ? match[1] : 'javascript'

                    if (Prism.languages[lang]) {
                        Prism.highlightElement(codeBlock)
                    }
                })
            }
        } catch (e) {
            console.error('Markdown rendering error:', e)
            element.textContent = markdown
        }
    }

    // ========== Thinking Handler ==========

    handleThinking(msg) {
        // Always render (visibility controlled by CSS)

        // Ensure we have an assistant message container
        if (!this.currentMessage) {
            this.currentMessage = document.createElement('div')
            this.currentMessage.className = 'assistant-message message-fade-in'
            this.currentMessage.innerHTML = `
                <div class="message-header">
                    <span class="assistant-icon">🤖</span>
                    <span class="assistant-name">Bassi</span>
                </div>
                <div class="message-content"></div>
            `
            this.conversationEl.appendChild(this.currentMessage)
            this.blocks.clear()
        }

        const contentEl = this.currentMessage.querySelector('.message-content')

        // Create thinking block
        const thinkingBlock = document.createElement('div')
        thinkingBlock.className = 'thinking-block'
        thinkingBlock.innerHTML = `
            <div class="thinking-header">
                <span class="thinking-icon">💭</span>
                <span>Thinking...</span>
            </div>
            <div class="thinking-content">${this.escapeHtml(msg.text)}</div>
        `
        contentEl.appendChild(thinkingBlock)

        // Delay scroll to let DOM render
        setTimeout(() => this.scrollToBottom(), 50)
    }

    // ========== Tool Handlers ==========

    handleToolStart(msg) {
        // Always render (visibility controlled by CSS)

        // Ensure we have an assistant message container
        if (!this.currentMessage) {
            this.currentMessage = document.createElement('div')
            this.currentMessage.className = 'assistant-message message-fade-in'
            this.currentMessage.innerHTML = `
                <div class="message-header">
                    <span class="assistant-icon">🤖</span>
                    <span class="assistant-name">Bassi</span>
                </div>
                <div class="message-content"></div>
            `
            this.conversationEl.appendChild(this.currentMessage)
            this.blocks.clear()
        }

        const contentEl = this.currentMessage.querySelector('.message-content')

        // PHASE 3: Enhanced tool badge visuals with type labels
        // Detect tool type and get appropriate icon, type label, and display name
        let icon = '🛠️'
        let typeLabel = ''
        let displayName = msg.tool_name

        // Check for Skill (e.g., contact-creator)
        if (msg.tool_name === 'Skill' && msg.input && msg.input.command) {
            icon = '⚙️'
            typeLabel = 'SKILL'
            displayName = msg.input.command
        }
        // Check for SlashCommand (e.g., /adresse-erstellen)
        else if (msg.tool_name === 'SlashCommand' && msg.input && msg.input.command) {
            icon = '⚡'
            typeLabel = 'CMD'
            displayName = '/' + msg.input.command
        }
        // Check for Agent (Task with subagent_type)
        else if (msg.tool_name === 'Task' && msg.input && msg.input.subagent_type) {
            icon = '🤖'
            typeLabel = 'AGENT'
            displayName = msg.input.subagent_type
        }
        // Standard MCP tools
        else {
            const toolIcons = {
                'Bash': '💻',
                'ReadFile': '📄',
                'WriteFile': '✍️',
                'EditFile': '✏️',
                'Grep': '🔍',
                'Task': '📋',
                'WebSearch': '🌐',
                'WebFetch': '🌍',
                'Glob': '📁',
                'AskUserQuestion': '❓',
                'default': '🔌'  // Default MCP tool icon
            }
            icon = toolIcons[msg.tool_name] || toolIcons.default
            typeLabel = 'MCP'
        }

        // Format display: {icon} {TYPE}: {name}
        const fullDisplayName = typeLabel ? `${typeLabel}: ${displayName}` : displayName

        // Create tool panel
        const toolPanel = document.createElement('div')
        toolPanel.id = msg.id
        toolPanel.className = 'tool-call tool-running'
        toolPanel.innerHTML = `
            <div class="tool-header" title="Click to expand/minimize">
                <span class="tool-icon">${icon}</span>
                <span class="tool-name">${this.escapeHtml(fullDisplayName)}</span>
                <span class="tool-hint">Click to minimize</span>
                <span class="tool-status">Running...</span>
            </div>
            <div class="tool-body">
                <div class="tool-section tool-input">
                    <h4>Input</h4>
                    <pre>${this.escapeHtml(JSON.stringify(msg.input, null, 2))}</pre>
                </div>
                <div class="tool-section tool-output">
                    <h4>Output</h4>
                    <div class="tool-spinner"></div>
                    <pre class="output-content"></pre>
                </div>
            </div>
        `

        // Apply default verbosity state to new box
        this.applyVerbosityToBox(toolPanel, this.verboseLevel)

        // Add toggle functionality with custom state tracking
        const header = toolPanel.querySelector('.tool-header')
        const hintSpan = header.querySelector('.tool-hint')

        // Set initial hint text based on current collapsed state
        const initiallyCollapsed = toolPanel.classList.contains('collapsed')
        hintSpan.textContent = initiallyCollapsed ? 'Click to expand' : 'Click to minimize'
        header.title = initiallyCollapsed ? 'Click to expand' : 'Click to minimize'

        header.addEventListener('click', () => {
            const isCurrentlyCollapsed = toolPanel.classList.contains('collapsed')

            if (isCurrentlyCollapsed) {
                // Expanding: remove collapsed class, store custom state
                toolPanel.classList.remove('collapsed')
                this.boxStates.set(msg.id, 'expanded')
                header.title = 'Click to minimize'
                hintSpan.textContent = 'Click to minimize'
            } else {
                // Minimizing: add collapsed class, store custom state
                toolPanel.classList.add('collapsed')
                this.boxStates.set(msg.id, 'collapsed')
                header.title = 'Click to expand'
                hintSpan.textContent = 'Click to expand'
            }
        })

        contentEl.appendChild(toolPanel)
        this.blocks.set(msg.id, toolPanel)

        // Use forceScrollToBottom with delay to ensure DOM is rendered
        setTimeout(() => this.forceScrollToBottom(), 50)
    }

    handleToolEnd(msg) {
        console.log('🔧 Tool end - ID:', msg.id, 'Content:', msg.content || msg.output, 'Is error:', msg.is_error, 'Success:', msg.success)
        console.log('🔧 Blocks map:', Array.from(this.blocks.keys()))

        const toolPanel = this.blocks.get(msg.id)
        if (!toolPanel) {
            console.error('❌ Tool panel not found for ID:', msg.id)
            console.error('Available IDs:', Array.from(this.blocks.keys()))
            return
        }

        // Handle both V2 format (output/success) and V3 format (content/is_error)
        const output = msg.output || msg.content || ''
        const isSuccess = msg.success !== undefined ? msg.success : !msg.is_error

        // Remove running state, add completed/error state
        toolPanel.classList.remove('tool-running')
        toolPanel.classList.add(isSuccess ? 'tool-success' : 'tool-error')

        // Update status
        const statusEl = toolPanel.querySelector('.tool-status')
        if (statusEl) {
            statusEl.textContent = isSuccess ? '✓ Success' : '✗ Error'
            statusEl.className = `tool-status ${isSuccess ? 'status-success' : 'status-error'}`
        }

        // Remove spinner
        const spinner = toolPanel.querySelector('.tool-spinner')
        if (spinner) {
            spinner.remove()
        }

        // Update output
        const outputEl = toolPanel.querySelector('.output-content')
        if (outputEl) {
            const formattedOutput = this.formatToolOutput(output)
            outputEl.textContent = formattedOutput

            // Highlight code if it looks like code
            if (typeof Prism !== 'undefined' && formattedOutput.length > 0) {
                Prism.highlightElement(outputEl)
            }
        }

        // Use forceScrollToBottom with delay to ensure DOM is rendered
        setTimeout(() => this.forceScrollToBottom(), 50)
    }

    // ========== Message Complete Handler ==========

    handleMessageComplete(msg) {
        // Remove typing indicator
        if (this.currentMessage) {
            const typingIndicator = this.currentMessage.querySelector('.typing-indicator')
            if (typingIndicator) {
                typingIndicator.remove()
            }
        }

        // Ready for next message
        this.currentMessage = null

        // Delay scroll to ensure typing indicator removal is rendered
        setTimeout(() => this.scrollToBottom(), 50)

        // Reset UI to idle state
        this.setAgentWorking(false)

        // 🔄 BUG FIX: Refresh session list to update last_activity timestamp
        // This ensures the active session moves to the top of the list
        if (this.sessionList) {
            this.loadSessions()
        }
    }

    // ========== Usage Handler ==========

    handleUsage(msg) {
        const { input_tokens, output_tokens, total_cost_usd } = msg
        this.totalCost += total_cost_usd

        // Find the current message or last message
        let targetMessage = this.currentMessage || this.conversationEl.lastElementChild

        // If no assistant message exists (e.g., /cost command with no prior conversation),
        // create a new assistant message to display the usage stats
        if (!targetMessage || !targetMessage.classList.contains('assistant-message')) {
            targetMessage = document.createElement('div')
            targetMessage.className = 'assistant-message message-fade-in'
            targetMessage.innerHTML = `
                <div class="message-header">
                    <span class="message-icon">🤖</span>
                    <span>Bassi</span>
                </div>
                <div class="message-content">
                    <div class="text-block">
                        <strong>Usage Statistics</strong>
                    </div>
                </div>
            `
            this.conversationEl.appendChild(targetMessage)
            this.currentMessage = targetMessage
        }

        // Check if usage stats already exist
        let statsEl = targetMessage.querySelector('.usage-stats')
        if (!statsEl) {
            statsEl = document.createElement('div')
            statsEl.className = 'usage-stats'
            targetMessage.appendChild(statsEl)
        }

        // Update stats
        statsEl.innerHTML = `
            <div class="usage-item">
                <span class="usage-label">Input tokens:</span>
                <span class="usage-value">${input_tokens.toLocaleString()}</span>
            </div>
            <div class="usage-item">
                <span class="usage-label">Output tokens:</span>
                <span class="usage-value">${output_tokens.toLocaleString()}</span>
            </div>
            <div class="usage-item">
                <span class="usage-label">Cost:</span>
                <span class="usage-value">${this.formatCost(total_cost_usd)}</span>
            </div>
            <div class="usage-item">
                <span class="usage-label">Total:</span>
                <span class="usage-value total-cost">${this.formatCost(this.totalCost)}</span>
            </div>
        `

        // Remove typing indicator when usage arrives (message is complete)
        const typingIndicator = targetMessage.querySelector('.typing-indicator')
        if (typingIndicator) {
            typingIndicator.remove()
        }

        // Agent finished working - reset button and clear current message
        this.currentMessage = null
        this.setAgentWorking(false)
        this.scrollToBottom()
    }

    handleInterrupted(msg) {
        console.log('⏹ Interrupted:', msg.message)

        // Show interrupted message in UI
        const messageEl = document.createElement('div')
        messageEl.className = 'system-message message-fade-in'
        messageEl.innerHTML = `
            <div class="system-header">
                <span class="system-icon">⏹</span>
                <span>Stopped</span>
            </div>
            <div class="system-content">${this.escapeHtml(msg.message || 'Agent execution stopped')}</div>
        `
        this.conversationEl.appendChild(messageEl)

        // Agent stopped - reset button (already done in stopAgent(), but ensure it)
        this.setAgentWorking(false)
        this.scrollToBottom()
    }

    // ========== Status & Error Handlers ==========

    handleStatus(msg) {
        console.log('📊 Status:', msg.message)
        // Could show a toast notification
    }

    handleSystemMessage(msg) {
        // NOTE: Capabilities are now fetched via REST API (/api/capabilities)
        // System messages are for status updates, warnings, and compaction events

        const subtype = msg.subtype || ''
        const content = msg.content || msg.message || msg.text || null

        // Skip 'init' subtype (metadata about tools/servers - not for display)
        if (subtype === 'init') {
            console.log('⏩ Skipping "init" system message (metadata only)')
            return
        }

        // Skip messages without displayable content
        if (!content || content.trim() === '' || content === 'System message') {
            console.log('⏩ Skipping system message without displayable content:', msg)
            return
        }

        console.log(`📢 System message (${subtype}):`, content)

        // Special styling for compaction events
        const isCompaction = subtype.includes('compact')
        const className = isCompaction
            ? 'system-message message-fade-in compaction-message'
            : 'system-message message-fade-in'

        const systemEl = document.createElement('div')
        systemEl.className = className
        systemEl.innerHTML = `
            <div class="system-header">
                <span class="system-icon">${isCompaction ? '⚡' : 'ℹ️'}</span>
                <span class="system-title">${isCompaction ? 'Context Management' : 'System'}</span>
            </div>
            <div class="system-content">
                ${this.formatMarkdown(content)}
            </div>
        `
        this.conversationEl.appendChild(systemEl)
        this.scrollToBottom()
    }

    handleAssistantMessage(msg) {
        console.log('🤖 Assistant message:', msg.content)
        const assistantEl = document.createElement('div')
        assistantEl.className = 'assistant-message message-fade-in'
        assistantEl.innerHTML = `
            <div class="message-header">
                <span class="message-icon">🤖</span>
                <span>Bassi</span>
            </div>
            <div class="message-content">
                ${this.formatMarkdown(msg.content)}
            </div>
        `
        this.conversationEl.appendChild(assistantEl)
        this.scrollToBottom()
    }

    handleError(msg) {
        console.error('❌ Error:', msg.message)
        const errorEl = document.createElement('div')
        errorEl.className = 'error-message message-fade-in'
        errorEl.innerHTML = `
            <div class="error-header">
                <span class="error-icon">⚠️</span>
                <span>Error</span>
            </div>
            <div class="error-content">${this.escapeHtml(msg.message)}</div>
        `
        this.conversationEl.appendChild(errorEl)

        // Agent errored - reset button
        this.setAgentWorking(false)
        this.scrollToBottom()
    }

    // ========== Utilities ==========

    formatToolOutput(output) {
        // Extract text from SDK format: [{"type": "text", "text": "..."}]
        if (Array.isArray(output) && output.length > 0 && output[0].type === 'text') {
            return output[0].text
        }
        // Otherwise return as formatted JSON
        if (typeof output === 'object') {
            return JSON.stringify(output, null, 2)
        }
        return String(output)
    }

    formatCost(value) {
        if (value === 0) return '$0.0000'
        if (value < 0.0001) return `$${value.toExponential(2)}`
        if (value < 0.01) return `$${value.toFixed(6)}`
        return `$${value.toFixed(4)}`
    }

    escapeHtml(text) {
        const div = document.createElement('div')
        div.textContent = text
        return div.innerHTML
    }

    formatMarkdown(text) {
        // If text already contains HTML tags, return as-is
        if (text.includes('<div') || text.includes('<h1>')) {
            return text
        }

        // Simple markdown formatting for plain text
        let html = this.escapeHtml(text)

        // Headers
        html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>')
        html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>')
        html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>')

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

        // Code blocks
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

        // Line breaks
        html = html.replace(/\n/g, '<br>')

        return html
    }

    isScrolledToBottom() {
        // Check if user is scrolled to the bottom (with small threshold)
        const threshold = 100 // pixels from bottom
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop
        const scrollHeight = document.documentElement.scrollHeight
        const clientHeight = window.innerHeight
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight

        console.log('📊 [SCROLL] isScrolledToBottom:', {
            scrollTop,
            scrollHeight,
            clientHeight,
            distanceFromBottom,
            threshold,
            result: distanceFromBottom < threshold
        })

        return distanceFromBottom < threshold
    }

    scrollToBottom() {
        // Only auto-scroll if user is already at bottom
        // Use a lightweight check since this is called frequently during streaming
        console.log('📜 [SCROLL] scrollToBottom() called (smart scroll)')
        if (this.isScrolledToBottom()) {
            console.log('✅ [SCROLL] User is at bottom, scrolling...')
            // Use double RAF to ensure layout is ready (lighter than forceScrollToBottom)
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const scrollHeight = document.documentElement.scrollHeight
                    const viewportHeight = window.innerHeight
                    const targetScroll = scrollHeight - viewportHeight
                    console.log(`🎯 [SCROLL] Scrolling to ${targetScroll} (height: ${scrollHeight}, viewport: ${viewportHeight})`)
                    window.scrollTo({
                        top: targetScroll,
                        behavior: 'smooth'
                    })
                })
            })
        } else {
            console.log('⏭️ [SCROLL] User scrolled up, skipping auto-scroll')
        }
    }

    forceScrollToBottom() {
        // Force scroll to bottom (used on initial page load)
        // Wait for layout to stabilize before scrolling
        console.log('🚀 [SCROLL] forceScrollToBottom() called (forced scroll)')
        
        // Use multiple requestAnimationFrame calls to wait for layout to complete
        // This ensures scrollHeight has reached its final value
        let lastHeight = 0
        let stableCount = 0
        const maxWaitFrames = 10  // Maximum frames to wait for stability
        
        const checkAndScroll = () => {
            const currentHeight = document.documentElement.scrollHeight
            const viewportHeight = window.innerHeight
            
            // If height hasn't changed for 2 frames, consider it stable
            if (currentHeight === lastHeight) {
                stableCount++
                if (stableCount >= 2) {
                    // Layout is stable, perform scroll
                    const targetScroll = currentHeight - viewportHeight
                    console.log(`🎯 [SCROLL] Layout stable. Force scrolling to ${targetScroll} (height: ${currentHeight}, viewport: ${viewportHeight})`)
                    window.scrollTo({
                        top: targetScroll,
                        behavior: 'instant'
                    })
                    
                    // Verify scroll completed
                    requestAnimationFrame(() => {
                        const actualScroll = window.pageYOffset || document.documentElement.scrollTop
                        const distanceFromBottom = currentHeight - actualScroll - viewportHeight
                        console.log(`✅ [SCROLL] Scroll complete: position=${actualScroll}, distanceFromBottom=${distanceFromBottom}px`)
                    })
                    return
                }
            } else {
                stableCount = 0  // Reset counter if height changed
            }
            
            lastHeight = currentHeight
            
            // Continue waiting if we haven't exceeded max frames
            if (stableCount < maxWaitFrames) {
                requestAnimationFrame(checkAndScroll)
            } else {
                // Timeout - scroll anyway with current height
                const targetScroll = currentHeight - viewportHeight
                console.log(`⚠️ [SCROLL] Layout timeout. Scrolling to ${targetScroll}`)
                window.scrollTo({
                    top: targetScroll,
                    behavior: 'instant'
                })
            }
        }
        
        requestAnimationFrame(checkAndScroll)
    }

    forceScrollToBottomSmooth() {
        // Force scroll to bottom with smooth behavior (used during streaming)
        // This ensures we scroll even if user isn't currently at bottom
        console.log('🌊 [SCROLL] forceScrollToBottomSmooth() called (forced smooth scroll)')
        
        // Use double RAF to ensure layout is ready
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                const scrollHeight = document.documentElement.scrollHeight
                const viewportHeight = window.innerHeight
                const targetScroll = scrollHeight - viewportHeight
                console.log(`🎯 [SCROLL] Force smooth scrolling to ${targetScroll} (height: ${scrollHeight}, viewport: ${viewportHeight})`)
                window.scrollTo({
                    top: targetScroll,
                    behavior: 'smooth'
                })
            })
        })
    }

    // ========== Verbose Level Management ==========

    loadVerboseLevel() {
        return localStorage.getItem('bassi_verbose_level') || 'minimal'
    }

    setVerboseLevel(level) {
        this.verboseLevel = level
        localStorage.setItem('bassi_verbose_level', level)

        // Update CSS class on conversation container
        this.conversationEl.classList.remove('verbose-none', 'verbose-minimal', 'verbose-full')
        this.conversationEl.classList.add(`verbose-${level}`)

        // Apply verbosity to all tool boxes, respecting custom states
        this.blocks.forEach((toolPanel, id) => {
            const customState = this.boxStates.get(id)
            if (customState) {
                // Box has custom state, don't change it
                return
            }

            // Apply global verbosity setting
            this.applyVerbosityToBox(toolPanel, level)
        })

        console.log('Verbose level set to:', level)
    }

    applyVerbosityToBox(toolPanel, level) {
        // Set INITIAL collapse state based on verbosity level
        // This only applies to new boxes - user can toggle individual boxes afterwards
        if (level === 'none') {
            // Hide completely (handled by CSS)
            toolPanel.classList.add('verbose-none')
        } else if (level === 'minimal') {
            // Start collapsed (minimized)
            toolPanel.classList.add('collapsed')
        } else if (level === 'full') {
            // Start expanded
            toolPanel.classList.remove('collapsed')
        }
    }

    // ========== Interactive Questions ==========

    handleQuestion(msg) {
        console.log('📋 Question received:', msg)

        // Create question dialog
        const dialog = this.createQuestionDialog(msg)

        // The question should appear right after the AskUserQuestion tool badge
        // within the current streaming message, not as a separate message
        if (this.currentMessage) {
            // Find the message-content div within currentMessage
            const messageContent = this.currentMessage.querySelector('.message-content')
            if (messageContent) {
                messageContent.appendChild(dialog)
            } else {
                this.currentMessage.appendChild(dialog)
            }
        } else {
            // Fallback: create standalone container
            const questionContainer = document.createElement('div')
            questionContainer.className = 'message question-message'
            questionContainer.appendChild(dialog)
            this.conversationEl.appendChild(questionContainer)
        }

        this.scrollToBottom()
    }

    createQuestionDialog(msg) {
        const dialog = document.createElement('div')
        dialog.className = 'question-dialog'
        dialog.dataset.questionId = msg.id

        const questions = msg.questions || []
        const selectedAnswers = {} // Track selected answers per question

        // For each question
        questions.forEach((q, qIndex) => {
            const questionContainer = document.createElement('div')
            questionContainer.className = 'question-container'

            // Header
            const header = document.createElement('div')
            header.className = 'question-header'
            header.textContent = q.header
            questionContainer.appendChild(header)

            // Question text
            const questionText = document.createElement('div')
            questionText.className = 'question-text'
            questionText.textContent = q.question
            questionContainer.appendChild(questionText)

            // Options
            const optionsContainer = document.createElement('div')
            optionsContainer.className = 'question-options'

            const questionKey = q.question
            if (q.multiSelect) {
                selectedAnswers[questionKey] = []
            } else {
                selectedAnswers[questionKey] = null
            }

            q.options.forEach((option, optIndex) => {
                const optionEl = document.createElement('button')
                optionEl.className = 'question-option'
                optionEl.dataset.questionIndex = qIndex
                optionEl.dataset.optionLabel = option.label

                const labelEl = document.createElement('div')
                labelEl.className = 'option-label'
                labelEl.textContent = option.label

                const descEl = document.createElement('div')
                descEl.className = 'option-description'
                descEl.textContent = option.description

                optionEl.appendChild(labelEl)
                optionEl.appendChild(descEl)

                // Click handler
                optionEl.addEventListener('click', () => {
                    if (q.multiSelect) {
                        // Toggle selection for multiSelect
                        optionEl.classList.toggle('selected')
                        const label = option.label
                        if (optionEl.classList.contains('selected')) {
                            if (!selectedAnswers[questionKey].includes(label)) {
                                selectedAnswers[questionKey].push(label)
                            }
                        } else {
                            selectedAnswers[questionKey] = selectedAnswers[questionKey].filter(a => a !== label)
                        }
                    } else {
                        // Single select - remove other selections
                        optionsContainer.querySelectorAll('.question-option').forEach(el => {
                            el.classList.remove('selected')
                        })
                        optionEl.classList.add('selected')
                        selectedAnswers[questionKey] = option.label
                    }
                })

                optionsContainer.appendChild(optionEl)
            })

            // "Other" option (always available)
            const otherOption = document.createElement('div')
            otherOption.className = 'question-option-other'

            const otherLabel = document.createElement('div')
            otherLabel.className = 'option-label'
            otherLabel.textContent = 'Other (type your answer)'

            const otherInput = document.createElement('input')
            otherInput.type = 'text'
            otherInput.className = 'other-input'
            otherInput.placeholder = 'Type your custom answer...'

            otherOption.appendChild(otherLabel)
            otherOption.appendChild(otherInput)

            optionsContainer.appendChild(otherOption)

            questionContainer.appendChild(optionsContainer)
            dialog.appendChild(questionContainer)
        })

        // Submit button
        const submitBtn = document.createElement('button')
        submitBtn.className = 'question-submit-btn'
        submitBtn.textContent = 'Submit Answers'

        submitBtn.addEventListener('click', () => {
            console.log('📤 Submit button clicked')
            console.log('📋 Selected answers:', selectedAnswers)

            // Validate - ensure all questions answered
            let allAnswered = true
            const finalAnswers = {}

            questions.forEach((q, qIndex) => {
                const questionKey = q.question
                let answer = selectedAnswers[questionKey]

                // Check if "Other" was used
                const questionContainers = dialog.querySelectorAll('.question-container')
                const questionEl = questionContainers[qIndex]
                const otherInput = questionEl.querySelector('.other-input')
                if (otherInput && otherInput.value.trim()) {
                    if (q.multiSelect) {
                        if (!Array.isArray(answer)) answer = []
                        answer.push(otherInput.value.trim())
                    } else {
                        answer = otherInput.value.trim()
                    }
                }

                if (q.multiSelect) {
                    if (!answer || answer.length === 0) {
                        allAnswered = false
                    }
                } else {
                    if (!answer) {
                        allAnswered = false
                    }
                }

                finalAnswers[questionKey] = answer
            })

            if (!allAnswered) {
                console.log('⚠️ Not all questions answered:', finalAnswers)
                alert('Please answer all questions before submitting.')
                return
            }

            console.log('✅ All questions answered, sending:', finalAnswers)

            // Send answer to server
            this.sendQuestionAnswer(msg.id, finalAnswers)

            // Replace dialog with summary
            const summary = document.createElement('div')
            summary.className = 'question-summary'
            summary.innerHTML = `
                <div class="summary-header">✓ Questions Answered</div>
                ${Object.entries(finalAnswers).map(([q, a]) => `
                    <div class="summary-item">
                        <strong>${q}</strong><br>
                        <span class="summary-answer">${Array.isArray(a) ? a.join(', ') : a}</span>
                    </div>
                `).join('')}
            `
            dialog.replaceWith(summary)
        })

        dialog.appendChild(submitBtn)

        return dialog
    }

    // ========== Permission Requests ==========

    handlePermissionRequest(msg) {
        console.log('🔐 Permission request received:', msg)

        // Create permission dialog
        const dialog = this.createPermissionDialog(msg)

        // Add to conversation
        if (this.currentMessage) {
            const messageContent = this.currentMessage.querySelector('.message-content')
            if (messageContent) {
                messageContent.appendChild(dialog)
            } else {
                this.currentMessage.appendChild(dialog)
            }
        } else {
            const permissionContainer = document.createElement('div')
            permissionContainer.className = 'message permission-message'
            permissionContainer.appendChild(dialog)
            this.conversationEl.appendChild(permissionContainer)
        }

        this.scrollToBottom()
    }

    createPermissionDialog(msg) {
        const dialog = document.createElement('div')
        dialog.className = 'permission-dialog'

        // Header
        const header = document.createElement('div')
        header.className = 'permission-header'
        header.innerHTML = `<strong>🔐 Tool Permission Required</strong>`
        dialog.appendChild(header)

        // Message
        const message = document.createElement('div')
        message.className = 'permission-message-text'
        message.textContent = msg.message || `The agent wants to use the '${msg.tool_name}' tool.`
        dialog.appendChild(message)

        // Options container
        const optionsContainer = document.createElement('div')
        optionsContainer.className = 'permission-options'

        const options = [
            {
                scope: 'one_time',
                label: 'This one time',
                description: 'Allow just this single use',
                icon: '1️⃣'
            },
            {
                scope: 'session',
                label: 'This session',
                description: 'Allow for current session',
                icon: '🔄'
            },
            {
                scope: 'persistent',
                label: 'All sessions',
                description: 'Allow across all sessions',
                icon: '💾'
            },
            {
                scope: 'global',
                label: 'All tools always',
                description: 'Bypass all permissions forever',
                icon: '🌐'
            }
        ]

        options.forEach(option => {
            const button = document.createElement('button')
            button.className = 'permission-option'
            button.dataset.scope = option.scope

            const labelEl = document.createElement('div')
            labelEl.className = 'option-label'
            labelEl.innerHTML = `${option.icon} ${option.label}`

            const descEl = document.createElement('div')
            descEl.className = 'option-description'
            descEl.textContent = option.description

            button.appendChild(labelEl)
            button.appendChild(descEl)

            button.addEventListener('click', () => {
                this.sendPermissionResponse(msg.tool_name, option.scope)
                dialog.remove()
            })

            optionsContainer.appendChild(button)
        })

        dialog.appendChild(optionsContainer)
        return dialog
    }

    sendPermissionResponse(toolName, scope) {
        console.log(`📤 Sending permission response: ${toolName} → ${scope}`)

        const message = {
            type: 'permission_response',
            tool_name: toolName,
            scope: scope
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message))
        } else {
            console.error('❌ Cannot send permission response - WebSocket not connected')
        }
    }

    sendQuestionAnswer(questionId, answers) {
        console.log('📤 Sending answer:', questionId, answers)

        const message = {
            type: 'answer',
            question_id: questionId,
            answers: answers
        }

        console.log('📤 Full message:', JSON.stringify(message, null, 2))
        console.log('📤 WebSocket state:', this.ws.readyState)

        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message))
            console.log('✅ Answer sent successfully')
        } else {
            console.error('❌ WebSocket not open! State:', this.ws.readyState)
        }
    }

    // ========== Session Sidebar Management ==========

    initSessionSidebar() {
        /**
         * Initialize session sidebar event listeners and load sessions.
         */
        if (!this.sessionSidebarToggle || !this.sessionSidebar) {
            console.warn('⚠️ Session sidebar elements not found')
            return
        }

        // Toggle button click
        this.sessionSidebarToggle.addEventListener('click', () => {
            this.toggleSessionSidebar()
        })

        // Search input
        if (this.sessionSearch) {
            this.sessionSearch.addEventListener('input', (e) => {
                this.filterSessions(e.target.value)
            })
        }

        // New session button
        if (this.newSessionButton) {
            this.newSessionButton.addEventListener('click', () => {
                this.createNewSession()
            })
        }

        // Load sessions on init
        this.loadSessions()

        console.log('✅ Session sidebar initialized')
    }

    toggleSessionSidebar() {
        /**
         * Toggle session sidebar open/close state.
         */
        this.sessionSidebarOpen = !this.sessionSidebarOpen
        this.updateSessionSidebarState()
    }

    closeSessionSidebar() {
        /**
         * Close session sidebar if open.
         */
        if (this.sessionSidebarOpen) {
            this.sessionSidebarOpen = false
            this.updateSessionSidebarState()
        }
    }

    updateSessionSidebarState() {
        /**
         * Update sidebar UI based on open/close state.
         */
        if (this.sessionSidebarOpen) {
            this.sessionSidebar.classList.add('open')
            this.sessionSidebarControls?.classList.add('open')
            document.body.classList.add('sidebar-open')
            // Reload sessions when opening
            this.loadSessions()
        } else {
            this.sessionSidebar.classList.remove('open')
            this.sessionSidebarControls?.classList.remove('open')
            document.body.classList.remove('sidebar-open')
        }
    }

    async loadSessions() {
        /**
         * Load all sessions from the API and render them.
         */
        try {
            const response = await fetch('/api/sessions?limit=100&sort_by=last_activity&order=desc')

            if (!response.ok) {
                console.error('❌ Failed to load sessions:', response.status)
                return
            }

            const data = await response.json()
            this.allSessions = data.sessions || []
            this.filteredSessions = this.allSessions

            console.log('📚 Sessions loaded:', this.allSessions.length)

            this.renderSessions()
        } catch (error) {
            console.error('❌ Error loading sessions:', error)
        }
    }

    filterSessions(query) {
        /**
         * Filter sessions by search query.
         */
        const lowerQuery = query.toLowerCase().trim()

        if (!lowerQuery) {
            this.filteredSessions = this.allSessions
        } else {
            this.filteredSessions = this.allSessions.filter(session => {
                const nameMatch = session.display_name?.toLowerCase().includes(lowerQuery)
                const idMatch = session.session_id?.toLowerCase().includes(lowerQuery)
                return nameMatch || idMatch
            })
        }

        this.renderSessions()
    }

    groupSessionsByDate(sessions) {
        /**
         * Group sessions by date: Today, Yesterday, This Week, Older
         */
        const now = new Date()
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const yesterday = new Date(today)
        yesterday.setDate(yesterday.getDate() - 1)
        const weekStart = new Date(today)
        weekStart.setDate(weekStart.getDate() - 7)

        const groups = {
            'Today': [],
            'Yesterday': [],
            'This Week': [],
            'Older': []
        }

        sessions.forEach(session => {
            const sessionDate = new Date(session.last_activity)
            const sessionDay = new Date(sessionDate.getFullYear(), sessionDate.getMonth(), sessionDate.getDate())

            if (sessionDay.getTime() === today.getTime()) {
                groups['Today'].push(session)
            } else if (sessionDay.getTime() === yesterday.getTime()) {
                groups['Yesterday'].push(session)
            } else if (sessionDay >= weekStart) {
                groups['This Week'].push(session)
            } else {
                groups['Older'].push(session)
            }
        })

        return groups
    }

    renderSessions() {
        /**
         * Render session list with date grouping.
         */
        if (!this.sessionList) return

        if (this.filteredSessions.length === 0) {
            this.sessionList.innerHTML = `
                <div class="session-list-empty">
                    ${this.allSessions.length === 0
                        ? 'No sessions yet. Start chatting to create your first session!'
                        : 'No sessions match your search.'}
                </div>
            `
            return
        }

        const groups = this.groupSessionsByDate(this.filteredSessions)
        let html = ''

        // Render each group
        for (const [groupName, sessions] of Object.entries(groups)) {
            if (sessions.length === 0) continue

            html += `<div class="session-group">`
            html += `<div class="session-group-header">${groupName}</div>`

            sessions.forEach(session => {
                const isActive = session.session_id === this.sessionId
                const messageCount = session.message_count || 0
                const lastActivity = this.formatRelativeTime(session.last_activity)

                html += `
                    <div class="session-item ${isActive ? 'active' : ''}"
                         data-session-id="${session.session_id}">
                        <div class="session-item-content"
                             onclick="window.bassiClient.switchSession('${session.session_id}')">
                            <div class="session-item-name">${this.escapeHtml(session.display_name || 'Unnamed Session')}</div>
                            <div class="session-item-meta">${messageCount} message${messageCount !== 1 ? 's' : ''} • ${lastActivity}</div>
                        </div>
                        ${!isActive ? `
                            <button class="session-item-delete"
                                    onclick="event.stopPropagation(); window.bassiClient.deleteSession('${session.session_id}')"
                                    title="Delete session">
                                🗑️
                            </button>
                        ` : ''}
                    </div>
                `
            })

            html += `</div>`
        }

        this.sessionList.innerHTML = html
    }

    formatRelativeTime(isoString) {
        /**
         * Format ISO timestamp as relative time (e.g., "5 minutes ago").
         */
        const date = new Date(isoString)
        const now = new Date()
        const diffMs = now - date
        const diffSec = Math.floor(diffMs / 1000)
        const diffMin = Math.floor(diffSec / 60)
        const diffHour = Math.floor(diffMin / 60)
        const diffDay = Math.floor(diffHour / 24)

        if (diffSec < 60) return 'Just now'
        if (diffMin < 60) return `${diffMin} min ago`
        if (diffHour < 24) return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`
        if (diffDay < 7) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`

        // Format as date for older items
        return date.toLocaleDateString()
    }

    async switchSession(sessionId) {
        /**
         * Switch to a different session by reconnecting WebSocket.
         *
         * 🔄 PHASE 4: Session Switch Confirmation
         * Shows warning if user has unsent input to prevent accidental data loss.
         */
        console.log(`🔷 [FRONTEND] switchSession() called with sessionId: ${sessionId}`)

        // Guard: Block session switch while agent is working
        if (this.isAgentWorking) {
            this.showNotification('Cannot switch session while agent is working', 'warning')
            return
        }

        if (sessionId === this.sessionId) {
            console.log('⚠️ Already in this session')
            return
        }

        // 🔄 PHASE 4: Confirm if current session has unsent input
        const inputValue = this.messageInput.value.trim()
        if (inputValue.length > 0) {
            const confirmed = window.confirm(
                'You have unsent input. Switch sessions anyway?\n\n' +
                'Your typed message will be lost.'
            )
            if (!confirmed) {
                console.log('⚠️ Session switch cancelled - user has unsent input')
                return
            }
        }

        console.log(`🔄 Switching to session: ${sessionId}`)

        // Close current WebSocket connection (intentionally)
        this.isIntentionalDisconnect = true
        if (this.ws) {
            this.ws.close()
        }

        // Clear current state (but NOT conversation - we'll load messages first)
        this.blocks.clear()
        this.textBuffers.clear()
        this.sessionFiles = []
        this.messageInput.value = ''  // Clear input field
        this.renderFileSidebar()  // Update file sidebar to show empty state

        // Set new session ID BEFORE connecting
        this.sessionId = sessionId

        // Clear conversation NOW, just before loading
        this.conversationEl.innerHTML = ''

        // Load message history FIRST (before connecting)
        await this.loadSessionHistory(sessionId)

        // THEN connect with new session ID
        this.connect()

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.toggleSessionSidebar()
        }
    }

    async loadSessionHistory(sessionId) {
        /**
         * Load and display message history from a session.
         *
         * Fetches messages from /api/sessions/{id}/messages and renders them.
         */
        console.log(`🔷 [FRONTEND] loadSessionHistory() called for session: ${sessionId}`)
        try {
            console.log(`📚 Loading message history for session: ${sessionId}`)

            const response = await fetch(`/api/sessions/${sessionId}/messages`)

            if (!response.ok) {
                console.error('❌ Failed to load message history:', response.status)
                return
            }

            const data = await response.json()
            const messages = data.messages || []

            console.log(`📝 Loaded ${messages.length} messages from history`)

            // Render each message
            for (const msg of messages) {
                if (msg.role === 'user') {
                    this.renderUserMessage(msg.content)
                } else if (msg.role === 'assistant') {
                    this.renderAssistantMessage(msg.content)
                }
            }

            // Scroll to bottom after loading all messages with delay for DOM rendering
            // Wait for fade-in animation (300ms) + extra buffer (50ms)
            setTimeout(() => this.forceScrollToBottom(), 350)

        } catch (error) {
            console.error('❌ Error loading message history:', error)
        }
    }

    renderUserMessage(content) {
        /**
         * Render a user message in the conversation (from history).
         * Matches the real-time rendering format exactly.
         */
        const messageDiv = document.createElement('div')
        messageDiv.className = 'user-message'

        const contentDiv = document.createElement('div')
        contentDiv.className = 'message-content'
        contentDiv.textContent = content

        messageDiv.appendChild(contentDiv)
        this.conversationEl.appendChild(messageDiv)
    }

    renderAssistantMessage(content) {
        /**
         * Render an assistant message in the conversation (from history).
         * Matches the real-time rendering format exactly, including:
         * - Message header with icon and assistant name
         * - Markdown parsing and syntax highlighting
         * - Text block structure
         */
        const messageDiv = document.createElement('div')
        messageDiv.className = 'assistant-message'

        // Add message header (same as real-time rendering)
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="assistant-icon">🤖</span>
                <span class="assistant-name">Bassi</span>
            </div>
            <div class="message-content"></div>
        `

        const contentEl = messageDiv.querySelector('.message-content')

        // Create text block for content
        const textBlock = document.createElement('div')
        textBlock.className = 'text-block'

        // Render markdown (same as real-time rendering)
        if (this.markdownRenderer) {
            try {
                const html = this.markdownRenderer.parse(content)
                textBlock.innerHTML = html

                // Highlight code blocks
                if (typeof Prism !== 'undefined') {
                    textBlock.querySelectorAll('pre code').forEach(codeBlock => {
                        const className = codeBlock.className
                        const match = className.match(/language-(\w+)/)
                        const lang = match ? match[1] : 'javascript'

                        if (Prism.languages[lang]) {
                            Prism.highlightElement(codeBlock)
                        }
                    })
                }
            } catch (e) {
                console.error('Markdown rendering error:', e)
                textBlock.textContent = content
            }
        } else {
            // Fallback: plain text
            textBlock.textContent = content
        }

        contentEl.appendChild(textBlock)
        this.conversationEl.appendChild(messageDiv)
    }

    renderUserMessageOld(content) {
        /**
         * OLD VERSION - DO NOT USE
         * Render an assistant message in the conversation.
         */
        const messageDiv = document.createElement('div')
        messageDiv.className = 'message assistant-message'

        const contentDiv = document.createElement('div')
        contentDiv.className = 'message-content'

        // Render markdown if marked is available
        if (this.markdownRenderer) {
            contentDiv.innerHTML = this.markdownRenderer.parse(content)
        } else {
            contentDiv.textContent = content
        }

        messageDiv.appendChild(contentDiv)
        this.conversationEl.appendChild(messageDiv)
    }

    async deleteSession(sessionId) {
        /**
         * Delete a session with confirmation.
         *
         * Shows a confirmation dialog before deleting.
         * Reloads session list after successful deletion.
         */
        const session = this.allSessions.find(s => s.session_id === sessionId)
        const sessionName = session?.display_name || 'Unnamed Session'

        // Show confirmation dialog
        if (!confirm(`Delete "${sessionName}"?\n\nThis will permanently delete all messages and files.`)) {
            return
        }

        try {
            const response = await fetch(`/api/sessions/${sessionId}`, {
                method: 'DELETE'
            })

            if (!response.ok) {
                const error = await response.json()
                alert(`Failed to delete session: ${error.error}`)
                return
            }

            console.log(`🗑️  Deleted session: ${sessionId}`)

            // Reload session list
            await this.loadSessions()

        } catch (error) {
            console.error('❌ Error deleting session:', error)
            alert('Failed to delete session')
        }
    }

    // ========== File Sidebar Management ==========

    initFileSidebar() {
        /**
         * Initialize file sidebar event listeners.
         */
        if (!this.fileSidebarToggle || !this.fileSidebar) {
            console.warn('⚠️ File sidebar elements not found')
            return
        }

        // Toggle button click
        this.fileSidebarToggle.addEventListener('click', () => {
            this.toggleFileSidebar()
        })

        // Upload button click (in sidebar)
        if (this.fileSidebarUploadBtn) {
            this.fileSidebarUploadBtn.addEventListener('click', () => {
                // Trigger the file input click
                this.fileInput?.click()
            })
        }

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (this.fileSidebarOpen &&
                window.innerWidth <= 768 &&
                !this.fileSidebar.contains(e.target) &&
                !this.fileSidebarToggle.contains(e.target)) {
                this.closeFileSidebar()
            }
        })

        // Initial render (empty state)
        this.renderFileSidebar()

        console.log('✅ File sidebar initialized')
    }

    toggleFileSidebar() {
        /**
         * Toggle file sidebar open/close state.
         */
        this.fileSidebarOpen = !this.fileSidebarOpen
        this.updateFileSidebarState()
    }

    closeFileSidebar() {
        /**
         * Close file sidebar if open.
         */
        if (this.fileSidebarOpen) {
            this.fileSidebarOpen = false
            this.updateFileSidebarState()
        }
    }

    updateFileSidebarState() {
        /**
         * Update file sidebar UI based on open/close state.
         */
        if (this.fileSidebarOpen) {
            this.fileSidebar.classList.add('open')
            this.fileSidebarControls?.classList.add('open')
            document.body.classList.add('file-sidebar-open')
        } else {
            this.fileSidebar.classList.remove('open')
            this.fileSidebarControls?.classList.remove('open')
            document.body.classList.remove('file-sidebar-open')
        }
    }

    renderFileSidebar() {
        /**
         * Render files in the file sidebar from sessionFiles array.
         */
        if (!this.fileSidebarList) return

        // Show empty state if no files
        if (!this.sessionFiles || this.sessionFiles.length === 0) {
            this.fileSidebarList.innerHTML = `
                <div class="file-sidebar-empty">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4;">
                        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p>No files uploaded yet</p>
                    <span>Upload files or drag & drop</span>
                </div>
            `
            this.updateFileSidebarStats()
            return
        }

        // Render file items
        const fileItems = this.sessionFiles.map(file => {
            const fileSize = this.formatFileSize(file.size || 0)
            const isImage = file.file_type === 'image'
            const isPdf = file.file_type === 'pdf'

            // Show thumbnail for images, icon for others
            let iconContent
            if (isImage && file.data) {
                const mimeType = file.mime_type || 'image/png'
                iconContent = `<img class="file-sidebar-item-thumbnail" src="data:${mimeType};base64,${file.data}" alt="${file.ref}">`
            } else {
                const fileIcon = this.getFileIcon(file.file_type || 'unknown')
                iconContent = `<span class="file-sidebar-item-emoji">${fileIcon}</span>`
            }

            // Type badge
            const typeBadge = isPdf ? '<span class="file-type-badge pdf">PDF</span>' :
                              isImage ? '<span class="file-type-badge image">IMG</span>' : ''

            return `
                <div class="file-sidebar-item ${isImage ? 'has-thumbnail' : ''}" data-ref="${file.ref}" title="${file.path || file.ref}">
                    <div class="file-sidebar-item-icon">${iconContent}</div>
                    <div class="file-sidebar-item-info">
                        <span class="file-sidebar-item-name">@${file.ref}</span>
                        <span class="file-sidebar-item-meta">${fileSize} ${typeBadge}</span>
                    </div>
                    <button class="file-sidebar-item-delete" data-ref="${file.ref}" title="Remove file">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
            `
        }).join('')

        this.fileSidebarList.innerHTML = fileItems

        // Add click handlers for file items
        this.fileSidebarList.querySelectorAll('.file-sidebar-item').forEach(item => {
            // Click on item to insert @reference
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.file-sidebar-item-delete')) {
                    const ref = item.dataset.ref
                    this.insertFileReference(ref)
                }
            })

            // Delete button
            const deleteBtn = item.querySelector('.file-sidebar-item-delete')
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation()
                    const ref = deleteBtn.dataset.ref
                    this.removeFileFromSidebar(ref)
                })
            }
        })

        this.updateFileSidebarStats()
    }

    insertFileReference(ref) {
        /**
         * Insert @reference into message input at cursor position.
         */
        if (!this.messageInput || !ref) return

        const input = this.messageInput
        const start = input.selectionStart
        const end = input.selectionEnd
        const text = input.value
        const refText = `@${ref} `

        // Insert at cursor position
        input.value = text.substring(0, start) + refText + text.substring(end)

        // Move cursor after inserted reference
        const newPos = start + refText.length
        input.setSelectionRange(newPos, newPos)
        input.focus()

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.closeFileSidebar()
        }
    }

    removeFileFromSidebar(ref) {
        /**
         * Remove file from sessionFiles array and re-render.
         * Note: This only removes from UI, not from server.
         */
        if (!ref) return

        // Find and remove file
        const index = this.sessionFiles.findIndex(f => f.ref === ref)
        if (index !== -1) {
            this.sessionFiles.splice(index, 1)
            console.log(`🗑️  Removed file from sidebar: @${ref}`)
            this.renderFileSidebar()
        }
    }

    updateFileSidebarStats() {
        /**
         * Update file count and total size in sidebar footer.
         */
        const fileCount = this.sessionFiles?.length || 0
        const totalSize = this.sessionFiles?.reduce((sum, f) => sum + (f.size || 0), 0) || 0

        if (this.fileSidebarCount) {
            this.fileSidebarCount.textContent = `${fileCount} file${fileCount !== 1 ? 's' : ''}`
        }

        if (this.fileSidebarSize) {
            this.fileSidebarSize.textContent = `${this.formatFileSize(totalSize)} used`
        }

        // Update badge on toggle button
        this.updateFileSidebarBadge(fileCount)
    }

    updateFileSidebarBadge(count) {
        /**
         * Update the file count badge on the toggle button.
         */
        if (!this.fileSidebarToggle) return

        let badge = this.fileSidebarToggle.querySelector('.file-sidebar-badge')

        if (count > 0) {
            if (!badge) {
                badge = document.createElement('span')
                badge.className = 'file-sidebar-badge'
                this.fileSidebarToggle.appendChild(badge)
            }
            badge.textContent = count > 99 ? '99+' : count
            badge.style.display = 'flex'
        } else if (badge) {
            badge.style.display = 'none'
        }
    }

    getFileIcon(fileType) {
        /**
         * Get icon for file type.
         */
        const icons = {
            'image': '🖼️',
            'pdf': '📄',
            'document': '📝',
            'spreadsheet': '📊',
            'code': '💻',
            'text': '📃',
            'archive': '📦',
            'video': '🎬',
            'audio': '🎵',
            'unknown': '📎'
        }
        return icons[fileType] || icons['unknown']
    }

    formatFileSize(bytes) {
        /**
         * Format bytes to human readable string.
         */
        if (bytes === 0) return '0 B'

        const units = ['B', 'KB', 'MB', 'GB']
        const k = 1024
        const i = Math.floor(Math.log(bytes) / Math.log(k))

        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i]
    }

    createNewSession() {
        /**
         * Create a new session by reconnecting without session_id.
         */
        console.log('➕ Creating new session')

        // Close current WebSocket connection (intentionally)
        this.isIntentionalDisconnect = true
        if (this.ws) {
            this.ws.close()
        }

        // Clear current state
        this.conversationEl.innerHTML = ''
        this.blocks.clear()
        this.textBuffers.clear()
        this.sessionFiles = []
        this.sessionId = null
        this.renderFileSidebar()  // Update file sidebar to show empty state

        // Connect without session ID to create new one
        this.connect()

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.toggleSessionSidebar()
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.bassiClient = new BassiWebClient()
})
