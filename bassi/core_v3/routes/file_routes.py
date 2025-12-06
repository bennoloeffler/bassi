"""
File Routes - HTTP endpoints for file management.

BLACK BOX INTERFACE:
- POST /api/upload - Upload file to session workspace
- GET /api/sessions/{session_id}/files - List files in session workspace
- GET /api/sessions/{session_id}/file/{path} - Get file content

DEPENDENCIES: UploadService, workspace manager
"""

import logging
import mimetypes
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from bassi.core_v3.upload_service import (
    FileTooLargeError,
    InvalidFilenameError,
    UploadService,
)

logger = logging.getLogger(__name__)


def create_file_router(
    workspaces: dict, upload_service: UploadService
) -> APIRouter:
    """
    Create file routes with dependencies injected.

    Args:
        workspaces: Dictionary mapping session_id -> SessionWorkspace
        upload_service: File upload service instance

    Returns:
        Configured APIRouter
    """
    # Create fresh router for each server instance (critical for test isolation)
    router = APIRouter(tags=["files"])

    @router.post("/api/upload")
    async def upload_file(
        session_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> JSONResponse:
        """
        Upload a file to session-specific workspace.

        Args:
            session_id: Session ID for workspace isolation
            file: Uploaded file from multipart/form-data

        Returns:
            JSON with FileEntry data including @reference name

        Raises:
            HTTPException(404): If session not found
            HTTPException(413): If file too large
            HTTPException(400): If invalid filename or registry limits exceeded
        """
        try:
            # Get workspace for this session
            workspace = workspaces.get(session_id)
            if not workspace:
                raise HTTPException(
                    status_code=404, detail=f"Session not found: {session_id}"
                )

            # Upload file using UploadService (returns FileEntry)
            file_path, entry = await upload_service.upload_to_session(
                file, workspace
            )

            logger.info(
                f"📁 Uploaded to session {session_id[:8]}: "
                f"{file.filename} -> @{entry.ref}"
            )

            # Return FileEntry data for frontend
            return JSONResponse(entry.to_dict())

        except FileTooLargeError as e:
            logger.warning(f"File too large: {file.filename} - {e}")
            raise HTTPException(status_code=413, detail=str(e))

        except InvalidFilenameError as e:
            logger.warning(f"Invalid filename: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        except ValueError as e:
            # Registry limits exceeded (max files, max storage, etc.)
            logger.warning(f"File registry limit: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        except Exception as e:
            logger.error(f"File upload failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Upload failed: {str(e)}"
            )

    @router.get("/api/sessions/{session_id}/files")
    async def list_session_files(session_id: str) -> list[dict[str, Any]]:
        """
        List all registered files in a session's workspace.

        Returns FileRegistry entries with @reference names, types, and metadata.

        Args:
            session_id: The session ID

        Returns:
            List of FileEntry dictionaries with ref, type, size, etc.

        Raises:
            HTTPException(404): If session not found
        """
        workspace = workspaces.get(session_id)
        if not workspace:
            raise HTTPException(
                status_code=404, detail=f"Session not found: {session_id}"
            )

        try:
            # Return files from the FileRegistry
            return workspace.file_registry.to_json()

        except Exception as e:
            logger.error(
                f"Failed to list files for session {session_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to list files: {str(e)}"
            )

    @router.get("/api/sessions/{session_id}/file/{file_path:path}")
    async def get_file_content(
        session_id: str, file_path: str
    ) -> FileResponse:
        """
        Get file content from session workspace.

        Args:
            session_id: The session ID
            file_path: Relative path to file within workspace

        Returns:
            FileResponse with file content

        Raises:
            HTTPException(404): If session or file not found
            HTTPException(403): If path traversal attempt detected
        """
        workspace = workspaces.get(session_id)
        if not workspace:
            raise HTTPException(
                status_code=404, detail=f"Session not found: {session_id}"
            )

        try:
            # Resolve and validate file path
            workspace_path = workspace.physical_path
            full_path = (workspace_path / file_path).resolve()

            # Security: ensure path is within workspace
            if not str(full_path).startswith(str(workspace_path.resolve())):
                raise HTTPException(
                    status_code=403, detail="Path traversal not allowed"
                )

            if not full_path.exists() or not full_path.is_file():
                raise HTTPException(
                    status_code=404, detail=f"File not found: {file_path}"
                )

            # Determine media type
            media_type, _ = mimetypes.guess_type(str(full_path))
            if not media_type:
                media_type = "application/octet-stream"

            return FileResponse(
                path=full_path, media_type=media_type, filename=full_path.name
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get file {file_path}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get file: {str(e)}"
            )

    return router
