#!/usr/bin/env python3
"""
Automated test for context persistence

Tests that:
1. SDK generates a session ID on first interaction
2. Session ID is captured and saved to .bassi_context.json
3. Session ID is loaded on restart
4. Conversation history is actually restored (Claude remembers)
"""

import asyncio
import json
import sys
from pathlib import Path

# Add bassi to path
sys.path.insert(0, str(Path(__file__).parent))

from bassi.agent import BassiAgent


async def test_context_persistence():
    """Test that context is properly saved and loaded"""

    print("\n" + "=" * 70)
    print("CONTEXT PERSISTENCE TEST")
    print("=" * 70)

    context_file = Path.cwd() / ".bassi_context_test.json"

    # Clean up any existing test context
    if context_file.exists():
        context_file.unlink()
        print("✓ Cleaned up old test context")

    # === PHASE 1: First Session ===
    print("\n" + "-" * 70)
    print("PHASE 1: First Session - Teaching the agent")
    print("-" * 70)

    agent1 = BassiAgent()
    agent1.context_file = context_file  # Use test context file
    agent1.verbose = False  # Quiet mode for testing

    print(f"Initial session_id: {agent1.session_id}")
    assert agent1.session_id is None, "Session ID should start as None"

    # First interaction - teach the agent
    print("\nSending message: 'remember: my favorite color is purple'")
    response_text = []

    async for msg in agent1.chat("remember: my favorite color is purple"):
        msg_class = type(msg).__name__

        if msg_class == "AssistantMessage":
            content = getattr(msg, "content", [])
            for block in content:
                if type(block).__name__ == "TextBlock":
                    text = getattr(block, "text", "")
                    response_text.append(text)

        elif msg_class == "ResultMessage":
            # Session ID should be captured here
            sdk_session_id = getattr(msg, "session_id", None)
            print(f"\n✓ SDK returned session_id: {sdk_session_id}")

    # Check that session ID was captured
    print(f"✓ Agent captured session_id: {agent1.session_id}")
    assert (
        agent1.session_id is not None
    ), "❌ FAIL: Session ID was not captured!"
    assert len(agent1.session_id) > 10, "❌ FAIL: Session ID looks invalid!"

    first_session_id = agent1.session_id
    print(f"✓ First session ID: {first_session_id}")

    # Check that context was saved
    assert context_file.exists(), "❌ FAIL: Context file was not created!"
    saved_data = json.loads(context_file.read_text())
    print(f"✓ Context file created: {context_file}")
    print(f"  Saved session_id: {saved_data.get('session_id')}")

    assert (
        saved_data.get("session_id") == first_session_id
    ), "❌ FAIL: Saved session_id doesn't match agent's session_id!"

    # Check that SDK created a session file
    project_dir = (
        Path.home()
        / ".claude"
        / "projects"
        / "-Users-benno-projects-ai-bassi"
    )
    session_file = project_dir / f"{first_session_id}.jsonl"

    # Give SDK a moment to write the file
    await asyncio.sleep(1)

    if session_file.exists():
        file_size = session_file.stat().st_size
        print(f"✓ SDK session file created: {session_file}")
        print(f"  File size: {file_size} bytes")
    else:
        print(f"⚠️  WARNING: SDK session file not found: {session_file}")
        print("  (This might be okay if SDK batches writes)")

    print("\n✅ PHASE 1 PASSED: Session created and saved")

    # === PHASE 2: Second Session (Restart) ===
    print("\n" + "-" * 70)
    print("PHASE 2: Second Session - Loading context and testing memory")
    print("-" * 70)

    # Load context first
    loaded_context = None
    if context_file.exists():
        loaded_context = json.loads(context_file.read_text())
        print(f"✓ Context loaded: {loaded_context}")

    assert (
        loaded_context is not None
    ), "❌ FAIL: Context file exists but didn't load!"

    # Get session ID to resume
    resume_session_id = loaded_context.get("session_id")
    print(f"✓ Will resume session_id: {resume_session_id}")

    assert (
        resume_session_id == first_session_id
    ), f"❌ FAIL: Loaded session_id ({resume_session_id}) != original ({first_session_id})"

    # Simulate restart - create new agent with resume parameter
    agent2 = BassiAgent(resume_session_id=resume_session_id)
    agent2.context_file = context_file
    agent2.verbose = False

    print(f"✓ Agent created with resume_session_id: {agent2.session_id}")

    # Test if agent remembers - ask about favorite color
    print("\nSending message: 'what is my favorite color?'")
    response_text = []
    got_result = False

    async for msg in agent2.chat("what is my favorite color?"):
        msg_class = type(msg).__name__

        if msg_class == "AssistantMessage":
            content = getattr(msg, "content", [])
            for block in content:
                if type(block).__name__ == "TextBlock":
                    text = getattr(block, "text", "")
                    response_text.append(text)
                    print(f"\nAssistant response:\n{text}")

        elif msg_class == "ResultMessage":
            got_result = True
            sdk_session_id = getattr(msg, "session_id", None)
            print(f"\n✓ Session ID in result: {sdk_session_id}")
            assert (
                sdk_session_id == first_session_id
            ), "❌ FAIL: Session ID changed between sessions!"

    assert got_result, "❌ FAIL: Never received ResultMessage"

    # Check if response mentions purple
    full_response = " ".join(response_text).lower()
    print("\n--- Checking Response ---")
    print(f"Full response: {full_response[:200]}")

    if "purple" in full_response:
        print("✅ SUCCESS: Agent remembered 'purple'!")
        success = True
    else:
        print("❌ FAIL: Agent did NOT remember 'purple'")
        print(f"Response was: {full_response}")
        success = False

    # Clean up test context file
    if context_file.exists():
        context_file.unlink()
        print("\n✓ Cleaned up test context file")

    print("\n" + "=" * 70)
    if success:
        print("✅ CONTEXT PERSISTENCE TEST PASSED!")
        print("=" * 70)
        return True
    else:
        print("❌ CONTEXT PERSISTENCE TEST FAILED!")
        print("=" * 70)
        print("\nDEBUG INFO:")
        print(f"  First session_id: {first_session_id}")
        print(f"  Second session_id: {agent2.session_id}")
        print(f"  SDK session file: {session_file}")
        print(f"  File exists: {session_file.exists()}")
        if session_file.exists():
            print("  Last 3 lines of session file:")
            lines = session_file.read_text().strip().split("\n")
            for line in lines[-3:]:
                try:
                    data = json.loads(line)
                    print(f"    - {data.get('type')}: {str(data)[:100]}")
                except Exception:
                    print(f"    - {line[:100]}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_context_persistence())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ TEST CRASHED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
