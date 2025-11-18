"""
Capability Routes - HTTP endpoints for session capabilities.

BLACK BOX INTERFACE:
- GET /api/capabilities - Get available tools, MCP servers, slash commands, skills, agents

DEPENDENCIES: CapabilityService
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from bassi.core_v3.services.capability_service import CapabilityService

logger = logging.getLogger(__name__)


def create_capability_router(
    capability_service: CapabilityService,
) -> APIRouter:
    """
    Create capability routes with dependencies injected.

    Args:
        capability_service: Capability discovery service instance

    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/api", tags=["capabilities"])

    @router.get("/capabilities")
    async def get_capabilities() -> JSONResponse:
        """
        Get session capabilities via discovery + SDK.

        Returns available tools, MCP servers, slash commands, skills, and agents.

        This is a REST endpoint separate from WebSocket to provide
        semantic clarity (capabilities are metadata, not conversation).

        Returns:
            JSON with capabilities dictionary

        Raises:
            HTTPException(500): If capability discovery fails
        """
        try:
            capabilities = await capability_service.get_capabilities()
            return JSONResponse(capabilities)

        except Exception as e:
            logger.error(f"Error fetching capabilities: {e}", exc_info=True)
            return JSONResponse(status_code=500, content={"error": str(e)})

    return router
