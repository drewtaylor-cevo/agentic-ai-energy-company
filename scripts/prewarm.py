#!/usr/bin/env python3
"""Phase 13 pre-warm CLI — per-flow-gate warming + measurement against the live API.

Warms the Phase 13 demo rotation (CUST-001 single-tool + CUST-003 multi-tool)
via the Phase 7 pre-warm query branch, settles for 30s, then fires 3 timed
`GET /recommendations/{customer_id}` calls per persona and asserts warm median
< per-flow gate (3000ms single-tool, 2500ms multi-tool CUST-003). Runs pre-demo
to eliminate AgentCore / Lambda cold-start latency before the presenter walks
on stage.

Per amendment A-01 (Phase 13) Marcus was removed from the rotation — Elena
(the bill-shock persona) is the multi-tool target. Per amendment A-03 the
warming loop runs THREE passes (was 2) before the 30s settle to mitigate
Strands + Bedrock first-call variance on the 2500ms multi-tool gate.

Usage:
    BACKEND_API_URL=https://... \\
    python3 scripts/prewarm.py

    OR (from ui/):
    BACKEND_API_URL=https://... npm run prewarm

Exit taxonomy (D-06) — preserved unchanged:
    0 — ALL personas under their per-flow gate
    1 — any gate-fail OR non-204 on warm pass OR non-200 on measurement GET
    2 — setup error (missing BACKEND_API_URL, unreachable endpoint on first call)
"""
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request

# Phase 13 A-01: rotation is CUST-001 (single-tool) + CUST-003 (multi-tool).
# Marcus was deprecated from the rotation — his fixture does not trip the
# D-03 bill-shock gate, so he cannot exercise the multi-tool flow.
PERSONAS = ["CUST-001", "CUST-003"]

# Phase 13 D-18: per-flow warm-median gate map. Exit 0 iff ALL personas
# pass their own gate; LD-4 multi-tool target is 2500ms for CUST-003.
# Pitfall 1: DO NOT collapse this map back to a single scalar — that would
# accidentally apply the CUST-001 3000ms gate to multi-tool flows and let
# a real AGENT-01a regression slip through unnoticed.
GATE_MS: dict[str, int] = {
    "CUST-001": 3000,  # single-tool flow (v2.0 baseline — unchanged)
    "CUST-003": 2500,  # multi-tool flow (AGENT-01a contractual target)
}

# Phase 13 A-03: 3 warming passes (promotion 2 → 3). Mitigates Strands +
# Bedrock first-call variance; 2500ms CUST-003 gate has ZERO headroom
# (RESEARCH §4 training-knowledge estimate 2600-5400ms), so extra warming
# is a cheap insurance play.
WARMING_PASSES = 3

PREWARM_SPACING_S = 2          # D-02 step 1
SETTLE_WAIT_S = 30             # D-02 step 2 — load-bearing for microVM pool settling
MEASUREMENT_SAMPLES = 3        # D-02 step 3
HTTP_TIMEOUT_S = 30            # D-08

# Sentinel value used when a measurement times out — sample is treated as
# "over any conceivable gate" for median-contribution purposes (D-08).
_TIMEOUT_SENTINEL_MS = max(GATE_MS.values())


def main() -> int:
    t_start = time.perf_counter()
    api_url = os.environ.get("BACKEND_API_URL", "").rstrip("/")
    if not api_url:
        print("BACKEND_API_URL not set", file=sys.stderr)
        return 2

    # Step 1 — warm pass (D-02 step 1). Phase 13 A-03: WARMING_PASSES=3 per persona
    # (was 2) to mitigate Strands + Bedrock first-call variance on the 2500ms
    # multi-tool gate. Each pass is a separate ?prewarm=1 hit with PREWARM_SPACING_S
    # between consecutive hits. The 0/1/2 exit taxonomy is preserved: connectivity
    # failure on PERSONAS[0]'s FIRST pass is a setup error (exit 2); any later
    # failure is a runtime failure (exit 1).
    for idx, persona in enumerate(PERSONAS):
        warm_url = f"{api_url}/recommendations/{persona}?prewarm=1"
        for pass_idx in range(WARMING_PASSES):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(warm_url, timeout=HTTP_TIMEOUT_S) as resp:
                    status = resp.status
                    resp.read()
            except urllib.error.HTTPError as exc:
                # HTTPError carries a status code — runtime failure, not setup error.
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                print(
                    f"prewarm {persona} pass {pass_idx + 1}/{WARMING_PASSES}: "
                    f"{exc.code} {elapsed_ms}ms FAIL (expected 204)"
                )
                return 1
            except (urllib.error.URLError, ConnectionRefusedError, socket.gaierror, socket.timeout) as exc:
                # Connectivity failure on the FIRST persona's FIRST pass is a setup error → exit 2.
                # Any later pass or persona treats it as runtime failure → exit 1.
                if idx == 0 and pass_idx == 0:
                    print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
                    return 2
                print(
                    f"prewarm {persona} pass {pass_idx + 1}/{WARMING_PASSES}: "
                    f"ERROR {exc}"
                )
                return 1

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if status != 204:
                print(
                    f"prewarm {persona} pass {pass_idx + 1}/{WARMING_PASSES}: "
                    f"{status} {elapsed_ms}ms FAIL (expected 204)"
                )
                return 1
            print(
                f"prewarm {persona} pass {pass_idx + 1}/{WARMING_PASSES}: "
                f"{status} {elapsed_ms}ms ok"
            )

            # 2-second spacing between warm hits, but not after the very last
            # warm-pass of the very last persona (before the settle wait).
            is_last_pass = pass_idx == WARMING_PASSES - 1
            is_last_persona = idx == len(PERSONAS) - 1
            if not (is_last_pass and is_last_persona):
                time.sleep(PREWARM_SPACING_S)

    # Step 2 — settle wait (D-02 step 2). Load-bearing per specifics line 261.
    print("(wait 30s)")
    time.sleep(SETTLE_WAIT_S)

    # Step 3 — measurement pass (D-02 step 3).
    medians: dict[str, list[int]] = {persona: [] for persona in PERSONAS}
    for persona in PERSONAS:
        for i in range(MEASUREMENT_SAMPLES):
            measure_url = f"{api_url}/recommendations/{persona}"
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(measure_url, timeout=HTTP_TIMEOUT_S) as resp:
                    status = resp.status
                    resp.read()
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
            except (socket.timeout, urllib.error.URLError):
                # D-08: timeout logged and treated as a >= gate-ceiling sample
                # for median purposes. Uses the largest per-flow gate so that
                # a timeout reliably pushes the median over whichever gate
                # applies to this persona.
                print(f"{persona} warm {i+1}/3: TIMEOUT")
                medians[persona].append(_TIMEOUT_SENTINEL_MS)
                continue

            verdict = "ok" if status == 200 else "FAIL"
            print(f"{persona} warm {i+1}/3: {elapsed_ms}ms {status} {verdict}")
            medians[persona].append(elapsed_ms)
            if status != 200:
                return 1

    # Step 4 — gate (D-02 step 4 + D-04 summary block). Phase 13 D-18:
    # per-flow gate via GATE_MS map — exit 0 iff ALL personas clear their
    # own gate. Output format remains "median CUST-XXX: Nms PASS (<Gms)" /
    # "median CUST-XXX: Nms FAIL (≥Gms)" for operator grep-compat.
    print("---")
    any_fail = False
    failed_persona = None
    for persona in PERSONAS:
        median_ms = int(statistics.median(medians[persona]))
        gate_ms = GATE_MS[persona]
        if median_ms < gate_ms:
            print(f"median {persona}: {median_ms}ms PASS (<{gate_ms}ms)")
        else:
            print(f"median {persona}: {median_ms}ms FAIL (≥{gate_ms}ms)")
            if not any_fail:
                failed_persona = persona
            any_fail = True

    # Step 5 — exit summary + total runtime.
    total_runtime_s = time.perf_counter() - t_start
    if any_fail:
        print(f"{failed_persona} failed — exit 1")
        print(f"total: {total_runtime_s:.1f}s")
        return 1
    print("all personas under gate — exit 0")
    print(f"total: {total_runtime_s:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
