---
phase: 09-pre-warm-tooling-eval-harness-keep-alive
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - scripts/prewarm.py
  - scripts/demo-keepalive.sh
  - ui/package.json
  - tests/test_narrative_eval_live.py
  - tests/test_prewarm_script.py
findings:
  critical: 0
  warning: 2
  info: 6
  total: 8
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-04-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed all five Phase 9 deliverables at standard depth. Overall quality is high — the code is well-commented, stays within stated freeze surfaces, and maps cleanly to the plan's decision tokens (D-02/D-04/D-06/D-08/D-12/D-21). No Critical issues and no security vulnerabilities were found.

Two Warnings are worth flagging:

1. `tests/test_narrative_eval_live.py` performs an unconditional top-level `import requests`, which means `pytest -m "not smoke"` will still fail at collection time if `requests` is not importable in the test environment. This partially undermines the smoke-gating invariant that non-smoke runs collect 0 tests from this module.
2. The `_narrative_source` leak assertion in the same file only checks top-level keys — if a future regression nests the marker under `body["green"]` or `body["cheapest"]`, this guard misses it.

The remaining findings are minor quality items (misleading variable names, weak tautological test assertions, redundant exception types). No bugs, data corruption risks, or security problems detected.

## Warnings

### WR-01: Unconditional `import requests` breaks module isolation for `-m "not smoke"` runs

**File:** `tests/test_narrative_eval_live.py:27`
**Issue:** The module is smoke-gated via `pytestmark = [pytest.mark.smoke, ...]`, and the phase plan's acceptance criterion states that `pytest -m "not smoke"` must collect zero tests from this module. However, pytest's collection phase **imports the module before evaluating marker filters**. If the `requests` package is not installed in the environment running `pytest -m "not smoke"`, collection fails with `ImportError` — even though no test from this module would ever run. This converts a "quietly skipped" contract into a hard failure whenever the non-smoke dev dependency set diverges from the smoke dependency set.

**Fix:** Guard the import with `importorskip`, mirroring the pattern used in the companion test file for optional deps:

```python
import os

import pytest

requests = pytest.importorskip("requests")  # collected-but-skipped if requests not installed

from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
```

Alternatively, if `requests` is a hard dependency of the project (verify via `pyproject.toml`/`requirements.txt`), document that invariant in the module docstring so future readers don't assume it's optional. Either way, the current file-level `import requests` should either be guarded or explicitly defended.

### WR-02: `_narrative_source` leak check only inspects top-level keys

**File:** `tests/test_narrative_eval_live.py:88-91`
**Issue:** The assertion `"_narrative_source" not in body` relies on Python's `in`-operator-on-dict semantics, which checks only the **top-level** keys of `body`. The Phase 7 D-06 invariant is that the marker must never reach the client, but a future code path that injects the marker into `body["green"]` or `body["cheapest"]` (e.g., a partial Lambda sanitiser that strips only the outer layer) would silently pass this guard. Given this harness is the closeout gate for the invariant, the blind spot matters.

**Fix:** Walk the response body recursively, or at minimum include the per-track dicts in the check:

```python
def _contains_marker(obj) -> bool:
    """Return True if '_narrative_source' appears anywhere in the response tree."""
    if isinstance(obj, dict):
        if "_narrative_source" in obj:
            return True
        return any(_contains_marker(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_marker(item) for item in obj)
    return False

assert not _contains_marker(body), (
    f"D-06 violation for {customer_id}: _narrative_source leaked "
    f"to client somewhere in response tree (body={body!r})"
)
```

## Info

### IN-01: Variable name `medians` holds raw samples, not medians

**File:** `scripts/prewarm.py:82`
**Issue:** `medians: dict[str, list[int]] = {persona: [] for persona in PERSONAS}` — the dict value is a list of raw per-call elapsed-ms **samples**, not medians. Medians are computed inline at line 109 via `statistics.median(medians[persona])`. The current name makes the code harder to read and invites confusion about whether `medians[persona]` has already been collapsed to a single value.
**Fix:** Rename to `samples` (or `latencies_by_persona`):

```python
samples: dict[str, list[int]] = {persona: [] for persona in PERSONAS}
# ...
samples[persona].append(elapsed_ms)
# ...
median_ms = int(statistics.median(samples[persona]))
```

### IN-02: `failed_persona` only tracks the first failed persona

**File:** `scripts/prewarm.py:107,114-116,121`
**Issue:** When multiple personas fail the gate, the summary line `"{failed_persona} failed — exit 1"` names only the first. This matches the D-06 wording ("first failed persona"), but operators reading the log may assume the *only* failure. The per-persona "FAIL" lines above are authoritative, so this is a log-clarity concern, not a bug.
**Fix:** Either tighten the wording or list all failures:

```python
failed_personas = [p for p in PERSONAS if int(statistics.median(samples[p])) >= MEDIAN_GATE_MS]
if failed_personas:
    print(f"{', '.join(failed_personas)} failed — exit 1")
```

### IN-03: Redundant exception type in `except` tuple

**File:** `scripts/prewarm.py:58`
**Issue:** `except (urllib.error.URLError, ConnectionRefusedError, socket.gaierror, socket.timeout)` — `urllib.error.URLError` already wraps `ConnectionRefusedError` and `socket.gaierror` as its `.reason` attribute when the underlying socket raises them. Listing them separately is redundant (though not incorrect: direct raises of `ConnectionRefusedError` are theoretically possible at lower layers).
**Fix:** Simplify to `except (urllib.error.URLError, socket.timeout) as exc:` unless there's a concrete scenario where a bare `ConnectionRefusedError`/`socket.gaierror` escapes `urlopen`. Low priority — current form is defensive and harmless.

### IN-04: Missing return type annotation on helper

**File:** `tests/test_narrative_eval_live.py:49`
**Issue:** `def _fails_rules(value: str, max_words: int, max_chars: int):` — the function returns `str | None` but the annotation is omitted, inconsistent with the parameter annotations.
**Fix:**

```python
def _fails_rules(value: str, max_words: int, max_chars: int) -> str | None:
```

Matches the behaviour documented in the docstring ("Return failure reason string, or None if value is clean").

### IN-05: `test_prewarm_median_computation` mostly exercises the Python stdlib

**File:** `tests/test_prewarm_script.py:201-212`
**Issue:** Five of the seven executable lines in this test assert behaviour of `statistics.median` directly (`_stats.median([1000, 2000, 3000]) == 2000`, etc.) rather than behaviour of `scripts/prewarm.py`. Only lines 211-212 touch the module under test, and they do so via a source-text grep (`assert "statistics.median" in prewarm_src`) — a comment reading `# uses statistics.median` would satisfy the check. The test name promises a behaviour test, but the weight is on tautological stdlib assertions plus a weak textual grep.
**Fix:** Either delete the stdlib-only assertions (they add no signal), or rewrite the test to construct samples, call the gate-evaluation logic directly, and assert the resulting exit code — similar to `test_prewarm_gate_fail_exit_1` but parameterised across median boundary cases (2999ms PASS, 3000ms FAIL, 3001ms FAIL).

### IN-06: `npm run prewarm` assumes `python3` is on PATH

**File:** `ui/package.json:13`
**Issue:** `"prewarm": "cd .. && python3 scripts/prewarm.py"` hardcodes the `python3` binary name. On Windows, the canonical command is `python` (via the py-launcher shim); `python3` may not be on PATH. Given this is a demo script for macOS/Linux presenters this is probably fine, but a future contributor on Windows will hit a cryptic failure.
**Fix:** Either document the macOS/Linux assumption in the script's README or prefer a cross-platform entrypoint. No change required for the demo milestone.

---

_Reviewed: 2026-04-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
