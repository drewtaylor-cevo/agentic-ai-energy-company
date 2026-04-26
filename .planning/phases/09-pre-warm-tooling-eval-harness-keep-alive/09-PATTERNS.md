# Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive — Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 5 (4 new, 1 modified)
**Analogs found:** 4 / 5 (the bash keep-alive script has no in-repo analog — flagged "New Pattern")

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/prewarm.py` | operator script (CLI) | request-response (HTTP GET, 2-pass warm+measure) | `scripts/capture_samples.py` | exact role; stdlib/stderr/exit-taxonomy conventions byte-for-byte; HTTP replaces boto3 |
| `scripts/demo-keepalive.sh` | operator script (bash daemon loop) | request-response (HTTP ping loop) | **NONE — new pattern** | no `.sh` files exist in repo; pattern sourced from CONTEXT.md canonical refs (bash `trap`, `curl -f -s -o /dev/null -w`, `date -u +%Y-%m-%dT%H:%M:%SZ`) |
| `tests/test_narrative_eval_live.py` | smoke test (live-endpoint) | request-response (HTTP GET × 3 personas) | `tests/test_backend_api_smoke.py` (primary — `pytestmark`, env var, `requests.get`); `tests/test_fallbacks_pass_validator.py` (secondary — `_fails_rules()` helper + word/char cap constants) | exact — dual analog combining env-var/pytestmark pattern with validator-rule-application pattern |
| `tests/test_prewarm_script.py` | offline pytest (mocked I/O) | request-response (mocked `urllib.request.urlopen`) | `tests/test_backend_api_handler.py` (primary — `@patch(...)` + `MagicMock` + `pytestmark = pytest.mark.skipif(...)`); `tests/test_fallbacks_pass_validator.py` (secondary — helper-function + individual-test-function style) | role-match — handler test mocks boto3 client; prewarm test mocks urllib |
| `ui/package.json` | config (npm scripts block) | N/A | `ui/package.json` itself (existing `scripts` block) | exact — one-line append to existing block |

## Pattern Assignments

### `scripts/prewarm.py` (operator script, request-response)

**Analog:** `scripts/capture_samples.py` (57 lines, stdlib-first convention reference)

**Shebang + module docstring + stdlib imports pattern** (capture_samples.py lines 1-17):
```python
#!/usr/bin/env python3
"""Phase 6 sample capture — one-shot live dump to 06-SAMPLES.md.
...
Usage:
    AWS_DEFAULT_REGION=us-east-1 \\
    AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:... \\
    python3 scripts/capture_samples.py
"""
import json
import os
import sys
import uuid
from pathlib import Path
```
**Copy for prewarm.py:** identical shebang, identical docstring shape (purpose + multi-line `Usage:` block naming `BACKEND_API_URL`). Replace imports with `import urllib.request, urllib.error, time, os, statistics, sys, socket` per D-01.

**Exit-taxonomy + env-var-fast-fail pattern** (capture_samples.py lines 20-26):
```python
def main() -> int:
    arn = os.environ.get("AGENT_RUNTIME_ARN")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    if not arn:
        print("AGENT_RUNTIME_ARN not set", file=sys.stderr)
        return 2
```
**Copy for prewarm.py:** identical `def main() -> int:` signature, identical `os.environ.get` + `if not …: print(..., file=sys.stderr); return 2` shape — but with `BACKEND_API_URL` and the D-05 error string `"BACKEND_API_URL not set"`. D-06 extends the taxonomy: return 1 on gate-fail / non-204 / non-200; return 0 on happy path.

**`if __name__ == "__main__"` convention** (capture_samples.py lines 58-59):
```python
if __name__ == "__main__":
    sys.exit(main())
```
**Copy verbatim** — this is the project convention for CLI scripts.

**Stderr-for-progress pattern** (capture_samples.py lines 43, 54):
```python
print(f"Invoking {cust} ...", file=sys.stderr)
...
print(f"Wrote {out}", file=sys.stderr)
```
**Adapt for prewarm.py:** D-04 inverts this — happy-path progress (per-call latency lines + summary block) goes to **stdout** (one-line-per-call format); only setup errors (exit 2) go to stderr. This is the Claude's-Discretion item in CONTEXT.md: planner confirms stdout for latency logs, stderr for exit-2 errors.

**Per-persona iteration pattern** (capture_samples.py lines 34, 42):
```python
personas = ["CUST-001", "CUST-002", "CUST-003"]
...
for cust in personas:
    print(f"Invoking {cust} ...", file=sys.stderr)
    resp = client.invoke_agent_runtime(...)
```
**Copy for prewarm.py:** same `personas = [...]` list literal; two iteration passes per D-02 (warm pass with `?prewarm=1` + 2s spacing, then 30s wait, then measurement pass with 3 timed calls per persona via `time.perf_counter()`).

---

### `scripts/demo-keepalive.sh` (operator script, bash daemon loop)

**Analog:** **NONE — new pattern.** No `.sh` files exist in the repo (confirmed via `find . -maxdepth 3 -name "*.sh"`). CONTEXT.md canonical refs section line 218-219 is the sole source.

**Pattern assembled from CONTEXT.md canonical refs** (D-16, D-17, D-18, D-19 + external docs):

Shebang + strict mode (D-16):
```bash
#!/usr/bin/env bash
set -euo pipefail
```

Fast-fail on missing `BACKEND_API_URL` before the loop (D-19):
```bash
: "${BACKEND_API_URL:?BACKEND_API_URL not set}"
```

Deterministic rotation index (D-17 + specifics line 263):
```bash
personas=(CUST-001 CUST-002 CUST-003)
tick_count=0
```
Each tick computes `index=$((tick_count % 3))` and dereferences `persona="${personas[$index]}"`. Tick 0 → CUST-001, tick 1 → CUST-002, tick 2 → CUST-003, tick 3 → CUST-001, …

Signal trap for clean shutdown (D-18 + Claude's Discretion item on SIGHUP):
```bash
trap 'echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] keepalive stopped after ${tick_count} ticks"; exit 0' INT TERM HUP
```
`INT TERM HUP` covers Ctrl-C, `kill`, and tmux-pane-close per Claude's Discretion "trap handles SIGHUP — recommend yes."

Curl invocation shape (CONTEXT.md external refs line 217):
```bash
curl -f -s -o /dev/null -w '%{http_code} %{time_total}' \
  "${BACKEND_API_URL}/recommendations/${persona}?prewarm=1"
```
`-f` fails loudly on 4xx/5xx, `-s` silences progress, `-o /dev/null` discards body, `-w` prints status+time to stdout.

ISO-8601 UTC timestamp (D-19 line 118 + CONTEXT.md external refs):
```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```
Produces e.g. `2026-04-26T14:23:45Z` verbatim.

One-line-per-tick log (D-19):
```
2026-04-26T14:23:45Z CUST-001 204 312ms ok
```
Fields: `<UTC-timestamp> <persona> <http_status> <latency_ms> <verdict>`. Verdict is `ok` on 204, `WARN` on anything else (loop continues per D-19; Phase 7 D-04 guarantees 204 on all failure modes).

Sleep cadence (D-18): `sleep 600` per tick. No auto-stop clock — operator owns lifecycle (SC-3 "continues through termination").

Full loop skeleton (assembled from the above):
```bash
while true; do
  index=$((tick_count % 3))
  persona="${personas[$index]}"
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  result=$(curl -f -s -o /dev/null -w '%{http_code} %{time_total}' \
    "${BACKEND_API_URL}/recommendations/${persona}?prewarm=1" || echo "ERR 0")
  # parse $result into status + latency, format latency as ms, print one line
  tick_count=$((tick_count + 1))
  sleep 600
done
```

Target length (D-16): ~30 lines total.
Quality gate (D-21): `shellcheck scripts/demo-keepalive.sh` zero warnings (or documented suppressions — specifics line 264).

---

### `tests/test_narrative_eval_live.py` (smoke test, live-endpoint)

**Primary analog:** `tests/test_backend_api_smoke.py` (84 lines, byte-for-byte pattern per D-09)
**Secondary analog:** `tests/test_fallbacks_pass_validator.py` (57 lines, validator-rule-application per D-12)

**Smoke-gate pytestmark pattern** (test_backend_api_smoke.py lines 1-19):
```python
"""Live HTTP smoke tests for Phase 3 Backend API — requires deployed stack.

Skipped unless BACKEND_API_URL env var is set to the deployed API endpoint.
Tests all 3 demo personas, error cases (400/404), and session isolation.
"""
import os

import pytest
import requests

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BACKEND_API_URL,
        reason="BACKEND_API_URL not set — skip live backend API smoke tests",
    ),
]
```
**Copy for test_narrative_eval_live.py:** identical module docstring shape (purpose + smoke-gate explanation), identical `BACKEND_API_URL` read with `.rstrip("/")`, identical `pytestmark = [...]` list with both `pytest.mark.smoke` and `pytest.mark.skipif`. Only change: `reason=` string updated for the narrative-eval context.

**Parametrized-per-persona HTTP GET pattern** (test_backend_api_smoke.py lines 25-38):
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_all_personas_return_recommendations(customer_id):
    """SC-1: GET /recommendations/{customer_id} returns 200 with green + cheapest."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"
```
**Copy for test_narrative_eval_live.py:** identical `@pytest.mark.parametrize("customer_id", …)` decorator, identical `requests.get(..., timeout=60)` call (specifics line 266: eval harness uses `requests` to match this file byte-for-byte, while `prewarm.py` uses `urllib` to avoid a runtime dep), identical assertion-with-context-message style. D-11 specifies one HTTP GET per persona (3 total calls), each yielding 2 tracks × 2 narrative fields = 4 strings asserted.

**Validator-rule-application helper** (test_fallbacks_pass_validator.py lines 9-29):
```python
from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
from agent.narrative.fallbacks import FALLBACKS

_USAGE_NARRATIVE_MAX_WORDS = 20
_CALL_SCRIPT_MAX_WORDS = 22
_USAGE_NARRATIVE_MAX_CHARS = 140
_CALL_SCRIPT_MAX_CHARS = 180


def _fails_rules(value: str, max_words: int, max_chars: int):
    """Return failure reason string, or None if value is clean."""
    if NUMERIC_REGEX.search(value):
        return f"forbidden digit/currency in {value!r}"
    m = BANNED_REGEX.search(value)
    if m:
        return f"banned term {m.group()!r} in {value!r}"
    if len(value.split()) > max_words:
        return f"{len(value.split())} words > {max_words} cap in {value!r}"
    if len(value) > max_chars:
        return f"{len(value)} chars > {max_chars} cap in {value!r}"
    return None
```
**Copy for test_narrative_eval_live.py verbatim:** D-12 mandates the import + 4 constants + `_fails_rules()` helper mirror this file exactly. DO NOT import `FALLBACKS` (eval harness reads live API, not fallbacks). DO NOT import the Pydantic `TrackInfo` model (D-12 rationale: model requires unrelated fields like `plan_id`/`saving_monthly`; regex + caps is the minimal surface).

**Assertion loop structure** (test_fallbacks_pass_validator.py lines 32-45):
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
@pytest.mark.parametrize("track", ["green", "cheapest"])
def test_usage_narrative_fallback_passes(customer_id, track):
    value = FALLBACKS[customer_id][track]["usage_narrative"]
    reason = _fails_rules(value, _USAGE_NARRATIVE_MAX_WORDS, _USAGE_NARRATIVE_MAX_CHARS)
    assert reason is None, f"{customer_id}/{track}/usage_narrative: {reason}"
```
**Adapt for test_narrative_eval_live.py:** D-11 collapses to **one HTTP call per persona** (not per track — the response body carries both tracks). Shape becomes:
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_narrative_eval_live(customer_id):
    r = requests.get(f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60)
    assert r.status_code == 200, f"..."
    body = r.json()
    assert "_narrative_source" not in body, f"D-06 marker leaked for {customer_id}"
    for track in ("green", "cheapest"):
        for field, max_words, max_chars in (
            ("usage_narrative", _USAGE_NARRATIVE_MAX_WORDS, _USAGE_NARRATIVE_MAX_CHARS),
            ("call_script", _CALL_SCRIPT_MAX_WORDS, _CALL_SCRIPT_MAX_CHARS),
        ):
            value = body[track][field]
            reason = _fails_rules(value, max_words, max_chars)
            assert reason is None, f"{customer_id}/{track}/{field}: {reason}"
```
D-13 three-part assertion set: (a) 200 + presence on both tracks, (b) validator rules pass, (c) `_narrative_source` absent (Phase 7 D-06 invariant). 12 assertions per run (3 personas × 2 tracks × 2 fields).

---

### `tests/test_prewarm_script.py` (offline pytest, mocked I/O)

**Primary analog:** `tests/test_backend_api_handler.py` (mock + `pytestmark.skipif` on import; the module-under-test pattern)
**Secondary analog:** `tests/test_fallbacks_pass_validator.py` (individual-function test style per D-20 Claude's-Discretion item — "recommend individual functions … parametrize would obscure distinct semantics")

**Mocked-client import-guard pattern** (test_backend_api_handler.py lines 1-25):
```python
"""Offline unit tests for api_lambda/handler.py — no AWS credentials needed.

Mocks the module-level _agentcore_client to test all handler paths:
validation, success pass-through, error taxonomy (400/404/502/504/500),
and fresh session ID per invocation (D-11).
"""
import io
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

try:
    from api_lambda.handler import handler
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda.handler import failed: {}".format(_IMPORT_ERROR),
)
```
**Adapt for test_prewarm_script.py:** identical docstring shape ("Offline unit tests for scripts/prewarm.py — no network needed"). Identical `try: import ... _CAN_IMPORT = True` import-guard around `scripts.prewarm` (handles the case where `scripts/` is not on sys.path by default — planner decides whether to add a `conftest.py` sys.path shim or restructure imports). Identical `pytestmark = pytest.mark.skipif(not _CAN_IMPORT, ...)`. NOTE: this test must NOT carry `pytest.mark.smoke` — it runs under `pytest -m "not smoke"` per D-20 last line ("keeps the existing 81-passed/6-skipped baseline intact").

**Mock-decorator + per-test helper pattern** (test_backend_api_handler.py lines 28-56):
```python
def _make_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event with pathParameters."""
    return {"pathParameters": {"customer_id": customer_id}}


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response (StreamingBody via BytesIO)."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


@patch("api_lambda.handler._agentcore_client")
def test_valid_customer_success(mock_client, mock_savings_response):
    """SC-1: valid CUST-001 returns 200 with green + cheapest."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 200
```
**Adapt for test_prewarm_script.py:** D-20 mandates mocking `urllib.request.urlopen` (not boto3). Helper function shape becomes something like:
```python
def _make_urlopen_response(status: int, body: bytes = b""):
    """Context-manager mock matching urllib.request.urlopen's return shape."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp
```
Decorator shape: `@patch("scripts.prewarm.urllib.request.urlopen")` (patches the import location, not `urllib.request.urlopen` globally — same convention as `@patch("api_lambda.handler._agentcore_client")`).

**Seven individual test functions** (D-20 enumerates; individual-function style per Claude's-Discretion recommendation):

| Test | Purpose | Key mock setup |
|------|---------|----------------|
| `test_prewarm_happy_path_exit_0` | all 204s + all <3000ms → exit 0 | urlopen returns 204, then 200 with fast latencies |
| `test_prewarm_gate_fail_exit_1` | median ≥3000ms → exit 1 | patch `time.perf_counter` to force [3174, 3050, 3100] |
| `test_prewarm_bad_prewarm_response_exit_1` | `?prewarm=1` returns 500 → exit 1, fast-fail | urlopen returns 500 on first call |
| `test_prewarm_missing_env_var_exit_2` | `monkeypatch.delenv('BACKEND_API_URL')` → exit 2 | use `monkeypatch` fixture |
| `test_prewarm_measurement_timeout_pushes_median` | `socket.timeout` → ≥3000ms sample | `urlopen.side_effect = socket.timeout()` |
| `test_prewarm_per_call_log_format` | capsys captures D-04 format | use `capsys` fixture; assert `"prewarm CUST-001: 204"` in captured.out |
| `test_prewarm_median_computation` | known samples → median matches | unit-test `statistics.median` integration |

Invocation style per function follows handler-test pattern: `result = prewarm.main()` then `assert result == 0` (or 1/2) plus `captured = capsys.readouterr(); assert "..." in captured.out`.

---

### `ui/package.json` (config, scripts block append)

**Analog:** `ui/package.json` itself (self-analog — one-line addition to existing block)

**Existing `scripts` block** (lines 6-15):
```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "build:mock": "VITE_API_URL= vite build --outDir dist-mock",
    "lint": "eslint .",
    "preview": "vite preview",
    "preview:mock": "vite preview --outDir dist-mock",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

**Add one line** per D-07:
```json
    "prewarm": "cd .. && python3 scripts/prewarm.py",
```

Placement: alongside other scripts (alphabetical or functional grouping — planner's call). Trailing comma semantics preserved (if `prewarm` is not the last entry, ensure comma; if last, no comma). Match 2-space indentation convention.

---

## Shared Patterns

### Env-var-first live-stack addressing
**Source:** `tests/test_backend_api_smoke.py` lines 11-19 (and `scripts/capture_samples.py` lines 21-25 for the missing-var-exit-2 shape)
**Apply to:** `scripts/prewarm.py`, `scripts/demo-keepalive.sh`, `tests/test_narrative_eval_live.py`
```python
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")
```
Three artefacts share one env var — no flags, no config files, no hard-coded fallback. For `prewarm.py` and `demo-keepalive.sh`, missing env var → exit 2 / fast-fail before any HTTP call. For `test_narrative_eval_live.py`, missing env var → `pytest.mark.skipif` skips the whole module.

### stdlib-first for operator scripts
**Source:** `scripts/capture_samples.py` lines 13-17 (imports) and line 27 (lazy boto3 import comment)
**Apply to:** `scripts/prewarm.py` only (demo-keepalive.sh uses `curl` which is system-provided)
Project convention from Phase 6: operator scripts avoid non-stdlib Python deps. `capture_samples.py` uses `boto3` but lazy-imports it with a comment. `prewarm.py` avoids this entirely (D-01 — uses `urllib` instead of `requests`). D-23 freeze-surface rationale: "a demo-critical script should depend on nothing you need to lockfile-pin."

### 0/1/2 exit taxonomy for CLI scripts
**Source:** `scripts/capture_samples.py` (uses 0/2 only; Phase 9 extends to 0/1/2 per D-06)
**Apply to:** `scripts/prewarm.py`
```python
# 0: happy path — all personas under gate
# 1: gate-fail OR non-204 on prewarm call OR non-200 on measurement call (demo-broken)
# 2: setup error — missing env var, DNS failure on first call, import error
```
`demo-keepalive.sh` uses only `exit 0` from the trap (SC-3 "continues through termination" means no gate-fail exit — non-204 just logs `WARN` and continues).

### Pytest smoke-marker for live-endpoint tests
**Source:** `tests/test_backend_api_smoke.py` lines 13-19
**Apply to:** `tests/test_narrative_eval_live.py` only
```python
pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not BACKEND_API_URL, reason="..."),
]
```
`tests/test_prewarm_script.py` does NOT carry `pytest.mark.smoke` — it's offline and must run green under `pytest -m "not smoke"` per D-20.

### Import-guard pytestmark for tests that depend on importable modules
**Source:** `tests/test_backend_api_handler.py` lines 14-25
**Apply to:** `tests/test_prewarm_script.py`
```python
try:
    from scripts import prewarm
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(not _CAN_IMPORT, reason=...)
```
Defensive: if `scripts/` is not on pytest's sys.path, the test module skips rather than erroring at collection.

### `if __name__ == "__main__": sys.exit(main())` convention
**Source:** `scripts/capture_samples.py` lines 58-59
**Apply to:** `scripts/prewarm.py`
All Python CLI entry points in this repo use this pattern. Body of `main()` returns int; `sys.exit()` propagates to shell exit code. Matches D-06 exit taxonomy.

### Assertion-with-context-message style
**Source:** `tests/test_backend_api_smoke.py` lines 31-38 + `tests/test_fallbacks_pass_validator.py` line 37
**Apply to:** `tests/test_narrative_eval_live.py`, `tests/test_prewarm_script.py`
```python
assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
assert reason is None, f"{customer_id}/{track}/usage_narrative: {reason}"
```
On failure, the message carries enough context (persona, track, field, offending string) that the operator can diagnose without re-running with `-v`. D-15 requires this format for the eval harness.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/demo-keepalive.sh` | operator script (bash daemon loop) | request-response ping loop | No `.sh` files exist in the repo (verified). Pattern assembled from CONTEXT.md canonical external refs: bash `trap INT TERM HUP`, `curl -f -s -o /dev/null -w '%{http_code} %{time_total}'`, `date -u +%Y-%m-%dT%H:%M:%SZ`. Planner writes ~30-line script from scratch against D-16 through D-19. `shellcheck` is the sole offline quality gate (D-21). |

---

## Metadata

**Analog search scope:** `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/scripts/`, `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/tests/`, `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/package.json`, `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/agent/narrative/`
**Files scanned:** 6 analogs fully read (`scripts/capture_samples.py`, `tests/test_backend_api_smoke.py`, `tests/test_fallbacks_pass_validator.py`, `tests/test_backend_api_handler.py` header, `agent/narrative/banned_terms.py`, `ui/package.json`, `tests/conftest.py`)
**Bash analog search:** `find . -maxdepth 3 -name "*.sh" -not -path "*/node_modules/*" -not -path "*/.claude/*"` → zero results
**Pattern extraction date:** 2026-04-26
