"""
Session Workspace - DEPRECATED, use ChatWorkspace instead.

This module provides backward compatibility for code using SessionWorkspace.
The class has been renamed to ChatWorkspace for clarity:
- "Session" was confusing (browser sessions vs chat contexts)
- "Chat" clearly refers to a conversation context

Migration:
    # Old
    from bassi.core_v3.session_workspace import SessionWorkspace
    workspace = SessionWorkspace(session_id, ...)
    
    # New  
    from bassi.core_v3.chat_workspace import ChatWorkspace
    workspace = ChatWorkspace(chat_id, ...)
"""


# Re-export ChatWorkspace as SessionWorkspace for backward compatibility
from bassi.core_v3.chat_workspace import ChatWorkspace

# Alias for backward compatibility
SessionWorkspace = ChatWorkspace

# Note: Both session_id and chat_id work (chat_id internally, session_id as alias)

__all__ = ["SessionWorkspace", "ChatWorkspace"]
