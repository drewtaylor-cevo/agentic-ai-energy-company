#!/usr/bin/env python3
"""Phase 9 pre-warm CLI — two-pass warm + measurement against the live API.

Warms all three demo personas via the Phase 7 pre-warm query branch, settles
for 30s, then fires 3 timed `GET /recommendations/{customer_id}` calls per
persona and asserts warm median < 3000ms per persona. Runs pre-demo to
eliminate AgentCore / Lambda cold-start latency before the presenter walks
on stage.

Usage:
    BACKEND_API_URL=https://... \\
    python3 scripts/prewarm.py

    OR (from ui/):
    BACKEND_API_URL=https://... npm run prewarm

Exit taxonomy (D-06):
    0 — all three personas under gate
    1 — gate-fail OR non-204 on warm pass OR non-200 on measurement GET
    2 — setup error (missing BACKEND_API_URL, unreachable endpoint on first call)
"""
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request

PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]
MEDIAN_GATE_MS = 3000          # D-03 — matches ROADMAP SC-2 verbatim; do NOT tighten to 2500
PREWARM_SPACING_S = 2          # D-02 step 1
SETTLE_WAIT_S = 30             # D-02 step 2 — load-bearing for microVM pool settling
MEASUREMENT_SAMPLES = 3        # D-02 step 3
HTTP_TIMEOUT_S = 30            # D-08


def main() -> int:
    t_start = time.perf_counter()
    api_url = os.environ.get("BACKEND_API_URL", "").rstrip("/")
    if not api_url:
        print("BACKEND_API_URL not set", file=sys.stderr)
        return 2

    # Step 1 — warm pass (D-02 step 1)
    for idx, persona in enumerate(PERSONAS):
        warm_url = f"{api_url}/recommendations/{persona}?prewarm=1"
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(warm_url, timeout=HTTP_TIMEOUT_S) as resp:
                status = resp.status
                resp.read()
        except urllib.error.HTTPError as exc:
            # HTTPError carries a status code — runtime failure, not setup error.
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            print(f"prewarm {persona}: {exc.code} {elapsed_ms}ms FAIL (expected 204)")
            return 1
        except (urllib.error.URLError, ConnectionRefusedError, socket.gaierror, socket.timeout) as exc:
            # Connectivity failure on the FIRST persona is a setup error → exit 2.
            # Any later persona treats it as runtime failure → exit 1.
            if persona == PERSONAS[0]:
                print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
                return 2
            print(f"prewarm {persona}: ERROR {exc}")
            return 1

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if status != 204:
            print(f"prewarm {persona}: {status} {elapsed_ms}ms FAIL (expected 204)")
            return 1
        print(f"prewarm {persona}: {status} {elapsed_ms}ms ok")

        # 2-second spacing between warm calls, but not after the last one.
        if idx < len(PERSONAS) - 1:
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
                # D-08: timeout logged and treated as a ≥3000ms sample for median purposes.
                print(f"{persona} warm {i+1}/3: TIMEOUT")
                medians[persona].append(MEDIAN_GATE_MS)
                continue

            verdict = "ok" if status == 200 else "FAIL"
            print(f"{persona} warm {i+1}/3: {elapsed_ms}ms {status} {verdict}")
            medians[persona].append(elapsed_ms)
            if status != 200:
                return 1

    # Step 4 — gate (D-02 step 4 + D-04 summary block).
    print("---")
    any_fail = False
    failed_persona = None
    for persona in PERSONAS:
        median_ms = int(statistics.median(medians[persona]))
        if median_ms < MEDIAN_GATE_MS:
            print(f"median {persona}: {median_ms}ms PASS (<3000ms)")
        else:
            print(f"median {persona}: {median_ms}ms FAIL (≥3000ms)")
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
