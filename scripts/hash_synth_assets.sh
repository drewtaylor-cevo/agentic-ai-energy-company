#!/usr/bin/env bash
# hash_synth_assets.sh — deterministic content-manifest sha256 for a single
# cdk.out/asset.<hash>/ directory, excluding Python bytecode caches.
#
# Same hashing strategy as hash_dist.sh, but strips .pyc files and
# __pycache__ directories before hashing — they carry build timestamps in
# their headers and would otherwise break the cdk-synth-twice
# reproducibility proof (see 10-RESEARCH.md §Q3 Pitfall 3).
#
# Operator pattern (Phase 10 ceremony step 6 — one invocation per asset):
#   $ for d in cdk.out/asset.*/; do scripts/hash_synth_assets.sh "$d"; done
#
# Exit: 0 on happy path. Non-zero via `set -e` on missing arg or unreadable dir.
# Freeze surface: ~15 LOC, POSIX utilities only; shellcheck zero-warning gate.

set -euo pipefail

: "${1:?usage: hash_synth_assets.sh <cdk.out-asset-directory>}"

(cd "$1" && find . -type f -not -name '*.pyc' -not -path '*/__pycache__/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
