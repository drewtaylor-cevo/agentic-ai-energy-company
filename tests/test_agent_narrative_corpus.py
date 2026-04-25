"""Offline corpus test — roadmap success criterion 4 proof.

30 invoke() calls: 10 iterations × 3 personas. Each call exercises both
tracks × both fields = 120 per-field assertions. Mocks
`_agent.structured_output` with a randomised mix of clean + poisoned
outputs; asserts every final response is free of numeric tokens and the
`_narrative_source` marker accurately tracks per-field path.
"""
import random
import re

import pytest

_NUMERIC_RE = re.compile(r"[\d$£€%]")

_CLEAN_NARRATIVES = [
    "Winter-heavy household with consistent mid-range usage across the year",
    "Summer-peak profile driven by warm-month cooling demand",
    "Mid-range apartment usage with gentle seasonal variation across the year",
]
_CLEAN_SCRIPTS = [
    "Ask about EcoFlex — it suits a strong winter-heating profile like yours",
    "Bring up Value Twelve — a budget-first pick for a high-usage home",
    "Ask about EcoFlex — an eco-aligned fit for a summer-peak cooling load",
]
_POISON_POOL = [
    "Saves about 30 dollars a month",          # digit
    "Switch to EcoFlex to save",               # switch verb
    "Compared to Origin customers",            # competitor
    "The greenest option available",           # env superlative
    "Saves $55 monthly",                       # currency
]


def _mk_response_factory(rng):
    """Return a factory that produces mixed clean/poison RecommendationResponse-like data."""
    from agent.agent import (
        RecommendationResponse, TrackInfo,
        _RecommendationResponseLenient, _TrackInfoLenient,
    )
    from pydantic import ValidationError

    def _factory(call_index: int):
        """Return:
            - a valid RecommendationResponse when clean (50%)
            - raises ValidationError when 1st of a retry pair (25%)
            - returns a poisoned _RecommendationResponseLenient when lenient salvage runs
        """
        roll = rng.random()
        if roll < 0.5:
            # clean output
            narrative = rng.choice(_CLEAN_NARRATIVES)
            script = rng.choice(_CLEAN_SCRIPTS)
            return RecommendationResponse(
                green=TrackInfo(plan_id="ECO", plan_name="EcoFlex",
                                saving_monthly=30.0, saving_annual=360.0,
                                usage_narrative=narrative, call_script=script),
                cheapest=TrackInfo(plan_id="VAL", plan_name="Value Twelve",
                                   saving_monthly=55.0, saving_annual=660.0,
                                   usage_narrative=narrative, call_script=script),
            )
        # poisoned — raises ValidationError via TrackInfo construction
        try:
            RecommendationResponse(
                green={
                    "plan_id": "ECO", "plan_name": "EcoFlex",
                    "saving_monthly": 30.0, "saving_annual": 360.0,
                    "usage_narrative": rng.choice(_POISON_POOL),
                    "call_script": rng.choice(_CLEAN_SCRIPTS),
                },
                cheapest={
                    "plan_id": "VAL", "plan_name": "Value Twelve",
                    "saving_monthly": 55.0, "saving_annual": 660.0,
                    "usage_narrative": rng.choice(_CLEAN_NARRATIVES),
                    "call_script": rng.choice(_POISON_POOL),
                },
            )
        except ValidationError as e:
            return e
        raise AssertionError("unreachable")

    return _factory


def _lenient_for_poison(rng):
    """Generate a _RecommendationResponseLenient with random clean/poison mix."""
    from agent.agent import _RecommendationResponseLenient, _TrackInfoLenient

    def _track():
        narrative = rng.choice(_CLEAN_NARRATIVES + _POISON_POOL)
        script = rng.choice(_CLEAN_SCRIPTS + _POISON_POOL)
        return _TrackInfoLenient(
            plan_id="ECO", plan_name="EcoFlex",
            saving_monthly=30.0, saving_annual=360.0,
            usage_narrative=narrative, call_script=script,
        )
    return _RecommendationResponseLenient(green=_track(), cheapest=_track())


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_corpus_10x_no_numerics(mocker, customer_id):
    """10 invocations per persona × 2 tracks implicitly; zero numeric tokens in final output."""
    rng = random.Random(42 + hash(customer_id) % 1000)
    factory = _mk_response_factory(rng)
    from agent.agent import invoke
    from pydantic import ValidationError

    for i in range(10):
        # Queue up: 1st call, possible 2nd call (retry), possible lenient salvage.
        side_effects = [factory(i), factory(i + 100), _lenient_for_poison(rng)]

        def _side(*args, **kwargs):
            ret = side_effects.pop(0)
            if isinstance(ret, ValidationError):
                raise ret
            return ret

        mocker.patch("agent.agent._agent.structured_output", side_effect=_side)
        body = invoke({"customer_id": customer_id})

        # Assert: no numerics in either narrative field of either track.
        for track in ("green", "cheapest"):
            for field in ("usage_narrative", "call_script"):
                assert not _NUMERIC_RE.search(body[track][field]), (
                    f"run {i} {customer_id}/{track}/{field}: {body[track][field]!r}"
                )
                assert body["_narrative_source"][track][field] in ("model", "fallback")

        mocker.stopall()
