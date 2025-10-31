# Clipboard Image Paste - Feature Specification

**Feature**: Paste Images from Clipboard (Ctrl+V)
**Priority**: MEDIUM-HIGH ⭐⭐
**Phase**: 4
**Status**: Specification
**Version**: 1.0

---

## Overview

Allow users to paste images directly from clipboard into chat using Ctrl+V (Cmd+V on Mac). Images are sent to Claude Vision API for analysis.

**Depends On**: File handling infrastructure from Phase 3 (Drag & Drop)

---

## User Stories

### US-1: Paste Screenshot
**As a** user
**I want to** paste a screenshot directly
**So that** I can quickly ask questions about it

**Acceptance Criteria**:
- Ctrl+V pastes clipboard image
- Image preview appears immediately
- Can add text question
- Image sent to Claude Vision API

### US-2: Paste from Image Editor
**As a** user working in Photoshop/GIMP
**I want to** copy-paste images
**So that** I can get feedback without saving

**Acceptance Criteria**:
- Copy from any image editor
- Paste into chat
- Preview with dimensions
- Send to Claude

### US-3: Multiple Images
**As a** user
**I want to** paste multiple screenshots
**So that** I can compare or provide context

**Acceptance Criteria**:
- Paste multiple times before sending
- All images previewed
- Can remove individual images
- All sent together

---

## UI Design

### Paste Flow

**1. User presses Ctrl+V**:
```
[Clipboard contains image]
    ↓
[Image data extracted]
    ↓
[Preview appears above input]
    ↓
[User adds text (optional)]
    ↓
[Clicks Send]
    ↓
[Image + text sent to Claude]
```

### Image Preview
```
┌───────────────────────────────────────┐
│  ┌─ Image (1) ────────────────── [✕] ┐│
│  │ ┌────────────────┐           [✕]  ││
│  │ │ [Thumbnail]    │                ││
│  │ │ 1920x1080      │                ││
│  │ │ 245 KB         │                ││
│  │ └────────────────┘                ││
│  └────────────────────────────────────┘│
│                                        │
│  What's in this screenshot?  [Send]   │
└───────────────────────────────────────┘
```

---

## Technical Design

### Clipboard API

```javascript
class BassiWebClient {
    initClipboardPaste() {
        this.messageInput.addEventListener('paste', async (e) => {
            const items = e.clipboardData.items;

            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    await this.handleImagePaste(file);
                }
            }
        });
    }

    async handleImagePaste(file) {
        // Validate size
        if (file.size > 5 * 1024 * 1024) { // 5MB Claude limit
            this.showError('Image too large (max 5MB)');
            return;
        }

        // Read as data URL
        const reader = new FileReader();
        reader.onload = (e) => {
            const imageData = e.target.result;
            this.addImagePreview(file, imageData);
        };
        reader.readAsDataURL(file);
    }

    addImagePreview(file, dataUrl) {
        const preview = document.createElement('div');
        preview.className = 'image-preview';
        preview.innerHTML = `
            <img src="${dataUrl}" alt="Pasted image">
            <div class="image-info">
                <div>${file.name || 'Pasted image'}</div>
                <div>${this.formatSize(file.size)}</div>
            </div>
            <button class="remove-image">✕</button>
        `;

        this.imagesContainer.appendChild(preview);

        // Store for sending
        this.pastedImages.push({
            file: file,
            dataUrl: dataUrl
        });
    }
}
```

### Vision API Integration

```python
# bassi/agent.py

async def chat_with_images(
    self,
    message: str,
    images: list[dict]
) -> AsyncIterator[Any]:
    """
    Chat with image attachments

    Args:
        message: Text message
        images: List of {type: "image", data: base64, media_type: str}
    """
    # Build message with vision content
    content = []

    # Add images
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["media_type"],
                "data": img["data"]
            }
        })

    # Add text
    if message:
        content.append({
            "type": "text",
            "text": message
        })

    # Send to Claude Vision API
    await self.client.query(content)

    async for msg in self.client.receive_response():
        yield msg
```

---

## Image Formats

**Supported by Claude**:
- PNG
- JPEG
- WebP
- GIF (non-animated)

**Size Limits**:
- Max: 5MB (Claude API)
- Recommended: <1MB for performance

**Client-Side Compression**:
```javascript
async function compressImage(dataUrl, maxSize = 1024*1024) {
    const img = new Image();
    img.src = dataUrl;

    await img.decode();

    const canvas = document.createElement('canvas');
    let width = img.width;
    let height = img.height;

    // Resize if needed
    const maxDim = 2048;
    if (width > maxDim || height > maxDim) {
        if (width > height) {
            height = (height / width) * maxDim;
            width = maxDim;
        } else {
            width = (width / height) * maxDim;
            height = maxDim;
        }
    }

    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, width, height);

    // Compress
    return canvas.toDataURL('image/jpeg', 0.8);
}
```

---

## Conversation Display

### User Message with Image
```
┌────────────────────────────────────┐
│ 👤 You                             │
│                                    │
│ ┌──────────────┐                  │
│ │ [Screenshot] │                  │
│ │  640x480     │                  │
│ └──────────────┘                  │
│                                    │
│ What's wrong with this UI?        │
└────────────────────────────────────┘
```

### Assistant Response
```
┌────────────────────────────────────┐
│ 🤖 Assistant                       │
│                                    │
│ Looking at your screenshot, I can  │
│ see several UI issues:             │
│ 1. Button alignment is off...      │
│ 2. Text is cut off...              │
└────────────────────────────────────┘
```

---

## Privacy Considerations

**Important**: Images are sent to Claude API (external service)

**User Consent**:
- First paste: Show consent dialog
- Checkbox: "Don't ask again"
- Clear warning about external upload

**Consent Dialog**:
```
┌─ Send Image to Claude? ──────────┐
│                                   │
│ ⚠️  This image will be:           │
│   • Sent to Anthropic's servers   │
│   • Processed by Claude Vision    │
│   • Subject to Anthropic's ToS    │
│                                   │
│ Only paste images you're          │
│ comfortable sharing.              │
│                                   │
│ [Cancel]              [Send] [✓] │
│                  Don't ask again  │
└───────────────────────────────────┘
```

---

## Success Criteria

- [ ] Ctrl+V paste works
- [ ] Image preview clear and helpful
- [ ] Size validation (5MB limit)
- [ ] Compression for large images
- [ ] Vision API integration working
- [ ] Privacy consent shown
- [ ] Images display in conversation
- [ ] Multiple images supported
- [ ] Cross-browser compatibility

---

**Estimated Time**: 3-5 days
**Dependencies**:
- Phase 3 file infrastructure
- Claude Vision API access
- Image processing libraries
