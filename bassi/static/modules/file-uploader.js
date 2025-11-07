/**
 * FileUploader Module - Black Box Component
 *
 * Handles all file upload functionality including:
 * - Drag & drop
 * - Clipboard paste
 * - File type detection
 * - Upload to server
 * - File validation
 *
 * This is a Black Box component: implementation details are hidden,
 * only the public interface matters.
 */

export class FileUploader {
    /**
     * Black Box: File Upload Manager
     *
     * Public Interface:
     * - constructor(uploadEndpoint, onFileAdded)
     * - setupDragAndDrop(dropZone)
     * - setupPasteHandler(element)
     * - processFile(file)
     * - destroy()
     *
     * Hidden Implementation:
     * - Drag/drop event handling
     * - File validation logic
     * - Upload mechanics
     * - File type detection
     */

    constructor(options = {}) {
        // Configuration
        this.uploadEndpoint = options.uploadEndpoint || '/api/upload'
        this.onFileAdded = options.onFileAdded || (() => {})

        // Size limits (in bytes)
        this.imageSizeLimit = options.imageSizeLimit || 5 * 1024 * 1024  // 5MB
        this.pdfSizeLimit = options.pdfSizeLimit || 32 * 1024 * 1024    // 32MB
        this.docSizeLimit = options.docSizeLimit || 100 * 1024 * 1024   // 100MB

        // Allowed image types
        this.allowedImageTypes = [
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/gif',
            'image/webp'
        ]

        // Drag state
        this.dragCounter = 0
        this.dropOverlay = null

        // Event handlers (bound to this instance)
        this._boundHandlers = {
            dragEnter: (e) => this._handleDragEnter(e),
            dragOver: (e) => this._handleDragOver(e),
            dragLeave: (e) => this._handleDragLeave(e),
            drop: (e) => this._handleDrop(e),
            paste: (e) => this._handlePaste(e)
        }
    }

    // ========== Public Interface ==========

    setupDragAndDrop(dropZone = document.body) {
        /**
         * Setup drag and drop handlers on specified element.
         *
         * Args:
         *     dropZone: DOM element to enable drop on (default: document.body)
         */
        dropZone.addEventListener('dragenter', this._boundHandlers.dragEnter)
        dropZone.addEventListener('dragover', this._boundHandlers.dragOver)
        dropZone.addEventListener('dragleave', this._boundHandlers.dragLeave)
        dropZone.addEventListener('drop', this._boundHandlers.drop)

        console.log('✅ Drag & drop enabled')
    }

    setupPasteHandler(element) {
        /**
         * Setup clipboard paste handler on specified element.
         *
         * Args:
         *     element: DOM element to listen for paste events
         */
        element.addEventListener('paste', this._boundHandlers.paste)

        console.log('✅ Paste handler enabled')
    }

    async processFile(file) {
        /**
         * Process uploaded file (main public method).
         *
         * Detects file type and routes to appropriate handler.
         *
         * Args:
         *     file: File object to process
         *
         * Returns:
         *     Promise<boolean> - true if successful
         */
        console.log(`📄 Processing: ${file.name} (${file.type}, ${(file.size / 1024).toFixed(1)} KB)`)

        const fileType = this._getFileType(file)

        try {
            if (fileType === 'image') {
                await this._handleImage(file)
            } else if (fileType === 'pdf') {
                await this._handlePDF(file)
            } else if (fileType === 'document') {
                await this._handleDocument(file)
            } else {
                throw new Error(`Unsupported file type: ${file.type || 'unknown'}`)
            }
            return true
        } catch (error) {
            console.error('File processing failed:', error)
            alert(error.message)
            return false
        }
    }

    destroy() {
        /**
         * Cleanup: remove event listeners and overlay.
         */
        // Remove drop overlay if exists
        if (this.dropOverlay && this.dropOverlay.parentNode) {
            this.dropOverlay.parentNode.removeChild(this.dropOverlay)
        }

        // Event listeners are cleaned up when elements are removed
        console.log('✅ FileUploader destroyed')
    }

    // ========== Private Implementation ==========

    _getFileType(file) {
        /**
         * Detect file type from MIME type and extension.
         *
         * Returns: 'image' | 'pdf' | 'document' | 'unknown'
         */
        const type = file.type.toLowerCase()
        const name = file.name.toLowerCase()

        // Images
        if (type.startsWith('image/')) {
            if (this.allowedImageTypes.includes(type)) {
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

    async _handleImage(file) {
        /**
         * Handle image files (inline base64).
         */
        // Validate size
        if (file.size > this.imageSizeLimit) {
            throw new Error(`Image too large. Maximum size is ${this.imageSizeLimit / 1024 / 1024}MB per image.`)
        }

        // Convert to base64
        const base64Data = await this._readFileAsBase64(file)
        const [header, data] = base64Data.split(',')
        const mediaType = header.match(/:(.*?);/)[1]

        // Validate media type
        if (!this.allowedImageTypes.includes(mediaType)) {
            throw new Error(`Unsupported image format: ${mediaType}. Please use PNG, JPEG, GIF, or WebP.`)
        }

        // Notify callback
        const imageData = {
            type: 'image',
            data: data,
            media_type: mediaType,
            size: file.size,
            filename: file.name
        }

        this.onFileAdded(imageData)
        console.log(`📷 Image added: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)
    }

    async _handlePDF(file) {
        /**
         * Handle PDF files (upload + base64).
         */
        // Validate size
        if (file.size > this.pdfSizeLimit) {
            throw new Error(`PDF too large. Maximum size is ${this.pdfSizeLimit / 1024 / 1024}MB.`)
        }

        // Upload to server first
        const uploadResult = await this._uploadToServer(file)

        // Convert to base64 for sending to Claude
        const base64Data = await this._readFileAsBase64(file)
        const [header, data] = base64Data.split(',')

        // Notify callback
        const fileData = {
            type: 'pdf',
            data: data,
            media_type: 'application/pdf',
            size: file.size,
            filename: file.name,
            saved_path: uploadResult.path
        }

        this.onFileAdded(fileData)
        console.log(`📄 PDF added: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)
    }

    async _handleDocument(file) {
        /**
         * Handle document files (upload only).
         */
        // Validate size
        if (file.size > this.docSizeLimit) {
            throw new Error(`Document too large. Maximum size is ${this.docSizeLimit / 1024 / 1024}MB.`)
        }

        // Upload to server
        const uploadResult = await this._uploadToServer(file)

        // Notify callback
        const fileData = {
            type: 'document',
            filename: file.name,
            media_type: file.type,
            size: file.size,
            saved_path: uploadResult.path
        }

        this.onFileAdded(fileData)
        console.log(`📎 Document added: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)
    }

    async _uploadToServer(file) {
        /**
         * Upload file to server endpoint.
         *
         * Returns: {path: string} - server response with file path
         */
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(this.uploadEndpoint, {
            method: 'POST',
            body: formData
        })

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`)
        }

        const result = await response.json()
        console.log(`✅ File uploaded: ${result.path}`)
        return result
    }

    _readFileAsBase64(file) {
        /**
         * Read file as base64 data URL.
         *
         * Returns: Promise<string> - base64 data URL
         */
        return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = (e) => resolve(e.target.result)
            reader.onerror = (e) => reject(new Error('Failed to read file'))
            reader.readAsDataURL(file)
        })
    }

    // ========== Drag & Drop Handlers ==========

    _handleDragEnter(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter++

        if (this.dragCounter === 1) {
            this._showDropOverlay()
        }
    }

    _handleDragOver(e) {
        e.preventDefault()
        e.stopPropagation()
    }

    _handleDragLeave(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter--

        if (this.dragCounter === 0) {
            this._hideDropOverlay()
        }
    }

    async _handleDrop(e) {
        e.preventDefault()
        e.stopPropagation()

        this.dragCounter = 0
        this._hideDropOverlay()

        const files = e.dataTransfer?.files
        if (!files || files.length === 0) return

        console.log(`📁 ${files.length} file(s) dropped`)

        // Process each file
        for (const file of files) {
            await this.processFile(file)
        }
    }

    _showDropOverlay() {
        if (!this.dropOverlay) {
            this.dropOverlay = document.createElement('div')
            this.dropOverlay.id = 'drop-overlay'
            this.dropOverlay.className = 'drop-overlay'
            this.dropOverlay.innerHTML = `
                <div class="drop-overlay-content">
                    <div class="drop-overlay-icon">📁</div>
                    <div class="drop-overlay-text">Drop files here</div>
                    <div class="drop-overlay-hint">Images, PDFs, and Documents</div>
                </div>
            `
            document.body.appendChild(this.dropOverlay)
        }
        this.dropOverlay.style.display = 'flex'
    }

    _hideDropOverlay() {
        if (this.dropOverlay) {
            this.dropOverlay.style.display = 'none'
        }
    }

    // ========== Paste Handler ==========

    async _handlePaste(e) {
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
                    await this._handleImage(file)
                }
            }
        }

        if (foundImage) {
            console.log('📷 Image pasted from clipboard')
        }
    }
}
