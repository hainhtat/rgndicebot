import re
from typing import Dict, List, Optional, Any


def escape_markdown(text: str) -> str:
    """
    Escapes characters that have special meaning in plain Markdown
    to ensure they are displayed literally within a message.
    Used for content that should NOT be interpreted as Markdown formatting.
    Note: Underscores and asterisks are not escaped to allow proper formatting.
    """
    # Characters commonly needing escaping in plain Markdown
    # Order matters: escape backslashes first, then other special characters
    # Removed underscore (_) and asterisk (*) from escaping to preserve formatting
    # Added @ symbol to prevent markdown parsing issues
    special_chars = r'`[]()#+-.!@'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Note: The formatting functions have been moved to utils/message_formatter.py
# This file is kept for backward compatibility and only contains the escape_markdown function
# which is used by message_formatter.py