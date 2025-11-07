# Multimodal File Upload Support

**Status:** Implemented
**Target:** V3 Web UI
**Priority:** High

## Overview

Enable users to upload files (images, PDFs, documents) to the chat interface via:
1. **Clipboard paste** (CTRL-V / CMD-V) - for images
2. **Drag & Drop** - for all file types

This allows Claude to analyze visual content, read PDFs, and access document files.

## User Stories

### Image Paste
> As a user, I want to create a screenshot (CMD+SHIFT+4 on macOS / Windows+Shift+S on Windows), copy it to clipboard, and paste it into the Bassi chat using CTRL-V (or CMD-V), so that Claude can analyze the image content without me having to save it as a file first.

### Drag & Drop Files
> As a user, I want to drag and drop files (images, PDFs, documents) from my file explorer directly into the chat interface, so that Claude can process them without me having to manually upload or reference file paths.

## Current State Analysis

### Frontend (bassi/static/app.js)
- Text-only input via `<textarea id="message-input">`
- Message format: `{type: 'user_message', content: 'text string'}`
- No image handling
- No paste event listeners

### Backend (bassi/core_v3/web_server_v3.py)
- Processes text messages only
- Uses Claude Agent SDK (BassiAgentSession)
- No image storage or processing

### Claude API Capabilities

#### Images
- **Supports:** Images via content blocks in Messages API
- **Formats:** PNG, JPEG, GIF, WebP
- **Max Size:** 5MB per image (15MB total per request)
- **Encoding:** Base64 with media type specification
- **Content Block Format:**
  ```json
  {
    "type": "image",
    "source": {
      "type": "base64",
      "media_type": "image/png",
      "data": "iVBORw0KGgo..."
    }
  }
  ```

#### PDFs
- **Supports:** PDF documents via document blocks (since October 2024)
- **Max Size:** 32MB per PDF
- **Encoding:** Base64 with media type specification
- **Content Block Format:**
  ```json
  {
    "type": "document",
    "source": {
      "type": "base64",
      "media_type": "application/pdf",
      "data": "JVBERi0xLjQ..."
    }
  }
  ```

#### Other Documents
- **Not directly supported:** DOCX, XLSX, PPTX, TXT, etc.
- **Strategy:** Store file to `_DATA_FROM_USER/`, send file reference as text
- **Claude Access:** Uses Read tool to access file content when needed

## Design

### File Handling Strategy

| File Type | Size Limit | Encoding | Sent To Claude As | Storage |
|-----------|------------|----------|-------------------|---------|
| **Images** (PNG, JPEG, GIF, WebP) | 5MB | Base64 | `image` content block | `_DATA_FROM_USER/` |
| **PDFs** | 32MB | Base64 | `document` content block | `_DATA_FROM_USER/` |
| **Documents** (DOCX, XLSX, PPTX, TXT) | 100MB | Binary | Text reference + file path | `_DATA_FROM_USER/` |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User Actions:                                               │
│ 1. Screenshot → Clipboard → CTRL-V/CMD-V                   │
│ 2. Drag file from explorer → Drop onto chat                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend (app.js)                                           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 1. Input Event Handlers                                 │ │
│ │    a. Paste Event (images only)                         │ │
│ │       - Capture clipboard data                          │ │
│ │       - Extract image files                             │ │
│ │       - Convert to base64                               │ │
│ │    b. Drag & Drop Events (all files)                    │ │
│ │       - dragenter/dragover (visual feedback)            │ │
│ │       - drop (process files)                            │ │
│ │       - Handle: images, PDFs, documents                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 2. File Processing                                      │ │
│ │    - Images (< 5MB): Base64 encode inline               │ │
│ │    - PDFs (< 32MB): Upload to server, base64 encode    │ │
│ │    - Documents: Upload to server, get file path         │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 3. File Preview Component                               │ │
│ │    - Thumbnails for images                              │ │
│ │    - Icons for PDFs/documents                           │ │
│ │    - File name, size, type                              │ │
│ │    - Remove button                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 4. Message Sending                                      │ │
│ │    - Combine text + files                               │ │
│ │    - Send as content blocks array                       │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket
                       │ {type: 'user_message', content: [
                       │   {type: 'text', text: '...'},
                       │   {type: 'image', source: {...}, ...}
                       │ ]}
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend (web_server_v3.py)                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 1. File Upload Endpoint (POST /api/upload)              │ │
│ │    - Accept multipart/form-data                         │ │
│ │    - Validate file type/size                            │ │
│ │    - Save to _DATA_FROM_USER/                           │ │
│ │    - Return file metadata (path, size, type)            │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 2. Message Processing                                   │ │
│ │    - Accept content blocks array                        │ │
│ │    - Handle: text, image, document blocks               │ │
│ │    - Validate sizes/formats                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 3. File Storage                                         │ │
│ │    - Images: Save + send as base64                      │ │
│ │    - PDFs: Save + send as base64                        │ │
│ │    - Documents: Save + send file reference              │ │
│ │    - Unique filenames (timestamp + original name)       │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 4. SDK Integration                                      │ │
│ │    - Pass content blocks to BassiAgentSession          │ │
│ │    - Agent SDK formats for Claude API                   │ │
│ │    - Document blocks for PDFs                           │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Claude API (via Agent SDK)                                  │
│ - Receives message with image content blocks               │
│ - Processes visual content                                 │
│ - Returns analysis/response                                │
└─────────────────────────────────────────────────────────────┘
```

### Message Protocol Update

**Before (text-only):**
```json
{
  "type": "user_message",
  "content": "What is in this image?"
}
```

**After (multimodal):**
```json
{
  "type": "user_message",
  "content": [
    {
      "type": "text",
      "text": "What is in this image?"
    },
    {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": "image/png",
        "data": "iVBORw0KGgoAAAANSUhEUgA..."
      },
      "filename": "screenshot_20250106_143022.png"
    }
  ]
}
```

**Backward Compatibility:**
- Accept both string and array for `content`
- If string: Convert to `[{type: 'text', text: content}]`
- If array: Use as-is

**Supported Prompt Types:**
1. **Text-only** (existing behavior, backward compatible):
   ```json
   {
     "type": "user_message",
     "content": "What is the capital of France?"
   }
   ```
   OR
   ```json
   {
     "type": "user_message",
     "content": [{"type": "text", "text": "What is the capital of France?"}]
   }
   ```

2. **Image-only** (new):
   ```json
   {
     "type": "user_message",
     "content": [
       {
         "type": "image",
         "source": {"type": "base64", "media_type": "image/png", "data": "..."},
         "filename": "screenshot.png"
       }
     ]
   }
   ```

3. **Text + Image(s)** (new):
   ```json
   {
     "type": "user_message",
     "content": [
       {"type": "text", "text": "What is in this screenshot?"},
       {
         "type": "image",
         "source": {"type": "base64", "media_type": "image/png", "data": "..."},
         "filename": "screenshot.png"
       }
     ]
   }
   ```

### Frontend Implementation

#### 1. Paste Event Handler
```javascript
// Add to BassiWebClient.init()
this.messageInput.addEventListener('paste', (e) => {
    this.handlePaste(e)
})
```

#### 2. Image Processing
```javascript
handlePaste(e) {
    const items = e.clipboardData?.items
    if (!items) return

    // Look for images
    for (let item of items) {
        if (item.type.startsWith('image/')) {
            e.preventDefault()

            const file = item.getAsFile()
            if (file) {
                this.addImageToMessage(file)
            }
        }
    }
}

addImageToMessage(file) {
    // Validate size (5MB limit)
    if (file.size > 5 * 1024 * 1024) {
        alert('Image too large. Max 5MB per image.')
        return
    }

    // Convert to base64
    const reader = new FileReader()
    reader.onload = (e) => {
        const dataUrl = e.target.result
        const [header, base64Data] = dataUrl.split(',')
        const mediaType = header.match(/:(.*?);/)[1]

        // Store image data
        this.pendingImages.push({
            data: base64Data,
            media_type: mediaType,
            size: file.size,
            filename: `screenshot_${Date.now()}.${mediaType.split('/')[1]}`
        })

        // Show preview
        this.renderImagePreviews()
    }
    reader.readAsDataURL(file)
}
```

#### 3. Image Preview UI
```html
<!-- Add above textarea in input-container -->
<div id="image-preview-container" style="display: none;">
    <div class="image-previews">
        <!-- Thumbnails will be added here -->
    </div>
</div>
```

```css
.image-previews {
    display: flex;
    gap: 8px;
    padding: 8px;
    flex-wrap: wrap;
}

.image-preview {
    position: relative;
    width: 80px;
    height: 80px;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid #ddd;
}

.image-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.image-preview-remove {
    position: absolute;
    top: 2px;
    right: 2px;
    background: rgba(0,0,0,0.7);
    color: white;
    border: none;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    cursor: pointer;
}
```

#### 4. Send Message with Images
```javascript
sendMessage() {
    const text = this.messageInput.value.trim()

    // Build content blocks
    const contentBlocks = []

    // Add text if present
    if (text) {
        contentBlocks.push({
            type: 'text',
            text: text
        })
    }

    // Add images if present
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

    // Must have at least text or image
    if (contentBlocks.length === 0) return

    // Send to server
    this.ws.send(JSON.stringify({
        type: 'user_message',
        content: contentBlocks
    }))

    // Clear input and images
    this.messageInput.value = ''
    this.pendingImages = []
    this.renderImagePreviews()
}
```

### Backend Implementation

#### 1. Message Processing Update
```python
# In web_server_v3.py, _process_message()

if msg_type == "user_message":
    content = data.get("content", "")

    # Normalize content to content blocks array
    if isinstance(content, str):
        # Text-only (backward compatible)
        content_blocks = [{"type": "text", "text": content}]
    elif isinstance(content, list):
        # Multimodal content
        content_blocks = content
    else:
        logger.error(f"Invalid content type: {type(content)}")
        return

    # Process images and save to disk
    processed_blocks = []
    for block in content_blocks:
        if block.get("type") == "text":
            processed_blocks.append(block)
        elif block.get("type") == "image":
            # Save image to _DATA_FROM_USER/
            saved_path = await self._save_image(block)
            # Keep image block for Claude API
            processed_blocks.append({
                "type": "image",
                "source": block["source"],
                "saved_path": saved_path  # Add local path for reference
            })

    # Send to agent session
    async for message in session.query_multimodal(processed_blocks):
        # ... existing streaming logic
```

#### 2. Image Storage
```python
async def _save_image(self, image_block: dict) -> str:
    """
    Save image to _DATA_FROM_USER/ folder.

    Args:
        image_block: Image content block with base64 data

    Returns:
        Path to saved image file
    """
    import base64
    from pathlib import Path

    # Get image data
    source = image_block.get("source", {})
    base64_data = source.get("data", "")
    media_type = source.get("media_type", "image/png")
    filename = image_block.get("filename", f"image_{int(time.time())}.png")

    # Decode base64
    image_bytes = base64.b64decode(base64_data)

    # Save to _DATA_FROM_USER/
    data_dir = Path.cwd() / "_DATA_FROM_USER"
    data_dir.mkdir(exist_ok=True)

    save_path = data_dir / filename
    save_path.write_bytes(image_bytes)

    logger.info(f"Saved image: {save_path} ({len(image_bytes)} bytes)")

    return str(save_path)
```

#### 3. Agent SDK Integration
```python
# In agent_session.py

async def query_multimodal(
    self,
    content_blocks: list[dict],
    session_id: str | None = None
):
    """
    Send multimodal query (text + images) to Claude.

    Args:
        content_blocks: List of content blocks (text, image)
        session_id: Optional session ID for context

    Yields:
        StreamEvent objects from Claude Agent SDK
    """
    # Agent SDK handles content blocks natively
    # Just pass them through
    async for event in self.client.stream(content_blocks, session_id=session_id):
        yield event
```

### Conversation Display

#### User Message with Image
```html
<div class="user-message">
    <div class="message-header">
        <span class="user-icon">👤</span>
        <span>You</span>
    </div>
    <div class="message-content">
        <div class="message-text">What is in this screenshot?</div>
        <div class="message-images">
            <img src="data:image/png;base64,iVBORw0..."
                 alt="Uploaded image"
                 class="message-image">
        </div>
    </div>
</div>
```

## Implementation Plan

### Phase 1: Frontend Basic Support
1. ✅ Add paste event listener
2. ✅ Image to base64 conversion
3. ✅ Image preview component
4. ✅ Send multimodal messages
5. ✅ Display images in conversation

### Phase 2: Backend Integration
1. ✅ Accept content blocks array
2. ✅ Validate image size/format
3. ✅ Save images to _DATA_FROM_USER/
4. ✅ Pass to Agent SDK
5. ✅ Handle backward compatibility

### Phase 3: Enhancements
1. ⬜ Drag-and-drop support
2. ⬜ File picker button
3. ⬜ Image compression (if > 5MB)
4. ⬜ Multiple image support
5. ⬜ Image zoom/preview modal

## Testing Strategy

### Manual Testing
1. Screenshot → Paste → Send
2. Copy image from browser → Paste → Send
3. Multiple images in one message
4. Text + image combination
5. Image-only message
6. Large image (>5MB) rejection

### Automated Tests
```python
# tests/test_multimodal.py

async def test_image_paste():
    """Test image paste and processing"""
    # Create mock image data
    image_data = create_test_image_base64()

    # Send multimodal message
    content = [
        {"type": "text", "text": "What is this?"},
        {"type": "image", "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": image_data
        }}
    ]

    # Verify image saved
    saved_files = list(Path("_DATA_FROM_USER").glob("*.png"))
    assert len(saved_files) > 0
```

## Security Considerations

1. **Size Limits:** Enforce 5MB per image, 15MB total
2. **Format Validation:** Only allow PNG, JPEG, GIF, WebP
3. **Sanitization:** Validate base64 data before decoding
4. **Storage Quota:** Monitor _DATA_FROM_USER/ folder size
5. **XSS Prevention:** Sanitize filenames, don't render user-provided HTML

## Performance Considerations

1. **Image Compression:** Compress large images client-side before sending
2. **Lazy Loading:** Don't load full-size images in chat history
3. **Caching:** Cache base64 conversions to avoid re-encoding
4. **Cleanup:** Periodically clean old images from _DATA_FROM_USER/

## User Experience

### Happy Path
1. User takes screenshot (CMD+SHIFT+4)
2. User presses CTRL+V in chat
3. Thumbnail preview appears above input
4. User types question "What is in this screenshot?"
5. User sends message
6. Claude analyzes image and responds

### Error Cases
- **Image too large:** Show alert "Image too large. Max 5MB."
- **Unsupported format:** Show alert "Unsupported format. Use PNG, JPEG, GIF, or WebP."
- **Network error:** Retry with exponential backoff
- **API error:** Show error message from Claude

## Future Enhancements

1. **OCR Support:** Extract text from images automatically
2. **Image Editing:** Crop, rotate, annotate before sending
3. **Gallery View:** Browse all images in conversation
4. **Export:** Download images from conversation
5. **PDF Support:** Paste PDF pages as images

## References

- Claude API Documentation: https://docs.anthropic.com/claude/reference/messages-streaming
- FileReader API: https://developer.mozilla.org/en-US/docs/Web/API/FileReader
- Clipboard API: https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API
- Agent SDK: https://github.com/anthropics/claude-agent-sdk
