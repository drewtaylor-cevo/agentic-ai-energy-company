# Phase 8 — Deferred Items

Items discovered during Phase 8 execution that are out of scope for the current plan but should be tracked.

## Pre-existing issues (not introduced by Phase 8)

### `ui/dist-mock/` is tracked in git history

- **Discovered during:** Plan 08-04 Task 1 (re-ran `npm run build:mock` as part of D-23 Gate 3)
- **State:** `git ls-files ui/dist-mock/` returns 5+ entries (`assets/index-BQOccTBh.js`, `assets/index-s1b4m19o.css`, `favicon.svg`, `icons.svg`, `index.html`). These are v1.0-era artefacts.
- **Gitignore state:** root `.gitignore` has `dist/` (matches dist/, NOT dist-mock/); `ui/.gitignore` has `dist` + `dist-ssr` (no dist-mock entry). The tracked dist-mock files were committed before the v1.0 D-07 "don't commit dist" invariant was enforced.
- **Why deferred:** Phase 8 PLAN scope does not include `.gitignore` or cleanup of v1.0 tracked artefacts. Scope boundary (Rule N): only auto-fix issues DIRECTLY caused by the current task's changes. This is pre-existing leakage.
- **Impact:** Each re-run of `npm run build:mock` re-produces `dist-mock/` with new asset hashes, which shows up as modifications to tracked files. Task 1 reverted its churn via `git checkout --` + `rm` of the new hashed files to keep the working tree clean.
- **Recommended remediation (Phase 10 scope — freeze phase):** add `dist-mock/` to `ui/.gitignore` and `git rm -r ui/dist-mock/` in a dedicated hygiene commit. Phase 10 is the natural home because it owns the freeze manifest and will want a clean "source-of-truth, no build output" tree state before cutting `demo-v2.0`.
