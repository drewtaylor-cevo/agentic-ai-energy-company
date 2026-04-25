"""Banned-terms regex constants for narrative validation.

STRIDE: V5 Input Validation — compiled-once regex rejects narrative outputs
containing competitor names, switch verbs, environmental superlatives,
digits, or currency symbols before they reach the API response.

Frozen at DEMO-04. Expansion during PR review only (per CONTEXT.md D-13).
Do NOT expand inside the freeze window.
"""
import re

# --- Tuple constants ---

# D-12 locked (regulator-visible risk). Non-negotiable.
# Grep anchor: "Origin", "AGL", "EnergyAustralia", "Red Energy", "Alinta", "Momentum"
COMPETITORS = (
    "Origin",
    "AGL",
    "EnergyAustralia",
    "Red Energy",
    "Alinta",
    "Momentum",
)

# D-13 starter set. Base form + common inflections. Expand only in PR review.
SWITCH_VERBS = (
    "switch", "switches", "switching", "switched",
    "move", "moves", "moving", "moved",
    "change", "changes", "changing", "changed",
    "transfer", "transfers", "transferring", "transferred",
    "swap", "swaps", "swapping", "swapped",
    "shift", "shifts", "shifting", "shifted",
    "convert", "converts", "converting", "converted",
)

# D-13 starter set. Multi-word tokens included.
ENV_SUPERLATIVES = (
    "greenest",
    "cleanest",
    "most sustainable",
    "carbon-neutral",
    "carbon neutral",
    "zero-emission",
    "zero emission",
    "net-zero",
    "net zero",
    "best for the planet",
    "planet-friendly",
    "eco-friendliest",
)

# --- Compiled patterns (module-level — zero per-invocation overhead) ---

# D-14: case-insensitive word-boundary regex. Benchmarked at 3.5 µs/call
# on realistic narrative-length strings (2026-04-25 local run).
BANNED_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in COMPETITORS + SWITCH_VERBS + ENV_SUPERLATIVES) + r")\b",
    re.IGNORECASE,
)

# Any digit OR any of $ £ € %. Rejects "30 dollars", "$30", "15%".
NUMERIC_REGEX = re.compile(r"[\d$£€%]")
