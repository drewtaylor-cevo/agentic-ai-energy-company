# Demo Runbook — Customer Tariff & Billing Optimisation Agent

Presenter-facing guide for the **v2.0 demo** (frozen at `demo-v2.0`). Top-to-bottom read on the day before; on demo day follow the **T-48h → T-24h → T-10m → T-0** checklist.

> **Prior runbook:** The v1.0 runbook lives at `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` and was extended in-place with Phase 10 sections §7–§10. This document supersedes it for v2.0 presentations, consolidates everything a presenter needs into one file at the project root, and adds the v2.0-specific surfaces (narrative layer, `?narrative=off` kill switch, version indicator, pre-warm tooling, keep-alive, rollback drill).

---

## 0. What you are demoing

**The product:** a call-centre agent-assist tool. The agent at the phone enters a customer ID; the tool returns two personalised tariff recommendations (Green and Cheapest) with:

- Projected **monthly and annual savings** (byte-exact, deterministic from usage data)
- A **one-sentence usage narrative** (LLM-generated, validator-gated, no digits or currency symbols)
- A **one-sentence call script** (LLM-generated, second-person, ≤22 words, operator reads verbatim)
- A methodology line explaining how the number was computed

Both cards are visible above the fold at 1280×800. The system never picks between Green and Cheapest — the agent does, based on what the customer cares about.

**Stack:**
- React + Vite UI served by `vite preview` on the presenter laptop
- API Gateway HTTP v2 → Lambda (named alias `live`) → Bedrock AgentCore Runtime (Strands + Claude Sonnet 4.6)
- DynamoDB `tariff-billing` for the 36-item fixture dataset (3 personas × 12 months)
- All in AWS `us-east-1`, account `588738606436`, profile `cevo-dev25`

**Freeze state:** everything you'll use in the demo is locked at `demo-v2.0` (annotated git tag) with deny-Update:* CFN stack policies + termination protection live on all 3 stacks. See §7 for the freeze ceremony record.

---

## 1. Environment reference (keep this open)

```
AWS account:          588738606436
AWS region:           us-east-1
AWS profile:          cevo-dev25                       # shell-exported AWS_PROFILE=cevo-25 is STALE — override
Backend API URL:      https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
AgentCore Runtime:    arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V
Bedrock model:        us.anthropic.claude-sonnet-4-6   # literal at agent/agent.py:309
Demo git tags:        demo-v1.0 (rollback target) · demo-v2.0 (freeze target) · v2.0 (milestone)
Python interpreter:   /opt/homebrew/bin/python3.13     # /usr/bin/python3 is 3.9.6 and cannot install iniconfig==2.3.0
Freeze DynamoDB backup ARN:
  arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933
```

**Quick sanity before any command:**

```bash
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
aws sts get-caller-identity --query Account --output text   # expect 588738606436
```

---

## 2. Pre-demo setup (do once, before T-48h)

1. **Confirm AWS account + Bedrock access:**
   ```bash
   aws sts get-caller-identity --profile cevo-dev25 --query Account --output text
   # Expect 588738606436
   ```
   AWS console: Bedrock → Model access → us-east-1 → `Claude Sonnet 4.6` shows "Access granted".

2. **Check out the freeze tag:**
   ```bash
   git fetch --tags
   git checkout demo-v2.0
   ```

3. **Install / refresh local dependencies (use python3.13, not system python):**
   ```bash
   npm ci --prefix ui
   /opt/homebrew/bin/python3.13 -m venv .venv
   .venv/bin/pip install --require-hashes -r requirements-dev.txt
   ```
   `--require-hashes` is the freeze reproducibility contract — any lockfile drift fails here.

4. **Confirm the 3 stacks are healthy AND frozen:**
   ```bash
   aws cloudformation describe-stacks --profile cevo-dev25 \
     --query 'Stacks[?starts_with(StackName, `CustomerTariff`)].[StackName,StackStatus,EnableTerminationProtection]' \
     --output table
   # Expect: all UPDATE_COMPLETE/CREATE_COMPLETE, EnableTerminationProtection = True

   for STACK in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
     aws cloudformation get-stack-policy --stack-name "$STACK" --profile cevo-dev25 \
       --query 'StackPolicyBody' --output text | jq -r '.Statement[0].Effect'
   done
   # Expect: Deny · Deny · Deny
   ```

5. **Build both dists on the presenter laptop:**
   ```bash
   # Primary bundle (baked against live endpoint)
   rm -rf ui/dist && VITE_API_URL="$BACKEND_API_URL" npm run build --prefix ui

   # Fallback bundle (mock mode — no live API)
   rm -rf ui/dist-mock && npm run build:mock --prefix ui
   ```
   Confirm the bottom-right version indicator (`v2.0 · <git-sha>`) reflects the `demo-v2.0^` short SHA.

---

## 3. Timed checklist

### T-48h — Freeze ceremony (already done, verify only)

> Full ceremony is in §7 below. For a presenter who inherited a frozen environment, this section is **verify-only**. Do NOT re-run the freeze ceremony inside the 48-hour window unless something has broken.

- [ ] `git tag -n99 demo-v2.0` shows the annotated body naming the freeze commit SHA (`1a83a87c…`)
- [ ] `git rev-list -n 1 demo-v2.0^` == `1a83a87c2e134bb264f38f809e33611486821be0` (WN-2 self-consistency)
- [ ] `git ls-remote --tags origin | grep demo-v2.0` shows two refs (tag object + dereferenced)
- [ ] Freeze backup AVAILABLE:
  ```bash
  aws dynamodb describe-backup \
    --backup-arn arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933 \
    --profile cevo-dev25 --query 'BackupDescription.BackupDetails.BackupStatus' --output text
  # Expect: AVAILABLE
  ```

### T-24h — Visual rehearsal + gap closure

- [ ] **Visual rehearsal (Chrome DevTools, 1280×800):** open `http://localhost:4173/` in Chrome at 1280×800 with DevTools → Network. Run 2 passes (cold then warm, 30s apart) across all 3 personas plus `cust999` and `CUST-999` error cases. Record per-persona warm median from DevTools Network Duration. **Every warm median must be < 3000ms** — if not, treat as a gap against UI-02 before presenting.
- [ ] **Close v2.0 deferred UAT/VERIFICATION items** (5 total, recorded in `STATE.md §v2.0 Close Deferrals`):
  ```
  /gsd-verify-work 07   # resolve 3 HUMAN-UAT scenarios + VERIFICATION
  /gsd-verify-work 08   # resolve VERIFICATION
  /gsd-verify-work 09   # resolve 3 HUMAN-UAT scenarios + VERIFICATION
  ```
- [ ] Confirm the narrative text for each persona looks presentable (no digit leakage, no banned-term leakage, <20/<22 word caps respected). Quick check:
  ```bash
  for ID in CUST-001 CUST-002 CUST-003; do
    curl -s "$BACKEND_API_URL/recommendations/$ID" | \
      jq '.green.usage_narrative, .green.call_script, .cheapest.usage_narrative, .cheapest.call_script'
  done
  ```
- [ ] Customer-specific branding / slides updated (if any)
- [ ] Scan this runbook end-to-end

### T-2h — Launch rehearsal

- [ ] Version indicator present in primary dist:
  ```bash
  grep -l 'v2.0 · ' ui/dist/assets/*.js | head -1    # expect one match
  ```
- [ ] Live hostname baked into primary dist (not mock):
  ```bash
  grep -l 'execute-api.us-east-1.amazonaws.com' ui/dist/assets/*.js | head -1   # expect match
  ! grep -q 'execute-api.us-east-1.amazonaws.com' ui/dist-mock/assets/*.js && echo "mock isolated"
  ```
- [ ] Emergency-swap smoke (10 seconds):
  ```bash
  npm run preview:mock --prefix ui -- --port 4174
  # open http://localhost:4174/ in a private window → confirm CUST-001 returns Sarah's cards
  # Ctrl+C to stop
  ```
- [ ] AWS console tab pre-opened to CustomerTariffApi stack (in case a reviewer wants to see infra)
- [ ] Phone stopwatch accessible (if asked for live latency evidence)
- [ ] Browser tab pre-opened at `http://localhost:4173/` but closed for now

### T-30m — Start keep-alive (DEMO-05)

Open a persistent terminal pane (tmux recommended) and start the 10-minute rotating-persona ping loop so AgentCore's microVM stays warm through Q&A. See §8 for full procedure.

```bash
tmux new-session -s keepalive
export AWS_PROFILE=cevo-dev25
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
bash scripts/demo-keepalive.sh
# Expect: first tick prints "<UTC> CUST-001 204 Nms ok" within ~1s,
# then every 10 minutes rotating CUST-001 → CUST-002 → CUST-003
```

- [ ] `BACKEND_API_URL` exported and matches live endpoint
- [ ] First `ok` tick observed before leaving the pane
- [ ] Pane left running (detach tmux, don't close)

### T-10m — Pre-warm (DEMO-03)

Force-warm all 3 personas through the full Bedrock path and assert all warm medians < 3000ms. See §9 for full procedure.

```bash
cd ui
BACKEND_API_URL="$BACKEND_API_URL" npm run prewarm
cd -
# Expect exit 0; 3 warm lines + (wait 30s) + 9 measurement lines +
# 3 "median CUST-00X: Nms PASS (<3000ms)" lines + final summary.
```

- [ ] Exit code 0 on first attempt
- [ ] All 3 warm medians < 3000ms
- [ ] No cold-start re-runs needed

### T-eval — Live eval gate (DEMO-03 tail)

```bash
BACKEND_API_URL="$BACKEND_API_URL" \
  .venv/bin/pytest tests/test_narrative_eval_live.py -m smoke 2>&1 | tail -10
# Expect "3 passed"
```

- [ ] `3 passed` — narrative-validator and `_narrative_source` marker-strip contract both green against live
- [ ] If failed: go/no-go decision — `?narrative=off` is the presenter-grade fallback (§5)

### T-0 — Go live (2 minutes before presenting)

1. **Start the primary preview:**
   ```bash
   npm run preview --prefix ui
   # wait for "Local:   http://localhost:4173/"
   ```

2. **Ad-hoc warm** (belt-and-suspenders in case keepalive + prewarm haven't landed a recent tick):
   ```bash
   curl -s -o /dev/null "$BACKEND_API_URL/recommendations/CUST-001"
   ```

3. **Open `http://localhost:4173/` in the demo browser tab.** Resize to 1280×800 if not already. Confirm the idle state renders ("No customer selected").

4. **Sanity-check the version indicator.** Bottom-right corner should show `v2.0 · <7-char-sha>` where the SHA matches `git rev-parse --short demo-v2.0^`.

5. **You are live.**

---

## 4. Presenter cheat sheet

### The three demo personas (use in this order)

| ID | Persona | Expected Green | Expected Cheapest | Narrative angle |
|----|---------|----------------|-------------------|-----------------|
| CUST-001 | Sarah Chen — high usage | **$30.00/mo · $360.00/yr · EcoFlex 100** | **$55.00/mo · $660.00/yr · Value 12** | Flagship retention save — biggest delta, clearest story |
| CUST-002 | Marcus Webb — mid usage | **$16.90/mo · $202.80/yr · EcoFlex 100** | **$30.98/mo · $371.76/yr · Value 12** | Typical customer — moderate delta, both tracks viable |
| CUST-003 | Elena Vasquez — low usage | **$14.00/mo · $168.00/yr · EcoFlex 100** | **$25.67/mo · $308.04/yr · Value 12** | Low-usage — savings still meaningful, not rounding noise |

All dollar values are byte-exact across freeze. If the live API returns something different for a persona, **something is wrong** — switch to the mock fallback (§5) before continuing.

### Talking points

**Equal-cards framing (early, once, deliberately):**
> "We deliberately present Green and Cheapest side by side, with no ranking between them. The call-centre agent picks based on what the customer cares about — environmental preference or lowest bill. The system never decides for the customer."

**Determinism framing (when someone asks 'is that really an LLM doing the math?'):**
> "The dollar values are pure Python — a `simulate_savings` function with 29 pytest cases locked since v1.0. The LLM never sees the arithmetic. What the LLM produces is the narrative row and the call-script row. Both go through a Pydantic validator that hard-rejects digits, currency symbols, and a banned-terms list. If validation fails, we fall back to per-persona × per-card committed fallback strings we wrote by hand."

**Freeze framing (if asked about demo-day reliability):**
> "The environment is locked at T-48h. The 3 CloudFormation stacks have deny-Update:* policies and termination protection. Python dependencies are hash-pinned. We did a 5-step rollback drill two days ago — all 5 passed. There's a kill switch at `?narrative=off` if the LLM layer misbehaves mid-demo; the UI collapses to v1.0 shape without a redeploy."

### Error paths to rehearse (show one or two if a reviewer asks)

- `cust999` (lowercase, no dash) → 400 alert:
  > "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits."
- `CUST-999` → 404 alert:
  > "No customer found for CUST-999. Check the ID and try again."

Both error paths are baked into the UI and don't hit the LLM — fast, zero-cost, reliable to rehearse.

---

## 5. Fallback procedure

**Symptom A — single persona lookup stalls for >10s:** stack is cold. Do not wait. Keep talking (see §4 fallback framing), swap to mock mode, move on.

**Symptom B — narrative text visibly wrong (digits, currency, garbled):** LLM / validator layer broke. Use the **URL kill switch** — fastest recovery, no redeploy:

```
# Add ?narrative=off to the URL in your browser:
http://localhost:4173/?narrative=off
```

The UI collapses to v1.0 shape — both cards retain dollars, methodology, and track metadata; the narrative and call-script rows simply disappear. Loading-state skeletons also collapse so there is no layout shift when the flag is on.

**Symptom C — any other surprise (dollar values wrong, 5xx, blank page):** switch to mock dist:

```bash
# In the terminal running the primary preview:
Ctrl+C
npm run preview:mock --prefix ui
# Refresh the browser tab (preview:mock may bind a different port — check the terminal output)
```

What to say while you swap (keep talking, keep eye contact):
> "We're running on a live AWS deployment today, which occasionally has a cold-start moment. Let me swap to our pre-built local mode so we can keep moving — the data and recommendations are identical; this is just a network-path substitution."

The mock dist serves the same 3 personas with byte-identical dollar values AND narrative / call-script strings (Phase 8 mirrored Phase 6 fallbacks into the fixture byte-exact). Demo story unchanged.

**Do NOT attempt live debugging during the presentation.** If a fallback fires, the diagnosis happens post-demo.

**Hard rollback (only if everything is broken and you need a v1.0 demo instead):**

```bash
git checkout demo-v1.0
rm -rf ui/dist-mock && npm run build:mock --prefix ui
npm run preview:mock --prefix ui
# Open the printed URL; v1.0 has no narrative layer so 'narrative off' is not meaningful here
```

`demo-v1.0` is the rollback target the Phase 10 drill proved against. Tag is pushed to origin.

---

## 6. Launch commands (quick reference)

**Primary (live API, narrative on):**
```bash
npm run preview --prefix ui
# http://localhost:4173/
```

**Kill-switch URL:** append `?narrative=off` to any URL (works against both live and mock):
```
http://localhost:4173/?narrative=off
```

**Emergency mock fallback:**
```bash
npm run preview:mock --prefix ui
# http://localhost:4173/  (or whatever port the terminal prints)
```

**Hard rollback to v1.0:**
```bash
git checkout demo-v1.0
npm ci --prefix ui
rm -rf ui/dist-mock && npm run build:mock --prefix ui
npm run preview:mock --prefix ui
```

---

## 7. T-48h Freeze Ceremony — already executed (2026-04-26)

The freeze ceremony was executed on 2026-04-26 at 12:13:10 UTC (ceremony start) and closed at 14:11:52 UTC. **This section is a record of what was done**; do not re-run inside the 48-hour window unless something has broken and you need to cut a new tag.

**Result:** PASS. DEMO-04 + DEMO-06 satisfied.

### What the ceremony produced

- **CFN stack lock** — `Deny Update:*` policies on all 3 stacks (CustomerTariff, CustomerTariffAgent, CustomerTariffApi) via `aws cloudformation set-stack-policy`, plus `--enable-termination-protection` on all 3
- **Hash-pinned lockfiles** — `requirements.txt` (62 entries) + `requirements-dev.txt` (33 entries) with `--require-hashes` fresh-venv install gate PASSED
- **DynamoDB freeze backup** — `arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933`, status AVAILABLE, reused in both the drill restore AND the manifest (BL-2 single-backup invariant)
- **FREEZE-MANIFEST.md** — fully populated at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`. All `<pending>` placeholders replaced; WN-2 self-consistent (`manifest.git.freeze_commit_sha == demo-v2.0^`)
- **Annotated `demo-v2.0` tag** — commit `a09c0867b8acc047f4ed64dc2cb4a81d64401e0e`; `demo-v2.0^` = freeze commit `1a83a87c2e134bb264f38f809e33611486821be0`; pushed to origin
- **Rollback drill 5/5 PASS** — full log at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-DRILL-LOG.md`. Drill duration ~36 min.

### Rollback-drill evidence

| Step | What was drilled | Evidence | Verdict |
|------|------------------|----------|---------|
| 1 | `?narrative=off` URL flag kill switch | Screenshot `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/screenshots/narrative-off-20260426T130701Z.png` + DOM assertions | PASS |
| 2 | `npm run build:mock` <10s + intra-HEAD hash roundtrip | 0.95s build, hash `b0f2d9eb…` matches captured pre-drill | PASS |
| 3 | `git checkout demo-v1.0` + fresh-clone pytest green | 87 passed / 23 deselected with AWS creds | PASS |
| 4 | DynamoDB restore-from-backup + scan + spot-check | 36 items restored, 3 persona `usage_kwh` values non-null | PASS |
| 5 | Scratch table teardown | `tariff-billing-rollback-drill` → `ResourceNotFoundException` | PASS |

### D-22 closeout

All 15 rows of `10-VALIDATION.md` (`10-03-01` through `10-03-15`) re-run post-ceremony: PASS. Plus 3 extra invariants (DEMO-RUNBOOK has 10 sections, WN-2 self-consistency, post-ceremony pytest 189/34). Full evidence at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-03-SUMMARY.md`.

### Rule 4 deviations (user-approved + codified during ceremony)

1. **R1 — lockfile scope extension.** Original freeze lockfiles covered CDK-synth scope only; extended with `strands-agents` + `bedrock-agentcore` + `pydantic` for test-runtime reproducibility. Codified in `requirements.in` + `requirements-dev.in` and re-compiled with `--generate-hashes`.
2. **R2 — python3.13 + AWS_PROFILE codification.** `/usr/bin/python3` 3.9.6 cannot install `iniconfig==2.3.0`; shell `AWS_PROFILE=cevo-25` (stale) causes `ProfileNotFound`. Fix: use `/opt/homebrew/bin/python3.13` and explicit `export AWS_PROFILE=cevo-dev25`. Codified in `10-03-PLAN.md` Task 2 + `10-VALIDATION.md` row `10-03-08`.
3. **D-16 softening.** `vite.config.ts` embeds `git rev-parse --short HEAD` into the bundle as `__GIT_SHA__`, so `dist_bundles.*` hashes differ across commits. Softened D-16 from cross-HEAD reproducibility to intra-HEAD determinism (two consecutive rebuilds at the same HEAD produce the same hash). Cross-HEAD reproducibility is still provided by lockfile hashes + synth-asset hashes + `cdk diff == 0`.

### Reconciliation deploy done during ceremony

Phase 7-02 (`c033836 feat(07-02): add live alias + conditional PC`) had landed in git but was never `cdk deploy`'d, so `cdk diff` failed at Task 3. Resolution: `cdk deploy CustomerTariff CustomerTariffApi -c demo_pc=0` to reconcile code ↔ deployed state, then re-gate. `demo_pc=0` keeps provisioned-concurrency billing at $0.

### Break-glass (if you ever need to unlock)

Only use if the freeze must be lifted post-ceremony (e.g., a critical bug requires an infra change). This is strictly human-gated; no automation.

```bash
# 1. Apply allow-all stack policies (reverse of freeze)
aws cloudformation set-stack-policy --stack-name CustomerTariff \
  --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json \
  --profile cevo-dev25
aws cloudformation set-stack-policy --stack-name CustomerTariffAgent \
  --stack-policy-body file://infrastructure/stack-policies/agentcore-allow-all.json \
  --profile cevo-dev25
aws cloudformation set-stack-policy --stack-name CustomerTariffApi \
  --stack-policy-body file://infrastructure/stack-policies/backend-api-allow-all.json \
  --profile cevo-dev25

# 2. Disable termination protection
for STACK in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
  aws cloudformation update-termination-protection \
    --no-enable-termination-protection --stack-name "$STACK" --profile cevo-dev25
done

# 3. Make your change, redeploy, cut a new tag (demo-v2.0.1), re-freeze.
```

---

## 8. Keep-Alive (DEMO-05) — start at T-30m

The `scripts/demo-keepalive.sh` shell loop pings `/recommendations/CUST-00X` every 10 minutes, rotating through all 3 personas. It beats AgentCore's 15-minute microVM idle timeout so the first live persona lookup in the demo is warm.

### Start it

```bash
tmux new-session -s keepalive
export AWS_PROFILE=cevo-dev25
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
bash scripts/demo-keepalive.sh
# First tick within ~1s: "<UTC> CUST-001 204 Nms ok"
# Subsequent ticks every 10 minutes, rotating CUST-001 → CUST-002 → CUST-003
```

Detach from the tmux pane (`Ctrl-b d`) but do NOT close the terminal. The script traps `SIGINT`/`SIGTERM`/`SIGHUP` and exits cleanly when you `Ctrl-C` (post-demo).

### What "ok" vs "fail" means

- `ok` — HTTP 200/204 from the backend; cold/warm latency in the first column
- `fail` — non-2xx from the backend. Not demo-blocking on its own (a single dropped tick every hour or so is normal), but three in a row within a 30-minute window means the stack is degraded. Investigate before T-0.

### Stop it (post-demo)

```bash
tmux attach -t keepalive
Ctrl-C   # fires trap, exits 0
tmux kill-session -t keepalive
```

---

## 9. Pre-warm (DEMO-03) — run at T-10m

`npm run prewarm` (a thin wrapper over `scripts/prewarm.py`) warms all 3 personas via Phase 7's `?prewarm=1` route, waits 30s for provisioned concurrency to settle, then runs 9 timed measurement GETs (3 per persona). It asserts every warm median is < 3000ms.

### Run it

```bash
cd ui
BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/" npm run prewarm
cd -
```

### Expected output

```
warming CUST-001 ... 204 in 1234ms
warming CUST-002 ... 204 in 892ms
warming CUST-003 ... 204 in 945ms
(wait 30s)
measuring CUST-001 ... 200 in 1450ms
measuring CUST-001 ... 200 in 1390ms
measuring CUST-001 ... 200 in 1412ms
measuring CUST-002 ... 200 in 1250ms
measuring CUST-002 ... 200 in 1295ms
measuring CUST-002 ... 200 in 1308ms
measuring CUST-003 ... 200 in 1510ms
measuring CUST-003 ... 200 in 1488ms
measuring CUST-003 ... 200 in 1502ms
median CUST-001: 1412ms PASS (<3000ms)
median CUST-002: 1295ms PASS (<3000ms)
median CUST-003: 1502ms PASS (<3000ms)
all personas under gate — exit 0
```

### Exit codes

- `0` — all 3 medians <3000ms. You are ready to go live.
- `1` — at least one median ≥3000ms. Do NOT go live until you diagnose. Options: re-run (cold-start artefact clears on second run), use `?narrative=off` (removes narrative-latency contribution), hard-rollback to `demo-v1.0`.
- `2` — infrastructure error (non-200 from backend, network fault). Investigate stack health; check keepalive pane for a string of `fail` ticks.

---

## 10. Live eval harness (DEMO-03 tail) — run at T-eval

The smoke-gated live eval harness asserts (a) the Phase 6 narrative validator rules still hold end-to-end — no digits, no currency symbols, no banned terms in any of the 12 narrative/script fields across 3 personas × 2 tracks — AND (b) the Phase 7 `_narrative_source` marker is stripped from every response body.

### Run it

```bash
BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/" \
  .venv/bin/pytest tests/test_narrative_eval_live.py -m smoke 2>&1 | tail -10
```

### Expected output

```
tests/test_narrative_eval_live.py::test_sarah_narrative_validator PASSED
tests/test_narrative_eval_live.py::test_marcus_narrative_validator PASSED
tests/test_narrative_eval_live.py::test_elena_narrative_validator PASSED
============ 3 passed in X.XXs ============
```

### Failure handling

If any test fails: the narrative layer is leaking forbidden content against the live stack. Do NOT present with narratives on. Use the `?narrative=off` URL flag for the demo and capture the failing response bodies post-demo for investigation.

```bash
# Capture the live responses for each persona so you can diagnose post-demo
mkdir -p /tmp/eval-fail-capture
for ID in CUST-001 CUST-002 CUST-003; do
  curl -s "$BACKEND_API_URL/recommendations/$ID" > "/tmp/eval-fail-capture/$ID.json"
done
```

---

## 11. Post-demo — teardown (optional, only after you no longer need the live env)

Tear down the 3 stacks in reverse dependency order. Remember to unlock first (freeze policies deny Update:*; destroy requires an Update to IAM roles).

```bash
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1

# 1. Apply allow-all stack policies (reverse of freeze)
aws cloudformation set-stack-policy --stack-name CustomerTariff \
  --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json
aws cloudformation set-stack-policy --stack-name CustomerTariffAgent \
  --stack-policy-body file://infrastructure/stack-policies/agentcore-allow-all.json
aws cloudformation set-stack-policy --stack-name CustomerTariffApi \
  --stack-policy-body file://infrastructure/stack-policies/backend-api-allow-all.json

# 2. Disable termination protection on all 3
for STACK in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
  aws cloudformation update-termination-protection \
    --no-enable-termination-protection --stack-name "$STACK"
done

# 3. Destroy in reverse dependency order
npx aws-cdk@latest destroy CustomerTariffApi    --force
npx aws-cdk@latest destroy CustomerTariffAgent  --force
npx aws-cdk@latest destroy CustomerTariff       --force
```

After teardown:
- DynamoDB `tariff-billing` table is deleted (seed data is versioned in `infrastructure/seed_data/`; redeploy re-seeds from scratch)
- AgentCore runtime is deleted — the stable ARN `tariff_agent-O2Hai86N8V` is lost on redeploy
- API Gateway endpoint URL changes on redeploy — update `.planning/milestones/v1.0-phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` accordingly and, if the live URL changes materially, cut a new tag (e.g., `demo-v2.0.1`)
- **The freeze DynamoDB backup persists even after the table is deleted.** That backup ARN is the restore target if the stack is recreated and you want to come back to v2.0 demo state.

---

## 12. Troubleshooting playbook

| Symptom | Likely cause | Fast check | Remedy |
|---------|-------------|-----------|--------|
| First persona lookup spins >10s | AgentCore cold start; keepalive missed a window | Check keepalive pane for recent `ok` ticks | Fallback to `?narrative=off` or mock dist; don't wait |
| Narrative text has a digit or `$` | Validator bypass or regex miss | Run §10 live eval gate | `?narrative=off` for demo; capture bodies post-demo |
| Dollar values wrong for a persona | DynamoDB table content drift from v1.0 baseline | `aws dynamodb scan --table-name tariff-billing --profile cevo-dev25 --select COUNT` (expect 36) | Restore from freeze backup (§7 table), or hard rollback to `demo-v1.0` |
| Version indicator missing / shows wrong SHA | Wrong dist in `ui/dist/` | `grep 'v2.0 · ' ui/dist/assets/*.js` | Rebuild: `VITE_API_URL="$BACKEND_API_URL" npm run build --prefix ui` |
| `?narrative=off` doesn't collapse the cards | Not on demo-v2.0; on demo-v1.0 (no narrative layer) | `git describe --tags --exact-match` | `git checkout demo-v2.0 && npm ci --prefix ui && rebuild` |
| `cdk diff` no longer `== 0` | Something touched the stack post-freeze (D-13 violation) | Run §3 T-48h verification block | Decision: revert the change + redeploy, or accept drift for the demo |
| Pytest fails on fresh clone | `AWS_PROFILE` stale OR system python too old | `echo $AWS_PROFILE; which python3` | `export AWS_PROFILE=cevo-dev25`; use `/opt/homebrew/bin/python3.13` (Rule 4 R2) |
| `npm run prewarm` exit 1 | Warm median ≥3000ms on a persona | Re-run once (cold-start artefact); then decide | `?narrative=off` for demo; investigate post-demo |
| `git push origin demo-v2.0` fails ("tag exists") | Tag already pushed during ceremony | `git ls-remote --tags origin` | No action needed; push is idempotent |

---

## Cross-references

**Operational:**
- Live ARNs + endpoint: `.planning/milestones/v1.0-phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md`
- Rehearsal + latency evidence: `.planning/milestones/v1.0-phases/05-demo-hardening/05-VERIFICATION.md`
- v1.0 runbook (prior version this doc supersedes): `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`

**Freeze ceremony artifacts (v2.0 Phase 10):**
- Full manifest: `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`
- Drill log: `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-DRILL-LOG.md`
- Ceremony plan: `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-03-PLAN.md`
- Ceremony SUMMARY: `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-03-SUMMARY.md`
- CFN stack-policy JSONs: `infrastructure/stack-policies/`

**Contract references:**
- Phase 4 UI contract (error copy, layout): `.planning/milestones/v1.0-phases/04-agent-assist-ui/04-UI-SPEC.md`
- Requirements archive: `.planning/milestones/v2.0-REQUIREMENTS.md` (UI-03..08, DEMO-03..06)
- Project state: `.planning/PROJECT.md`
- Milestone archive: `.planning/MILESTONES.md` (v1.0 + v2.0 entries)
- Retrospective: `.planning/RETROSPECTIVE.md`

**Scripts used live on demo day:**
- `scripts/demo-keepalive.sh` — §8
- `scripts/prewarm.py` (via `npm run prewarm`) — §9
- `tests/test_narrative_eval_live.py` — §10

---

*Last updated: 2026-04-27 after v2.0 milestone close. Pinned to `demo-v2.0` (freeze target) + `v2.0` (milestone close). If you are reading this past demo day and see drift between what the runbook describes and what actually exists, trust `git describe --tags` and the live `aws cloudformation describe-stacks` state first, this document second.*
