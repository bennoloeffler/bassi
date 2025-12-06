"""Settings API routes.

Provides endpoints for managing user settings and preferences.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bassi.core_v3.services.config_service import ConfigService
from bassi.core_v3.services.model_service import (
    MODEL_LEVELS,
    get_model_info,
)
from bassi.core_v3.services.permission_manager import PermissionManager

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Singleton instances (set from web_server_v3.py)
_config_service: ConfigService | None = None
_permission_manager: PermissionManager | None = None


def get_config_service() -> ConfigService:
    """Get or create ConfigService singleton"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


def set_permission_manager(pm: PermissionManager) -> None:
    """Set the PermissionManager instance (called from web_server_v3.py)"""
    global _permission_manager
    _permission_manager = pm


def get_permission_manager() -> PermissionManager | None:
    """Get the PermissionManager instance"""
    return _permission_manager


class GlobalBypassRequest(BaseModel):
    """Request to update global bypass setting"""

    enabled: bool = Field(..., strict=True)


class GlobalBypassResponse(BaseModel):
    """Response with current global bypass setting"""

    enabled: bool


@router.get("/global-bypass", response_model=GlobalBypassResponse)
async def get_global_bypass():
    """Get current global bypass permissions setting

    Returns:
        GlobalBypassResponse with enabled status
    """
    service = get_config_service()
    enabled = service.get_global_bypass_permissions()
    return GlobalBypassResponse(enabled=enabled)


@router.post("/global-bypass", response_model=GlobalBypassResponse)
async def set_global_bypass(request: GlobalBypassRequest):
    """Update global bypass permissions setting

    Args:
        request: New setting value

    Returns:
        GlobalBypassResponse with updated status
    """
    service = get_config_service()
    service.set_global_bypass_permissions(request.enabled)
    return GlobalBypassResponse(enabled=request.enabled)


# ========== Model Settings ==========


class ModelInfoResponse(BaseModel):
    """Information about a model"""

    id: str
    name: str
    description: str
    icon_color: str


class ModelSettingsRequest(BaseModel):
    """Request to update model settings"""

    model_level: Optional[int] = Field(None, ge=1, le=3)
    auto_escalate: Optional[bool] = None


class ModelSettingsResponse(BaseModel):
    """Response with current model settings"""

    model_level: int
    auto_escalate: bool
    model_info: ModelInfoResponse
    available_models: list[dict]


def _build_model_response(
    model_level: int, auto_escalate: bool
) -> ModelSettingsResponse:
    """Build a complete model settings response."""
    info = get_model_info(model_level)
    available = [
        {
            "level": level,
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "icon_color": m.icon_color,
        }
        for level, m in MODEL_LEVELS.items()
    ]
    return ModelSettingsResponse(
        model_level=model_level,
        auto_escalate=auto_escalate,
        model_info=ModelInfoResponse(
            id=info.id,
            name=info.name,
            description=info.description,
            icon_color=info.icon_color,
        ),
        available_models=available,
    )


@router.get("/model", response_model=ModelSettingsResponse)
async def get_model_settings():
    """Get current model settings

    Returns:
        ModelSettingsResponse with current model level and auto-escalate setting
    """
    service = get_config_service()
    settings = service.get_model_settings()
    return _build_model_response(
        model_level=settings["default_model_level"],
        auto_escalate=settings["auto_escalate"],
    )


@router.post("/model", response_model=ModelSettingsResponse)
async def set_model_settings(request: ModelSettingsRequest):
    """Update model settings

    Args:
        request: New model settings (model_level and/or auto_escalate)

    Returns:
        ModelSettingsResponse with updated settings

    Note:
        When model_level changes, all pool agents are updated via SDK's set_model().
    """
    import logging

    logger = logging.getLogger(__name__)

    service = get_config_service()
    old_level = service.get_default_model_level()

    settings = service.set_model_settings(
        model_level=request.model_level,
        auto_escalate=request.auto_escalate,
    )

    new_level = settings["default_model_level"]

    # If model level changed, update model on all pool agents
    if request.model_level is not None and old_level != new_level:
        from bassi.core_v3.services.agent_pool import get_agent_pool

        new_model_id = get_model_info(new_level).id
        logger.info(
            f"🔄 [SETTINGS] Model level changed: {old_level} → {new_level}, "
            f"updating all agents to {new_model_id}..."
        )
        pool = get_agent_pool()
        updated = await pool.set_model_all(new_model_id)
        logger.info(
            f"✅ [SETTINGS] Updated {updated} agents to {new_model_id}"
        )

    return _build_model_response(
        model_level=settings["default_model_level"],
        auto_escalate=settings["auto_escalate"],
    )


# ========== Debug: Active Pool Agent Models ==========


class PoolAgentInfo(BaseModel):
    """Info about a pooled agent"""

    in_use: bool
    browser_id: Optional[str]
    use_count: int
    config_model_id: str


class ActiveModelsResponse(BaseModel):
    """Response with actual models being used by pool agents"""

    configured_level: int
    configured_model_id: str
    pool_agents: list[PoolAgentInfo]
    note: str


@router.get("/model/active", response_model=ActiveModelsResponse)
async def get_active_models():
    """Get the ACTUAL models being used by pool agents.

    This is for debugging to verify agents are using the correct model.
    Shows both the configured model and what each pool agent is actually using.
    """
    from bassi.core_v3.services.agent_pool import get_agent_pool

    service = get_config_service()
    configured_level = service.get_default_model_level()
    configured_model = get_model_info(configured_level)

    # Get pool and check each agent's config
    pool = get_agent_pool()
    agent_infos = []

    for pooled in pool._agents:
        agent = pooled.agent
        # Get the model_id from the agent's config
        config_model_id = getattr(agent.config, "model_id", "UNKNOWN")
        agent_infos.append(
            PoolAgentInfo(
                in_use=pooled.in_use,
                browser_id=(
                    pooled.browser_id[:8] if pooled.browser_id else None
                ),
                use_count=pooled.use_count,
                config_model_id=config_model_id,
            )
        )

    # Check if any agent has wrong model
    mismatched = [
        a for a in agent_infos if a.config_model_id != configured_model.id
    ]
    if mismatched:
        note = (
            f"⚠️ {len(mismatched)} agents have WRONG model! "
            f"Restart server to apply new model."
        )
    else:
        note = "✅ All agents have correct model."

    return ActiveModelsResponse(
        configured_level=configured_level,
        configured_model_id=configured_model.id,
        pool_agents=agent_infos,
        note=note,
    )


# ========== Permissions Info ==========


class PermissionsResponse(BaseModel):
    """Response with all active permissions"""

    global_bypass: bool
    session_permissions: list[str]
    persistent_permissions: list[str]
    one_time_permissions: dict[str, int]


@router.get("/permissions", response_model=PermissionsResponse)
async def get_permissions():
    """Get all active permissions for display.

    Returns permissions from all scopes:
    - global_bypass: If True, all tools run without asking
    - session_permissions: Tools allowed for current browser session
    - persistent_permissions: Tools allowed forever (saved to config)
    - one_time_permissions: Tools with remaining one-time uses

    Note: Session and one-time permissions come from the PermissionManager
    which is shared across all browser sessions. This endpoint shows
    the current state of all permission types.
    """
    config = get_config_service()
    pm = get_permission_manager()

    # Get global bypass from config
    global_bypass = config.get_global_bypass_permissions()

    # Get persistent permissions from config
    persistent = config.get_persistent_permissions()

    # Get session/one-time from PermissionManager (if available)
    if pm:
        session_perms = list(pm.session_permissions.keys())
        one_time = dict(pm.one_time_permissions)
    else:
        session_perms = []
        one_time = {}

    return PermissionsResponse(
        global_bypass=global_bypass,
        session_permissions=session_perms,
        persistent_permissions=persistent,
        one_time_permissions=one_time,
    )


class DeletePermissionResponse(BaseModel):
    """Response after deleting a permission"""

    success: bool
    tool: str
    scope: str


@router.delete(
    "/permissions/{scope}/{tool_name:path}",
    response_model=DeletePermissionResponse,
)
async def delete_permission(scope: str, tool_name: str):
    """Delete a specific tool permission.

    Args:
        scope: Permission scope - one of 'session', 'persistent', 'one_time'
        tool_name: The tool name to remove (URL encoded if contains special chars)

    Returns:
        Success status with tool and scope info

    Note:
        Deletion takes effect immediately. The next tool call will prompt
        for permission again. Deleting a non-existent permission succeeds
        (idempotent operation).
    """
    config = get_config_service()
    pm = get_permission_manager()

    if scope == "persistent":
        # Remove from config file
        current = config.get_persistent_permissions()
        if tool_name in current:
            current.remove(tool_name)
            config.set_persistent_permissions(current)

    elif scope == "session":
        # Remove from session memory
        if pm:
            pm.session_permissions.pop(tool_name, None)

    elif scope == "one_time":
        # Remove from one-time memory
        if pm:
            pm.one_time_permissions.pop(tool_name, None)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope: {scope}. Must be 'session', 'persistent', or 'one_time'",
        )

    return DeletePermissionResponse(
        success=True,
        tool=tool_name,
        scope=scope,
    )
