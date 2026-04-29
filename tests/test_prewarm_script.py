"""Offline unit tests for scripts/prewarm.py — no network needed.

Mocks urllib.request.urlopen at the module-under-test's import site to cover:
- Happy path (all 204s + all <3000ms medians → exit 0)
- Gate-fail (median ≥3000ms → exit 1)
- Bad prewarm response (non-204 on ?prewarm=1 → exit 1, fast-fail)
- Missing env var (BACKEND_API_URL unset → exit 2)
- Measurement timeout (socket.timeout pushes median over gate)
- Per-call log format (D-04)
- Median computation (statistics.median correctness)

Runs under `pytest -m "not smoke"` — this module carries NO @pytest.mark.smoke.
"""
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ is not on sys.path by default — add the repo root so `from scripts import prewarm` resolves.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))

try:
    from scripts import prewarm
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:  # pragma: no cover — defensive skip on import failure
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="scripts.prewarm import failed: {}".format(_IMPORT_ERROR),
)


def _make_urlopen_response(status: int, body: bytes = b""):
    """Context-manager mock matching urllib.request.urlopen's return shape.

    Used as: mock_urlopen.return_value = _make_urlopen_response(204)
    Supports: `with urlopen(...) as resp: resp.status; resp.read()`
    """
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


@pytest.fixture(autouse=True)
def _no_real_sleeps(monkeypatch):
    """Stub time.sleep in scripts.prewarm so the 30s settle wait + 2s spacings don't slow the suite."""
    monkeypatch.setattr("scripts.prewarm.time.sleep", lambda *_args, **_kwargs: None)


@patch("scripts.prewarm.urllib.request.urlopen")
def test_prewarm_happy_path_exit_0(mock_urlopen, monkeypatch, capsys):
    """D-06: all personas under gate → exit 0 + 'all personas under gate — exit 0' line.

    Phase 13 A-01/A-03: 2 personas × 3 warming passes = 6 warm 204s;
    2 personas × 3 measurement samples = 6 measurement 200s.
    """
    monkeypatch.setenv("BACKEND_API_URL", "https://mock.example")
    # 6 prewarm 204s (CUST-001 x3 + CUST-003 x3), then 6 measurement 200s.
    mock_urlopen.side_effect = [
        _make_urlopen_response(204) for _ in range(6)
    ] + [
        _make_urlopen_response(200, b'{"green":{},"cheapest":{}}') for _ in range(6)
    ]
    # perf_counter is called: t_start (1x), then per warm call (2x = start/stop, 6 calls),
    # then per measurement call (2x = start/stop, 6 calls), then total at end (1x).
    # Total: 1 + 12 + 12 + 1 = 26. Provide a generous sequence.
    counters = iter([i * 0.1 for i in range(60)])
    monkeypatch.setattr("scripts.prewarm.time.perf_counter", lambda: next(counters))
    result = prewarm.main()
    assert result == 0, f"Expected exit 0, got {result}"
    out = capsys.readouterr().out
    assert "all personas under gate — exit 0" in out, f"Missing D-04 final line; stdout was:\n{out}"


@patch("scripts.prewarm.urllib.request.urlopen")
def test_prewarm_gate_fail_exit_1(mock_urlopen, monkeypatch, capsys):
    """D-06: median above per-flow gate → exit 1 + 'FAIL' in that persona's summary line.

    Phase 13 A-01: CUST-003 gate is 2500ms (multi-tool). Measurement medians
    above 2500ms should trip the gate and exit 1.
    """
    monkeypatch.setenv("BACKEND_API_URL", "https://mock.example")
    # 6 warm 204s + 6 measurement 200s.
    mock_urlopen.side_effect = [
        _make_urlopen_response(204) for _ in range(6)
    ] + [
        _make_urlopen_response(200, b"{}") for _ in range(6)
    ]
    # Warm pass: t_start (0.0), then 6 warm call pairs (all fast ~100ms).
    # Measurement: CUST-001 fast (~100ms) — under 3000ms gate.
    # CUST-003 [2600, 2550, 2700]ms — median 2600 >= 2500ms gate, fails.
    # Sequence: [t_start, warm×12, meas×12, t_end] = 26 values.
    counters = iter([
        0.0,                                                      # t_start
        0.0, 0.1, 0.1, 0.2, 0.2, 0.3,                             # CUST-001 warm pass 1/2/3 (start/stop)
        0.3, 0.4, 0.4, 0.5, 0.5, 0.6,                             # CUST-003 warm pass 1/2/3
        # CUST-001 measurement: 3 × ~100ms (under 3000ms gate)
        0.6, 0.7, 0.7, 0.8, 0.8, 0.9,
        # CUST-003 measurement: [2600, 2550, 2700]ms → median 2600 >= 2500ms gate → FAIL
        0.9, 3.5, 3.5, 6.05, 6.05, 8.75,
        10.0,                                                     # t_end
    ])
    monkeypatch.setattr("scripts.prewarm.time.perf_counter", lambda: next(counters))
    result = prewarm.main()
    assert result == 1, f"Expected exit 1, got {result}"
    out = capsys.readouterr().out
    assert "median CUST-003" in out and "FAIL" in out, (
        f"Missing D-04 gate-fail line for CUST-003; stdout:\n{out}"
    )
    assert "exit 1" in out, f"Missing 'exit 1' summary token; stdout:\n{out}"


@patch("scripts.prewarm.urllib.request.urlopen")
def test_prewarm_bad_prewarm_response_exit_1(mock_urlopen, monkeypatch, capsys):
    """D-06: non-204 on ?prewarm=1 → exit 1 before measurement pass starts (D-02 step 1 last sentence)."""
    monkeypatch.setenv("BACKEND_API_URL", "https://mock.example")
    # First prewarm call returns 500 — should fast-fail immediately
    mock_urlopen.side_effect = [_make_urlopen_response(500)] + [
        _make_urlopen_response(200, b"{}") for _ in range(11)  # never consumed
    ]
    # Provide enough perf_counter values even though we fast-fail.
    counters = iter([i * 0.1 for i in range(30)])
    monkeypatch.setattr("scripts.prewarm.time.perf_counter", lambda: next(counters))
    result = prewarm.main()
    assert result == 1, f"Expected exit 1 on 500 prewarm response, got {result}"
    out = capsys.readouterr().out
    # The measurement pass must NOT have run: no "warm 1/3" lines present
    assert "warm 1/3" not in out, f"Measurement pass ran despite prewarm failure; stdout:\n{out}"
    # And only ONE urlopen call should have happened (fast-fail)
    assert mock_urlopen.call_count == 1, f"Expected 1 urlopen call, got {mock_urlopen.call_count}"


def test_prewarm_missing_env_var_exit_2(monkeypatch, capsys):
    """D-05, D-06: missing BACKEND_API_URL → exit 2 + 'BACKEND_API_URL not set' on stderr."""
    monkeypatch.delenv("BACKEND_API_URL", raising=False)
    result = prewarm.main()
    assert result == 2, f"Expected exit 2, got {result}"
    captured = capsys.readouterr()
    assert "BACKEND_API_URL not set" in captured.err, f"Missing exact error string on stderr; stderr:\n{captured.err}"


@patch("scripts.prewarm.urllib.request.urlopen")
def test_prewarm_measurement_timeout_pushes_median(mock_urlopen, monkeypatch, capsys):
    """D-08: socket.timeout on a measurement call → treated as >= gate-ceiling sample → median fails gate.

    Phase 13 A-01/A-03: 2 personas × 3 warming passes = 6 warm 204s. Two
    CUST-001 measurement timeouts + one fast sample sends the median to the
    timeout sentinel (max(GATE_MS.values()) = 3000ms), failing CUST-001's
    3000ms gate.
    """
    monkeypatch.setenv("BACKEND_API_URL", "https://mock.example")
    # 6 warm 204s (CUST-001 x3 + CUST-003 x3), then:
    # CUST-001 measurement: [TIMEOUT, TIMEOUT, 200ms OK] → median = 3000 (sentinel) → FAIL
    # CUST-003 measurement: 3 x fast
    mock_urlopen.side_effect = [
        _make_urlopen_response(204),  # CUST-001 warm pass 1
        _make_urlopen_response(204),  # CUST-001 warm pass 2
        _make_urlopen_response(204),  # CUST-001 warm pass 3
        _make_urlopen_response(204),  # CUST-003 warm pass 1
        _make_urlopen_response(204),  # CUST-003 warm pass 2
        _make_urlopen_response(204),  # CUST-003 warm pass 3
        socket.timeout(),              # CUST-001 measure 1/3 → TIMEOUT
        socket.timeout(),              # CUST-001 measure 2/3 → TIMEOUT
        _make_urlopen_response(200, b"{}"),  # CUST-001 measure 3/3 → 200ms
        _make_urlopen_response(200, b"{}"),  # CUST-003 x3 fast
        _make_urlopen_response(200, b"{}"),
        _make_urlopen_response(200, b"{}"),
    ]
    # Fast perf_counter for the non-timeout calls — provide a generous sequence.
    counters = iter([i * 0.1 for i in range(60)])
    monkeypatch.setattr("scripts.prewarm.time.perf_counter", lambda: next(counters))
    result = prewarm.main()
    assert result == 1, f"Expected exit 1 (median pushed over gate by timeouts), got {result}"
    out = capsys.readouterr().out
    assert "TIMEOUT" in out, f"Missing 'TIMEOUT' log line; stdout:\n{out}"
    assert "CUST-001" in out and "FAIL" in out, f"CUST-001 should have failed the gate; stdout:\n{out}"


@patch("scripts.prewarm.urllib.request.urlopen")
def test_prewarm_per_call_log_format(mock_urlopen, monkeypatch, capsys):
    """D-04: stdout log-line format stays operator-greppable after Phase 13 A-01/A-03 changes.

    Phase 13: warm lines now 'prewarm CUST-XXX pass N/3: 204 ... ok' (new pass idx);
    measurement lines unchanged 'CUST-XXX warm N/3: ...'; summary lines per-flow
    gate 'PASS (<3000ms)' / 'PASS (<2500ms)'.
    """
    monkeypatch.setenv("BACKEND_API_URL", "https://mock.example")
    # 6 warm 204s + 6 measurement 200s.
    mock_urlopen.side_effect = [_make_urlopen_response(204) for _ in range(6)] + [
        _make_urlopen_response(200, b"{}") for _ in range(6)
    ]
    counters = iter([i * 0.1 for i in range(60)])
    monkeypatch.setattr("scripts.prewarm.time.perf_counter", lambda: next(counters))
    result = prewarm.main()
    assert result == 0, f"Sanity: happy-path test; expected exit 0, got {result}"
    out = capsys.readouterr().out
    # D-04 format — prewarm lines now include 'pass N/3' per A-03 (3-pass warming):
    assert "prewarm CUST-001 pass 1/3:" in out, (
        f"Missing 'prewarm CUST-001 pass 1/3:' log line; stdout:\n{out}"
    )
    assert "prewarm CUST-001 pass 3/3:" in out, (
        f"Missing 'prewarm CUST-001 pass 3/3:' log line; stdout:\n{out}"
    )
    assert "prewarm CUST-003 pass 1/3:" in out, (
        f"Missing 'prewarm CUST-003 pass 1/3:' log line; stdout:\n{out}"
    )
    assert "prewarm CUST-003 pass 3/3:" in out, (
        f"Missing 'prewarm CUST-003 pass 3/3:' log line; stdout:\n{out}"
    )
    # CUST-002 must NOT be in the warm output (A-01 removed from rotation):
    assert "prewarm CUST-002" not in out, (
        f"CUST-002 should not appear in prewarm rotation (A-01); stdout:\n{out}"
    )
    # D-04 format — measurement line (warm N/3 + ms + 200 + ok) unchanged:
    assert "CUST-001 warm 1/3:" in out, f"Missing 'CUST-001 warm 1/3:' line; stdout:\n{out}"
    assert "CUST-003 warm 3/3:" in out, f"Missing 'CUST-003 warm 3/3:' line; stdout:\n{out}"
    # D-04 wait marker
    assert "(wait 30s)" in out, f"Missing '(wait 30s)' marker; stdout:\n{out}"
    # D-04 summary separator
    assert "---" in out, f"Missing '---' summary separator; stdout:\n{out}"
    # D-04 per-persona median line + per-flow PASS token (Phase 13 D-18):
    assert "median CUST-001:" in out, f"Missing 'median CUST-001:' summary line; stdout:\n{out}"
    assert "median CUST-003:" in out, f"Missing 'median CUST-003:' summary line; stdout:\n{out}"
    assert "PASS (<3000ms)" in out, f"Missing 'PASS (<3000ms)' marker for CUST-001; stdout:\n{out}"
    assert "PASS (<2500ms)" in out, f"Missing 'PASS (<2500ms)' marker for CUST-003; stdout:\n{out}"


def test_prewarm_median_computation(monkeypatch):
    """D-02: per-persona median uses statistics.median (3-sample odd-length → middle value)."""
    import statistics as _stats
    # Odd-length: middle value
    assert _stats.median([1000, 2000, 3000]) == 2000
    # Gate-fail boundary: [3174, 3050, 3100] → sorted [3050, 3100, 3174] → median 3100
    assert _stats.median([3174, 3050, 3100]) == 3100
    # Timeout-pushed: [200, 3000, 3000] → sorted [200, 3000, 3000] → median 3000
    assert _stats.median([200, 3000, 3000]) == 3000
    # Sanity: prewarm.py references statistics.median at least once
    prewarm_src = Path(__file__).resolve().parent.parent.joinpath("scripts", "prewarm.py").read_text()
    assert "statistics.median" in prewarm_src, "scripts/prewarm.py must invoke statistics.median per D-02"


# ----------------------------------------------------------------------
# Phase 13 Plan 07 — per-flow gate + rotation + warming-pass count (RED).
# ----------------------------------------------------------------------


def test_personas_rotation_is_cust001_and_cust003():
    """A-01: Marcus (CUST-002) removed; Elena (CUST-003) added."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("prewarm", "scripts/prewarm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PERSONAS == ["CUST-001", "CUST-003"]
    assert "CUST-002" not in module.PERSONAS


def test_gate_ms_is_per_flow_map_not_scalar():
    """D-18: per-persona gate dict, NOT a single MEDIAN_GATE_MS scalar (Pitfall 1)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("prewarm", "scripts/prewarm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.GATE_MS, dict)
    assert module.GATE_MS["CUST-001"] == 3000
    assert module.GATE_MS["CUST-003"] == 2500
    # Belt-and-braces: the old scalar is GONE.
    assert not hasattr(module, "MEDIAN_GATE_MS"), (
        "MEDIAN_GATE_MS scalar should be removed — per-flow map replaces it"
    )


def test_warming_passes_is_three():
    """A-03: 3 warming passes (promotion from 2)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("prewarm", "scripts/prewarm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.WARMING_PASSES == 3


def test_measurement_samples_and_settle_wait_unchanged():
    """Regression: load-bearing constants from Phase 9 SC-2 unchanged."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("prewarm", "scripts/prewarm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SETTLE_WAIT_S == 30
    assert module.MEASUREMENT_SAMPLES == 3
    assert module.HTTP_TIMEOUT_S == 30
