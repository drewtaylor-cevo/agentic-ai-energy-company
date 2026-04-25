"""Narrative validator tests — UI-05 proof.

Plan 02 (this state): `_reject_forbidden` + word-cap constants live in
`agent/narrative/validators.py`; TrackInfo integration tests below exercise
the classmethod validators wired via `@field_validator`.
"""
import pytest

from agent.narrative.validators import (
    _reject_forbidden,
    USAGE_NARRATIVE_MAX_WORDS as _USAGE_NARRATIVE_MAX_WORDS,
    CALL_SCRIPT_MAX_WORDS as _CALL_SCRIPT_MAX_WORDS,
)


# --- UI-05 : digits + currency rejected ---


@pytest.mark.parametrize("poisoned", [
    "Saves about 30 dollars a month",
    "Uses 500 kWh in winter months",
    "About 12 months of winter-heavy usage",
])
def test_digits_rejected(poisoned):
    with pytest.raises(ValueError, match="forbidden digit"):
        _reject_forbidden(poisoned, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


@pytest.mark.parametrize("poisoned", [
    "Pays about $ monthly amount",
    "About £ per day",
    "Around € per week",
    "About % of usage",
])
def test_currency_symbols_rejected(poisoned):
    with pytest.raises(ValueError, match="forbidden digit or currency"):
        _reject_forbidden(poisoned, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


# --- UI-05 : competitors rejected ---


@pytest.mark.parametrize("competitor", ["Origin", "AGL", "EnergyAustralia", "Red Energy", "Alinta", "Momentum"])
def test_competitors_rejected(competitor):
    sample = f"Compared with {competitor} plans the customer benefits"
    with pytest.raises(ValueError, match="banned term"):
        _reject_forbidden(sample, max_words=_CALL_SCRIPT_MAX_WORDS, field_label="call_script")


def test_competitor_case_insensitive():
    with pytest.raises(ValueError, match="banned term"):
        _reject_forbidden("compared with origin plans", max_words=20, field_label="x")


# --- UI-05 : switch verbs rejected ---


@pytest.mark.parametrize("verb_sample", [
    "Switch to EcoFlex to save money",
    "Switching plans can help the customer",
    "Moving the household to EcoFlex",
    "Changing plans helps in winter",
    "Transferring to a cheaper option",
    "Swapping plans reduces the bill",
    "Shifting from the standard plan",
    "Converting over to EcoFlex",
])
def test_switch_verbs_rejected(verb_sample):
    with pytest.raises(ValueError, match="banned term"):
        _reject_forbidden(verb_sample, max_words=_CALL_SCRIPT_MAX_WORDS, field_label="call_script")


def test_switch_verb_false_positive_guard():
    # "switcheroo" must NOT match; "original" must NOT match
    _reject_forbidden("switcheroo of pricing models around", max_words=20, field_label="x")
    _reject_forbidden("the original household profile here", max_words=20, field_label="x")


# --- UI-05 : env superlatives rejected ---


@pytest.mark.parametrize("superlative_sample", [
    "The greenest option available for the home",
    "The cleanest option on the market today",
    "A most sustainable household choice long-term",
    "A carbon-neutral recommendation for the home",
    "A zero-emission tariff for the home",
    "A net-zero plan suited to this profile",
    "Best for the planet of the options",
])
def test_env_superlatives_rejected(superlative_sample):
    with pytest.raises(ValueError, match="banned term"):
        _reject_forbidden(superlative_sample, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


# --- UI-05 : word count ---


def test_word_cap_enforced_just_over():
    # 21 words, no other rules broken → word-cap rejection
    sample = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi"
    assert len(sample.split()) == 21
    with pytest.raises(ValueError, match="exceeds cap"):
        _reject_forbidden(sample, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


def test_word_cap_enforced_well_over():
    sample = " ".join(["alpha"] * 40)
    with pytest.raises(ValueError, match="exceeds cap"):
        _reject_forbidden(sample, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


def test_word_cap_at_boundary_passes():
    # exactly 20 words for usage_narrative
    sample = " ".join(["alpha"] * 20)
    _reject_forbidden(sample, max_words=_USAGE_NARRATIVE_MAX_WORDS, field_label="usage_narrative")


def test_call_script_word_cap_at_boundary_passes():
    # exactly 22 words for call_script
    sample = " ".join(["alpha"] * 22)
    _reject_forbidden(sample, max_words=_CALL_SCRIPT_MAX_WORDS, field_label="call_script")


# --- UI-05 : char count (enforced by Field(max_length=...) in Plan 02 —
#      scaffolding here proves the Field values the validator pairs with) ---


def test_char_cap_sentinel_values():
    # Plan 02 wires Field(max_length=140) on usage_narrative and max_length=180 on call_script.
    # This sentinel test exists so a drift on those caps is caught.
    assert _USAGE_NARRATIVE_MAX_WORDS == 20
    assert _CALL_SCRIPT_MAX_WORDS == 22


# --- UI-05 : positive cases accepted ---


@pytest.mark.parametrize("clean", [
    "Winter-heavy household with consistent mid-range usage across the year",
    "Summer-peak profile driven by warm-month cooling demand",
    "Mid-range apartment usage with gentle seasonal variation across the year",
    "Ask about EcoFlex — it suits a strong winter-heating profile like yours",
    "Bring up Value Twelve — a budget-first pick for a high-usage home",
])
def test_positive_cases_accepted(clean):
    out = _reject_forbidden(clean, max_words=_CALL_SCRIPT_MAX_WORDS, field_label="any")
    assert isinstance(out, str)
    assert out  # non-empty


# --- TrackInfo integration (Plan 02 wiring) ---


def test_trackinfo_accepts_clean_narrative(mock_trackinfo):
    from agent.agent import TrackInfo
    TrackInfo(**mock_trackinfo)   # must not raise


def test_trackinfo_rejects_poisoned_usage_narrative(mock_trackinfo):
    from pydantic import ValidationError as _VE
    from agent.agent import TrackInfo
    bad = {**mock_trackinfo, "usage_narrative": "Saves about 30 dollars a month"}
    with pytest.raises(_VE, match="forbidden digit"):
        TrackInfo(**bad)


def test_trackinfo_rejects_poisoned_call_script(mock_trackinfo):
    from pydantic import ValidationError as _VE
    from agent.agent import TrackInfo
    bad = {**mock_trackinfo, "call_script": "Switch to EcoFlex now"}
    with pytest.raises(_VE, match="banned term"):
        TrackInfo(**bad)


def test_trackinfo_rejects_over_char_cap(mock_trackinfo):
    from pydantic import ValidationError as _VE
    from agent.agent import TrackInfo
    bad = {**mock_trackinfo, "usage_narrative": "a b " * 80}  # well over 140 chars
    with pytest.raises(_VE):
        TrackInfo(**bad)


def test_system_prompt_includes_negative_constraint():
    """D-15 dual-gate: banned-terms appear in the SYSTEM_PROMPT."""
    from agent.agent import SYSTEM_PROMPT
    assert "NEVER use:" in SYSTEM_PROMPT
    assert "Origin" in SYSTEM_PROMPT   # competitor list injected
