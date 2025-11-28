"""
File Routes - HTTP endpoints for file management.

BLACK BOX INTERFACE:
- POST /api/upload - Upload file to session workspace
- GET /api/sessions/{session_id}/files - List files in session workspace

DEPENDENCIES: UploadService, workspace manager
"""

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

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
            JSON with file metadata: path, size, media_type, filename

        Raises:
            HTTPException(404): If session not found
            HTTPException(413): If file too large
            HTTPException(400): If invalid filename
        """
        try:
            # Get workspace for this session
            workspace = workspaces.get(session_id)
            if not workspace:
                raise HTTPException(
                    status_code=404, detail=f"Session not found: {session_id}"
                )

            # Upload file using UploadService
            file_path = await upload_service.upload_to_session(
                file, workspace
            )

            # Get file info
            file_info = upload_service.get_upload_info(file_path, workspace)

            logger.info(
                f"📁 Uploaded to session {session_id[:8]}: "
                f"{file.filename} -> {file_info['path']}"
            )

            return JSONResponse(file_info)

        except FileTooLargeError as e:
            logger.warning(f"File too large: {file.filename} - {e}")
            raise HTTPException(status_code=413, detail=str(e))

        except InvalidFilenameError as e:
            logger.warning(f"Invalid filename: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        except Exception as e:
            logger.error(f"File upload failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Upload failed: {str(e)}"
            )

    @router.get("/api/sessions/{session_id}/files")
    async def list_session_files(session_id: str) -> list[dict[str, Any]]:
        """
        List all files in a session's workspace.

        Args:
            session_id: The session ID

        Returns:
            List of file metadata dictionaries

        Raises:
            HTTPException(404): If session not found
        """
        workspace = workspaces.get(session_id)
        if not workspace:
            raise HTTPException(
                status_code=404, detail=f"Session not found: {session_id}"
            )

        try:
            files = []
            workspace_path = workspace.physical_path

            # Metadata and system files to exclude from file list
            EXCLUDED_FILES = {
                "chat.json",  # ChatWorkspace metadata (new)
                "session.json",  # SessionWorkspace metadata (legacy)
                "session_metadata.json",  # Legacy name
                "session_state.json",  # SessionService state
                ".index.json",  # Session index
                "history.md",  # Conversation history (not a user upload)
            }

            # List all files in workspace (excluding metadata)
            for file_path in workspace_path.rglob("*"):
                if (
                    file_path.is_file()
                    and file_path.name not in EXCLUDED_FILES
                ):
                    relative_path = file_path.relative_to(workspace_path)
                    files.append(
                        {
                            "path": str(relative_path),
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime,
                        }
                    )

            return files

        except Exception as e:
            logger.error(
                f"Failed to list files for session {session_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to list files: {str(e)}"
            )

    return router
