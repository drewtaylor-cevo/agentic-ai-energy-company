---
phase: 05-demo-hardening
plan: 03
type: execute
status: complete
completed: 2026-04-25
---

# Plan 05-03 Summary — Production UI bundles (primary + mock fallback)

Two production bundles now exist side-by-side on the presenter's laptop: `ui/dist/` built against the live `ApiEndpoint` from Plan 02, and `ui/dist-mock/` built with `VITE_API_URL` empty so the existing `useRecommendations` mock branch serves the 3 personas from the local fixture. Presenter can swap with a single command (`npm run preview:mock`) during the demo if the live API hiccups.

## Outcome

The D-07 <10s swap gate is available. The committed sources are sufficient to regenerate both dists deterministically — no build output is versioned.

## Evidence

### Task 1 — package.json scripts added

Committed in `4a804a2`. Added 2 entries; existing 6 untouched:

```json
"build:mock":   "VITE_API_URL= vite build --outDir dist-mock",
"preview:mock": "vite preview --outDir dist-mock"
```

Verification:
- `node -e "JSON.parse(...)" → "OK"` — JSON parses clean
- Final script list: `dev, build, build:mock, lint, preview, preview:mock, test, test:watch`
- `git diff --stat ui/package-lock.json` → empty (no dependency change)

### Task 2 — Primary live-API dist

```
$ LIVE_API_URL=$(grep -oE 'https://...execute-api...' .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md | head -1)
$ echo "$LIVE_API_URL"
https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/

$ VITE_API_URL="$LIVE_API_URL" npm run build --prefix ui
...
dist/index.html                   0.72 kB │ gzip:  0.39 kB
dist/assets/index-s1b4m19o.css   27.32 kB │ gzip:  5.68 kB
dist/assets/index-D2w-Bo-b.js   234.67 kB │ gzip: 74.03 kB
✓ built in 1.44s

$ grep -l 'execute-api.us-east-1.amazonaws.com' ui/dist/assets/*.js
ui/dist/assets/index-D2w-Bo-b.js
```

Bundle size: ~234 kB JS + 27 kB CSS (within expected 100-400 kB band). Live hostname inlined. `ui/.env.production` unchanged (still empty-VITE_API_URL — Phase 4 D-03 preserved).

### Task 3 — Mock fallback dist + invariants

```
$ npm run build:mock --prefix ui
...
dist-mock/assets/index-BQOccTBh.js   235.30 kB │ gzip: 74.18 kB
✓ built in 209ms

POSITIVE (fixture bundled): grep '"CUST-001"' ui/dist-mock/assets/*.js
  → ui/dist-mock/assets/index-BQOccTBh.js (MATCH)
NEGATIVE (no live hostname): grep 'execute-api' ui/dist-mock/assets/*.js
  → empty (exit 1) — isolated OK
```

Preview smoke: `vite preview --outDir dist-mock --port 4174` → HTTP 200 at `http://localhost:4174/` (verified via curl). Note: Vite's preview binds to IPv6 `localhost` by default; `127.0.0.1` does not resolve without `--host`. Documenting this for the runbook.

### Re-buildability gate (Task 3 step 6)

```
$ rm -rf ui/dist ui/dist-mock
$ VITE_API_URL="$LIVE_API_URL" npm run build --prefix ui && npm run build:mock --prefix ui
$ primary has hostname: PASS
$ mock isolated: PASS
$ mock has fixture: PASS
$ gitignore-diff-empty
```

Both dists rebuilt cleanly from the committed tree + captured `ApiEndpoint` alone. Reproducibility confirmed — no committed build output required.

## Build artifacts (not committed)

| Path | Size | Contains live hostname? | Contains MOCK_RECOMMENDATIONS? |
|------|------|-------------------------|--------------------------------|
| `ui/dist/assets/index-D2w-Bo-b.js` | 234,679 bytes | YES | — |
| `ui/dist/assets/index-s1b4m19o.css` | 27,321 bytes | n/a | — |
| `ui/dist-mock/assets/index-BQOccTBh.js` | 235,308 bytes | NO | YES |
| `ui/dist-mock/assets/index-s1b4m19o.css` | 27,321 bytes | n/a | — |

CSS hash identical across both builds (no style divergence). JS hash differs because the bundles contain different API code paths.

## Self-Check: PASSED

- [x] `ui/package.json` has `build:mock` + `preview:mock`; 6 originals untouched
- [x] No new deps; `ui/package-lock.json` diff empty
- [x] `ui/dist/index.html` exists; bundle contains live hostname
- [x] `ui/dist-mock/index.html` exists; bundle does NOT contain live hostname
- [x] Mock bundle contains `"CUST-001"` (fixture inlined)
- [x] `npm run preview:mock -- --port 4174` serves HTTP 200
- [x] `ui/.env.production` unchanged (Phase 4 D-03 preserved)
- [x] `ui/.gitignore` unchanged
- [x] Re-build gate: both dists deleted, rebuilt, invariants re-verified
- [x] Only commit: `ui/package.json` (`4a804a2`)

## Key files

### Created (not committed — git-ignored build output)
- `ui/dist/` (primary, live-API)
- `ui/dist-mock/` (fallback, mock-mode)

### Modified (committed in `4a804a2`)
- `ui/package.json` — added 2 scripts

### Untouched (confirmed)
- `ui/package-lock.json` — no dep change
- `ui/.env.production` — Phase 4 D-03 locked-in default
- `ui/.gitignore` — reproducibility carried by sources, not artifacts

## Presenter commands (for DEMO-RUNBOOK.md)

From repo root:

```bash
# Primary (live-API) demo path
cd ui && npm run preview
# → opens at http://localhost:4173/ (Vite default preview port)

# Emergency fallback (Ctrl+C primary first, then this)
cd ui && npm run preview:mock -- --port 4174
# → opens at http://localhost:4174/ (mock fixture; no network required)
```

Rebuild sequence (T-2h per DEMO-RUNBOOK §1 step 6):

```bash
# From repo root, with AWS-cred shell:
export LIVE_API_URL=$(grep -oE 'https://[a-z0-9]+\.execute-api\.us-east-1\.amazonaws\.com[^ `|]*' .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md | head -1)
rm -rf ui/dist ui/dist-mock
cd ui && VITE_API_URL="$LIVE_API_URL" npm run build && npm run build:mock && cd ..
```

## What this unblocks

- **Plan 05-05** rehearsals will run against `cd ui && npm run preview` using the primary dist from this plan.
- **Plan 05-06** (DEMO-RUNBOOK.md) can reference the three command blocks above verbatim.
- **Plan 05-07** tag does not carry dist output — reproducibility is re-verified from source at tag time.
