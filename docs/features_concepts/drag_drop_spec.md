# Drag & Drop Documents - Feature Specification

**Feature**: Drag & Drop File Upload
**Priority**: HIGH ⭐⭐⭐
**Phase**: 3
**Status**: Specification
**Version**: 1.0

---

## Overview

Allow users to drag files from Finder/Explorer directly into the chat interface. Files are uploaded, processed, and included in the message to Claude.

**Foundation Feature**: Builds file handling infrastructure used by image paste (Phase 4)

---

## Supported File Types

### Phase 1
- **Images**: PNG, JPEG, WebP, GIF → Vision API
- **Text**: TXT, MD, PY, JS, JSON, etc. → Direct content
- **PDFs**: Extract text → Direct content

### Phase 2 (Future)
- **Documents**: DOCX, XLSX → Parse and extract
- **Archives**: ZIP → List contents
- **Audio/Video**: Transcription

---

## User Stories

### US-1: Quick File Upload
**As a** user
**I want to** drag a file into chat
**So that** I can quickly share it with Claude

**Acceptance Criteria**:
- Drag file from desktop
- Drop zone appears with visual feedback
- File preview shows immediately
- Can add text message with file
- Send button uploads and sends

### US-2: Multiple Files
**As a** user
**I want to** drag multiple files at once
**So that** I can share related documents together

**Acceptance Criteria**:
- Accept multiple files in one drop
- Show all previews
- Can remove individual files
- All files sent together

### US-3: File Validation
**As a** user
**I want** clear feedback for invalid files
**So that** I know what went wrong

**Acceptance Criteria**:
- Size limit enforced (10MB)
- Type validation with clear errors
- Helpful error messages

---

## UI Design

### Drop Zone States

**1. Idle (No Drag)**:
```
┌───────────────────────────────────────┐
│  Type your message...        [Send]   │
└───────────────────────────────────────┘
```

**2. Drag Over**:
```
┌───────────────────────────────────────┐
│  ┌─────────────────────────────────┐  │
│  │  📎 Drop files here to upload   │  │
│  │                                 │  │
│  │  Supported: Images, PDFs, Text  │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

**3. File Dropped (Preview)**:
```
┌───────────────────────────────────────┐
│  ┌─ Files (2) ────────────────── [✕] ┐│
│  │ 📄 report.pdf (1.2 MB)       [✕]  ││
│  │ 📊 data.csv (345 KB)         [✕]  ││
│  └────────────────────────────────────┘│
│                                        │
│  Type your message...        [Send]   │
└───────────────────────────────────────┘
```

---

## File Preview Card

```html
<div class="file-preview">
    <div class="file-icon">📄</div>
    <div class="file-info">
        <div class="file-name">report.pdf</div>
        <div class="file-size">1.2 MB</div>
        <div class="file-status">Ready to send</div>
    </div>
    <button class="remove-file">✕</button>
</div>
```

---

## Technical Design

### Frontend

**Drag & Drop Events**:
```javascript
class BassiWebClient {
    initDragDrop() {
        this.conversationEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.showDropZone();
        });

        this.conversationEl.addEventListener('dragleave', (e) => {
            this.hideDropZone();
        });

        this.conversationEl.addEventListener('drop', async (e) => {
            e.preventDefault();
            this.hideDropZone();

            const files = Array.from(e.dataTransfer.files);
            await this.handleFiles(files);
        });
    }

    async handleFiles(files) {
        for (const file of files) {
            if (!this.validateFile(file)) continue;

            const fileData = await this.readFile(file);
            this.addFilePreview(file, fileData);
        }
    }

    validateFile(file) {
        const maxSize = 10 * 1024 * 1024; // 10MB
        const allowedTypes = ['image/', 'text/', 'application/pdf'];

        if (file.size > maxSize) {
            this.showError(`File too large: ${file.name} (max 10MB)`);
            return false;
        }

        if (!allowedTypes.some(type => file.type.startsWith(type))) {
            this.showError(`Unsupported type: ${file.name}`);
            return false;
        }

        return true;
    }

    async readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            if (file.type.startsWith('image/')) {
                reader.readAsDataURL(file);
            } else {
                reader.readAsText(file);
            }

            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
        });
    }
}
```

### Backend

**File Upload Endpoint**:
```python
# bassi/web_server.py

from fastapi import UploadFile, File, Form

@self.app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    message: str = Form(...)
):
    # Validate file
    if file.size > 10 * 1024 * 1024:
        return JSONResponse({"error": "File too large"}, status_code=400)

    # Read file content
    content = await file.read()

    # Process based on type
    if file.content_type.startswith('image/'):
        # Handle vision
        file_data = {
            "type": "image",
            "data": base64.b64encode(content).decode(),
            "media_type": file.content_type
        }
    else:
        # Handle text/pdf
        file_data = {
            "type": "document",
            "name": file.filename,
            "content": content.decode('utf-8')
        }

    # Send to agent with attachments
    async for event in self.agent.chat_with_files(message, [file_data]):
        yield event
```

---

## File Handling

**File Types**:

1. **Images** → Vision API
```python
{
    "type": "image",
    "source": {
        "type": "base64",
        "media_type": "image/png",
        "data": "..."
    }
}
```

2. **Text Files** → System Message
```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "Here's the file content:"},
        {"type": "text", "text": f"File: {filename}\n\n{content}"}
    ]
}
```

3. **PDFs** → Extract Text
```python
import PyPDF2

def extract_pdf_text(pdf_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text
```

---

## Security

1. **File Size Limits**: 10MB max
2. **Type Validation**: Whitelist only
3. **Filename Sanitization**: Remove path components
4. **Temp Storage**: Auto-cleanup after processing
5. **No Execution**: Never execute uploaded files

---

## Success Criteria

- [ ] Drag & drop works on all browsers
- [ ] Visual feedback (drop zone)
- [ ] File previews clear and helpful
- [ ] Size/type validation working
- [ ] Multiple files supported
- [ ] Files sent to Claude correctly
- [ ] Cleanup after processing
- [ ] Mobile support (file picker)

---

**Estimated Time**: 3-5 days
**Dependencies**: File handling infrastructure
