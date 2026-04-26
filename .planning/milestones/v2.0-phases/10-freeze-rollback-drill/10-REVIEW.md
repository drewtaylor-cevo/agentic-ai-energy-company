---
phase: 10-freeze-rollback-drill
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - infrastructure/stack-policies/foundation-freeze.json
  - infrastructure/stack-policies/agentcore-freeze.json
  - infrastructure/stack-policies/backend-api-freeze.json
  - infrastructure/stack-policies/foundation-allow-all.json
  - infrastructure/stack-policies/agentcore-allow-all.json
  - infrastructure/stack-policies/backend-api-allow-all.json
  - scripts/hash_dist.sh
  - scripts/hash_synth_assets.sh
  - requirements.in
  - requirements-dev.in
  - requirements.txt
  - requirements-dev.txt
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found (info-only — no Critical or Warning findings)

## Summary

The Phase 10 freeze-rollback-drill artifacts are small (under ~35 LOC of hand-written code total, excluding lockfiles), semantically correct, and meet the stated determinism/freeze-surface goals. All six CloudFormation stack-policy JSON bodies parse cleanly and implement the documented intent: the three `*-freeze.json` files `Deny Update:*` against `Principal: "*"` / `Resource: "*"`, and the three `*-allow-all.json` files `Allow Update:*` with the same principal/resource. Both shell scripts (`hash_dist.sh`, `hash_synth_assets.sh`) pass `shellcheck` with zero warnings, correctly set `set -euo pipefail`, use null-delimited file iteration with `LC_ALL=C sort -z`, and contain no arbitrary-code-execution surface (no `eval`, no unquoted interpolation into subshells, no user-supplied format strings). The Python lockfiles are fully hash-pinned — 63/63 entries in `requirements.txt` and 11/11 entries in `requirements-dev.txt` carry `--hash=sha256:...` lines — and `requirements-dev.in` correctly layers via `-c requirements.txt`.

There are no Critical or Warning findings. Four Info items are recorded below, all relating to maintainability and minor consistency, not to correctness, security, or determinism. None blocks the T-48h freeze ceremony.

Positive highlights worth preserving:

- **Stack policy Principal:** correctly uses `"*"` (CloudFormation stack policies reject any other value — this is not IAM). Confirmed legal and intended.
- **Shell determinism hardening:** `hash_synth_assets.sh` strips `*.pyc` and `__pycache__/*` before hashing, as documented in `10-RESEARCH.md §Q3 Pitfall 3` — this is exactly the mitigation for the `cdk synth` mtime-leak footgun.
- **Hash-pin completeness:** mechanical scan of both lockfiles shows every pinned package block contains at least one `--hash=sha256:` line, including the newly-added `strands-agents==1.37.0`, `bedrock-agentcore==1.6.3`, `pydantic==2.13.3`, and their transitives.
- **Freeze surface:** combined hand-written code under review is ~35 LOC across 8 files (6 four-key JSON bodies + 2 shell scripts of ~15 LOC each), consistent with the phase's "minimise freeze surface" objective.

## Info

### IN-01: Freeze stack-policy JSON bodies are byte-identical across the three stacks (likewise for allow-all)

**File:** `infrastructure/stack-policies/foundation-freeze.json`, `infrastructure/stack-policies/agentcore-freeze.json`, `infrastructure/stack-policies/backend-api-freeze.json` (and the three `*-allow-all.json` counterparts)

**Issue:** `diff` confirms the three freeze files are byte-identical, and the three allow-all files are likewise byte-identical. This creates a subtle drift risk: if an operator edits one copy (e.g. narrows the Resource glob for `backend-api-freeze.json` only) the other two stay stale without any automated detector catching the divergence. The current naming convention implies per-stack specialisation that does not actually exist.

**Fix:** Two reasonable options — pick one consistent with the phase's freeze-surface discipline:

Option A (keep per-stack files, add a drift detector): commit a one-line guard such as

```bash
# scripts/verify_stack_policies.sh
set -euo pipefail
cd infrastructure/stack-policies
diff -q foundation-freeze.json agentcore-freeze.json
diff -q foundation-freeze.json backend-api-freeze.json
diff -q foundation-allow-all.json agentcore-allow-all.json
diff -q foundation-allow-all.json backend-api-allow-all.json
```

and wire it into CI so byte drift breaks the build.

Option B (collapse to two canonical files): ship a single `freeze.json` and single `allow-all.json`, and reference them from all three `set-stack-policy` invocations in the ceremony runbook — halves the freeze surface and eliminates the drift vector at the cost of slightly less self-documenting filenames.

Both are acceptable; Option A is lower-risk right before the ceremony.

---

### IN-02: `requirements.in` uses dot-separated distribution name for one package; `requirements.txt` normalises to hyphenated

**File:** `requirements.in:2`

**Issue:** Line 2 pins `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` (dot between `aws-cdk` and `aws-bedrock-agentcore-alpha`), whereas the generated `requirements.txt:35` uses `aws-cdk-aws-bedrock-agentcore-alpha==2.250.0a0` (all hyphens). PEP 503 §Normalized names treats `.`, `-`, and `_` as equivalent for the purpose of name matching, so `pip-compile` and `pip install` resolve both forms to the same wheel — nothing is broken. The inconsistency is purely stylistic, but it does make `grep`-based audits of the `.in` vs `.txt` pairing slightly noisier.

**Fix:** Normalise `requirements.in:2` to the canonical hyphenated form and regenerate the lockfile:

```diff
- aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0
+ aws-cdk-aws-bedrock-agentcore-alpha==2.250.0a0
```

followed by `pip-compile --generate-hashes --output-file=requirements.txt requirements.in`. Expect the resulting `requirements.txt` diff to be zero-content (same wheel, same hashes) — only the `# via -r requirements.in` breadcrumb name changes. Defer to a post-freeze cleanup commit rather than touching lockfiles inside the freeze window.

---

### IN-03: Hash scripts do not pre-validate `$1` is a directory; they rely on `cd` + `set -e`

**File:** `scripts/hash_dist.sh:20`, `scripts/hash_synth_assets.sh:20`

**Issue:** Both scripts run `(cd "$1" && find . -type f -print0 ...)`. If `$1` is a regular file, a symlink to a nonexistent target, or a directory without `+x` for the current user, `cd` fails with a terse message like `hash_dist.sh: line 20: cd: ui/dist: No such file or directory` and `set -e` exits non-zero. Functionally correct (fail-closed, no hash produced), but the error phrasing conflates "arg missing" (handled by the `: "${1:?...}"` guard on line 18) with "arg invalid" (not guarded). A freeze-ceremony operator reading the failure at 02:00 may briefly wonder which it is.

**Fix (optional):** Add an explicit directory check immediately after the existing arg guard:

```bash
: "${1:?usage: hash_dist.sh <dist-directory>}"
[[ -d "$1" ]] || { printf 'hash_dist.sh: %s: not a directory\n' "$1" >&2; exit 2; }
```

This is a three-line ergonomic improvement and does not change the happy-path hash. Skip if the freeze-surface budget is tighter than the operator-UX budget — current behaviour is safe, just terser.

---

### IN-04: `requirements.in` and `requirements-dev.in` carry no per-line provenance comments

**File:** `requirements.in`, `requirements-dev.in`

**Issue:** Both `.in` files list bare `package==version` pins without comments explaining why each package is a direct dependency. For a demo-hardening milestone where future maintainers will re-do `pip-compile` without the Phase 10 context, a one-line `# reason` comment per entry would make it obvious which pins can be relaxed and which are load-bearing (e.g. `strands-agents` is required because the agent test harness instantiates `Agent(...)` in-process; `bedrock-agentcore` is required because the runtime imports `@app.entrypoint` in unit tests).

**Fix (optional):** Annotate each `.in` line:

```
aws-cdk-lib==2.251.0                                # CDK synth runtime
aws-cdk-aws-bedrock-agentcore-alpha==2.250.0a0      # L2 construct for AgentCore Runtime
constructs==10.6.0                                  # peer of aws-cdk-lib (pin explicitly for determinism)
boto3==1.42.96                                      # SigV4 signing in agent + backend-api
strands-agents==1.37.0                              # Agent() test-harness import (phase 10 addition)
bedrock-agentcore==1.6.3                            # @app.entrypoint import path (phase 10 addition)
```

Non-blocking for the freeze; purely a legibility win. Defer to a post-milestone hygiene commit.

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
