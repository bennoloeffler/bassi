"""Settings API routes.

Provides endpoints for managing user settings and preferences.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bassi.core_v3.services.config_service import ConfigService

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Singleton instance
_config_service: ConfigService | None = None


def get_config_service() -> ConfigService:
    """Get or create ConfigService singleton"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


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
