/**
 * bassi Web UI Client
 *
 * Handles:
 * - WebSocket connection
 * - Message sending/receiving
 * - Streaming markdown rendering
 * - Tool call display
 * - UI updates
 */

class BassiWebClient {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.currentAssistantMessage = null;
        this.markdownBuffer = '';

        // DOM elements
        this.conversationEl = document.getElementById('conversation');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');

        this.init();
    }

    init() {
        // Setup event listeners
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
        });

        // Connect to WebSocket
        this.connect();
    }

    connect() {
        const wsUrl = `ws://${window.location.host}/ws`;
        console.log('Connecting to WebSocket:', wsUrl);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => this.onConnected();
        this.ws.onmessage = (event) => this.onMessage(event);
        this.ws.onclose = () => this.onDisconnected();
        this.ws.onerror = (error) => this.onError(error);
    }

    onConnected() {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.updateConnectionStatus('online', 'Connected');
        this.sendButton.disabled = false;

        // Remove welcome message if exists
        const welcome = this.conversationEl.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }
    }

    onDisconnected() {
        console.log('WebSocket disconnected');
        this.isConnected = false;
        this.updateConnectionStatus('offline', 'Disconnected');
        this.sendButton.disabled = true;

        // Attempt reconnection after 3 seconds
        setTimeout(() => this.connect(), 3000);
    }

    onError(error) {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('offline', 'Connection error');
    }

    onMessage(event) {
        const data = JSON.parse(event.data);
        console.log('Received:', data);

        switch (data.type) {
            case 'connected':
                // Initial connection message
                break;

            case 'content_delta':
                this.handleContentDelta(data);
                break;

            case 'tool_call_start':
                this.handleToolCallStart(data);
                break;

            case 'tool_call_end':
                this.handleToolCallEnd(data);
                break;

            case 'message_complete':
                this.handleMessageComplete(data);
                break;

            case 'status':
                this.handleStatus(data);
                break;

            case 'error':
                this.handleError(data);
                break;

            default:
                console.warn('Unknown message type:', data.type);
        }
    }

    updateConnectionStatus(status, text) {
        this.statusIndicator.className = `status-dot ${status}`;
        this.statusText.textContent = text;
    }

    sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || !this.isConnected) return;

        // Display user message
        this.addUserMessage(content);

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'user_message',
            content: content
        }));

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.messageInput.focus();
    }

    addUserMessage(content) {
        const messageEl = this.createMessageElement('user', content);
        this.conversationEl.appendChild(messageEl);
        this.scrollToBottom();
    }

    createMessageElement(role, content = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });

        const icon = role === 'user' ? '👤' : '🤖';
        const label = role === 'user' ? 'You' : 'Assistant';

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="icon">${icon}</span>
                <span class="label">${label}</span>
                <span class="timestamp">${timestamp}</span>
            </div>
            <div class="message-content markdown">${this.escapeHtml(content)}</div>
        `;

        return messageDiv;
    }

    handleContentDelta(data) {
        // Create assistant message if doesn't exist
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createMessageElement('assistant');
            this.conversationEl.appendChild(this.currentAssistantMessage);

            // Add streaming indicator
            const header = this.currentAssistantMessage.querySelector('.message-header');
            const statusEl = document.createElement('span');
            statusEl.className = 'status';
            statusEl.textContent = '● streaming...';
            header.appendChild(statusEl);

            // Clear markdown buffer
            this.markdownBuffer = '';
        }

        // Append text to buffer
        this.markdownBuffer += data.text;

        // Update display with plain text during streaming
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        contentEl.textContent = this.markdownBuffer;

        this.scrollToBottom();
    }

    handleToolCallStart(data) {
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createMessageElement('assistant');
            this.conversationEl.appendChild(this.currentAssistantMessage);
        }

        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const toolCallEl = this.createToolCallElement(data.tool_name, data.input);
        contentEl.appendChild(toolCallEl);

        this.scrollToBottom();
    }

    handleToolCallEnd(data) {
        // Find the tool call element and update it
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const toolCallEl = contentEl.querySelector(`[data-tool="${data.tool_name}"]`);

        if (toolCallEl) {
            const outputEl = toolCallEl.querySelector('.tool-output pre');
            outputEl.textContent = this.formatToolOutput(data.output);

            // Update tool call status
            toolCallEl.classList.add('completed');
            if (!data.success) {
                toolCallEl.classList.add('error');
            }
        }

        this.scrollToBottom();
    }

    handleMessageComplete(data) {
        if (!this.currentAssistantMessage) return;

        // Remove streaming indicator
        const statusEl = this.currentAssistantMessage.querySelector('.status');
        if (statusEl) {
            statusEl.remove();
        }

        // Render accumulated markdown
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        if (this.markdownBuffer) {
            try {
                const html = marked.parse(this.markdownBuffer);
                contentEl.innerHTML = html;

                // Highlight code blocks with Prism
                contentEl.querySelectorAll('pre code').forEach((block) => {
                    Prism.highlightElement(block);
                });
            } catch (e) {
                console.error('Error parsing markdown:', e);
                contentEl.textContent = this.markdownBuffer;
            }
        }

        // Add usage stats
        const usageEl = this.createUsageStatsElement(data.usage);
        contentEl.appendChild(usageEl);

        // Reset current message
        this.currentAssistantMessage = null;
        this.markdownBuffer = '';

        this.scrollToBottom();
    }

    handleStatus(data) {
        this.updateConnectionStatus('online', data.message);
    }

    handleError(data) {
        console.error('Error from server:', data.message);

        // Display error message
        const errorEl = document.createElement('div');
        errorEl.className = 'message error-message';
        errorEl.innerHTML = `
            <div class="message-header">
                <span class="icon">⚠️</span>
                <span class="label">Error</span>
            </div>
            <div class="message-content">
                ${this.escapeHtml(data.message)}
            </div>
        `;
        this.conversationEl.appendChild(errorEl);

        this.currentAssistantMessage = null;
        this.markdownBuffer = '';
        this.scrollToBottom();
    }

    createToolCallElement(toolName, input) {
        const toolEl = document.createElement('div');
        toolEl.className = 'tool-call collapsed';
        toolEl.setAttribute('data-tool', toolName);

        const inputHtml = this.syntaxHighlightJSON(input);

        toolEl.innerHTML = `
            <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="icon">🔧</span>
                <span class="name">${this.escapeHtml(toolName)}</span>
                <span class="toggle">▼</span>
            </div>
            <div class="tool-body">
                <div class="tool-input">
                    <h4>Input:</h4>
                    <pre>${inputHtml}</pre>
                </div>
                <div class="tool-output">
                    <h4>Output:</h4>
                    <pre>Running...</pre>
                </div>
            </div>
        `;

        return toolEl;
    }

    createUsageStatsElement(usage) {
        const statsEl = document.createElement('div');
        statsEl.className = 'usage-stats';

        const duration = (usage.duration_ms / 1000).toFixed(1);
        const cost = usage.cost_usd.toFixed(4);

        statsEl.innerHTML = `
            <span class="stat">⏱️ ${duration}s</span>
            <span class="stat">💰 $${cost}</span>
        `;

        return statsEl;
    }

    syntaxHighlightJSON(obj) {
        let json = JSON.stringify(obj, null, 2);
        json = this.escapeHtml(json);

        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            (match) => {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    cls = /:$/.test(match) ? 'json-key' : 'json-string';
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
    }

    formatToolOutput(output) {
        if (typeof output === 'object') {
            return JSON.stringify(output, null, 2);
        }
        return String(output);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.conversationEl.scrollTop = this.conversationEl.scrollHeight;
    }
}


// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.bassiClient = new BassiWebClient();
});
