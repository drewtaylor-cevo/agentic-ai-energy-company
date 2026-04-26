---
phase: 05-demo-hardening
artifact: demo-runbook
status: ready
audience: presenter (user)
created: 2026-04-25T22:15:32Z
depends_on:
  - 05-DEPLOY-OUTPUTS.md (live endpoint + ARNs)
  - 05-VERIFICATION.md (rehearsal evidence + latency baselines)
---

# Demo Runbook — Customer Tariff & Billing Optimisation Agent

Presenter-facing guide for the v1.0 demo. Read top-to-bottom the day before. On demo day, follow the T-24h / T-2h / T-0 checklist.

**Environment:** live AWS deployment in us-east-1 (see `05-DEPLOY-OUTPUTS.md` for ARNs + endpoint).
**Primary launch surface:** `vite preview` on presenter laptop, pointing at `ui/dist/`.
**Emergency fallback:** `vite preview` on presenter laptop, pointing at `ui/dist-mock/` (no AWS dependency).

**Known gap (tracked in `05-VERIFICATION.md`):** A Chrome DevTools-measured visual rehearsal per D-14/D-15 was not executed at phase close. Plan 02's live pytest smoke stands in as structural proof (all 3 personas + error paths return correctly on the live endpoint with ≲2s per request). The T-24h checklist below includes a mandatory visual rehearsal step to close this gap before demo day.

---

## 1. Pre-demo setup (do this once, before T-24h)

1. Confirm AWS account and Bedrock model access:
   ```bash
   aws sts get-caller-identity --region us-east-1
   # Account should match the one recorded in .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md (ending 6436)
   ```
   In the AWS console: Bedrock → Model access → us-east-1 → Claude models show "Access granted".

2. Check out the tagged demo commit:
   ```bash
   git fetch --tags
   git checkout demo-v1.0
   ```

3. Install / refresh local dependencies:
   ```bash
   npm ci --prefix ui
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

4. Confirm the deployed stacks are still CREATE_COMPLETE / UPDATE_COMPLETE:
   ```bash
   aws cloudformation describe-stacks --region us-east-1 \
     --query 'Stacks[?starts_with(StackName, `CustomerTariff`)].[StackName,StackStatus]' \
     --output table
   ```
   If any stack is in a failed state: re-deploy following the order in step 5 below.

5. (Only if re-deploying) Deploy stacks in dependency order:
   ```bash
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariff      --require-approval never
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffAgent --require-approval never
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffApi   --require-approval never
   ```
   Then re-capture CfnOutputs into `05-DEPLOY-OUTPUTS.md` and cut a new tag (`demo-v1.0.1`).

6. Build both dists on the presenter laptop:
   ```bash
   # Extract the live API URL from the captured-outputs file
   export LIVE_API_URL=$(grep -oE 'https://[a-z0-9]+\.execute-api\.us-east-1\.amazonaws\.com[^ `|]*' \
     .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md | head -1)

   # Primary bundle (baked against live endpoint)
   rm -rf ui/dist && VITE_API_URL="$LIVE_API_URL" npm run build --prefix ui

   # Fallback bundle (mock mode — no live API)
   rm -rf ui/dist-mock && npm run build:mock --prefix ui
   ```

---

## 2. Timed checklist (D-19)

### T-24h

- [ ] `git tag --list demo-v1.0` shows the tag exists
- [ ] `05-DEPLOY-OUTPUTS.md` reflects the currently-deployed ARNs (re-run `aws cloudformation describe-stacks` and diff)
- [ ] **Visual rehearsal (closes D-14/D-15 gap):** open `http://localhost:4173/` in Chrome at 1280×800 with DevTools → Network open, run 2 passes (cold then warm, 30s apart) across all 3 personas plus the `cust999` and `CUST-999` error cases. Record per-persona warm median from DevTools Network Duration. Every warm median must be <3000ms; if not, treat as a gap against UI-02 before presenting.
- [ ] Runbook scanned end-to-end; any customer-specific branding or slides updated

### T-2h

- [ ] `ui/dist/index.html` exists and a grep confirms it contains the live hostname:
  ```bash
  grep -l 'execute-api.us-east-1.amazonaws.com' ui/dist/assets/*.js | head -1
  ```
- [ ] `ui/dist-mock/index.html` exists and does NOT contain the live hostname:
  ```bash
  ! grep -q 'execute-api.us-east-1.amazonaws.com' ui/dist-mock/assets/*.js && echo "mock isolated"
  ```
- [ ] Emergency-swap test: in a second terminal,
  ```bash
  npm run preview:mock --prefix ui -- --port 4174
  # open http://localhost:4174/ in a private browser window and confirm CUST-001 returns Sarah's cards
  # then Ctrl+C to stop
  ```
- [ ] Laptop browser has a tab pre-opened at `http://localhost:4173/` (closed for now; will open at T-0)
- [ ] AWS console tab pre-opened to the `CustomerTariffApi` stack (useful if you need to show infrastructure)
- [ ] Phone stopwatch accessible (in case a reviewer asks for live latency evidence)

### T-0 (2 minutes before going live)

1. Start the primary preview:
   ```bash
   npm run preview --prefix ui
   # wait for "Local:   http://localhost:4173/"
   ```

2. Warm the stack (ad-hoc warm-up per D-04):
   ```bash
   export BACKEND_API_URL=$(grep -oE 'https://[a-z0-9]+\.execute-api\.us-east-1\.amazonaws\.com[^ `|]*' \
     .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md | head -1)
   curl -s -o /dev/null "$BACKEND_API_URL/recommendations/CUST-001"
   # Confirms the Lambda + AgentCore runtime are warm for the first demo call
   ```

3. Open `http://localhost:4173/` in the demo browser tab. Resize window to 1280×800 if not already. Confirm the idle state renders ("No customer selected").

4. You are live.

---

## 3. Presenter cheat sheet

**The three demo personas** (use in this order):

| ID | Persona | Expected Green | Expected Cheapest | One-line narrative |
|----|---------|----------------|-------------------|---------------------|
| CUST-001 | Sarah Chen — high usage | $30.00/mo · $360.00/yr · EcoFlex 100 | $55.00/mo · $660.00/yr · Value 12 | "Flagship retention save — biggest delta, clearest story." |
| CUST-002 | Marcus Webb — mid usage | $16.90/mo · $202.80/yr · EcoFlex 100 | $30.98/mo · $371.76/yr · Value 12 | "Typical customer — moderate delta, both tracks are viable options." |
| CUST-003 | Elena Vasquez — low usage | $14.00/mo · $168.00/yr · EcoFlex 100 | $25.67/mo · $308.04/yr · Value 12 | "Low-usage customer — savings still meaningful, not a rounding error." |

**Equal-cards talking point (say this once, early — REC-03):**

> "We deliberately present Green and Cheapest side by side, with no ranking between them. The call centre agent picks based on what the customer cares about — environmental preference or lowest bill. The system never decides for the customer."

**Error paths to rehearse (if a reviewer asks to see them):**
- `cust999` (no dash, lowercase) → 400 alert with copy "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits."
- `CUST-999` → 404 alert with copy "No customer found for CUST-999. Check the ID and try again."

---

## 4. Launch commands (D-06)

Per D-06, the launch surface is `vite preview` on the presenter laptop — continuing Phase 4 D-05. No cloud hosting, one command, localhost only.

**Primary (live API):**
```bash
npm run preview --prefix ui
# Open http://localhost:4173/
```

**Emergency fallback (mock mode — if live API fails mid-demo):**
```bash
# In the terminal running the primary preview: Ctrl+C
npm run preview:mock --prefix ui
# Refresh http://localhost:4173/ (preview:mock defaults to a different port if 4173 is busy — the terminal prints the exact URL)
```

The mock dist serves the same 3 personas with the same dollar values — the demo story is unchanged. The only difference is that the request is satisfied from local fixture data rather than a live Lambda + AgentCore call.

---

## 5. Fallback procedure

**Symptom:** a persona lookup spins for more than ~10 seconds, or an error alert appears unexpectedly.

**What to say** (keep talking, keep eye contact):

> "We're running on a live AWS deployment today, which occasionally has a cold-start moment. Let me swap to our pre-built local mode so we can keep moving — the data and recommendations are identical; this is just a network-path substitution."

**What to do** (should take <10 seconds):

1. Ctrl+C the primary preview terminal.
2. `npm run preview:mock --prefix ui` (same terminal is fine).
3. Browser tab: reload (use the URL the mock preview printed — it may be a different port).
4. Re-enter the persona ID that failed.

**After the demo:** investigate root cause. Do NOT attempt live debugging during the presentation.

---

## 6. Post-demo teardown (D-18 — documented, not executed)

Tear down the stacks after the demo when you no longer need the live environment. Order is the reverse of deploy (dependencies come last):

```bash
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest destroy CustomerTariffApi    --force
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest destroy CustomerTariffAgent  --force
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest destroy CustomerTariff       --force
```

After teardown:
- DynamoDB `BillingTable` is deleted (seed data is versioned in `infrastructure/seed_data/` — redeploy re-seeds)
- AgentCore runtime is deleted — re-creation triggers a cold-start on the next deploy
- API Gateway endpoint URL changes on redeploy — update `05-DEPLOY-OUTPUTS.md` accordingly and, if the live URL changes materially, cut a new tag (`demo-v1.0.1`)

---

## Cross-references

- Live ARNs and endpoint: `.planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md`
- Rehearsal + latency evidence (includes known-gap note): `.planning/phases/05-demo-hardening/05-VERIFICATION.md`
- Phase 4 UI contract (error copy, layout): `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md`
- Requirements: `.planning/REQUIREMENTS.md` (DEMO-01, DEMO-02, UI-02 are what the demo shows)

---

# v2.0 Demo Extensions (Phase 10 additions)

> Sections 7-10 are appended for the v2.0 demo. D-20 originally numbered these
> §3-§6; renumbered to §7-§10 per 10-PATTERNS.md line 406 to avoid collision
> with the existing §3-§6 (presenter cheat sheet / launch / fallback /
> teardown) that the presenter has already memorised. 10-VALIDATION.md row
> 10-02-06 regex is updated to match this renumber.

## 7. T-48h Freeze Ceremony (D-18 / DEMO-04)

The T-48h ceremony freezes the v2.0 demo environment. Seven sub-steps in strict
dependency order — a failed step blocks later steps. Full acceptance gates live
in `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` rows 10-03-01
through 10-03-08.

### 7.1 Reproducibility gate (D-19)

Fresh clone + fresh venv + `pip install --require-hashes` + `pytest -m "not smoke"` green.

```bash
# Run from a clean temporary location, NOT the working repo.
rm -rf /tmp/freeze-repro
git clone . /tmp/freeze-repro
cd /tmp/freeze-repro

python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt
# Expect: exit 0 (hash-pinned wheels resolve)

.venv/bin/pytest -m "not smoke" 2>&1 | tail -5
# Expect: final line matches "81 passed, 6 skipped" (v1.0 baseline preserved by Phase 10)

cd -
```

- [ ] Fresh-clone venv install exited 0 (no hash mismatch).
- [ ] `pytest -m "not smoke"` green.

### 7.2 Drift gate (D-05)

`cdk diff` must be empty on all three root stacks before the tag is cut.

```bash
AWS_DEFAULT_REGION=us-east-1 AWS_PROFILE=cevo-dev25 \
  npx aws-cdk@latest diff CustomerTariff CustomerTariffAgent CustomerTariffApi 2>&1 \
  | tee /tmp/cdk-diff.log
# Expect: "Number of stacks with differences: 0" OR "no differences" per stack
```

- [ ] All three stacks report no differences. Any drift blocks the freeze —
      investigate + resolve before proceeding.

### 7.3 Rollback drill (D-12 through D-17)

Populate `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` end-to-end
following the Commands appendix in that file. All 5 drill steps must reach
`Verdict: PASS`; final `Drill Verdict: PASS` overall. **Tag MUST NOT be cut
before the drill passes** — a failed drill post-tag leaves the tag pointing
at an unprovable commit.

- [ ] Step 1 (`?narrative=off`) — `Verdict: PASS`, screenshot attached.
- [ ] Step 2 (`build:mock` + hash-roundtrip) — `Verdict: PASS`.
- [ ] Step 3 (`git checkout demo-v1.0` + pytest) — `Verdict: PASS`.
- [ ] Step 4 (DynamoDB restore + scan=36 + spot-check) — `Verdict: PASS`.
- [ ] Step 5 (scratch table teardown) — `Verdict: PASS`.
- [ ] Final overall verdict PASS; operator identity + drill duration recorded.

### 7.4 Stack lock (D-01 REVISED / D-02 / D-03)

Apply deny-Update:* stack policies via `aws cloudformation set-stack-policy`
(NOT CDK — the policy is not part of the template body; see 10-RESEARCH §Q1).
Enable termination protection on all three stacks via CLI.

```bash
# Stack-policy lock — explicit stack-to-file mapping
aws cloudformation set-stack-policy --stack-name CustomerTariff \
    --stack-policy-body file://infrastructure/stack-policies/foundation-freeze.json \
    --region us-east-1 --profile cevo-dev25

aws cloudformation set-stack-policy --stack-name CustomerTariffAgent \
    --stack-policy-body file://infrastructure/stack-policies/agentcore-freeze.json \
    --region us-east-1 --profile cevo-dev25

aws cloudformation set-stack-policy --stack-name CustomerTariffApi \
    --stack-policy-body file://infrastructure/stack-policies/backend-api-freeze.json \
    --region us-east-1 --profile cevo-dev25

# Verify each stack's policy is now Deny
for STACK in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
  aws cloudformation get-stack-policy --stack-name "$STACK" \
    --region us-east-1 --profile cevo-dev25 \
    --query 'StackPolicyBody' --output text | jq -e '.Statement[0].Effect=="Deny"'
  # Expect: true per stack
done

# Termination protection — loop over the three stack names
for STACK in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
  aws cloudformation update-termination-protection \
    --enable-termination-protection \
    --stack-name "$STACK" \
    --region us-east-1 --profile cevo-dev25
done

# Verify
aws cloudformation describe-stacks \
  --region us-east-1 --profile cevo-dev25 \
  --query 'Stacks[?starts_with(StackName, `CustomerTariff`)].[StackName,EnableTerminationProtection]' \
  --output table
# Expect: True for all three rows
```

- [ ] Three set-stack-policy calls succeeded; get-stack-policy confirms `Effect: Deny` on each.
- [ ] Termination protection True on all three stacks per describe-stacks.

### 7.5 DynamoDB backup (D-18 step 5)

On-demand backup of `tariff-billing`. Wait-loop until `BackupStatus == AVAILABLE`
before capturing the ARN into FREEZE-MANIFEST.md.

```bash
BACKUP_NAME="tariff-billing-freeze-v2.0-$(date -u +%Y%m%dT%H%M%SZ)"

BACKUP_ARN=$(aws dynamodb create-backup \
  --table-name tariff-billing \
  --backup-name "$BACKUP_NAME" \
  --region us-east-1 --profile cevo-dev25 \
  --query 'BackupDetails.BackupArn' --output text)

echo "Backup ARN: $BACKUP_ARN"

# Wait for BackupStatus to transition CREATING -> AVAILABLE (usually ~30s for 36-item table)
while true; do
  STATUS=$(aws dynamodb describe-backup --backup-arn "$BACKUP_ARN" \
    --region us-east-1 --profile cevo-dev25 \
    --query 'BackupDescription.BackupDetails.BackupStatus' --output text)
  echo "BackupStatus: $STATUS"
  [ "$STATUS" = "AVAILABLE" ] && break
  sleep 5
done

BACKUP_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "Captured at: $BACKUP_TS"
# Operator pastes BACKUP_ARN + BACKUP_TS into FREEZE-MANIFEST.md dynamodb_backup block.
```

- [ ] `BACKUP_ARN` captured; `BackupStatus: AVAILABLE` observed.
- [ ] UTC timestamp captured.

### 7.6 FREEZE-MANIFEST.md population (D-08 REVISED / D-09 REVISED / D-10)

Compute all hashes, fill every `<pending>` field in FREEZE-MANIFEST.md, commit.

```bash
# Lockfile hashes
for F in requirements.txt requirements-dev.txt ui/package-lock.json; do
  printf '%s: sha256:%s\n' "$F" "$(sha256sum "$F" | awk '{print $1}')"
done

# Dist hashes (both primary + mock)
scripts/hash_dist.sh ui/dist
scripts/hash_dist.sh ui/dist-mock

# Synth asset hashes — loop over cdk.out/asset.*/ dirs
AWS_DEFAULT_REGION=us-east-1 AWS_PROFILE=cevo-dev25 \
  npx aws-cdk@latest synth --all --quiet
for ASSET_DIR in cdk.out/asset.*/; do
  printf '%s: sha256:%s\n' "$ASSET_DIR" "$(scripts/hash_synth_assets.sh "$ASSET_DIR")"
done

# CloudFormation StackIds (rename-immune)
aws cloudformation describe-stacks \
  --region us-east-1 --profile cevo-dev25 \
  --query 'Stacks[?starts_with(StackName, `CustomerTariff`)].[StackName,StackId]' \
  --output text

# Freeze commit SHA + ISO-8601 UTC timestamp
echo "freeze_commit_sha: $(git rev-parse HEAD)"
echo "freeze_timestamp_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Operator edits `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` to
replace every `<pending>` placeholder with the captured value. `bedrock_model_id`
is already filled with `us.anthropic.claude-sonnet-4-6` (literal from
`agent/agent.py:309`); do not change it.

- [ ] All `<pending>` fields replaced with real values.
- [ ] `python3 -c "import yaml,re; ..."` schema check from 10-VALIDATION.md row
      10-02-05 re-runs clean after the edit.
- [ ] Commit: `docs(10-03): populate FREEZE-MANIFEST.md hashes + ARNs`.

### 7.7 Tag cut + origin push (D-18 step 7 REVISED)

Cut the annotated tag AFTER drill passes and manifest is populated. Push to
origin per revised D-18 step 7 (origin IS configured; `demo-v1.0` was already
pushed).

```bash
# Human checkpoint: confirm drill passed, manifest populated, ready to tag.
# Type `yes` to proceed.

FREEZE_SHA=$(git rev-parse HEAD)
git tag -a demo-v2.0 \
  -m "v2.0 demo freeze: narrative layer + guardrail + pre-warm tooling + rollback drill passed" \
  "$FREEZE_SHA"

git tag -n99 demo-v2.0
# Expect: demo-v2.0 line + annotation body

git cat-file -t demo-v2.0
# Expect: "tag" (annotated), NOT "commit" (lightweight)

# Second human checkpoint: push to origin?
git push origin demo-v2.0
git ls-remote --tags origin | grep 'refs/tags/demo-v2.0'
# Expect: line showing demo-v2.0 present on remote
```

- [ ] Annotated tag cut at the freeze commit SHA.
- [ ] `git cat-file -t demo-v2.0` returns `tag` (not `commit`).
- [ ] `demo-v2.0` visible in `git ls-remote --tags origin`.

---

## 8. T-30m Keep-Alive Start (DEMO-05 / D-20)

Open a persistent terminal pane (tmux recommended) and start the 10-minute
rotating-persona ping loop so AgentCore's microVM stays warm through Q&A.

```bash
# In a dedicated tmux pane:
tmux new-session -s keepalive     # OR: attach to existing session and open a new pane

# Export the live API Gateway URL
export BACKEND_API_URL=$(grep -oE 'https://[a-z0-9]+\.execute-api\.us-east-1\.amazonaws\.com[^ `|]*' \
  .planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md | head -1)
echo "BACKEND_API_URL=$BACKEND_API_URL"

# Start the loop — runs until Ctrl-C or signal (SIGINT/TERM/HUP)
bash scripts/demo-keepalive.sh
# Expect: first tick within ~1s printing "<UTC> CUST-001 204 Nms ok"
#         subsequent ticks every 10 minutes rotating CUST-001 -> 002 -> 003
```

- [ ] `BACKEND_API_URL` exported and matches live endpoint.
- [ ] First `ok` tick observed before leaving the pane.
- [ ] Pane left running through end of Q&A; Ctrl-C fires the trap (exit 0).

---

## 9. T-10m Pre-Warm (DEMO-03 / D-20)

Run `npm run prewarm` to force-warm all three personas through the full
Bedrock path and assert all warm medians < 3000ms. Any persona over gate
prints FAIL and the script exits 1.

```bash
cd ui
BACKEND_API_URL=$BACKEND_API_URL npm run prewarm
cd -
# Expect: exit 0; 3 warm lines + "(wait 30s)" + 9 measurement lines +
#         3 "median CUST-00X: Nms PASS (<3000ms)" lines +
#         "all personas under gate — exit 0" final summary.
# If any median >= 3000ms: non-zero exit + FAIL line for that persona.
#   Recovery lever: `?narrative=off` fallback (see section 10 below + D-15).
```

- [ ] Exit code 0 on first attempt (no cold-start re-runs needed at T-10m).
- [ ] All 3 warm medians < 3000ms.

---

## 10. T-eval Live Eval Harness Gate (DEMO-03 / D-20)

Run the Phase 6 validator + Phase 7 marker-strip contract against the live
stack. Three HTTP GETs asserting BANNED_REGEX / NUMERIC_REGEX miss on every
(persona × track × narrative field) combination + `_narrative_source` absent
from every response body.

```bash
BACKEND_API_URL=$BACKEND_API_URL pytest tests/test_narrative_eval_live.py -m smoke 2>&1 | tail -10
# Expect: "3 passed" in pytest summary. No warnings, no errors.
#
# If the narrative layer is broken (e.g., banned-terms regex match): the
# `?narrative=off` kill-switch (Phase 8 D-10) collapses the UI to v1.0 shape
# without needing a redeploy. Presenter fallback:
#   Open https://<frontend-url>/?narrative=off and proceed with the demo.
# Capture the failing response bodies post-demo for Phase 6 investigation.
```

- [ ] `3 passed` in pytest summary.
- [ ] If failed: operator decides go/no-go — `?narrative=off` URL flag is the
      presenter-grade fallback; no redeploy required.
