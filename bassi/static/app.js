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
        this.textBuffers = new Map()         // id -> accumulated text
        this.currentMessage = null           // Current assistant message container
        this.totalCost = 0                   // Cumulative cost
        this.verboseLevel = this.loadVerboseLevel()
        this.isAgentWorking = false          // Track if agent is processing

        // Streaming markdown renderer
        this.markdownRenderer = null
        this.renderDebounceTimers = new Map()  // id -> timer

        // DOM elements
        this.conversationEl = document.getElementById('conversation')
        this.messageInput = document.getElementById('message-input')
        this.sendButton = document.getElementById('send-button')
        this.verboseLevelSelect = document.getElementById('verbose-level')
        this.statusIndicator = document.getElementById('status-indicator')
        this.connectionStatus = document.getElementById('connection-status')

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
            if (this.isAgentWorking) {
                this.stopAgent()
            } else {
                this.sendMessage()
            }
        })
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!this.isAgentWorking) {
                    this.sendMessage()
                }
            }
        })

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto'
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px'
        })

        if (this.verboseLevelSelect) {
            this.verboseLevelSelect.value = this.verboseLevel
            this.verboseLevelSelect.addEventListener('change', (e) => {
                this.setVerboseLevel(e.target.value)
            })
        }

        // Connect WebSocket
        this.connect()
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
            this.isConnected = true
            this.reconnectAttempts = 0
            this.updateConnectionStatus('connected')
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
            try {
                const data = JSON.parse(event.data)
                this.handleMessage(data)
            } catch (e) {
                console.error('Failed to parse message:', e)
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

    // ========== Message Sending ==========

    sendMessage() {
        const content = this.messageInput.value.trim()
        if (!content || !this.isConnected) return

        // Add user message to UI
        this.addUserMessage(content)

        // IMPORTANT: Reset currentMessage so NEW assistant message is created at BOTTOM
        this.currentMessage = null
        this.blocks.clear()
        this.textBuffers.clear()

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'user_message',
            content: content
        }))

        // Clear input and reset height
        this.messageInput.value = ''
        this.messageInput.style.height = 'auto'

        // Set agent as working and update button
        this.setAgentWorking(true)
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

    setAgentWorking(working) {
        this.isAgentWorking = working

        if (working) {
            // Transform to STOP button
            this.sendButton.textContent = '⏹ Stop'
            this.sendButton.classList.add('stop-mode')
            this.messageInput.disabled = true
        } else {
            // Transform back to SEND button
            this.sendButton.textContent = '↑ Send'
            this.sendButton.classList.remove('stop-mode')
            this.messageInput.disabled = false
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

        switch (msg.type) {
            case 'connected':
                console.log('Session ID:', msg.session_id)
                this.showWelcomeMessage()
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
                this.handleStatus(msg)
                break

            case 'error':
                this.handleError(msg)
                break

            case 'system_message':
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
        welcomeEl.className = 'system-message message-fade-in'
        welcomeEl.innerHTML = `
            <div class="welcome-content">
                <h1>🤖 Bassi Agent</h1>
                <p>Your AI-powered assistant with Claude Agent SDK</p>
                <div class="welcome-features">
                    <div class="feature">✨ Real-time streaming</div>
                    <div class="feature">🛠️ Tool execution</div>
                    <div class="feature">📊 Token usage tracking</div>
                </div>
            </div>
        `
        this.conversationEl.appendChild(welcomeEl)
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
        // Only show in verbose mode
        if (this.verboseLevel === 'minimal') return

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
        // Skip if verbose level is minimal
        if (this.verboseLevel === 'minimal') {
            return
        }

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

        // Tool icons mapping
        const toolIcons = {
            'Bash': '💻',
            'ReadFile': '📄',
            'WriteFile': '✍️',
            'EditFile': '✏️',
            'Grep': '🔍',
            'Task': '📋',
            'default': '🛠️'
        }

        const icon = toolIcons[msg.tool_name] || toolIcons.default

        // Create tool panel
        const toolPanel = document.createElement('div')
        toolPanel.id = msg.id
        toolPanel.className = 'tool-call tool-running'
        toolPanel.innerHTML = `
            <div class="tool-header">
                <span class="tool-icon">${icon}</span>
                <span class="tool-name">${this.escapeHtml(msg.tool_name)}</span>
                <span class="tool-status">Running...</span>
                <span class="tool-toggle">▼</span>
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

        // Add toggle functionality
        const header = toolPanel.querySelector('.tool-header')
        header.addEventListener('click', () => {
            toolPanel.classList.toggle('collapsed')
            const toggle = toolPanel.querySelector('.tool-toggle')
            toggle.textContent = toolPanel.classList.contains('collapsed') ? '▶' : '▼'
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
    }

    // ========== Usage Handler ==========

    handleUsage(msg) {
        const { input_tokens, output_tokens, total_cost_usd } = msg
        this.totalCost += total_cost_usd

        // Find the current message or last message
        const targetMessage = this.currentMessage || this.conversationEl.lastElementChild

        if (!targetMessage || !targetMessage.classList.contains('assistant-message')) {
            return
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
        console.log('📢 System message:', msg.content)
        const systemEl = document.createElement('div')
        systemEl.className = 'system-message message-fade-in'
        systemEl.innerHTML = `
            <div class="system-content">
                ${this.formatMarkdown(msg.content)}
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
        return localStorage.getItem('bassi_verbose_level') || 'normal'
    }

    setVerboseLevel(level) {
        this.verboseLevel = level
        localStorage.setItem('bassi_verbose_level', level)
        console.log('Verbose level set to:', level)
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
