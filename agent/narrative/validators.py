"""Narrative field validators — UI-05 hard code-level gate.

STRIDE: V5 Input Validation. Runs inside Pydantic's `output_model(**dict)` call
inside `BedrockModel.structured_output`; ValidationError propagates up to
`invoke()`, which owns the retry-once-then-per-field-fallback policy (D-01).

D-15 dual-gate: the banned-terms list is ALSO injected as a negative constraint
in the system prompt (agent/narrative/prompt.txt). The validator is the
non-negotiable backstop per REQUIREMENTS.md UI-05.
"""
from pydantic import ValidationInfo, field_validator

from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX

# --- Cap constants (stricter-of-word-or-char wins automatically via Pydantic order) ---

USAGE_NARRATIVE_MAX_WORDS = 20   # REQUIREMENTS.md UI-04
USAGE_NARRATIVE_MAX_CHARS = 140  # ARCHITECTURE.md
CALL_SCRIPT_MAX_WORDS = 22       # REQUIREMENTS.md UI-03
CALL_SCRIPT_MAX_CHARS = 180      # ARCHITECTURE.md


def _reject_forbidden(value: str, max_words: int, field_label: str) -> str:
    """Raise ValueError when value breaks any rule; otherwise return stripped value.

    Pydantic converts ValueError into ValidationError with the field loc populated.
    Checks fire in this fixed order (matches test expectations):
      1. digits + currency  → "contains forbidden digit or currency symbol"
      2. banned term        → "contains banned term 'X'"
      3. word cap           → "N words exceeds cap M"

    Char cap is enforced separately by `Field(max_length=...)` — runs inside
    Pydantic before this validator (mode="after" on a str field).
    """
    if NUMERIC_REGEX.search(value):
        raise ValueError(f"{field_label}: contains forbidden digit or currency symbol")
    m = BANNED_REGEX.search(value)
    if m:
        raise ValueError(f"{field_label}: contains banned term {m.group()!r}")
    words = value.split()
    if len(words) > max_words:
        raise ValueError(f"{field_label}: {len(words)} words exceeds cap {max_words}")
    return value.strip()


# --- Pydantic v2 classmethod validators (attached to TrackInfo in agent.py) ---


@field_validator("usage_narrative", mode="after")
@classmethod
def validate_usage_narrative(cls, value: str, info: ValidationInfo) -> str:
    return _reject_forbidden(value, max_words=USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


@field_validator("call_script", mode="after")
@classmethod
def validate_call_script(cls, value: str, info: ValidationInfo) -> str:
    return _reject_forbidden(value, max_words=CALL_SCRIPT_MAX_WORDS, field_label="call_script")
