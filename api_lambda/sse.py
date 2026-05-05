"""Pure SSE formatting functions — no I/O, no state.

Formats Server-Sent Events (SSE) frames for the streaming reasoning trace
wire protocol. Each event follows the format:

    event: <type>\ndata: <json>\n\n

The data field is always a single-line compact JSON string (no embedded
newlines) produced with separators=(",", ":").
"""
import json
from typing import Any


def format_sse_event(event_type: str, data: Any) -> str:
    """Format a single SSE event frame.

    Returns: 'event: <type>\\ndata: <json>\\n\\n'
    """
    json_str = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {json_str}\n\n"


def format_done_event() -> str:
    """Format the terminal done event.

    Returns: 'event: done\\ndata: {}\\n\\n'
    """
    return "event: done\ndata: {}\n\n"
