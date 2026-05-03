# Demo Runbook — Customer Tariff & Billing Optimisation Agent

Presenter-facing guide for the **v2.0 demo** (frozen at `demo-v2.0`). Top-to-bottom read on the day before; on demo day follow the **T-48h → T-24h → T-10m → T-0** checklist.

> **Prior runbook:** The v1.0 runbook lives at `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` and was extended in-place with Phase 10 sections §7–§10. This document supersedes it for v2.0 presentations, consolidates everything a presenter needs into one file at the project root, and adds the v2.0-specific surfaces (narrative layer, `?narrative=off` kill switch, version indicator, pre-warm tooling, keep-alive, rollback drill).

> **v3.0 Phase 11 amendment (2026-04-28):** The data layer has been extended on top of `demo-v2.0` — DynamoDB now carries **6 personas (CUST-001…006) and 6 tariff archetypes** (STD/ECO/VAL/TOU + new SOL/EV-TOU). The UI, API, and agent code are unchanged and still pinned to `demo-v2.0`. The CustomerTariff stack was lifted/redeployed/re-frozen on 2026-04-28 via the documented break-glass sequence; sibling stacks (Agent, Api) never moved. See §4 for the extended persona set, §5 for the mock-fallback caveat this introduces, and §7 for the live-deploy amendment record.

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
  # ↑ 36-row v2.0 baseline. Live table is now 73 rows after Phase 11 (36 v2.0 +
  #   36 new billing + 1 PROFILE sentinel). Restoring from this backup rolls the
  #   data layer BACK to v2.0 — use only for a v1.0/v2.0 fallback demo.
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

   > **Note (Phase 11, 2026-04-28):** CustomerTariff was lifted, redeployed (extended Tools Lambda + 6-plan catalog + 73-row seed), and re-frozen byte-equal to `foundation-freeze.json` on 2026-04-28. Sibling stacks (CustomerTariffAgent, CustomerTariffApi) never moved. Deny·Deny·Deny still holds — this is the expected state, not drift.

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
- [ ] **Live table is at the post-Phase-11 row count** (73, not the 36-row v2.0 baseline):
  ```bash
  aws dynamodb scan --table-name tariff-billing --select COUNT --profile cevo-dev25 \
    --query 'Count' --output text
  # Expect: 73 (36 v2.0 + 36 CUST-004/005/006 billing + 1 PROFILE sentinel)
  # If this returns 36, Phase 11 seed backfill has been rolled back — see §7 amendment.
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
- [ ] **Phase 13 AGENT-01 rehearsal (CUST-003 Elena — bill-shock multi-tool flow):**
  - Run the per-flow prewarm gate: `BACKEND_API_URL="$BACKEND_API_URL" python3 scripts/prewarm.py` — exit 0 required. CUST-003 Elena warm median must be under 2500ms (AGENT-01a). CUST-001 Sarah under 3000ms (single-tool baseline). Per amendment A-01, Marcus (CUST-002) is the non-shock foil — used for cross-persona canary assertions only, not the multi-tool demo beat.
  - Verify CUST-003 returns a `reasoning_trace` array with 2–3 entries (depending on A-03 sighting-shot outcome — see Plan 07 summary). CUST-001 and CUST-002 should return `reasoning_trace: []` (single-tool flow).
  - At 1280×800 viewport, confirm the collapsed `ReasoningTrace` row renders above the card grid for CUST-003 and both cards remain above the fold.
  - `?narrative=off` collapses the `ReasoningTrace` component entirely (returns null) — verify no layout shift.
  - Phase 13 ceremony log: `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-08-CEREMONY-LOG.md` (stack-policy lift + byte-equivalence gate + re-freeze evidence).

- [ ] **Phase 13.1 post-ceremony verification (2026-04-30):**

  #### Post-Phase-13.1 warm-p95 expectations (measured 2026-04-30)

  Per-flow prewarm gate rotation (`BACKEND_API_URL=<api> python3 scripts/prewarm.py`); numbers measured at end of Phase 13.1 ceremony (see `.planning/phases/13.1-agent-01-gap-closure-latency-short-circuit-404-detection/ceremony-log.md §Gate 5`):

  | Persona | Tool count | Warm median measured | Per-flow gate | Outcome |
  |---------|-----------|----------------------|---------------|---------|
  | CUST-001 Sarah (non-shock) | 2 tools (hardship + simulate) | 13840ms | 3000ms (non-shock) | FINDING — 4.6× over gate |
  | CUST-003 Elena (shock) | 2 tools (observed; expected 3) | 10990ms | 2500ms (multi-tool AGENT-01a) | FINDING — 4.4× over gate |

  **Context:** Phase 13.1 reduced tool count from 3→2 on non-shock personas (mechanism fix). Pre-fix warm latency was 17.2s (CUST-001) / 19.7s (CUST-003). Post-fix: 13.8s / 11.0s — a ~25-40% reduction, but the inherent AgentCore round-trip dominates. The latency gates (3000ms / 2500ms) were set as aspirational targets per LD-4; meeting them likely requires infrastructure-level changes (Provisioned Concurrency, model selection) outside Phase 13.1's scope.

  **Elena trace-shape finding:** CUST-003 returned a 2-entry reasoning trace instead of the expected 3-entry (bill-shock) trace. The SHORT-CIRCUIT RULE is being applied more broadly than intended by the LLM. Savings are byte-exact (SAV-03 preserved), so the mechanism is correct — the "visible 3-tool reasoning" demo story for Elena may need prompt tuning in a follow-up phase.

  #### Phase 13.1 reasoning-trace visuals (what the presenter should expect)

  - **CUST-001 (Sarah, non-shock) and CUST-002 (Marcus, non-shock):** ReasoningTrace renders a collapsed row reading "▶ 2 steps: get_hardship_flag → simulate_savings". No `detect_bill_shock` or `get_billing_history` entries.
  - **CUST-003 (Elena, shock):** ReasoningTrace renders "▶ 3 steps: get_hardship_flag → detect_bill_shock → simulate_savings". This is the visible AGENT-01a short-circuit signal — non-shock personas have a shorter trace by design, and that difference is intentional (Phase 13.1 D-13.1-14). If the presenter sees a 3-step trace on CUST-001 or CUST-002, treat it as a Gap 1 regression and halt the demo.
  - **Post-ceremony finding (2026-04-30):** Elena was observed returning a 2-step trace instead of 3-step. If this persists at T-24h rehearsal, the presenter should note that the bill-shock demo beat (visible 3-tool reasoning on Elena) is not reliably triggered. The savings and recommendations are still correct; only the reasoning-trace visual is affected.

  The `?narrative=off` kill switch still collapses reasoning traces entirely (v2.0 shape) regardless of tool count per the D-10 single-flag contract.

  Phase 13.1 ceremony log: `.planning/phases/13.1-agent-01-gap-closure-latency-short-circuit-404-detection/ceremony-log.md`.

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
# Expect exit 0; CUST-001 (single-tool, <3000ms) + CUST-003 Elena (multi-tool, <2500ms per A-01 amendment)
# 3 warm passes per persona + 30s settle + 6 measurement GETs + per-flow median summary.
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

### Extended persona set (v3.0 Phase 11 — seeded on the live stack, NOT in mock fallback)

These three personas ship in the live DynamoDB table (73-row seed) and round-trip through the deployed Tools Lambda with byte-exact savings. Use them if the CX story calls for tariff archetypes beyond flat-rate — solar feed-in, EV time-of-use, or hardship flagging. If you demo these, **do not fall back to `build:mock` mid-demo** — the mock dist only covers CUST-001/002/003 (see §5).

| ID | Persona | Expected Green | Expected Cheapest | Tariff archetype | Narrative angle |
|----|---------|----------------|-------------------|------------------|-----------------|
| CUST-004 | Solar PV household | **$40.02/mo · $480.24/yr · EcoFlex 100** | **$76.03/mo · $912.36/yr · Solar Feed-in (SOL)** | `plan_type: solar_fit` — rate 0.23, fit_rate 0.08, green_score 80 | Export credits move the needle; Cheapest is also the Greenest-adjacent track |
| CUST-005 | EV household | **$35.00/mo · $420.00/yr · EcoFlex 100** | **$84.00/mo · $1008.00/yr · EV Time-of-Use (EV-TOU)** | `plan_type: time_of_use` — peak 0.40, offpeak 0.08, 30/70 split | Off-peak charging behaviour unlocks the biggest delta in the portfolio |
| CUST-006 | Hardship persona | **$12.00/mo · $144.00/yr · EcoFlex 100** | **$22.00/mo · $264.00/yr · Value 12** | Flat-rate + `hardship_flag: true` PROFILE row | Data is seeded; hardship routing is Phase 14 scope — agent today still returns both tracks. Don't claim autonomy it doesn't have yet. |

**SAV-03 still holds end-to-end** — live `aws lambda invoke` on CUST-001 on the re-frozen stack returns $30/$55 byte-exact (per 11-06-SUMMARY). The dispatcher refactor (flat-rate / TOU / solar_fit branches) did not regress v2.0 numbers.

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

The mock dist serves the same 3 personas with byte-identical dollar values AND narrative / call-script strings (Phase 8 mirrored Phase 6 fallbacks into the fixture byte-exact). Demo story unchanged **for CUST-001/002/003**.

> **Phase 11 caveat — mock dist does NOT cover CUST-004/005/006.** `ui/src/lib/mock/recommendations.ts` and `ui/src/personas.ts` still ship only the three flagship personas. If your demo story was built around the extended set (solar / EV / hardship) and the live stack fails, your recovery path is:
> 1. Finish the current persona on live if it rendered — don't panic-swap mid-card.
> 2. Swap to `build:mock`, but **pivot the narrative back to the flagship three**. Say something like: "Let me pull up a cleaner account to keep moving" — the audience won't notice the pivot; they will notice a blank card.
> 3. Alternative: `?narrative=off` keeps the extended personas working from live but collapses the LLM layer. Good if the narrative layer is the thing broken, not the stack.

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

### Phase 11 amendment — live-deploy of extended data layer (2026-04-28)

After the v2.0 freeze held for two days, v3.0 Phase 11 required extending the CustomerTariff stack to add 3 personas, 2 tariff archetypes, a dispatcher refactor in `simulate_savings_pure`, and a PROFILE sentinel-SK row. Executed via the break-glass sequence above — **scoped to CustomerTariff only**; sibling stacks (CustomerTariffAgent, CustomerTariffApi) were not touched.

| Step | What happened | Result |
|------|--------------|--------|
| 1. LIFT | `set-stack-policy foundation-allow-all.json` + `update-termination-protection --no-enable` on CustomerTariff only. Sibling stacks verified still byte-equal to their freeze JSONs. | Scoped lift; no sibling disturbance |
| 2. DEPLOY | `cdk deploy CustomerTariff --require-approval never` with extended Tools Lambda (6-plan dispatcher + `get_hardship_flag_pure`), 6-plan `tariff_plans.json`, and `BillingSeeder-*-v2` phys-id bump for 73-row re-chunk | Stack UPDATE_COMPLETE |
| 3. Post-deploy anomaly | `aws dynamodb scan --select COUNT` returned **59**, not 73. Seeder1 Update didn't re-fire its `batchWriteItem` call despite payload change (CDK `AwsCustomResource` phys-id-change semantics are subtler than the construct docstring implied). | 14-row deficit |
| 4. Mitigation | Direct `aws dynamodb batch-write-item` backfill of the 14 missing rows (CUST-004 + CUST-005 months 2025-04/2025-05), payload byte-identical to what BillingSeeder1 would have written. `UnprocessedItems = {}`. | Scan Count = 73 |
| 5. Live SAV-03 gate | `aws lambda invoke --function-name tariff-tools {"customer_id":"CUST-001"}` → Green ECO $30.00/$360.00, Cheapest VAL $55.00/$660.00 | Byte-exact preserved through dispatcher |
| 6. REAPPLY | `set-stack-policy foundation-freeze.json` + `update-termination-protection --enable` on CustomerTariff. Policy diff against freeze JSON silent. | Byte-equal re-freeze; termination protection back on |
| 7. VERIFY | `pytest tests/test_seeder_smoke.py -v` (AWS env) twice — once pre-REAPPLY, once post-REAPPLY | 12/12 PASS both times |

**What this means for a presenter reading this post-Phase-11:**
- The §3 T-48h verification block (Deny·Deny·Deny, termination protection true) still passes — this is the correct expected state.
- The `demo-v2.0` git tag is unchanged. UI, API, and agent code are still frozen at that tag. Only the data layer + the Tools Lambda's pure-math dispatcher have evolved.
- The original freeze DynamoDB backup (`01777208516554-e1bee933`) is a **36-row snapshot** and does NOT match live state. Restoring from it rolls the data layer back to v2.0.
- **Future re-seed risk:** if the seed grows past another 25-item chunk boundary (75, 100, …) the same Seeder1-Update-doesn't-fire bug is likely to recur. Pattern to reuse: bump phys-id, deploy, scan count, and `batch-write-item` backfill any deficit rather than relying on CDK's phys-id-change machinery alone. Warning captured in `.planning/phases/11-new-personas-tariff-archetypes/11-REVIEW.md`.
- **Not yet wired to the agent:** `get_hardship_flag_pure` exists as a pure helper in the Lambda, and the `hardship_flag: true` row for CUST-006 is in DynamoDB, but the API response is unchanged — hardship short-circuit routing is Phase 14 scope. Don't claim a hardship workflow in the demo until Phase 14 lands.

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
| Dollar values wrong for a persona | DynamoDB table content drift from post-Phase-11 baseline | `aws dynamodb scan --table-name tariff-billing --profile cevo-dev25 --select COUNT` (expect **73** post-Phase 11; 36 is the pre-Phase-11 v2.0 shape) | If ≠73 but ≥36: seed re-chunk deficit — see §7 amendment step 4 (`batch-write-item` backfill). If ≤36: restore from freeze backup rolls to v2.0 data, hard rollback to `demo-v1.0` for tag parity |
| Extended-persona lookup (CUST-004/005/006) returns 404 in mock mode | `build:mock` dist only covers the flagship 3 personas | `git describe --tags --exact-match` + check browser URL (`localhost:4174/?...`) | Pivot demo narrative back to CUST-001/002/003 (§5 caveat), or swap back to live preview if the live stack is healthy |
| Live DynamoDB count is 59 (or any number between 36 and 73) | Seed re-chunk deficit — Seeder1 Update didn't re-fire its batchWriteItem after phys-id bump | `aws dynamodb scan --table-name tariff-billing --select COUNT --profile cevo-dev25` | `aws dynamodb batch-write-item` with the missing persona-month rows pulled from `DYNAMO_RECORDS` — documented pattern in §7 amendment |
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

**CX surface mockups:**
- `demo/mockups/portal-tile.html` — customer portal / mobile self-service tile (§13)
- `demo/mockups/email-nudge.html` — proactive monthly nudge email (§13)

---

## 13. CX Lens — Three Surfaces from One API

**Why this section exists:** The demo everyone has been watching surfaces the agent to one audience — the call-centre operator. A reasonable executive question is *"how does this reach my actual customer?"* The answer is: the same deterministic savings engine + validated LLM narrative already powers three distinct customer-experience surfaces. Only one is built for the demo; the other two are mockups that consume the exact same API.

### The 30-second talking track (use this slide immediately after the softphone demo)

> "The demo you just saw is one of three surfaces — the one we've built for the call centre. Same API, same byte-exact savings, same validated narrative can drive a customer portal tile in your existing mobile app [**show `portal-tile.html`**], or a proactive monthly email nudge for customers already signed up for savings alerts [**show `email-nudge.html`**]. The point is that the deterministic savings engine, the LLM narrative layer, and the guardrails we've drilled against are a platform — not a single screen. Different channels, different risk profiles, same source of truth."

Budget: ~30 seconds. Goal: reframe the demo from "cool agent-assist widget" to "customer-experience platform with three distinct delivery channels, one of which is already live."

### The three surfaces at a glance

| Surface | Status in the demo | Audience | Authentication surface | Narrative risk profile |
|---------|---------------------|----------|-------------------------|------------------------|
| **Softphone / agent-assist** (this demo) | Built, frozen at `demo-v2.0`, drilled | Call-centre operator reads to customer | Operator's existing softphone session | Low — operator filters; `?narrative=off` kills it live |
| **Customer portal tile / mobile** (`portal-tile.html`) | Mockup | End customer, self-serve | OIDC + MFA + session scoping (load-bearing new work) | Medium — narrative on-screen for the customer directly, kill switch still via URL flag |
| **Proactive email nudge** (`email-nudge.html`) | Mockup | End customer, opt-in | None (email is the channel) | High — no kill switch once sent; validation must be airtight pre-batch |

### Open the mockups in a browser

```bash
# In a second terminal (DON'T Ctrl-C the primary preview):
open demo/mockups/portal-tile.html   # macOS — opens in default browser
open demo/mockups/email-nudge.html
```

Or drag the files into Chrome from Finder. Both are static HTML with embedded CSS — no build step, no dependencies, work offline. Each file has an annotation layer below the fold that labels what's reused from the agent-assist build vs what's new per surface.

### What each mockup uses verbatim from the live API

Both mockups display **byte-exact Sarah Chen (CUST-001) data** fetched from the live `demo-v2.0` stack at build time:

| Field | Source | Value in mockups |
|-------|--------|------------------|
| Green saving / plan | `simulate_savings` pure function | $30/mo · $360/yr · EcoFlex 100 |
| Cheapest saving / plan | `simulate_savings` pure function | $55/mo · $660/yr · Value 12 |
| Green narrative | LLM output, validated | "Established household with a consistent high-load profile and strong eco-aligned energy values." |
| Green call script | LLM output, validated | "Ask about EcoFlex — an eco-aligned plan well suited to your established, high-usage home." |
| Cheapest narrative | LLM output, validated | "High-consumption household seeking cost-effective coverage across the full year." |
| Cheapest call script | LLM output, validated | "Bring up Value Twelve — a cost-led plan designed to suit a high-usage household like yours." |

If a reviewer asks "is that the actual API output or did you make up the copy?" — paste this into any terminal:

```bash
curl -s "$BACKEND_API_URL/recommendations/CUST-001" | jq
```

The response will match the text in both mockups byte-for-byte.

### What's genuinely new per surface (not built; roadmap signal)

**Portal tile / mobile (Option 1 — recommended next build):**
- Customer authentication — OIDC (likely Auth0 / Cognito / existing IdP), MFA, session scoping by customer-ID claim
- Rate limiting — a human can't spam the API manually; an authenticated mobile app can
- Self-serve action — "Switch to EcoFlex" CTA replaces the agent reading the script aloud; needs a plan-change workflow, confirmation modal, and email receipt
- Mobile-first responsive layout (375–428px) — today's UI is fixed at 1280×800

**Email nudge (Option 2 — supporting surface):**
- HTML email rendering tested across Gmail / Outlook / Apple Mail
- Monthly batch scheduler — cron + idempotent per-customer send + opt-in check + unsubscribe suppression list
- Material-delta filter — skip customers where `saving_monthly < $10` to avoid noise
- Deep link into the portal — CTA lands on the portal tile after login

### Risk framing (answers to the hard questions)

**"Why isn't the portal built yet?"** Authentication is the load-bearing addition. The agent-assist demo has zero auth surface; the operator's session handles identity. Building the portal means adding OIDC / MFA / PII handling / session scoping before any customer sees a dollar figure. That's a phase, not a week, and it belongs in front of legal and security review.

**"How do you stop a bad narrative going out in an email to 100k customers?"** Three layers, all already live from the agent-assist build:
1. Pydantic validator rejects any narrative containing digits, currency symbols, or banned terms (competitor names, switch verbs, environmental superlatives) *before* the string leaves the LLM layer
2. Per-persona × per-card committed fallback strings ship if validation fails — the email goes out with hand-written copy, not a broken row
3. Smoke-gated `tests/test_narrative_eval_live.py` asserts all 12 fields (3 personas × 2 tracks × 2 field types) pass validator rules against the live stack — runs at T-eval before demo day, would run before each batch send

**"What stays the same across all three surfaces?"** The savings arithmetic. `simulate_savings` is a pure Python function with 29 pytest cases locked since v1.0. LLM never sees the numbers. So the $30/mo figure Sarah sees in her portal is the same figure the call-centre agent sees on the softphone, is the same figure in her monthly email. Byte-exact. That property is the platform claim.

### Post-demo followups this section unlocks

If the CX framing lands and there's appetite for building the portal surface:
1. `/gsd-new-milestone` for v3.0 with a proposed scope: OIDC login + portal tile + mobile responsive breakpoints + plan-change workflow
2. Add a Phase 0 for authentication + PII handling review (legal + security) — load-bearing, not optional
3. Reuse the `demo-v2.0` API contract as the portal's backend; no backend changes needed for read-side

If the email channel is more urgent (e.g., retention campaign pressure):
1. Dedicated batch-send milestone — infrastructure is simpler but regulatory surface (AEMC / ACCC on savings claims in marketing) is heavier
2. Legal review of `call_script` copy for email use — the current validator passes but email copy has different standards than an operator reading live

---

*Last updated: 2026-04-30 after v3.0 Phase 13.1 (AGENT-01 Gap Closure — Latency Short-Circuit + 404 Detection) ceremony completed and re-froze CustomerTariffAgent + CustomerTariffApi stacks. Code pinned to `demo-v2.0` (freeze target) + `v2.0` (milestone close); data layer extended to 73 rows / 6 personas / 6 tariff archetypes on top. Phase 13.1 deployed prompt short-circuit (2-tool non-shock path) + UNKNOWN sentinel (404 detection defence-in-depth). Verification findings: Elena trace length 2 (expected 3), warm latency 11-14s (gates 2.5-3s). If you are reading this past demo day and see drift between what the runbook describes and what actually exists, trust `git describe --tags` and the live `aws cloudformation describe-stacks` state first, this document second.*
