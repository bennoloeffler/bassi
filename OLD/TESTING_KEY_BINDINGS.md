# Testing Key Bindings - Automated Integration Tests

## Overview
This document explains how bassi's key bindings are tested using **automated integration tests** that simulate real user keyboard input without manual interaction.

## The Challenge

Testing interactive terminal applications is tricky:
- ❌ Can't just pipe input: `echo "test" | python main.py` (not a TTY)
- ❌ Manual testing is slow and error-prone
- ❌ Unit tests don't test actual terminal interaction
- ✅ **Solution**: Use `pexpect` with pseudo-terminals (PTY)

## How It Works

### 1. Pseudo-Terminal (PTY)
A PTY simulates a real terminal:
```
┌─────────────────┐
│   Test Process  │
│    (pexpect)    │
└────────┬────────┘
         │ writes input
         ▼
    ┌────────┐  PTY Master
    │  PTY   │◄──────────────┐
    └────────┘                │
         │                    │
         │ PTY Slave          │ reads output
         ▼                    │
┌─────────────────┐          │
│  bassi process  │──────────┘
│  (thinks it's   │
│  a real TTY)    │
└─────────────────┘
```

**Key insight:** bassi thinks it's running in a real terminal!

### 2. The `pexpect` Library

`pexpect` (Python Expect) automates interactive applications:

```python
import pexpect

# Spawn bassi with a PTY
child = pexpect.spawn('uv run python -m bassi.main')

# Wait for prompt to appear
child.expect('You:', timeout=5)

# Send "hello" + Enter
child.sendline('hello')

# Wait for agent response
child.expect('Assistant:', timeout=10)

# Clean exit
child.sendcontrol('d')  # Ctrl+D
```

**Magic:**
- `child.expect('text')` waits until "text" appears in output
- `child.sendline('text')` sends text + Enter key
- `child.send('\x1b')` sends special characters like ESC

### 3. Test Structure

```
tests/
├── test_key_bindings.py     # Main integration tests
├── conftest.py              # Pytest fixtures and setup
└── __pycache__/
```

## Running the Tests

### Run All Key Binding Tests
```bash
uv run pytest tests/test_key_bindings.py -v
```

### Run Specific Test
```bash
uv run pytest tests/test_key_bindings.py::TestKeyBindings::test_slash_quit_exits_cleanly -v
```

### Run with Output Visible (Debugging)
```bash
uv run pytest tests/test_key_bindings.py -v -s
```

### Run Only Non-Skipped Tests
```bash
uv run pytest tests/test_key_bindings.py -v -k "not skip"
```

## Test Coverage

### ✅ Implemented Tests

| Test | Description | Status |
|------|-------------|--------|
| `test_slash_quit_exits_cleanly` | /quit command exits | ✅ |
| `test_ctrl_d_exits` | Ctrl+D exits | ✅ |
| `test_ctrl_c_during_prompt_clears_buffer` | Ctrl+C clears input | ✅ |
| `test_empty_input_ignored` | Empty Enter ignored | ✅ |
| `test_slash_help_shows_help` | /help shows help | ✅ |
| `test_slash_config_shows_config` | /config shows config | ✅ |
| `test_multiline_input_with_manual_newlines` | Multiline support | ✅ |
| `test_slash_command_menu` | / shows menu | ✅ |
| `test_invalid_command_shows_error` | Invalid command error | ✅ |
| `test_welcome_message_shows_instructions` | Welcome shows keys | ✅ |

### ⏭️ Skipped Tests (Require API)

| Test | Description | Reason Skipped |
|------|-------------|----------------|
| `test_enter_sends_message_to_agent` | Enter sends to Claude | Requires real API key |
| `test_esc_interrupts_running_agent` | ESC interrupts agent | Requires agent execution |

**Why skip?**
- Don't want to hit Anthropic API during every test run
- Tests should be fast and not require network
- Can enable manually with real API key for integration testing

## Special Key Sequences

Terminal control characters and escape sequences:

```python
KEYS = {
    'ENTER': '\r',           # Carriage return
    'NEWLINE': '\n',         # Line feed
    'ESC': '\x1b',          # Escape key
    'CTRL_C': '\x03',       # Interrupt
    'CTRL_D': '\x04',       # EOF
    'CTRL_R': '\x12',       # Reverse search (history)
    'TAB': '\t',            # Tab completion
    'BACKSPACE': '\x7f',    # Delete previous char
    'ARROW_UP': '\x1b[A',   # History navigation
    'ARROW_DOWN': '\x1b[B',
}
```

**Usage in tests:**
```python
# Send ESC key
child.send('\x1b')

# Send Ctrl+C
child.sendcontrol('c')

# Send Ctrl+D
child.sendcontrol('d')
```

## Example Test Walkthrough

Let's walk through `test_slash_quit_exits_cleanly`:

```python
def test_slash_quit_exits_cleanly(self, bassi_session):
    """Test that /quit command exits the application"""

    # 1. bassi_session fixture already spawned bassi and saw "You:" prompt

    # 2. Send /quit + Enter
    bassi_session.sendline("/quit")

    # 3. Wait for goodbye message to appear
    bassi_session.expect("Goodbye!", timeout=5)

    # 4. Wait for process to exit (EOF = End Of File)
    bassi_session.expect(pexpect.EOF, timeout=3)

    # 5. Verify process is dead
    assert not bassi_session.isalive()
```

**What happens under the hood:**
1. ✅ Fixture spawns: `uv run python -m bassi.main`
2. ✅ Waits for output to contain "You:"
3. ✅ Sends characters: `/quit\r\n`
4. ✅ Reads output until "Goodbye!" appears
5. ✅ Waits for process to exit
6. ✅ Cleanup: kills process if still alive

## Test Fixtures

From `conftest.py`:

### `test_environment`
**Auto-runs for every test:**
```python
@pytest.fixture(autouse=True)
def test_environment(monkeypatch, tmp_path):
    """Isolated test environment"""
    os.chdir(tmp_path)  # Isolated directory
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-mock")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    yield tmp_path
```

**Benefits:**
- Each test runs in isolated temp directory
- Mock API key prevents real API calls
- Test history files don't pollute home directory

### `bassi_session` (in test class)
**Spawns bassi for a single test:**
```python
@pytest.fixture
def bassi_session(self):
    """Spawn bassi with PTY"""
    child = pexpect.spawn('uv run python -m bassi.main', ...)
    child.expect('You:', timeout=10)

    yield child  # Test runs here

    # Cleanup
    child.sendcontrol('d')
    child.expect(pexpect.EOF)
```

**Benefits:**
- Fresh bassi instance per test
- Automatic cleanup even if test fails
- Consistent starting state

## Debugging Failed Tests

### 1. See What bassi Output
```python
def test_something(self, bassi_session):
    bassi_session.sendline('/help')

    try:
        bassi_session.expect('Help:', timeout=5)
    except pexpect.TIMEOUT:
        # Print what we got instead
        print(f"Got: {bassi_session.before}")
        raise
```

### 2. Increase Timeout
```python
# Instead of:
child.expect('You:', timeout=5)

# Use:
child.expect('You:', timeout=30)  # Slower systems
```

### 3. Run Single Test with Output
```bash
uv run pytest tests/test_key_bindings.py::test_slash_quit_exits_cleanly -v -s
```

### 4. Check PTY Output Manually
```python
# Add to test:
print(bassi_session.before)  # Everything before last expect
print(bassi_session.after)   # The matched text
print(bassi_session.buffer)  # Remaining buffer
```

## Common Issues & Solutions

### Issue: Test times out waiting for prompt

**Problem:**
```
TIMEOUT waiting for "You:"
```

**Solutions:**
1. Check if bassi is crashing on startup:
   ```python
   print(child.before)  # See what output we got
   ```
2. Increase timeout: `child.expect('You:', timeout=30)`
3. Check API key is set: `echo $ANTHROPIC_API_KEY`

### Issue: Terminal escape sequences differ

**Problem:**
Shift+Enter sequence varies by terminal type.

**Solution:**
Test multiline by sending literal newlines:
```python
child.send('line 1\nline 2\nline 3')
child.sendline()  # Final Enter
```

### Issue: Process doesn't exit cleanly

**Problem:**
Test hangs at cleanup.

**Solution:**
```python
# Force kill if graceful exit fails
try:
    child.sendcontrol('d')
    child.expect(pexpect.EOF, timeout=3)
except pexpect.TIMEOUT:
    child.kill(0)  # Force kill
```

### Issue: Tests pass locally but fail in CI

**Problem:**
CI environment differences.

**Solutions:**
1. Set proper environment variables in CI
2. Increase timeouts for slower CI machines
3. Mock out network-dependent parts
4. Check if PTY is available (`os.isatty()`)

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync

      - name: Run key binding tests
        run: uv run pytest tests/test_key_bindings.py -v
        env:
          ANTHROPIC_API_KEY: test-mock-key
```

## Advanced: Testing with Real API

To run integration tests with real Claude API:

```bash
# Set real API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run all tests including skipped ones
uv run pytest tests/test_key_bindings.py -v --runxfail
```

**Warning:** This will:
- Make real API calls
- Cost money (small amounts)
- Require network connection
- Be slower

## Technical Deep Dive

### Why PTY Instead of Pipes?

**Pipes don't work:**
```bash
echo "test" | python main.py
# stdin.isatty() = False
# prompt_toolkit detects this and may behave differently
```

**PTY works:**
```python
child = pexpect.spawn('python main.py')
# stdin.isatty() = True
# prompt_toolkit works normally
```

### How pexpect Manages I/O

```python
import pexpect

child = pexpect.spawn('bassi')

# Under the hood:
# 1. Creates PTY master/slave pair: master_fd, slave_fd
# 2. Forks process
# 3. Child process: connects slave_fd to stdin/stdout/stderr
# 4. Parent process: uses master_fd to read/write
```

### Expect Patterns

```python
# Simple string match
child.expect('You:')

# Regex match
child.expect(r'You:\s+')

# Multiple alternatives
child.expect(['You:', 'Error:', pexpect.TIMEOUT])

# Match returns index:
index = child.expect(['Option A', 'Option B'])
if index == 0:
    print('Got Option A')
```

## Best Practices

1. **Always set timeouts**
   ```python
   child.expect('text', timeout=5)  # Don't wait forever
   ```

2. **Use fixtures for cleanup**
   ```python
   @pytest.fixture
   def resource():
       r = setup()
       yield r
       cleanup(r)  # Always runs
   ```

3. **Test independent features separately**
   - One test = one key binding
   - Makes failures easier to diagnose

4. **Mock external dependencies**
   - Don't hit real API in tests
   - Use mock API keys

5. **Print diagnostics on failure**
   ```python
   try:
       child.expect('text')
   except pexpect.TIMEOUT:
       print(f"Buffer: {child.before}")
       raise
   ```

## Future Enhancements

Possible additions:
- [ ] Test Ctrl+R reverse history search
- [ ] Test arrow key navigation in input
- [ ] Test tab completion (if implemented)
- [ ] Test very long input handling
- [ ] Test Unicode/emoji input
- [ ] Test rapid Ctrl+C mashing
- [ ] Performance tests (startup time)

## References

- **pexpect docs**: https://pexpect.readthedocs.io/
- **prompt_toolkit**: https://python-prompt-toolkit.readthedocs.io/
- **PTY concept**: `man pty`
- **Terminal escape codes**: https://en.wikipedia.org/wiki/ANSI_escape_code

---

## Summary

**What we achieved:**
✅ Automated testing of interactive terminal application
✅ No manual testing required
✅ Tests run in CI/CD
✅ Fast feedback on key binding changes
✅ Comprehensive coverage of all commands

**How it works:**
1. `pexpect` spawns bassi with a pseudo-terminal (PTY)
2. Bassi thinks it's running in a real terminal
3. Tests send keyboard input programmatically
4. Tests wait for expected output with `expect()`
5. Automatic cleanup prevents hung processes

**Run tests:**
```bash
uv run pytest tests/test_key_bindings.py -v
```

All key bindings are now automatically tested! 🎉
