#!/usr/bin/env bash
# hash_dist.sh — deterministic content-manifest sha256 for a UI dist directory.
#
# Computes sha256(hash-of-sorted-per-file-hashes) over the files inside $1.
# No tar, no mtime leakage — stable across `npm run build` cycles
# (see 10-RESEARCH.md §Q4 for the mtime-leakage evidence that ruled out the
# original `find | sort | tar | sha256sum` pattern).
#
# Operator pattern (Phase 10 ceremony step 6 + drill step D-16):
#   $ scripts/hash_dist.sh ui/dist
#   2fdc8d85...   # 64-char hex sha256 — the manifest value
#
# Exit: 0 on happy path. Non-zero via `set -e` on missing arg or unreadable dir.
# Freeze surface: ~15 LOC, POSIX utilities only; shellcheck zero-warning gate.

set -euo pipefail

: "${1:?usage: hash_dist.sh <dist-directory>}"

(cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
