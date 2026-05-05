"""Tests for typed hardship category call scripts (Task 4.6).

Verifies:
1. All new hardship scripts (CUST-007 through CUST-010) pass D-15 validation
   via `_reject_forbidden`.
2. family_violence scripts contain zero financial terms from FINANCIAL_TERMS.
"""
import pytest

from agent.narrative.fallbacks import FALLBACKS
from agent.narrative.validators import (
    _reject_forbidden,
    CALL_SCRIPT_MAX_WORDS,
    USAGE_NARRATIVE_MAX_WORDS,
)
from agent.specialists.hardship_config import FINANCIAL_TERMS


# --- Typed hardship personas ---
_TYPED_HARDSHIP_PERSONAS = ("CUST-007", "CUST-008", "CUST-009", "CUST-010")


def _all_typed_hardship_scripts():
    """Yield (customer_id, category, field_name, value) for all typed hardship scripts."""
    for cust_id in _TYPED_HARDSHIP_PERSONAS:
        hardship = FALLBACKS[cust_id]["hardship"]
        for cat, fields in hardship.items():
            for field_name in ("reason", "call_script"):
                yield cust_id, cat, field_name, fields[field_name]


def _typed_hardship_ids():
    """Generate test IDs for parametrize."""
    return [
        f"{cust_id}/{cat}/{field}"
        for cust_id, cat, field, _ in _all_typed_hardship_scripts()
    ]


@pytest.mark.parametrize(
    "cust_id,category,field_name,value",
    list(_all_typed_hardship_scripts()),
    ids=_typed_hardship_ids(),
)
def test_hardship_script_passes_reject_forbidden(cust_id, category, field_name, value):
    """Every typed hardship script must pass D-15 validation."""
    max_words = (
        USAGE_NARRATIVE_MAX_WORDS if field_name == "reason" else CALL_SCRIPT_MAX_WORDS
    )
    # Should not raise — if it does, the test fails with the ValueError message.
    result = _reject_forbidden(value, max_words=max_words, field_label=f"{cust_id}/{category}/{field_name}")
    assert result == value.strip()


@pytest.mark.parametrize("field_name", ["reason", "call_script"])
def test_family_violence_no_financial_terms(field_name):
    """family_violence scripts must contain zero financial terms (CP-3)."""
    fv = FALLBACKS["CUST-009"]["hardship"]["family_violence"]
    text = fv[field_name].lower()
    words = text.split()
    # Strip punctuation from words for matching
    clean_words = [w.strip(".,;:!?—-'\"()") for w in words]
    violations = [term for term in FINANCIAL_TERMS if term in clean_words]
    assert violations == [], (
        f"family_violence/{field_name} contains financial terms: {violations}"
    )


def test_family_violence_full_text_no_financial_terms():
    """Concatenation of reason + call_script contains zero financial tokens."""
    fv = FALLBACKS["CUST-009"]["hardship"]["family_violence"]
    combined = f"{fv['reason']} {fv['call_script']}".lower()
    words = combined.split()
    clean_words = [w.strip(".,;:!?—-'\"()") for w in words]
    violations = [term for term in FINANCIAL_TERMS if term in clean_words]
    assert violations == [], (
        f"family_violence combined text contains financial terms: {violations}"
    )
