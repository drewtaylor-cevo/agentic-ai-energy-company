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
