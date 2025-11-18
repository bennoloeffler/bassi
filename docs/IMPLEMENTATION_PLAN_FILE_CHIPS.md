# Implementation Plan: File Chips Inside Input Area

**Status**: ✅ **IMPLEMENTED** (2025-11-16)
**Implementation**: File chips are integrated into input area (ChatGPT/Claude.ai pattern)

## Overview
Transform the file upload UX from "separate staging area above input" to "chips integrated inside input area" (ChatGPT/Claude.ai pattern).

---

## Current vs. Desired Architecture

### Current (WRONG Pattern):
```
[Conversation Area]
┌─────────────────────────────┐
│ 📋 Staging Area             │ ← Separate container ABOVE input
│ [Large Thumbnail (120x140)] │
│ [Large Thumbnail (120x140)] │
└─────────────────────────────┘
┌─────────────────────────────┐
│ [textarea]                  │ ← Input wrapper (separate)
│ 📎 ⏹ [Send]                 │
└─────────────────────────────┘
```

### Desired (CORRECT Pattern):
```
[Conversation Area]
┌─────────────────────────────────────┐
│ [chip][chip][chip]                  │ ← Chips INSIDE wrapper
│ ────────────────────────────────── │
│ Ask me anything...                  │ ← Textarea below chips
│                                     │
│ [+] [📎] [↑Send]                   │ ← Buttons at bottom
└─────────────────────────────────────┘
```

---

## Code Analysis

### Files to Modify:

#### 1. `/Users/benno/projects/ai/bassi/bassi/static/index.html`
**Lines 62-92** - Current HTML structure

**Current:**
```html
<!-- File Staging Area (WRONG) -->
<div id="file-staging-area" class="file-staging-area" style="display: none;">
    <div id="file-staging-grid" class="file-staging-grid">
        <!-- Staged files will appear here as thumbnails -->
    </div>
</div>

<!-- Input Area -->
<div class="input-container">
    <div class="input-wrapper">
        <textarea id="message-input" placeholder="Ask me anything..." rows="1"></textarea>
        <div class="button-group">
            <input type="file" id="file-input" style="display: none;" multiple>
            <button id="upload-button" title="Upload files">📎</button>
            <button id="stop-button" style="display: none;">⏹</button>
            <button id="send-button" disabled>Send</button>
        </div>
    </div>
</div>
```

**Changes Needed:**
- REMOVE `<div id="file-staging-area">` container (lines 62-67)
- MOVE file chips container INSIDE `.input-wrapper`
- Reorganize `.input-wrapper` to contain: chips container → textarea → buttons
- Add + button, change send button to arrow

#### 2. `/Users/benno/projects/ai/bassi/bassi/static/app.js`
**Lines 67-69** - Constructor references

**Current:**
```javascript
// File staging area elements (new design)
this.fileStagingArea = document.getElementById('file-staging-area')
this.fileStagingGrid = document.getElementById('file-staging-grid')
```

**Changes Needed:**
- Update constructor to reference chips container inside input wrapper
- Rename variables: `this.fileChipsContainer`, `this.fileChipsGrid`

**Lines 1326-1447** - Rendering logic

**Current:**
- `renderStagingArea()` - Renders large thumbnails to separate area
- `addFileToStaging()` - Adds to stagedFiles array
- `removeFromStaging()` - Removes file

**Changes Needed:**
- Rename: `renderStagingArea()` → `renderFileChips()`
- Change rendering: small chips (80x30px) instead of large thumbnails (120x140px)
- Render to `.file-chips-grid` inside `.input-wrapper`
- Add collapsible indicator: "n files" button to show/hide chips

**Lines 731-734** - sendMessage() cleanup

**Current:**
```javascript
this.stagedFiles = []  // Clear staging area (NEW DESIGN)
this.renderStagingArea()  // Hide staging area (NEW DESIGN)
```

**Changes Needed:**
```javascript
this.stagedFiles = []  // Clear chips
this.renderFileChips()  // Hide chips
```

#### 3. `/Users/benno/projects/ai/bassi/bassi/static/style.css`
**Lines 1281-1397** - Current staging area styles

**Current:**
- `.file-staging-area` - Separate container above input (WRONG)
- `.file-staging-grid` - Horizontal flex grid
- `.file-thumbnail` - Large thumbnails (120x140px)

**Changes Needed:**
- REMOVE `.file-staging-area` styles
- ADD new chip styles inside input wrapper

**Lines 1529-1535** - Input wrapper

**Current:**
```css
.input-wrapper {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    gap: var(--spacing-md);
    align-items: flex-end;
}
```

**Changes Needed:**
```css
.input-wrapper {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;  /* Stack chips → textarea → buttons */
    gap: var(--spacing-sm);
}
```

#### 4. `/Users/benno/projects/ai/bassi/docs/features_concepts/file_upload_ux.md`
**Lines 69-107** - Design document

**Current:**
```markdown
#### 1. **File Staging Area** (NEW)
- **Location**: Between conversation and input area
- **Visibility**: Hidden when empty, appears when files uploaded
- **Content**: Thumbnail grid of files waiting to be sent
```

**Changes Needed:**
- Update to describe chip-inside-input pattern
- Document ChatGPT/Claude.ai UX
- Add collapsible indicator feature
- Remove references to "staging area between conversation and input"

#### 5. `/Users/benno/projects/ai/bassi/bassi/core_v3/tests/test_file_upload_simple_e2e.py`
**Lines 77-159** - E2E tests

**Current:**
- `test_staging_area_hidden_initially()` - Tests separate staging area
- `test_upload_file_via_button()` - Tests files appear in staging area
- `test_staging_area_remove_file()` - Tests removing from staging area

**Changes Needed:**
- Rename: `test_staging_area_*` → `test_file_chips_*`
- Update selectors: `#file-staging-area` → `.file-chips-container`
- Test chips appear inside `.input-wrapper`
- Test collapsible indicator functionality

---

## Implementation Steps

### Phase 1: Update Design Document (15 min)
**File:** `docs/features_concepts/file_upload_ux.md`

1. Replace "File Staging Area" section with "File Chips Inside Input"
2. Document new visual layout with chips inside input wrapper
3. Add collapsible indicator feature ("n files" button)
4. Remove all references to "staging area between conversation and input"
5. Add CSS specifications for chip styling

### Phase 2: HTML Structure (10 min)
**File:** `bassi/static/index.html`

1. REMOVE lines 62-67 (old staging area container)
2. Restructure `.input-wrapper` (lines 70-92):
```html
<div class="input-container">
    <div class="input-wrapper">
        <!-- NEW: File chips container inside wrapper -->
        <div class="file-chips-container" style="display: none;">
            <div class="file-chips-header">
                <button class="file-chips-toggle" id="chips-toggle">
                    <span id="chips-count">2 files</span>
                    <span class="chips-arrow">▼</span>
                </button>
            </div>
            <div class="file-chips-grid" id="file-chips-grid">
                <!-- Chips will appear here -->
            </div>
        </div>

        <!-- Textarea -->
        <textarea
            id="message-input"
            placeholder="Ask me anything..."
            rows="1"
        ></textarea>

        <!-- Buttons -->
        <div class="button-group">
            <input type="file" id="file-input" style="display: none;" multiple>
            <button id="add-button" class="icon-button" title="Add content">
                ➕
            </button>
            <button id="upload-button" class="icon-button" title="Upload files">
                📎
            </button>
            <button id="stop-button" class="icon-button" style="display: none;">
                ⏹
            </button>
            <button id="send-button" class="icon-button" disabled>
                ↑
            </button>
        </div>
    </div>
</div>
```

### Phase 3: CSS Styling (30 min)
**File:** `bassi/static/style.css`

1. **REMOVE** old staging area styles (lines 1281-1397)

2. **UPDATE** `.input-wrapper` (line 1529):
```css
.input-wrapper {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;  /* Stack vertically */
    gap: 8px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px;
}
```

3. **ADD** new chip styles:
```css
/* File Chips Container (inside input wrapper) */
.file-chips-container {
    display: none;  /* Hidden when no files */
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 8px;
}

.file-chips-container.has-files {
    display: block;
}

.file-chips-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.file-chips-toggle {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all var(--transition-fast);
}

.file-chips-toggle:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

.chips-arrow {
    font-size: 10px;
    transition: transform var(--transition-fast);
}

.file-chips-toggle.collapsed .chips-arrow {
    transform: rotate(-90deg);
}

.file-chips-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.file-chips-grid.collapsed {
    display: none;
}

/* File Chip (Small, Inline) */
.file-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;  /* Rounded pill shape */
    padding: 4px 8px 4px 4px;
    max-width: 200px;
    transition: all var(--transition-fast);
}

.file-chip:hover {
    border-color: var(--accent-blue);
    background: var(--bg-tertiary);
}

.file-chip-thumbnail {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    background: var(--bg-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex-shrink: 0;
}

.file-chip-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.file-chip-icon {
    font-size: 16px;
}

.file-chip-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.file-chip-name {
    font-size: 12px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.file-chip-size {
    font-size: 10px;
    color: var(--text-secondary);
}

.file-chip-remove {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    transition: all var(--transition-fast);
}

.file-chip-remove:hover {
    background: var(--accent-red);
    color: white;
}
```

4. **UPDATE** button styles (line 2781):
```css
.button-group {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
}

.icon-button {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: all var(--transition-fast);
}

.icon-button:hover:not(:disabled) {
    background: var(--accent-blue);
    color: white;
    border-color: var(--accent-blue);
    transform: scale(1.05);
}

.icon-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

#send-button:not(:disabled) {
    background: var(--accent-blue);
    color: white;
    border-color: var(--accent-blue);
}

#send-button:hover:not(:disabled) {
    background: var(--accent-blue-hover);
    transform: scale(1.1);
}
```

### Phase 4: JavaScript Logic (45 min)
**File:** `bassi/static/app.js`

1. **UPDATE** constructor (lines 67-69):
```javascript
// File chips container (inside input wrapper)
this.fileChipsContainer = document.querySelector('.file-chips-container')
this.fileChipsGrid = document.getElementById('file-chips-grid')
this.chipsToggle = document.getElementById('chips-toggle')
this.chipsCount = document.getElementById('chips-count')
```

2. **ADD** toggle functionality in `init()`:
```javascript
// File chips toggle
if (this.chipsToggle) {
    this.chipsToggle.addEventListener('click', () => {
        this.toggleFileChips()
    })
}
```

3. **REPLACE** `renderStagingArea()` with `renderFileChips()` (line 1326):
```javascript
renderFileChips() {
    /**
     * Render file chips inside the input wrapper.
     * Files here are waiting to be sent with the next message.
     */
    if (!this.fileChipsContainer || !this.fileChipsGrid) {
        console.warn('⚠️ File chips elements not found')
        return
    }

    // Clear existing chips
    this.fileChipsGrid.innerHTML = ''

    // Hide if no files
    if (this.stagedFiles.length === 0) {
        this.fileChipsContainer.style.display = 'none'
        this.fileChipsContainer.classList.remove('has-files')
        return
    }

    // Show chips container
    this.fileChipsContainer.style.display = 'block'
    this.fileChipsContainer.classList.add('has-files')

    // Update count
    if (this.chipsCount) {
        this.chipsCount.textContent = `${this.stagedFiles.length} file${this.stagedFiles.length === 1 ? '' : 's'}`
    }

    // Render each file chip
    this.stagedFiles.forEach((file) => {
        const chip = document.createElement('div')
        chip.className = 'file-chip'
        chip.dataset.fileId = file.id

        // Thumbnail
        const thumbnail = document.createElement('div')
        thumbnail.className = 'file-chip-thumbnail'

        if (file.type === 'image' && file.dataUrl) {
            const img = document.createElement('img')
            img.src = file.dataUrl
            img.alt = file.filename
            thumbnail.appendChild(img)
        } else {
            const icon = document.createElement('div')
            icon.className = 'file-chip-icon'
            icon.textContent = this.getFileIcon(file.filename)
            thumbnail.appendChild(icon)
        }

        // Info
        const info = document.createElement('div')
        info.className = 'file-chip-info'

        const name = document.createElement('div')
        name.className = 'file-chip-name'
        name.textContent = file.filename
        name.title = file.filename

        const size = document.createElement('div')
        size.className = 'file-chip-size'
        size.textContent = this.formatFileSize(file.size)

        info.appendChild(name)
        info.appendChild(size)

        // Remove button
        const removeBtn = document.createElement('button')
        removeBtn.className = 'file-chip-remove'
        removeBtn.textContent = '×'
        removeBtn.title = 'Remove file'
        removeBtn.onclick = (e) => {
            e.stopPropagation()
            this.removeFromStaging(file.id)
        }

        // Assemble chip
        chip.appendChild(thumbnail)
        chip.appendChild(info)
        chip.appendChild(removeBtn)

        this.fileChipsGrid.appendChild(chip)
    })

    console.log(`📋 File chips updated: ${this.stagedFiles.length} file(s)`)
}
```

4. **ADD** `toggleFileChips()` method:
```javascript
toggleFileChips() {
    /**
     * Toggle visibility of file chips grid (collapse/expand).
     */
    if (!this.fileChipsGrid || !this.chipsToggle) return

    this.fileChipsGrid.classList.toggle('collapsed')
    this.chipsToggle.classList.toggle('collapsed')
}
```

5. **UPDATE** `addFileToStaging()` (line 1422):
```javascript
// Change line 1446:
this.renderFileChips()  // Was: this.renderStagingArea()
```

6. **UPDATE** `removeFromStaging()` (line 1409):
```javascript
// Change line 1418:
this.renderFileChips()  // Was: this.renderStagingArea()
```

7. **UPDATE** `sendMessage()` (line 734):
```javascript
// Change line 734:
this.renderFileChips()  // Was: this.renderStagingArea()
```

### Phase 5: Update Tests (30 min)
**File:** `bassi/core_v3/tests/test_file_upload_simple_e2e.py`

1. **UPDATE** test names and selectors (lines 77-159):
```python
def test_file_chips_hidden_initially(page, server_url):
    """Test that file chips container is hidden when no files are uploaded."""
    page.goto(server_url)
    page.wait_for_selector("#connection-status:has-text('Connected')", timeout=10000)

    # Chips container should be hidden initially
    chips_container = page.query_selector(".file-chips-container")
    assert chips_container is not None, "Chips container element should exist"

    is_hidden = chips_container.is_hidden()
    assert is_hidden, "Chips container should be hidden when no files"

    print("✅ File chips container is hidden initially")


def test_upload_file_shows_chip(page, server_url, test_file):
    """Test uploading a file shows a chip inside input wrapper."""
    page.goto(server_url)
    page.wait_for_selector("#connection-status:has-text('Connected')", timeout=10000)

    # Get file input
    file_input = page.query_selector('input[type="file"]')
    assert file_input is not None, "File input should exist"

    # Set file
    file_input.set_input_files(str(test_file))

    # Wait for upload
    page.wait_for_timeout(2000)

    # Verify chips container appears INSIDE input wrapper
    input_wrapper = page.query_selector(".input-wrapper")
    chips_container = input_wrapper.query_selector(".file-chips-container")
    assert chips_container is not None, "Chips container should exist inside input wrapper"

    is_visible = chips_container.is_visible()
    assert is_visible, "Chips container should be visible after file upload"

    # Verify file chip appears
    file_chip = page.query_selector(".file-chip")
    assert file_chip is not None, "File chip should appear"

    # Verify file name is displayed
    file_name_el = page.query_selector(".file-chip-name")
    assert file_name_el is not None, "File name element should exist"
    file_name = file_name_el.text_content()
    assert "test_document.txt" in file_name, f"File name should be displayed, got: {file_name}"

    print(f"✅ File chip appears inside input wrapper: {file_name}")


def test_file_chips_remove(page, server_url, test_file):
    """Test removing a file chip."""
    page.goto(server_url)
    page.wait_for_selector("#connection-status:has-text('Connected')", timeout=10000)

    # Upload a file first
    file_input = page.query_selector('input[type="file"]')
    file_input.set_input_files(str(test_file))
    page.wait_for_timeout(2000)

    # Verify chips container is visible
    chips_container = page.query_selector(".file-chips-container")
    assert chips_container.is_visible(), "Chips container should be visible"

    # Verify file chip exists
    file_chip = page.query_selector(".file-chip")
    assert file_chip is not None, "File chip should exist"

    # Click remove button (×)
    remove_button = page.query_selector(".file-chip-remove")
    assert remove_button is not None, "Remove button should exist"
    page.click(".file-chip-remove")
    page.wait_for_timeout(500)

    # Verify chips container is hidden after removing file
    is_hidden = chips_container.is_hidden()
    assert is_hidden, "Chips container should be hidden after removing last file"

    # Verify no chips remain
    chips = page.query_selector_all(".file-chip")
    assert len(chips) == 0, "No file chips should remain"

    print("✅ File chip removal works correctly")


def test_file_chips_toggle(page, server_url, test_file):
    """Test collapsible file chips toggle."""
    page.goto(server_url)
    page.wait_for_selector("#connection-status:has-text('Connected')", timeout=10000)

    # Upload a file first
    file_input = page.query_selector('input[type="file"]')
    file_input.set_input_files(str(test_file))
    page.wait_for_timeout(2000)

    # Verify chips are visible
    chips_grid = page.query_selector(".file-chips-grid")
    assert chips_grid.is_visible(), "Chips grid should be visible initially"

    # Click toggle button
    toggle_button = page.query_selector("#chips-toggle")
    assert toggle_button is not None, "Toggle button should exist"
    page.click("#chips-toggle")
    page.wait_for_timeout(300)

    # Verify chips are hidden
    assert not chips_grid.is_visible(), "Chips grid should be hidden after collapse"

    # Click toggle again
    page.click("#chips-toggle")
    page.wait_for_timeout(300)

    # Verify chips are visible again
    assert chips_grid.is_visible(), "Chips grid should be visible after expand"

    print("✅ File chips toggle works correctly")
```

---

## Testing Strategy

### Manual Testing:
1. Upload file via 📎 button → chip appears inside input wrapper
2. Upload file via paste (Ctrl+V) → chip appears
3. Upload file via drag-drop → chip appears
4. Click × on chip → chip removed, container hides if empty
5. Click "n files" toggle → chips collapse/expand
6. Send message → chips move to message bubble, input chips clear

### E2E Tests:
```bash
pytest bassi/core_v3/tests/test_file_upload_simple_e2e.py -v --headed
```

---

## Rollout Plan

### Step 1: Update Documentation (Day 1, Morning)
- Update `docs/features_concepts/file_upload_ux.md`
- Get user approval on design document

### Step 2: Implement HTML + CSS (Day 1, Afternoon)
- Modify `index.html` structure
- Add chip styles to `style.css`
- Test visual layout in browser

### Step 3: Implement JavaScript (Day 2, Morning)
- Update `app.js` rendering logic
- Add collapsible toggle functionality
- Test file upload → chip display

### Step 4: Update Tests (Day 2, Afternoon)
- Modify E2E tests
- Run full test suite
- Fix any issues

### Step 5: QA & Polish (Day 3)
- Manual testing all upload methods
- Cross-browser testing
- Performance testing
- User acceptance testing

---

## Success Criteria

- ✅ Files appear as small chips (80x30px) inside input wrapper
- ✅ All upload methods (button/paste/drag) produce identical chips
- ✅ Chips have remove (×) button
- ✅ "n files" toggle collapses/expands chips
- ✅ Chips clear after sending message
- ✅ Visual design matches ChatGPT/Claude.ai pattern
- ✅ All E2E tests pass
- ✅ No visual regressions

---

## Risk Mitigation

### Risk 1: Layout breaks on mobile
**Mitigation:** Add responsive CSS breakpoints

### Risk 2: Input wrapper becomes too tall
**Mitigation:** Add max-height with scroll for chips grid

### Risk 3: Tests fail after refactor
**Mitigation:** Update all test selectors before running

---

## Notes

- Keep the inline file rendering in MESSAGE BUBBLES (already implemented correctly)
- Only change the PRE-SEND file display (chips in input wrapper)
- Maintain existing upload API (no backend changes needed)
- Use existing `this.stagedFiles` array (just change rendering location)
