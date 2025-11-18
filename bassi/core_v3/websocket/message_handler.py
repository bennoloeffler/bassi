"""
Message Handler - Routes incoming WebSocket messages to type-specific processors.

BLACK BOX INTERFACE:
- dispatch(websocket, data, connection_id) -> Routes message to appropriate processor

DEPENDENCIES: Message processors (user_message, hint, config, answer, interrupt, server_info)
"""

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class MessageHandler:
    """Routes WebSocket messages to type-specific processors."""

    def __init__(
        self,
        user_message_processor=None,
        hint_processor=None,
        config_processor=None,
        answer_processor=None,
        interrupt_processor=None,
        server_info_processor=None,
    ):
        """
        Initialize message handler with processors.

        Args:
            user_message_processor: Processor for user_message type
            hint_processor: Processor for hint type
            config_processor: Processor for config_change type
            answer_processor: Processor for answer type
            interrupt_processor: Processor for interrupt type
            server_info_processor: Processor for get_server_info type
        """
        self.processors = {
            "user_message": user_message_processor,
            "hint": hint_processor,
            "config_change": config_processor,
            "answer": answer_processor,
            "interrupt": interrupt_processor,
            "get_server_info": server_info_processor,
        }

    async def dispatch(
        self, websocket: WebSocket, data: dict[str, Any], connection_id: str
    ):
        """
        Dispatch message to appropriate processor based on type.

        Args:
            websocket: WebSocket connection
            data: Message data with 'type' field
            connection_id: Session/connection ID

        Returns:
            Result from processor (if any)
        """
        msg_type = data.get("type")

        if not msg_type:
            logger.warning(f"Message missing 'type' field: {data}")
            return

        processor = self.processors.get(msg_type)

        if not processor:
            logger.warning(
                f"No processor registered for message type: {msg_type}"
            )
            return

        try:
            return await processor(websocket, data, connection_id)
        except Exception as e:
            logger.error(
                f"Error processing {msg_type} message: {e}", exc_info=True
            )
            # Send error to client
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error processing message: {str(e)}",
                    }
                )
            except Exception:
                pass  # WebSocket might be closed
