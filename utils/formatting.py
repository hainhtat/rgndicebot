import re
from typing import Dict, List, Optional, Any


def escape_markdown(text: str) -> str:
    """
    Escapes characters that have special meaning in plain Markdown
    to ensure they are displayed literally within a message.
    Used for content that should NOT be interpreted as Markdown formatting.
    """
    if not text:
        return text
    
    # Characters that need escaping in Telegram Markdown
    # Order matters: escape backslashes first, then other special characters
    # Include underscore and asterisk to prevent conflicts with markdown formatting
    special_chars = r'\`*_[]()#+-.!@{}|~'
    
    # Escape backslashes first to avoid double escaping
    text = text.replace('\\', '\\\\')
    
    # Then escape other special characters
    for char in special_chars[1:]:  # Skip backslash as it's already handled
        text = text.replace(char, f'\\{char}')
    
    return text


def escape_markdown_username(text: str) -> str:
    """
    Special escaping function for usernames that need to be displayed in markdown messages.
    This function ensures usernames don't interfere with markdown formatting.
    Note: Underscores are NOT escaped as they're common in usernames and don't break Telegram markdown.
    """
    if not text:
        return text
    
    # For usernames, escape characters that can break markdown but exclude underscores
    # Underscores are common in usernames and don't interfere with Telegram's markdown
    special_chars = r'\`*[]()#+-.!@{}|~<>'
    
    # Escape backslashes first
    text = text.replace('\\', '\\\\')
    
    # Then escape other special characters (excluding underscores)
    for char in special_chars[1:]:
        text = text.replace(char, f'\\{char}')
    
    return text


def escape_html(text: str) -> str:
    """
    Escapes characters that have special meaning in HTML to ensure they are displayed literally.
    Used for content that should NOT be interpreted as HTML formatting.
    """
    if not text:
        return text
    
    # HTML entities for special characters
    text = text.replace('&', '&amp;')  # Must be first to avoid double escaping
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    return text

# Note: The formatting functions have been moved to utils/message_formatter.py
# This file is kept for backward compatibility and only contains the escape_markdown function
# which is used by message_formatter.py