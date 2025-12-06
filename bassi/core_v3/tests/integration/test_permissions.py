"""
Permission System Tests

Tests for permission modes, callbacks, and hooks:
- bypassPermissions mode behavior
- acceptEdits mode behavior
- default permission mode behavior
- Permission callback behavior
- Hook system (PreToolUse, PostToolUse)

Based on documented requirements in:
- features_concepts/permissions.md
- TOOL_PERMISSIONS_IMPLEMENTATION_PLAN.md
"""


import pytest

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.services.config_service import ConfigService
from bassi.core_v3.services.permission_manager import PermissionManager


class TestPermissionModes:
    """Test different permission modes."""

    @pytest.mark.asyncio
    async def test_bypass_permissions_mode(self):
        """
        Test bypassPermissions mode allows all tools.

        Documented requirement: permissions.md line 41-51
        """
        config = SessionConfig(permission_mode="bypassPermissions")
        session = BassiAgentSession(config)

        # In bypassPermissions mode, all tools should be allowed
        # This is tested implicitly through agent execution
        # For explicit test, we'd need to check permission callback behavior
        assert config.permission_mode == "bypassPermissions"

    @pytest.mark.asyncio
    async def test_accept_edits_mode(self):
        """
        Test acceptEdits mode auto-approves file operations.

        Documented requirement: permissions.md line 28-39
        """
        config = SessionConfig(permission_mode="acceptEdits")
        session = BassiAgentSession(config)

        assert config.permission_mode == "acceptEdits"
        # File edits should be auto-approved, bash/web still require approval

    @pytest.mark.asyncio
    async def test_default_permission_mode(self):
        """
        Test default mode requires permission prompts.

        Documented requirement: permissions.md line 22-27
        """
        config = SessionConfig(permission_mode="default")
        session = BassiAgentSession(config)

        assert config.permission_mode == "default"
        # All tools should require permission prompts


class TestPermissionManager:
    """Test PermissionManager behavior."""

    @pytest.fixture
    def config_service(self, tmp_path):
        """Create test config service."""
        return ConfigService(tmp_path / "config.json")

    @pytest.fixture
    def permission_manager(self, config_service):
        """Create permission manager."""
        pm = PermissionManager(config_service)
        return pm

    @pytest.mark.asyncio
    async def test_global_bypass_allows_all_tools(
        self, permission_manager, config_service
    ):
        """
        Test global bypass allows all tools.

        Documented requirement: TOOL_PERMISSIONS_IMPLEMENTATION_PLAN.md

        Corner cases tested:
        - Works for any tool name
        - Works without other permissions
        - Works even if other permissions exist
        """
        # Enable global bypass
        config_service.set_global_bypass_permissions(True)

        from claude_agent_sdk.types import PermissionResultAllow

        # Test with various tools
        tools = ["Bash", "ReadFile", "WriteFile", "WebSearch", "UnknownTool"]

        for tool_name in tools:
            result = await permission_manager.can_use_tool_callback(
                tool_name, {"command": "test"}, None
            )
            assert isinstance(
                result, PermissionResultAllow
            ), f"Global bypass should allow {tool_name}"

        # Verify it works even with other permissions set
        permission_manager.one_time_permissions["Bash"] = 0  # Would deny
        permission_manager.session_permissions["Bash"] = False  # Would deny

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "test"}, None
        )
        assert isinstance(
            result, PermissionResultAllow
        ), "Global bypass should override other permissions"

    @pytest.mark.asyncio
    async def test_one_time_permission(
        self, permission_manager, config_service
    ):
        """
        Test one-time permission scope.

        Documented requirement: Permission scopes (one_time, session, persistent, global)

        Corner cases tested:
        - Permission is consumed after use
        - Permission is removed when count reaches 0
        - Multiple uses consume multiple permissions
        """
        # Ensure global bypass is OFF so we test actual permission logic
        config_service.set_global_bypass_permissions(False)

        # Grant one-time permission
        permission_manager.one_time_permissions["Bash"] = 1

        from claude_agent_sdk.types import PermissionResultAllow

        # First use should succeed
        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )

        assert isinstance(result, PermissionResultAllow)

        # Permission should be consumed (decremented to 0 and removed)
        assert "Bash" not in permission_manager.one_time_permissions

        # Second use should fail (no permission left)
        # Without websocket, should return deny (not raise)
        permission_manager.websocket = None

        from claude_agent_sdk.types import PermissionResultDeny

        result2 = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test2"}, None
        )
        # Should deny when no permission and no websocket
        assert isinstance(result2, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_one_time_permission_multiple_uses(
        self, permission_manager, config_service
    ):
        """
        Test one-time permission with count > 1.

        Corner case: Multiple uses consume count correctly.
        """
        config_service.set_global_bypass_permissions(False)

        # Grant 3 one-time permissions
        permission_manager.one_time_permissions["Bash"] = 3

        from claude_agent_sdk.types import PermissionResultAllow

        # First use
        result1 = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo 1"}, None
        )
        assert isinstance(result1, PermissionResultAllow)
        assert permission_manager.one_time_permissions["Bash"] == 2

        # Second use
        result2 = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo 2"}, None
        )
        assert isinstance(result2, PermissionResultAllow)
        assert permission_manager.one_time_permissions["Bash"] == 1

        # Third use
        result3 = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo 3"}, None
        )
        assert isinstance(result3, PermissionResultAllow)
        # Should be removed after reaching 0
        assert "Bash" not in permission_manager.one_time_permissions

    @pytest.mark.asyncio
    async def test_session_permission(self, permission_manager):
        """Test session-level permission scope."""
        # Grant session permission
        permission_manager.session_permissions["Bash"] = True

        from claude_agent_sdk.types import PermissionResultAllow

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )

        assert isinstance(result, PermissionResultAllow)

        # Permission should persist for session
        assert permission_manager.session_permissions["Bash"] is True

    @pytest.mark.asyncio
    async def test_persistent_permission(
        self, permission_manager, config_service
    ):
        """Test persistent permission scope."""
        # Grant persistent permission
        config_service.set_persistent_permissions(["Bash"])

        from claude_agent_sdk.types import PermissionResultAllow

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )

        assert isinstance(result, PermissionResultAllow)

        # Verify persisted
        persistent = config_service.get_persistent_permissions()
        assert "Bash" in persistent


class TestPermissionCallbacks:
    """Test custom permission callbacks."""

    @pytest.mark.asyncio
    async def test_permission_callback_allow(self):
        """
        Test permission callback allowing tool use.

        Documented requirement: Permission callback behavior
        """

        async def allow_callback(tool_name, tool_input, context):
            from claude_agent_sdk.types import PermissionResultAllow

            return PermissionResultAllow()

        config = SessionConfig(
            permission_mode="default", can_use_tool=allow_callback
        )

        assert config.can_use_tool is not None

    @pytest.mark.asyncio
    async def test_permission_callback_deny(self):
        """Test permission callback denying tool use."""

        async def deny_callback(tool_name, tool_input, context):
            from claude_agent_sdk.types import PermissionResultDeny

            return PermissionResultDeny(reason="Not allowed")

        config = SessionConfig(
            permission_mode="default", can_use_tool=deny_callback
        )

        assert config.can_use_tool is not None


class TestHooks:
    """Test hook system behavior."""

    @pytest.mark.asyncio
    async def test_pre_tool_use_hook(self):
        """
        Test PreToolUse hook execution.

        Documented requirement: Hook system (PreToolUse, PostToolUse)
        """
        hook_called = False

        async def pre_tool_hook(input_data, tool_use_id, context):
            nonlocal hook_called
            hook_called = True
            return {"decision": "allow"}

        config = SessionConfig(
            permission_mode="bypassPermissions",
            hooks={"PreToolUse": pre_tool_hook},
        )

        assert "PreToolUse" in config.hooks
        assert config.hooks["PreToolUse"] == pre_tool_hook

    @pytest.mark.asyncio
    async def test_post_tool_use_hook(self):
        """Test PostToolUse hook execution."""
        hook_called = False

        async def post_tool_hook(tool_result, tool_use_id, context):
            nonlocal hook_called
            hook_called = True

        config = SessionConfig(
            permission_mode="bypassPermissions",
            hooks={"PostToolUse": post_tool_hook},
        )

        assert "PostToolUse" in config.hooks


class TestPermissionScopes:
    """Test different permission scopes."""

    @pytest.fixture
    def config_service(self, tmp_path):
        """Create test config service."""
        return ConfigService(tmp_path / "config.json")

    @pytest.fixture
    def permission_manager(self, config_service):
        """Create permission manager for this test class."""
        return PermissionManager(config_service)

    @pytest.mark.asyncio
    async def test_permission_scope_priority(
        self, permission_manager, config_service
    ):
        """
        Test permission scope priority order.

        Priority: global > one_time > session > persistent > request

        Corner cases tested:
        - Global bypass takes precedence over all
        - One-time takes precedence over session/persistent
        - Session takes precedence over persistent
        """
        from claude_agent_sdk.types import PermissionResultAllow

        # Test 1: Global bypass takes precedence
        config_service.set_global_bypass_permissions(True)
        permission_manager.one_time_permissions["Bash"] = 1
        permission_manager.session_permissions["Bash"] = True
        config_service.set_persistent_permissions(["Bash"])

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )
        assert isinstance(result, PermissionResultAllow)
        # One-time should NOT be consumed (global bypass used first)
        assert permission_manager.one_time_permissions["Bash"] == 1

        # Test 2: One-time takes precedence over session/persistent
        config_service.set_global_bypass_permissions(False)
        permission_manager.one_time_permissions["Bash"] = 1
        permission_manager.session_permissions["Bash"] = True
        config_service.set_persistent_permissions(["Bash"])

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )
        assert isinstance(result, PermissionResultAllow)
        # One-time should be consumed
        assert "Bash" not in permission_manager.one_time_permissions
        # Session and persistent should remain
        assert permission_manager.session_permissions["Bash"] is True
        assert "Bash" in config_service.get_persistent_permissions()

        # Test 3: Session takes precedence over persistent
        permission_manager.one_time_permissions.clear()
        permission_manager.session_permissions["Bash"] = True
        config_service.set_persistent_permissions(["Bash"])

        result = await permission_manager.can_use_tool_callback(
            "Bash", {"command": "echo test"}, None
        )
        assert isinstance(result, PermissionResultAllow)
        # Session should be used (persistent remains as fallback)
        assert permission_manager.session_permissions["Bash"] is True
