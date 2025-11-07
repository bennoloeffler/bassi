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

        // State
        this.blocks = new Map()              // id -> DOM element
        this.boxStates = new Map()           // id -> custom state ('expanded'|'collapsed'|null)
        this.textBuffers = new Map()         // id -> accumulated text
        this.currentMessage = null           // Current assistant message container
        this.totalCost = 0                   // Cumulative cost
        this.verboseLevel = this.loadVerboseLevel()
        this.isAgentWorking = false          // Track if agent is processing
        this.sessionCapabilities = null      // Capabilities from init system message

        // Autocomplete state
        this.commandRegistry = []            // All available commands
        this.autocompletePanel = null        // Autocomplete panel DOM element
        this.autocompleteVisible = false     // Is panel visible
        this.autocompleteSelectedIndex = -1  // Currently selected command index
        this.autocompleteCommands = []       // Filtered commands for current input

        // Streaming markdown renderer
        this.markdownRenderer = null
        this.renderDebounceTimers = new Map()  // id -> timer

        // File handling
        this.pendingImages = []                  // Images to send with next message (legacy, kept for compatibility)
        this.pendingFiles = []                   // All files to send (images, PDFs, documents)
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

        // Initialize settings
        this.initSettings()

        // Initialize autocomplete
        this.initAutocomplete()

        // PHASE 1: Eager capability loading - load in parallel on startup
        this.loadCapabilities().then(() => {
            console.log('✅ Capabilities loaded on startup')
            this.rebuildCommandRegistry()
        }).catch(err => {
            console.warn('⚠️ Failed to load capabilities on startup:', err)
        })

        // Connect WebSocket
        this.connect()
    }

    // ========== Settings ==========

    initSettings() {
        const settingsButton = document.getElementById('settings-button')
        const settingsModal = document.getElementById('settings-modal')
        const settingsClose = document.getElementById('settings-close')
        const thinkingToggle = document.getElementById('thinking-toggle')

        // Load thinking preference from localStorage
        const showThinking = localStorage.getItem('showThinking')
        if (showThinking === 'false') {
            thinkingToggle.checked = false
            document.body.classList.add('hide-thinking')
        } else {
            // Default to true
            thinkingToggle.checked = true
            document.body.classList.remove('hide-thinking')
        }

        // Open settings modal
        if (settingsButton) {
            settingsButton.addEventListener('click', () => {
                settingsModal.style.display = 'flex'
            })
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
            })
        }
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

        // If autocomplete is visible, refresh it
        if (this.autocompleteVisible) {
            const currentQuery = this.messageInput.value.startsWith('/')
                ? this.messageInput.value.substring(1).toLowerCase()
                : ''
            this.showAutocomplete(currentQuery)
        }

        console.log('🔄 Command registry rebuilt:', this.commandRegistry.length, 'commands')
    }

    handleAutocompleteInput(e) {
        const value = this.messageInput.value

        // Show autocomplete when "/" is typed at the start
        if (value === '/') {
            this.showAutocomplete('')
        }
        // Filter autocomplete if it's visible and starts with "/"
        else if (value.startsWith('/') && !value.includes(' ')) {
            const query = value.substring(1).toLowerCase()
            this.showAutocomplete(query)
        }
        // Hide if user deleted the "/" or added a space
        else if (this.autocompleteVisible) {
            this.hideAutocomplete()
        }
    }

    handleAutocompleteKeydown(e) {
        if (!this.autocompleteVisible || this.autocompleteCommands.length === 0) {
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                this.autocompleteSelectedIndex =
                    (this.autocompleteSelectedIndex + 1) % this.autocompleteCommands.length
                this.renderAutocomplete()
                break

            case 'ArrowUp':
                e.preventDefault()
                this.autocompleteSelectedIndex =
                    this.autocompleteSelectedIndex <= 0
                        ? this.autocompleteCommands.length - 1
                        : this.autocompleteSelectedIndex - 1
                this.renderAutocomplete()
                break

            case 'Enter':
                if (this.autocompleteSelectedIndex >= 0) {
                    e.preventDefault()
                    const selected = this.autocompleteCommands[this.autocompleteSelectedIndex]
                    this.selectCommand(selected.name)
                }
                break

            case 'Tab':
                e.preventDefault()
                if (this.autocompleteSelectedIndex >= 0) {
                    const selected = this.autocompleteCommands[this.autocompleteSelectedIndex]
                    this.messageInput.value = selected.name
                    this.hideAutocomplete()
                } else if (this.autocompleteCommands.length > 0) {
                    // Tab with no selection: complete to first match
                    this.messageInput.value = this.autocompleteCommands[0].name
                    this.hideAutocomplete()
                }
                break

            case 'Escape':
                e.preventDefault()
                this.hideAutocomplete()
                break
        }
    }

    showAutocomplete(query) {
        // Rebuild registry if capabilities have loaded
        if (this.sessionCapabilities && this.commandRegistry.length === 6) {
            this.buildCommandRegistry()
        }

        // Filter commands
        this.autocompleteCommands = this.filterCommands(query)

        if (this.autocompleteCommands.length === 0) {
            this.hideAutocomplete()
            return
        }

        // Reset selection
        this.autocompleteSelectedIndex = -1

        // Position panel above input
        const inputRect = this.messageInput.getBoundingClientRect()
        this.autocompletePanel.style.left = inputRect.left + 'px'
        this.autocompletePanel.style.bottom = (window.innerHeight - inputRect.top + 10) + 'px'
        this.autocompletePanel.style.width = inputRect.width + 'px'

        // Render and show
        this.renderAutocomplete()
        this.autocompletePanel.classList.remove('hidden')
        this.autocompleteVisible = true
    }

    hideAutocomplete() {
        this.autocompletePanel.classList.add('hidden')
        this.autocompleteVisible = false
        this.autocompleteSelectedIndex = -1
        this.autocompleteCommands = []
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

    renderAutocomplete() {
        const html = this.autocompleteCommands.map((cmd, index) => {
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

        this.autocompletePanel.innerHTML = html

        // Add click handlers
        this.autocompletePanel.querySelectorAll('.autocomplete-item').forEach((item, index) => {
            item.addEventListener('click', () => {
                this.selectCommand(this.autocompleteCommands[index].name)
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

    selectCommand(commandName) {
        this.messageInput.value = commandName
        this.hideAutocomplete()
        this.messageInput.focus()
    }

    // ========== WebSocket Connection ==========

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/ws`

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

        // Add images if present (legacy pendingImages for backward compatibility)
        for (const img of this.pendingImages) {
            contentBlocks.push({
                type: 'image',
                source: {
                    type: 'base64',
                    media_type: img.media_type,
                    data: img.data
                },
                filename: img.filename
            })
        }

        // Add files (PDFs and documents) from pendingFiles
        for (const file of this.pendingFiles) {
            if (file.type === 'image') {
                // Image from drag & drop
                contentBlocks.push({
                    type: 'image',
                    source: {
                        type: 'base64',
                        media_type: file.media_type,
                        data: file.data
                    },
                    filename: file.filename
                })
            } else if (file.type === 'pdf') {
                // PDF as document block
                contentBlocks.push({
                    type: 'document',
                    source: {
                        type: 'base64',
                        media_type: 'application/pdf',
                        data: file.data
                    },
                    filename: file.filename
                })
            } else if (file.type === 'document') {
                // Document as text reference (Claude will use Read tool)
                contentBlocks.push({
                    type: 'text',
                    text: `[Attached file: ${file.filename} (${(file.size / 1024).toFixed(1)} KB) - saved to ${file.saved_path}]`
                })
            }
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
            // Display user message with images
            this.addUserMessageWithImages(content, this.pendingImages)
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

        // Clear input, images, files, and reset height
        this.messageInput.value = ''
        this.messageInput.style.height = 'auto'
        this.pendingImages = []
        this.pendingFiles = []
        this.renderImagePreviews()
        this.renderFilePreviews()

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

    addImageToMessage(file) {
        // Validate size (5MB limit)
        if (file.size > 5 * 1024 * 1024) {
            alert('Image too large. Maximum size is 5MB per image.')
            return
        }

        // Convert to base64
        const reader = new FileReader()
        reader.onload = (e) => {
            const dataUrl = e.target.result
            const [header, base64Data] = dataUrl.split(',')
            const mediaType = header.match(/:(.*?);/)[1]

            // Validate media type
            const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
            if (!allowedTypes.includes(mediaType)) {
                alert(`Unsupported image format: ${mediaType}. Please use PNG, JPEG, GIF, or WebP.`)
                return
            }

            // Store image data
            const imageData = {
                data: base64Data,
                media_type: mediaType,
                size: file.size,
                filename: `screenshot_${Date.now()}.${mediaType.split('/')[1]}`
            }

            this.pendingImages.push(imageData)

            console.log(`📷 Image added: ${imageData.filename} (${(file.size / 1024).toFixed(1)} KB)`)

            // Show preview
            this.renderImagePreviews()
        }
        reader.onerror = (error) => {
            console.error('Failed to read image file:', error)
            alert('Failed to read image file. Please try again.')
        }
        reader.readAsDataURL(file)
    }

    renderImagePreviews() {
        // Get or create preview container
        let previewContainer = document.getElementById('image-preview-container')
        if (!previewContainer) {
            // Create it before the input wrapper
            const inputContainer = document.querySelector('.input-container')
            const inputWrapper = document.querySelector('.input-wrapper')

            previewContainer = document.createElement('div')
            previewContainer.id = 'image-preview-container'
            previewContainer.className = 'image-preview-container'

            const previewsDiv = document.createElement('div')
            previewsDiv.className = 'image-previews'
            previewContainer.appendChild(previewsDiv)

            inputContainer.insertBefore(previewContainer, inputWrapper)
        }

        const previewsDiv = previewContainer.querySelector('.image-previews')

        // Clear existing previews
        previewsDiv.innerHTML = ''

        if (this.pendingImages.length === 0) {
            previewContainer.style.display = 'none'
            return
        }

        previewContainer.style.display = 'block'

        // Render each image preview
        this.pendingImages.forEach((img, index) => {
            const previewEl = document.createElement('div')
            previewEl.className = 'image-preview'

            const imgEl = document.createElement('img')
            imgEl.src = `data:${img.media_type};base64,${img.data}`
            imgEl.alt = img.filename

            const removeBtn = document.createElement('button')
            removeBtn.className = 'image-preview-remove'
            removeBtn.textContent = '×'
            removeBtn.title = 'Remove image'
            removeBtn.onclick = () => {
                this.removeImage(index)
            }

            previewEl.appendChild(imgEl)
            previewEl.appendChild(removeBtn)
            previewsDiv.appendChild(previewEl)
        })
    }

    removeImage(index) {
        this.pendingImages.splice(index, 1)
        this.renderImagePreviews()
        console.log(`🗑️ Image removed (${this.pendingImages.length} remaining)`)
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
            this.addImageToMessage(file)
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

        // Convert to base64 for sending to Claude
        const reader = new FileReader()
        reader.onload = (e) => {
            const dataUrl = e.target.result
            const [header, base64Data] = dataUrl.split(',')

            const fileData = {
                type: 'pdf',
                data: base64Data,
                media_type: 'application/pdf',
                size: file.size,
                filename: file.name,
                saved_path: uploadResult.path
            }

            this.pendingFiles.push(fileData)
            console.log(`📄 PDF added: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)

            // Show preview
            this.renderFilePreviews()
        }
        reader.onerror = (error) => {
            console.error('Failed to read PDF file:', error)
            alert('Failed to read PDF file. Please try again.')
        }
        reader.readAsDataURL(file)
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

        const fileData = {
            type: 'document',
            filename: file.name,
            media_type: file.type,
            size: file.size,
            saved_path: uploadResult.path
        }

        this.pendingFiles.push(fileData)
        console.log(`📎 Document added: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)

        // Show preview
        this.renderFilePreviews()
    }

    async uploadFile(file) {
        try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            })

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`)
            }

            const result = await response.json()
            console.log(`✅ File uploaded: ${result.path}`)
            return result

        } catch (error) {
            console.error('File upload failed:', error)
            alert(`Failed to upload file: ${error.message}`)
            return null
        }
    }

    renderFilePreviews() {
        // Combine images and files for unified preview
        // For now, keep using the existing renderImagePreviews for images
        // and add a new preview area for other files

        // Get or create file preview container
        let previewContainer = document.getElementById('file-preview-container')
        if (!previewContainer) {
            const inputContainer = document.querySelector('.input-container')
            const inputWrapper = document.querySelector('.input-wrapper')

            previewContainer = document.createElement('div')
            previewContainer.id = 'file-preview-container'
            previewContainer.className = 'file-preview-container'

            const previewsDiv = document.createElement('div')
            previewsDiv.className = 'file-previews'
            previewContainer.appendChild(previewsDiv)

            inputContainer.insertBefore(previewContainer, inputWrapper)
        }

        const previewsDiv = previewContainer.querySelector('.file-previews')
        previewsDiv.innerHTML = ''

        if (this.pendingFiles.length === 0) {
            previewContainer.style.display = 'none'
            return
        }

        previewContainer.style.display = 'block'

        // Render each file preview
        this.pendingFiles.forEach((file, index) => {
            const previewEl = document.createElement('div')
            previewEl.className = 'file-preview'

            // Get icon based on type
            let icon = '📄'
            if (file.type === 'pdf') icon = '📕'
            else if (file.type === 'document') {
                if (file.filename.endsWith('.docx') || file.filename.endsWith('.doc')) icon = '📘'
                else if (file.filename.endsWith('.xlsx') || file.filename.endsWith('.xls')) icon = '📗'
                else if (file.filename.endsWith('.pptx') || file.filename.endsWith('.ppt')) icon = '📙'
                else if (file.filename.endsWith('.txt')) icon = '📝'
            }

            previewEl.innerHTML = `
                <div class="file-preview-icon">${icon}</div>
                <div class="file-preview-info">
                    <div class="file-preview-name">${file.filename}</div>
                    <div class="file-preview-size">${(file.size / 1024).toFixed(1)} KB</div>
                </div>
            `

            const removeBtn = document.createElement('button')
            removeBtn.className = 'file-preview-remove'
            removeBtn.textContent = '×'
            removeBtn.title = 'Remove file'
            removeBtn.onclick = () => {
                this.removeFile(index)
            }

            previewEl.appendChild(removeBtn)
            previewsDiv.appendChild(previewEl)
        })
    }

    removeFile(index) {
        this.pendingFiles.splice(index, 1)
        this.renderFilePreviews()
        console.log(`🗑️ File removed (${this.pendingFiles.length} remaining)`)
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

            // Disable send button if no input
            if (!this.messageInput.value.trim()) {
                this.sendButton.disabled = true
            }

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
            <div class="message-content">${this.escapeHtml(content)}</div>
        `
        this.conversationEl.appendChild(messageEl)
        this.scrollToBottom()
    }

    addUserMessageWithImages(content, images) {
        const messageEl = document.createElement('div')
        messageEl.className = 'user-message message-fade-in'

        // Build message HTML
        let messageHtml = `
            <div class="message-header">
                <span class="user-icon">👤</span>
                <span class="user-name">You</span>
            </div>
        `

        // Add text content if present
        if (content) {
            messageHtml += `<div class="message-content">${this.escapeHtml(content)}</div>`
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

        messageEl.innerHTML = messageHtml
        this.conversationEl.appendChild(messageEl)
        this.scrollToBottom()
    }

    addHintMessage(content) {
        const hintMsg = document.createElement('div')
        hintMsg.className = 'message hint-message message-fade-in'
        hintMsg.innerHTML = `
            <div class="message-header">
                <span class="hint-icon">💡</span>
                <span class="hint-label">HINT</span>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `
        this.conversationEl.appendChild(hintMsg)
        this.scrollToBottom()
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
        this.scrollToBottom()
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

    handleMessage(msg) {
        console.log('📨 Received:', msg.type, msg.id || '', msg)
        console.log('🔷 [FRONTEND] Handling message type:', msg.type)

        switch (msg.type) {
            case 'connected':
                console.log('🔷 [FRONTEND] Got "connected" event, Session ID:', msg.session_id)
                // Clear any old messages from previous session
                this.conversationEl.innerHTML = ''
                console.log('🔷 [FRONTEND] Calling showWelcomeMessage()...')
                this.showWelcomeMessage()
                console.log('🔷 [FRONTEND] showWelcomeMessage() completed')

                // Hide loading status - agent is ready
                this.hideServerStatus()
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
                        Powered by <strong>Claude Sonnet 4.5</strong>, I can help you with
                        software development, database operations, document processing, and more.
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
                            <span class="qs-text">Connected to MCP servers</span>
                        </div>
                    </div>
                </div>
            </div>
        `
        this.conversationEl.appendChild(welcomeEl)
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
        this.scrollToBottom()
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
        this.scrollToBottom()
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
        this.scrollToBottom()
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

        this.scrollToBottom()
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
        this.scrollToBottom()

        // Reset UI to idle state
        this.setAgentWorking(false)
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
        return scrollHeight - scrollTop - clientHeight < threshold
    }

    scrollToBottom() {
        // Only auto-scroll if user is already at bottom
        if (this.isScrolledToBottom()) {
            requestAnimationFrame(() => {
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                })
            })
        }
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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.bassiClient = new BassiWebClient()
})
