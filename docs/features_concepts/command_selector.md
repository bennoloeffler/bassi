# Command Menu

## Overview
A numbered command menu that appears when the user presses "/" in the CLI. This feature provides a user-friendly way to discover and execute commands without memorizing them.

## User Story
As a user of bassi, when I press "/", I want to see a numbered list of all available commands that I can select by typing a number, so that I can easily discover and execute commands without memorizing them.

## Behavior

### Trigger
- User types "/" and presses Enter (or types "//" and presses Enter)
- System detects the "/" or "//" input pattern

### Display
- Shows a numbered list of all available commands with descriptions
- User can interact by:
  - **Type a number (1-5)**: Execute that command
  - **Press Enter** (without typing): Cancel and return to normal prompt
  - **Ctrl+C**: Cancel and return to normal prompt

### Available Commands
The selector displays:
- `/help` - Show detailed help and examples
- `/config` - Display current configuration
- `/alles_anzeigen` - Toggle verbose mode
- `/reset` - Reset conversation history
- `/quit` - Exit the application

## Technical Implementation

### Dependencies
- **Rich**: Already in use for console output and prompts
  - Uses `Prompt.ask()` for number input
  - No additional dependencies required

### Components
1. **Command Registry**: Dictionary mapping command names to descriptions (COMMANDS constant)
2. **Command Selector Function**: `show_command_selector()` in `bassi/main.py`
   - Displays numbered list of commands
   - Uses `Prompt.ask()` to get user selection
   - Validates input and returns selected command or None if cancelled
3. **Input Detection**: Modified main loop to detect "/" or "//" input pattern

### Integration Points
- **bassi/main.py**:
  - Command registry constant (lines 19-25)
  - `show_command_selector()` function (lines 113-157)
  - Main loop modification to handle "/" input (lines 207-214)

## Design Decisions

### Why a numbered menu?
- **No cursor jumping**: Simple text-based interface without terminal manipulation
- **No additional dependencies**: Uses existing Rich library for prompts
- **Familiar UX**: Numbered menus are universally understood
- **Accessible**: Works in all terminal environments without special key handling
- **Simple implementation**: Easy to understand and maintain

### Alternative Approaches Considered
1. **Arrow key navigation (questionary)**: Caused cursor jumping issues
2. **Rich Prompt with choices**: More complex than numbered menu
3. **Custom keyboard handling**: Too complex, reinventing the wheel

## Future Enhancements
- Add command history/favorites
- Support fuzzy search while typing
- Show command shortcuts/aliases
- Add command categories/grouping
