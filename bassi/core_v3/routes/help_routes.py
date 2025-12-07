"""
Help Routes - HTTP endpoints for enhanced help system.

BLACK BOX INTERFACE:
- GET /api/help - Get formatted help for local ecosystem
- GET /api/help?query=<query> - Get formatted help for specific query

DEPENDENCIES: HelpFormatter from bassi.shared
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from time import perf_counter

from bassi.shared.help_formatter import format_help
from bassi.shared.help_system import EcosystemScanner

logger = logging.getLogger(__name__)


def create_help_router() -> APIRouter:
    """
    Create help routes.

    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/api", tags=["help"])

    @router.get("/help")
    async def get_help(query: str | None = None) -> JSONResponse:
        """
        Get formatted help for the local ecosystem.

        Args:
            query: Optional query string for specific help topic.
                   Examples: "agents", "skills", "commands", "ecosystem", "<name>", etc.

        Returns:
            JSON response with formatted help text.
            The 'help' field contains the formatted help output.
            The 'query' field echoes back the query that was processed.

        Examples:
            GET /api/help → Overview of entire ecosystem
            GET /api/help?query=agents → List all agents
            GET /api/help?query=xlsx → Details for xlsx skill
            GET /api/help?query=ecosystem → Ecosystem map with workflow patterns
        """
        try:
            normalized_query = (query or "").strip() or None
            start = perf_counter()
            scanner = EcosystemScanner()
            scanner.scan_all()

            help_text = format_help(normalized_query, width=80, scanner=scanner)
            help_items = [item.to_dict() for item in scanner.items.values()]
            help_items_by_type = {
                item_type: [item.to_dict() for item in scanner.get_by_type(item_type)]
                for item_type in ("command", "skill", "agent")
            }
            counts = {
                "agents": len(help_items_by_type.get("agent", [])),
                "skills": len(help_items_by_type.get("skill", [])),
                "commands": len(help_items_by_type.get("command", [])),
            }

            return JSONResponse(
                {
                    "success": True,
                    "query": normalized_query or "overview",
                    "help": help_text,
                    "items": help_items,
                    "items_by_type": help_items_by_type,
                    "counts": counts,
                }
            )

            duration = (perf_counter() - start) * 1000
            logger.info(
                "⏱️ /api/help completed",
                extra={
                    "query": normalized_query or "overview",
                    "items": len(help_items),
                    "duration_ms": round(duration, 2),
                },
            )

        except Exception as e:
            logger.error(f"Error generating help: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(e)},
            )

    return router
