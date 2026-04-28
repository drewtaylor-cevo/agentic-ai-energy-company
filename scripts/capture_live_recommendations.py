#!/usr/bin/env python3
"""Phase 12 pre/post live-diff capture — SAV-03 byte-exact proof.

Hits /recommendations/{customer_id} for CUST-001..005 and stores the JSON
response bodies under
.planning/phases/12-customerdataprovider-abstraction/baseline/{pre|post}/.
In --mode compare, diffs pre/ vs post/ on numeric fields ONLY (D-08) and
exits non-zero on any drift — the phase-close deploy gate (D-06).

Usage:
    # Before the Phase 12 refactor lands:
    BACKEND_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com \\
    AWS_PROFILE=cevo-dev25 \\
    python3 scripts/capture_live_recommendations.py --mode pre

    # After the refactor is deployed (Plan 06 lift -> deploy -> re-apply):
    BACKEND_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com \\
    AWS_PROFILE=cevo-dev25 \\
    python3 scripts/capture_live_recommendations.py --mode post

    # Gate: numeric-field byte-equality across all five personas:
    python3 scripts/capture_live_recommendations.py --mode compare

Exit taxonomy (D-06, matches scripts/prewarm.py):
    0 - capture or diff clean
    1 - diff drift / HTTP non-200 / later-persona connectivity failure
    2 - setup error (missing BACKEND_API_URL, first-persona unreachable,
        missing --mode flag)
"""
import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PERSONAS = ("CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005")
NUMERIC_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")  # D-08
HTTP_TIMEOUT_S = 30

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "12-customerdataprovider-abstraction"
BASELINE_ROOT = PHASE_DIR / "baseline"


def _capture(mode: str) -> int:
    """Capture live recommendation bodies into baseline/{mode}/."""
    api_url = os.environ.get("BACKEND_API_URL", "").rstrip("/")
    if not api_url:
        print("BACKEND_API_URL not set", file=sys.stderr)
        return 2

    target_dir = BASELINE_ROOT / mode
    target_dir.mkdir(parents=True, exist_ok=True)

    for persona in PERSONAS:
        url = f"{api_url}/recommendations/{persona}"
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
                if resp.status != 200:
                    print(f"{persona}: HTTP {resp.status} FAIL")
                    return 1
                body: dict[str, Any] = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            print(f"{persona}: HTTP {exc.code} FAIL")
            return 1
        except (
            urllib.error.URLError,
            ConnectionRefusedError,
            socket.gaierror,
            socket.timeout,
        ) as exc:
            # Connectivity failure on FIRST persona is a setup error -> exit 2.
            # Later persona is runtime failure -> exit 1.
            if persona == PERSONAS[0]:
                print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
                return 2
            print(f"{persona}: ERROR {exc}")
            return 1

        # Sanity check: body must contain both tracks with required numeric fields.
        for track in ("green", "cheapest"):
            if track not in body:
                print(f"{persona}: missing '{track}' track in response")
                return 1
            for field in NUMERIC_FIELDS:
                if field not in body[track]:
                    print(f"{persona}.{track}.{field}: missing in response")
                    return 1

        target = target_dir / f"{persona}.json"
        target.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
        print(f"{persona}: captured to {target.relative_to(REPO_ROOT)}")

    print(f"OK: {len(PERSONAS)}/{len(PERSONAS)} personas captured under baseline/{mode}/")
    return 0


def _compare() -> int:
    """Diff baseline/pre/ vs baseline/post/ on numeric fields only (D-08)."""
    pre_dir = BASELINE_ROOT / "pre"
    post_dir = BASELINE_ROOT / "post"

    drifts: list[str] = []
    missing: list[str] = []
    compared = 0

    for persona in PERSONAS:
        pre_path = pre_dir / f"{persona}.json"
        post_path = post_dir / f"{persona}.json"
        if not pre_path.exists() or not post_path.exists():
            missing.append(persona)
            continue

        pre_body = json.loads(pre_path.read_text())
        post_body = json.loads(post_path.read_text())

        for track in ("green", "cheapest"):
            pre_track = pre_body.get(track, {})
            post_track = post_body.get(track, {})
            for field in NUMERIC_FIELDS:
                compared += 1
                pre_val = pre_track.get(field)
                post_val = post_track.get(field)
                if pre_val != post_val:
                    drifts.append(
                        f"{persona}.{track}.{field}: {pre_val!r} -> {post_val!r}"
                    )

    if missing:
        for p in missing:
            print(f"{p}: missing pre or post capture - run --mode pre and --mode post first")
        return 1
    if drifts:
        print(f"DRIFT: {len(drifts)}/{compared} numeric fields changed")
        for line in drifts:
            print(f"  {line}")
        return 1
    print(f"OK: {compared}/{compared} numeric fields byte-equal across {len(PERSONAS)} personas")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pre", "post", "compare"), required=True)
    args = parser.parse_args()

    if args.mode in ("pre", "post"):
        return _capture(args.mode)
    return _compare()


if __name__ == "__main__":
    sys.exit(main())
