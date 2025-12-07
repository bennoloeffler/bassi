"""
Routes package for V3 web server.

Contains HTTP endpoint handlers organized by domain.
"""

from bassi.core_v3.routes import capability_routes, file_routes, help_routes
from bassi.core_v3.routes.session_routes import create_session_router

__all__ = [
    "create_session_router",
    "file_routes",
    "capability_routes",
    "help_routes",
]
