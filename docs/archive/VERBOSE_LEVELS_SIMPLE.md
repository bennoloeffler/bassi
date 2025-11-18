# Verbose Levels - Simple CSS Implementation

## Concept

Use CSS classes to control visibility of tool details based on verbose level setting.
Always render all content, just hide via CSS.

## HTML Structure

```html
<!-- Container has verbose level class -->
<div id="conversation" class="verbose-normal">

  <!-- Assistant message -->
  <div class="assistant-message">

    <!-- Tool call block -->
    <div class="tool-block">
      <!-- Header: ALWAYS visible -->
      <div class="tool-header">
        🔧 bash__execute ✓ Success
      </div>

      <!-- Details: Visibility controlled by CSS -->
      <div class="tool-details">
        <div class="tool-input">
          CALL
          {
            "command": "wc -w README.md"
          }
        </div>

        <div class="tool-output">
          OUTPUT
          197 README.md
        </div>
      </div>
    </div>

    <!-- Text content: ALWAYS visible -->
    <div class="text-block">
      The file contains 197 words.
    </div>

  </div>
</div>
```

## CSS Rules

```css
/* ========== Minimal Mode ========== */
.verbose-minimal .tool-details {
  display: none;
}

.verbose-minimal .tool-output {
  display: none;
}

.verbose-minimal .code-block-content {
  display: none;
}

/* Show compact summary instead */
.verbose-minimal .tool-header::after {
  content: ' (click to expand)';
  color: var(--text-muted);
  font-size: 0.85em;
}

/* ========== Normal Mode ========== */
.verbose-normal .tool-input {
  /* Hide detailed input params */
  display: none;
}

.verbose-normal .tool-output {
  /* Show first 3 lines only */
  max-height: 4.5em;
  overflow: hidden;
  position: relative;
}

.verbose-normal .tool-output::after {
  /* Fade gradient */
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1.5em;
  background: linear-gradient(transparent, var(--bg-elevated));
}

/* ========== Full Mode ========== */
.verbose-full .tool-details {
  /* Show everything */
  display: block;
}

.verbose-full .tool-output {
  /* No restrictions */
  max-height: none;
}

.verbose-full .tool-output::after {
  /* No fade */
  display: none;
}
```

## JavaScript Changes

### 1. Set verbose class on container

```javascript
setVerboseLevel(level) {
  this.verboseLevel = level

  // Update CSS class on conversation container
  const conversation = document.getElementById('conversation')
  conversation.classList.remove('verbose-minimal', 'verbose-normal', 'verbose-full')
  conversation.classList.add(`verbose-${level}`)

  // Save preference
  localStorage.setItem('verbose-level', level)
}
```

### 2. Always render tool blocks

```javascript
renderToolBlock(tool) {
  const toolBlock = document.createElement('div')
  toolBlock.className = 'tool-block'
  toolBlock.dataset.toolId = tool.id

  // Header - ALWAYS visible
  const header = document.createElement('div')
  header.className = 'tool-header'
  header.innerHTML = `🔧 ${tool.name} ${tool.status === 'success' ? '✓' : '✗'}`
  toolBlock.appendChild(header)

  // Details - Visibility controlled by CSS
  const details = document.createElement('div')
  details.className = 'tool-details'

  // Input
  const input = document.createElement('div')
  input.className = 'tool-input'
  input.textContent = JSON.stringify(tool.input, null, 2)
  details.appendChild(input)

  // Output
  const output = document.createElement('div')
  output.className = 'tool-output'
  output.textContent = tool.output
  details.appendChild(output)

  toolBlock.appendChild(details)

  return toolBlock
}
```

### 3. Optional: Click to expand individual blocks

```javascript
// Add click handler to tool headers
header.addEventListener('click', () => {
  // Toggle expanded state on THIS block only
  toolBlock.classList.toggle('user-expanded')
})
```

```css
/* User manually expanded - override verbose setting */
.tool-block.user-expanded .tool-details {
  display: block !important;
}

.tool-block.user-expanded .tool-output {
  max-height: none !important;
}

.tool-block.user-expanded .tool-output::after {
  display: none !important;
}
```

## Benefits

✅ **Simple**: Just CSS classes, no complex logic
✅ **No DOM errors**: Everything always rendered
✅ **Fast**: CSS show/hide is instant
✅ **User control**: Can expand individual blocks
✅ **Clean code**: Separation of content and presentation

## Migration Steps

1. Add `verbose-normal` class to `#conversation` by default
2. Update `setVerboseLevel()` to change class
3. Add CSS rules for `.verbose-minimal`, `.verbose-normal`, `.verbose-full`
4. Ensure all tool blocks are always rendered with proper class names
5. Test switching between levels

## Edge Cases

**System messages**:
- Show warning icon in minimal/normal
- Show full error in full mode

**Questions**:
- Always show (they need user interaction)

**Short outputs** (< 3 lines):
- Always show even in normal mode
- Don't truncate

**Errors**:
- Always show full details (even in minimal)
- Errors need visibility for debugging
