"""
Session Index - DEPRECATED, use ChatIndex instead.

This module provides backward compatibility for code using SessionIndex.
The class has been renamed to ChatIndex for clarity:
- "Session" was confusing (browser sessions vs chat contexts)
- "Chat" clearly refers to a conversation context

Migration:
    # Old
    from bassi.core_v3.session_index import SessionIndex
    index = SessionIndex(base_path)
    
    # New
    from bassi.core_v3.chat_index import ChatIndex
    index = ChatIndex(base_path)
"""

import warnings

# Re-export ChatIndex as SessionIndex for backward compatibility
from bassi.core_v3.chat_index import ChatIndex

# Alias for backward compatibility
SessionIndex = ChatIndex

__all__ = ["SessionIndex", "ChatIndex"]
