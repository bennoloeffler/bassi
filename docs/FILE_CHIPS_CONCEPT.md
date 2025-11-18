# File Chips Concept: Keep Files in Input Area Until Sent

**Status**: ✅ **IMPLEMENTED** (2025-11-16)
**Implementation**: File chips are integrated into input area (ChatGPT/Claude.ai pattern)

## Problem Statement

**Current (WRONG) behavior:**
```
┌─ Conversation Area ─────────────────┐
│                                     │
│ [User Message: "explain pictures"]  │
│                                     │
│ ❌ [File chip] [File chip] [File chip] │ ← FILES APPEARING HERE (WRONG!)
│                                     │
│ 💭 Thinking...                      │
│ The user is asking...               │
└─────────────────────────────────────┘

┌─ Input Area ────────────────────────┐
│ Ask me anything...                  │
│ 📎 ⏹ [Send]                         │
└─────────────────────────────────────┘
```

Files are "flowing up" into the conversation history BEFORE the message is sent.

---

## Desired Behavior

**Files ONLY in input area until sent:**
```
┌─ Conversation Area ─────────────────┐
│                                     │
│ [Previous messages...]              │
│                                     │
│ ✅ (No files shown here yet)        │
│                                     │
└─────────────────────────────────────┘

┌─ Input Area ────────────────────────┐
│ ┌───────────────────────────────┐   │
│ │ 2 files                    ▼  │   │ ← Collapsible header
│ └───────────────────────────────┘   │
│                                     │
│ [chip 📄×] [chip 🖼️×] [chip 🖼️×]   │ ← Files as chips in input
│ ─────────────────────────────────   │
│                                     │
│ Ask me anything...                  │ ← Textarea
│                                     │
│ 📎 ⏹ [Send]                         │
└─────────────────────────────────────┘
```

**After clicking Send:**
```
┌─ Conversation Area ─────────────────┐
│                                     │
│ [User Message: "explain pictures"]  │
│                                     │
│ ┌───────────────────────────────┐   │
│ │ 📎 Show 3 files            ▶  │   │ ← NOW files appear in message
│ └───────────────────────────────┘   │
│                                     │
│ 💭 Thinking...                      │
└─────────────────────────────────────┘

┌─ Input Area ────────────────────────┐
│ Ask me anything...                  │ ← Chips cleared
│ 📎 ⏹ [Send]                         │
└─────────────────────────────────────┘
```

---

## Key Rules

### Rule 1: Files Stay in Input Until Sent
- ✅ Upload file → chip appears in INPUT wrapper
- ✅ Type message → chips stay in INPUT wrapper
- ❌ Files should NOT appear in conversation area
- ❌ Files should NOT appear above "Thinking..." block

### Rule 2: Files Move to Message After Send
- ✅ Click Send → files attached to message
- ✅ Message appears in conversation with files inline
- ✅ Input chips cleared

### Rule 3: Hover Preview (Like Claude.ai)
When hovering over chip in input wrapper:
```
┌─────────────────────────┐
│ [Preview Thumbnail]     │ ← Popup tooltip
│ Anna_SMALL(1).jpg       │
│ 43.35 KB                │
└─────────────────────────┘
     ▼
[chip 🖼️ Anna... ×]
```

---

## Implementation Steps

### Step 1: Remove File Display from Conversation Before Send
**Problem:** Files are currently being added to conversation area before Send is clicked.

**Fix:** Ensure `addUserMessageWithImages()` is ONLY called AFTER Send is clicked, not during file upload.

### Step 2: Keep Chips in Input Wrapper
**Current:** Chips might be rendering in wrong location.

**Fix:** Ensure chips render inside `.input-wrapper`, not in conversation area.

### Step 3: Add Hover Preview Tooltip
**Feature:** When hovering over chip, show preview popup.

**Implementation:**
```javascript
chip.addEventListener('mouseenter', (e) => {
    showPreviewTooltip(file, e)
})

chip.addEventListener('mouseleave', () => {
    hidePreviewTooltip()
})
```

---

## Code Changes Needed

### 1. Check `handleFileSelect()` / `addFileToStaging()`
Ensure these functions ONLY:
- Upload file to server
- Add chip to input wrapper
- Do NOT add to conversation area

### 2. Check `sendMessage()`
Ensure this function:
- Collects chips from input wrapper
- Calls `addUserMessageWithImages()` with text + files
- Clears chips from input wrapper

### 3. Add Preview Tooltip Component
```javascript
showPreviewTooltip(file, event) {
    const tooltip = document.createElement('div')
    tooltip.className = 'file-preview-tooltip'

    // Position near chip
    tooltip.style.left = event.clientX + 'px'
    tooltip.style.top = (event.clientY - 100) + 'px'

    // Add preview image if image file
    if (file.type === 'image' && file.dataUrl) {
        const img = document.createElement('img')
        img.src = file.dataUrl
        tooltip.appendChild(img)
    }

    // Add filename + size
    const info = document.createElement('div')
    info.textContent = `${file.filename} (${formatFileSize(file.size)})`
    tooltip.appendChild(info)

    document.body.appendChild(tooltip)
    this.currentTooltip = tooltip
}

hidePreviewTooltip() {
    if (this.currentTooltip) {
        this.currentTooltip.remove()
        this.currentTooltip = null
    }
}
```

---

## Visual Specification

### File Chip (Normal State)
```css
.file-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px 4px 4px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
    max-width: 200px;
    cursor: pointer;  /* Indicates hoverable */
    transition: all 0.2s;
}

.file-chip:hover {
    border-color: var(--accent-blue);
    background: var(--bg-tertiary);
    transform: translateY(-2px);
}
```

### Preview Tooltip
```css
.file-preview-tooltip {
    position: fixed;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 10000;
    pointer-events: none;
    max-width: 300px;
}

.file-preview-tooltip img {
    width: 100%;
    height: auto;
    max-height: 200px;
    object-fit: contain;
    border-radius: 4px;
    margin-bottom: 8px;
}

.file-preview-tooltip div {
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
}
```

---

## Testing Checklist

### Before Send:
- [ ] Upload file → chip appears in INPUT wrapper only
- [ ] No files appear in conversation area
- [ ] Hover chip → preview tooltip appears
- [ ] Remove chip (×) → chip disappears from input
- [ ] Multiple uploads → all chips in input wrapper

### After Send:
- [ ] Click Send → message appears in conversation with files
- [ ] Input wrapper chips cleared
- [ ] Files visible in message (collapsible toggle)
- [ ] Hover message file → preview

### Edge Cases:
- [ ] Upload → remove → upload again → chips correct
- [ ] Upload → send → upload again → new chips separate
- [ ] Multiple messages with files → each message has its own files

---

## Summary

**The core issue:** Files were appearing in the conversation history BEFORE sending. They should ONLY appear in the input wrapper as chips, then move to the message after Send is clicked.

**The fix:** Ensure file upload logic adds chips to input wrapper only, and `addUserMessageWithImages()` is only called when Send is clicked.

**Bonus feature:** Add hover preview tooltip like Claude.ai for better UX.
