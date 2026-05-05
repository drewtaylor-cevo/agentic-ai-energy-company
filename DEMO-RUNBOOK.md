# Demo Runbook — Customer Tariff & Billing Optimisation Agent

Presenter-facing guide for the **v3.0 demo** (Agentic Depth & Workflow Assist). Top-to-bottom read on the day before; on demo day follow the **T-48h → T-24h → T-10m → T-0** checklist.

> **Prior runbooks:** v1.0 at `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`; v2.0 was the previous version of this file. This document supersedes both for v3.0 presentations.

> **Presenter artefacts (Phase 16):** Three documents under `.planning/docs/presenter/` support the demo narrative:
> - `TRUST-ARCHITECTURE.md` (DOC-01) — regulatory-aware architecture one-pager
> - `NARRATIVE-TRADEOFFS.md` (DOC-02) — honest cost-vs-value of LLM narrative
> - `DEFERRED-ROADMAP.md` (DOC-03) — architecture-with-stubs view + what comes next

---

## 0. What you are demoing

**The product:** a call-centre agent-assist tool. The agent at the phone enters a customer ID; the tool returns:

- Two personalised **tariff recommendations** (Green and Cheapest) with projected monthly and annual savings (byte-exact, deterministic)
- A **one-sentence usage narrative** and **call script** (LLM-generated, validator-gated)
- A **reasoning trace** showing the agent's tool-call chain (collapsed by default)
- A **hardship routing banner** when the customer is flagged for specialist support — now with **typed categories** (payment difficulty, medical equipment, family violence, other) that drive distinct call scripts, routing targets, and compliance checks (no tariff recommendations shown)
- A **follow-up email draft** the operator can edit and send, referencing the prior recommendation via AgentCore Memory
- A **compliance review** showing the ComplianceReviewer's pass/fail verdict on every response (AER NECF-aligned rules)
- A **supervisor trace** showing which specialist agent handled the request and why
- A **conversational chat box** where the rep can ask free-text questions about the customer — the agent picks from 10 tools based on intent and streams reasoning in real time
- A **retention queue** showing all customers ranked by risk signal when no customer is selected — click to investigate
- **Confirmable action cards** below the recommendations — tariff switch, SMS follow-up, and payment plan offer that the rep approves with one click
- An **enriched bill-shock decomposition** with root-cause attribution (rate/usage/seasonal/billing-day) and a code-composed explanation sentence

Both recommendation cards are visible above the fold at 1280×800. The system never picks between Green and Cheapest — the agent does, based on what the customer cares about.

**v3.0 surfaces (new since v2.0):**
- Multi-tool reasoning trace (Phase 13) — visible on bill-shock personas
- Hardship short-circuit (Phase 14) — code-side pre-LLM guard, dignity-preserving routing
- **Typed hardship categories** (Phase 16 AGENT-03) — four hardship categories (`payment_difficulty`, `medical_equipment`, `family_violence`, `other`) with category-specific call scripts, tool permissions, routing targets, and compliance checks. Family violence customers get safety-first routing with zero financial terminology. Category detection is deterministic from DynamoDB PROFILE row data.
- Follow-up email draft (Phase 15) — AgentCore Memory-backed second turn
- CustomerDataProvider Protocol (Phase 12) — production-shaped CRM adapter seam
- **Multi-agent supervisor** (Phase 18) — code-side Supervisor router dispatches to TariffSpecialist, HardshipSpecialist, and ComplianceReviewer. Two new public response fields: `compliance_review` (pass/fail verdict + rules checked) and `supervisor_trace` (routing decision + hardship/compliance flags). Both collapse under `?narrative=off`.
- **Streaming reasoning trace** (Phase 19) — real-time SSE streaming of reasoning trace steps as the agent executes. The UI shows progressive "agent thinking" steps as each tool completes, making the 2–3 second agent latency feel responsive. Uses a Lambda Function URL with `RESPONSE_STREAM` invoke mode as the SSE transport. The batch path via API Gateway remains unchanged as the canonical fallback. New env var `VITE_STREAMING_URL` enables the streaming path; when unset, the UI falls back to batch fetch or mock streaming simulation.
- **Expanded tool gallery** (Phase 20) — agent tool set expanded from 4 tariff-math-centric tools to 10 tools representing a real Energy & Utilities CRM/OSS toolkit. New tools: `check_outage_status` (suburb-level outage awareness), `decompose_bill_shock` (replaces boolean `detect_bill_shock` with rate/usage/seasonal component attribution), `lookup_concessions` (AU-specific energy concessions and rebates), `estimate_solar_payback` (solar PV payback estimation), `propose_payment_plan` (instalment schedule for hardship/payment-difficulty customers), `schedule_callback` (demo-safe action tool — simulates a write without persisting state). All tools are deterministic and demo-safe (hardcoded seed data, no external API calls). ToolCapHook budget raised from 4 to 8 to accommodate richer multi-tool traces. Each tool has a deterministic reasoning-trace summary formatter.
- **Conversational chat layer** (Phase 21) — free-text question box below the recommendation cards. The rep can ask open-ended questions about the customer ("Why did her bill jump in February?", "What would solar do for her?"). A new `POST /chat/{customer_id}` endpoint reuses the same AgentCore runtime and tools — the LLM picks tools based on intent rather than a fixed recommendation flow. SSE streaming shows reasoning trace steps in real time. Sessions are scoped per-customer with 15-min TTL and 20-turn cap (SC-3). The `?narrative=off` kill switch hides the chat UI entirely.
- **Agentic actions portfolio** (Phase 22) — the agent evolves from advisor to actor. Three connected capabilities:
  - *Agent-as-Actor (AGENT-04):* After producing a recommendation, the agent prepares confirmable actions (tariff switch, SMS follow-up, payment plan offer) that the rep approves with one click. "Agent prepares, human approves." Actions are stored in DynamoDB with 24h TTL; confirm/dismiss transitions are atomic.
  - *Bill-Shock Root-Cause Decomposition:* The `decompose_bill_shock` tool now returns structured `contributing_factors` (rate_increase, usage_spike, seasonal_variation, billing_day_difference) with dollar amounts, percentages, and a code-composed `explanation_sentence`. Zero-value factors are omitted from the explanation.
  - *Retention Queue / Cohort Landing Page:* Replaces the empty state with a portfolio-level view ("N customers at risk today") ranked by a deterministic risk signal. Click → full agent flow. Demonstrates the agent works at portfolio scale, not just on a known ID.
  - New API routes: `GET /retention-queue`, `POST /actions/{action_id}/confirm`, `POST /actions/{action_id}/dismiss`. All deterministic — no LLM involvement in risk scoring or action state transitions (SAV-03 preserved). `?narrative=off` hides Action Cards but still shows the Retention Queue (it contains no LLM content).

**Stack:**
- React + Vite UI hosted on **AWS Amplify** at `https://main.d1b6s4i8w2zlzo.amplifyapp.com`
- API Gateway HTTP v2 → Lambda (named alias `live`) → Bedrock AgentCore Runtime (Strands + Claude Sonnet 4.6)
- Lambda Function URL (RESPONSE_STREAM) → same Lambda → SSE streaming path for real-time reasoning trace
- DynamoDB `tariff-billing` for the fixture dataset (10 personas × 12 months + PROFILE rows)
- AgentCore Memory for follow-up email context (short-term, same-day TTL)
- 10 agent tools: `simulate_savings`, `get_billing_history`, `get_hardship_flag`, `decompose_bill_shock`, `check_outage_status`, `lookup_concessions`, `estimate_solar_payback`, `propose_payment_plan`, `schedule_callback`, `detect_bill_shock` (legacy alias)
- All in AWS `us-east-1`, account `588738606436`, profile `cevo-dev25`

**Freeze state:** everything you'll use in the demo will be locked at `demo-v3.0` (annotated git tag, cut during Phase 17 freeze ceremony) with deny-Update:* CFN stack policies + termination protection on all 3 stacks.

---

## 1. Environment reference (keep this open)

```
AWS account:          588738606436
AWS region:           us-east-1
AWS profile:          cevo-dev25                       # shell-exported AWS_PROFILE=cevo-25 is STALE — override
Demo UI URL:          https://main.d1b6s4i8w2zlzo.amplifyapp.com   # Amplify Hosting — open this in the demo browser
Amplify App ID:       d1b6s4i8w2zlzo
Backend API URL:      https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
Streaming URL:        <Lambda Function URL from SSM /customer-tariff/streaming-url>  # SSE endpoint for real-time trace
AgentCore Runtime:    arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V
Bedrock model:        us.anthropic.claude-sonnet-4-6   # literal at agent/agent.py:309
Demo git tags:        demo-v1.0 (v1.0 rollback) · demo-v2.0 (v2.0 rollback) · demo-v3.0 (freeze target, Phase 17)
Python interpreter:   /opt/homebrew/bin/python3.13     # /usr/bin/python3 is 3.9.6 and cannot install iniconfig==2.3.0
Personas:             CUST-001 (Sarah, high-usage) · CUST-002 (Marcus, mid-usage) · CUST-003 (Elena, bill-shock)
                      CUST-004 (Solar PV) · CUST-005 (EV TOU) · CUST-006 (Hardship, legacy)
                      CUST-007 (Hardship, payment_difficulty) · CUST-008 (Hardship, medical_equipment)
                      CUST-009 (Hardship, family_violence) · CUST-010 (Hardship, other)
Follow-up route:      GET /recommendations/{customer_id}/follow-up
Chat route:           POST /chat/{customer_id}         # free-text Q&A, SSE streaming with Accept: text/event-stream
Retention queue:      GET /retention-queue              # portfolio-level risk ranking (deterministic, no LLM)
Action confirm:       POST /actions/{action_id}/confirm # transition pending action → confirmed
Action dismiss:       POST /actions/{action_id}/dismiss # transition pending action → rejected
SSE streaming:        GET <streaming-url>/recommendations/{customer_id} (Accept: text/event-stream)
Tool gallery:         10 tools (simulate_savings, get_billing_history, get_hardship_flag, decompose_bill_shock,
                      check_outage_status, lookup_concessions, estimate_solar_payback, propose_payment_plan,
                      schedule_callback, detect_bill_shock [legacy alias])
                      + 3 action queue functions: queue_action, confirm_action, dismiss_action
                      + 1 portfolio function: compute_risk_signals
Tool cap budget:      8 calls per invocation (FourToolCapHook)
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
   git checkout demo-v3.0
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

   > **Note (Phase 11, 2026-04-28; Phase 16 AGENT-03, 2026-05-05):** CustomerTariff was lifted, redeployed (extended Tools Lambda + 6-plan catalog + 125-row seed including 4 typed hardship personas), and re-frozen. Sibling stacks (CustomerTariffAgent, CustomerTariffApi) never moved. Deny·Deny·Deny still holds — this is the expected state, not drift.

5. **Confirm the Amplify-hosted UI is live:**
   ```bash
   curl -s "https://main.d1b6s4i8w2zlzo.amplifyapp.com/" -o /dev/null -w "%{http_code}"
   # Expect: 200
   ```
   Open `https://main.d1b6s4i8w2zlzo.amplifyapp.com` in a browser and confirm the app loads.

   > **To redeploy the UI** (after code changes): rebuild and push to Amplify:
   > ```bash
   > rm -rf ui/dist
   > VITE_API_URL="$BACKEND_API_URL" npm run build --prefix ui
   > # Manual Amplify deployment:
   > DEPLOY_JSON=$(aws amplify create-deployment --app-id d1b6s4i8w2zlzo --branch-name main --output json --profile cevo-dev25)
   > UPLOAD_URL=$(echo "$DEPLOY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")
   > JOB_ID=$(echo "$DEPLOY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['jobId'])")
   > (cd ui/dist && zip -r /tmp/amplify-deploy.zip .)
   > curl -T /tmp/amplify-deploy.zip "$UPLOAD_URL"
   > aws amplify start-deployment --app-id d1b6s4i8w2zlzo --branch-name main --job-id "$JOB_ID" --profile cevo-dev25
   > ```

   Confirm the bottom-right version indicator (`v2.0 · <git-sha>`) reflects the expected short SHA.

---

## 3. Timed checklist

### T-48h — Freeze ceremony (already done, verify only)

> Full ceremony is in §7 below. For a presenter who inherited a frozen environment, this section is **verify-only**. Do NOT re-run the freeze ceremony inside the 48-hour window unless something has broken.

- [ ] `git tag -n99 demo-v3.0` shows the annotated body naming the freeze commit SHA (`62c8adf1…`)
- [ ] `git rev-list -n 1 demo-v3.0^` == `62c8adf1e1f9447b0bd923cd695776b1f5320d07` (WN-2 self-consistency)
- [ ] `git ls-remote --tags origin | grep demo-v3.0` shows two refs (tag object + dereferenced)
- [ ] Freeze backup AVAILABLE:
  ```bash
  aws dynamodb describe-backup \
    --backup-arn arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777859824019-989beacf \
    --profile cevo-dev25 --query 'BackupDescription.BackupDetails.BackupStatus' --output text
  # Expect: AVAILABLE
  ```
- [ ] **Live table row count** (125 — 10 personas × 12 months billing + 5 PROFILE rows):
  ```bash
  aws dynamodb scan --table-name tariff-billing --select COUNT --profile cevo-dev25 \
    --query 'Count' --output text
  # Expect: 125
  ```

### T-24h — Visual rehearsal + gap closure

- [ ] **Visual rehearsal (Chrome DevTools, 1280×800):** open `https://main.d1b6s4i8w2zlzo.amplifyapp.com` in Chrome at 1280×800 with DevTools → Network. Run 2 passes (cold then warm, 30s apart) across all 5 recommendation personas plus CUST-006 (hardship) plus `cust999` and `CUST-999` error cases. Record per-persona warm median from DevTools Network Duration. **Every warm median must be under the per-flow gate** (3000ms single-tool, 2500ms multi-tool for CUST-003).
- [ ] **v3.0 surface rehearsal:**
  - CUST-003 (Elena): expand reasoning trace, confirm 2-3 tool entries with deterministic summaries
  - CUST-003 (Elena) with streaming: if `VITE_STREAMING_URL` is baked in, confirm trace steps appear progressively (one by one with ~300ms gaps) before the recommendation cards render. The "Analysing…" indicator should pulse while streaming.
  - CUST-006: confirm hardship banner renders with dignity-preserving message, no tariff cards
  - CUST-009: confirm typed hardship banner renders with family_violence category, routing to family_violence_team, zero financial terms in any visible text
  - CUST-007: confirm typed hardship banner renders with payment_difficulty category, routing to hardship_team
  - After any recommendation: click "Draft follow-up email", confirm email draft loads with subject/body/plan_reference
  - After any recommendation: verify `compliance_review` field present in API response with `verdict: "pass"` and `rules_checked` populated
  - After any recommendation: verify `supervisor_trace` field present with `routed_to`, `routing_reason`, `hardship_checked: true`, `compliance_reviewed: true`
  - CUST-006 (hardship): verify `compliance_review.rules_checked` contains `"hardship_no_tariff_data"` and `"hardship_category_tool_restriction"` and verdict is `"pass"`
  - CUST-009 (family_violence): verify `compliance_review.rules_checked` additionally contains `"family_violence_no_financial_content"` and verdict is `"pass"`
  - `?narrative=off`: confirm reasoning trace, hardship banner, follow-up drawer, `compliance_review`, `supervisor_trace`, AND chat UI all collapse to v2.0 shape. In streaming mode, `?narrative=off` suppresses `trace_step` SSE events entirely.
  - **Expanded tool gallery**: after loading CUST-003, use the chat box to ask "Is there an outage near her suburb?" — confirm the agent calls `check_outage_status` and the reasoning trace shows the tool summary (e.g., "Planned outage in Marrickville: ~450 customers"). Try "What concessions is she eligible for?" — confirm `lookup_concessions` fires and returns the Low Income Household Rebate.
  - **Conversational chat**: after loading CUST-001, type "Why is her bill high?" in the chat box. Confirm: (a) the question appears right-aligned in the thread, (b) trace steps stream progressively, (c) the agent reply appears left-aligned with a reasoning trace disclosure, (d) the reply cites tool-returned numbers verbatim. Try a follow-up: "What would solar save her?" — confirm session context carries (no need to re-specify the customer).
  - **Chat session isolation**: load CUST-002, type a question, note the session_id in the response. Switch to CUST-001 — confirm the chat thread clears and a new session starts.
  - **Agentic actions — Retention Queue**: on page load (idle state), confirm the Retention Queue replaces the old "No customer selected" empty state. Verify "N customers at risk today" header with ranked CohortCards showing customer_id, risk_summary, and risk_score. Click a CohortCard — confirm it triggers the full recommendation lookup (same as PersonaChips).
  - **Agentic actions — Action Cards**: after loading CUST-003 (bill-shock persona), confirm Action Cards appear below the recommendation cards. Expect: "Switch to EcoFlex 100" (tariff_switch), "Send SMS follow-up" (send_sms), and "Offer payment plan (6 instalments)" (payment_plan_offer — only for bill-shock delta > $50). Each card has Confirm (primary) and Dismiss (ghost) buttons.
  - **Agentic actions — Confirm/Dismiss flow**: click Confirm on the tariff_switch card — confirm loading spinner, then success indicator ("✓ Confirmed"), both buttons disabled. Click Dismiss on the SMS card — confirm the card collapses from view. If an action has expired (24h TTL), confirm the error state shows "Action has expired" inline.
  - **Agentic actions — `?narrative=off`**: confirm Action Cards are HIDDEN when `?narrative=off` is active (LD-7 kill-switch — actions contain LLM-generated SMS content). Confirm the Retention Queue STILL displays (it contains no LLM content).
- [ ] Confirm the narrative text for each persona looks presentable (no digit leakage, no banned-term leakage, <20/<22 word caps respected). Quick check:
  ```bash
  for ID in CUST-001 CUST-002 CUST-003 CUST-004 CUST-005; do
    curl -s "$BACKEND_API_URL/recommendations/$ID" | \
      jq '.green.usage_narrative, .green.call_script, .cheapest.usage_narrative, .cheapest.call_script'
  done
  ```
- [ ] Confirm hardship response shape:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-006" | jq '.kind, .reason, .call_script'
  # Expect: "hardship", <reason string>, <call_script string>
  ```
- [ ] Confirm typed hardship categories:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-009" | jq '.kind, .category, .routing_target, .permitted_actions'
  # Expect: "hardship", "family_violence", "family_violence_team", ["schedule_callback"]
  curl -s "$BACKEND_API_URL/recommendations/CUST-007" | jq '.kind, .category, .routing_target, .permitted_actions'
  # Expect: "hardship", "payment_difficulty", "hardship_team", ["payment_plan", "billing_history", "schedule_callback"]
  curl -s "$BACKEND_API_URL/recommendations/CUST-008" | jq '.kind, .category, .routing_target'
  # Expect: "hardship", "medical_equipment", "priority_services_team"
  ```
- [ ] Confirm family_violence response has zero financial terms:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-009" | jq '.reason, .call_script' | grep -iE 'dollar|payment|bill|tariff|plan|cost|price|save|switch|account|balance|debt|arrears|overdue'
  # Expect: NO output (zero matches)
  ```
- [ ] Confirm compliance review and supervisor trace on recommendation:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-001" | jq '.compliance_review, .supervisor_trace'
  # Expect: compliance_review.verdict == "pass", supervisor_trace.routed_to == "TariffSpecialist"
  ```
- [ ] Confirm compliance review on hardship response:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-006" | jq '.compliance_review'
  # Expect: verdict == "pass", rules_checked contains "hardship_no_tariff_data" and "hardship_category_tool_restriction"
  curl -s "$BACKEND_API_URL/recommendations/CUST-009" | jq '.compliance_review'
  # Expect: verdict == "pass", rules_checked contains "hardship_no_tariff_data", "hardship_category_tool_restriction", AND "family_violence_no_financial_content"
  ```
- [ ] Confirm streaming endpoint responds (if deployed):
  ```bash
  STREAMING_URL=$(aws ssm get-parameter --name /customer-tariff/streaming-url --query Parameter.Value --output text --profile cevo-dev25)
  curl -s -N -H "Accept: text/event-stream" "$STREAMING_URL/recommendations/CUST-003" | head -20
  # Expect: event: trace_step\ndata: {"tool":"...","summary":"..."}\n\n ... event: result\n ... event: done\n
  ```
- [ ] Confirm narrative=off strips new fields:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-001?narrative=off" | jq 'has("compliance_review"), has("supervisor_trace")'
  # Expect: false, false
  ```
- [ ] Confirm chat endpoint responds:
  ```bash
  curl -s -X POST "$BACKEND_API_URL/chat/CUST-001" \
    -H "Content-Type: application/json" \
    -d '{"message": "Why is her bill high?"}' | jq '.reply, .reasoning_trace | length, .session_id'
  # Expect: non-empty reply, reasoning_trace with 1+ entries, valid session_id
  ```
- [ ] Confirm chat input validation:
  ```bash
  curl -s -X POST "$BACKEND_API_URL/chat/INVALID" \
    -H "Content-Type: application/json" \
    -d '{"message": "test"}' | jq '.error'
  # Expect: error message about invalid customer ID format
  ```
- [ ] Confirm expanded tools via chat:
  ```bash
  curl -s -X POST "$BACKEND_API_URL/chat/CUST-003" \
    -H "Content-Type: application/json" \
    -d '{"message": "Is there an outage near her suburb?"}' | jq '.reasoning_trace[].tool'
  # Expect: "check_outage_status" in the trace
  ```
- [ ] Confirm retention queue endpoint:
  ```bash
  curl -s "$BACKEND_API_URL/retention-queue" | jq '.customers_at_risk, .queue | length, .queue[0].customer_id, .queue[0].risk_score'
  # Expect: non-zero customers_at_risk, 6 entries in queue, highest-risk customer first, scores 0-100
  ```
- [ ] Confirm action confirm/dismiss endpoints:
  ```bash
  # Queue a test action via the recommendation flow (load CUST-001 first)
  curl -s "$BACKEND_API_URL/recommendations/CUST-001" | jq '.pending_actions[0].action_id'
  # Copy the action_id, then:
  ACTION_ID="<paste-action-id-here>"
  curl -s -X POST "$BACKEND_API_URL/actions/$ACTION_ID/confirm" | jq '.status'
  # Expect: "confirmed"
  ```
- [ ] Confirm action error mapping:
  ```bash
  curl -s -X POST "$BACKEND_API_URL/actions/not-a-uuid/confirm" | jq '.error'
  # Expect: "Invalid action_id" (HTTP 400)
  curl -s -X POST "$BACKEND_API_URL/actions/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d/confirm" | jq '.error'
  # Expect: "Action not found" (HTTP 404) for a non-existent action
  ```
- [ ] Confirm pending_actions in recommendation response:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-003" | jq '.pending_actions | length, .pending_actions[].action_type'
  # Expect: 2-3 actions (tariff_switch + send_sms + payment_plan_offer if delta > $50)
  ```
- [ ] Confirm follow-up route:
  ```bash
  curl -s "$BACKEND_API_URL/recommendations/CUST-001"  # prime recommendation
  curl -s "$BACKEND_API_URL/recommendations/CUST-001/follow-up" | jq '.subject, .plan_reference'
  # Expect: non-empty subject and plan_reference
  ```
- [ ] Customer-specific branding / slides updated (if any)
- [ ] Scan this runbook end-to-end
- [ ] Review presenter artefacts: `.planning/docs/presenter/TRUST-ARCHITECTURE.md`, `NARRATIVE-TRADEOFFS.md`, `DEFERRED-ROADMAP.md`
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

- [ ] **Amplify site is live:**
  ```bash
  curl -s "https://main.d1b6s4i8w2zlzo.amplifyapp.com/" -o /dev/null -w "%{http_code}"
  # Expect: 200
  ```
- [ ] Live API URL baked into the deployed bundle:
  ```bash
  curl -s "https://main.d1b6s4i8w2zlzo.amplifyapp.com/assets/index-C5HchoaQ.js" | grep -q 'execute-api.us-east-1.amazonaws.com' && echo "API URL baked in"
  # Expect: "API URL baked in"
  ```
- [ ] Emergency local fallback smoke (10 seconds):
  ```bash
  npm run preview:mock --prefix ui -- --port 4174
  # open http://localhost:4174/ in a private window → confirm CUST-001 returns Sarah's cards
  # Ctrl+C to stop
  ```
- [ ] AWS console tab pre-opened to CustomerTariffApi stack (in case a reviewer wants to see infra)
- [ ] Phone stopwatch accessible (if asked for live latency evidence)
- [ ] Browser tab pre-opened at `https://main.d1b6s4i8w2zlzo.amplifyapp.com` but closed for now

### T-30m — Start keep-alive (DEMO-05)

Open a persistent terminal pane (tmux recommended) and start the 10-minute rotating-persona ping loop so AgentCore's microVM stays warm through Q&A. See §8 for full procedure.

```bash
tmux new-session -s keepalive
export AWS_PROFILE=cevo-dev25
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
bash scripts/demo-keepalive.sh
# Expect: first tick prints "<UTC> CUST-001 204 Nms ok" within ~1s,
# then every 10 minutes rotating CUST-001 → CUST-002 → CUST-003 → CUST-004 → CUST-005
```

- [ ] `BACKEND_API_URL` exported and matches live endpoint
- [ ] First `ok` tick observed before leaving the pane
- [ ] Pane left running (detach tmux, don't close)

### T-10m — Pre-warm (DEMO-03)

Force-warm all 5 recommendation personas + follow-up route through the full Bedrock path and assert all warm medians under per-flow gate. See §9 for full procedure.

```bash
cd ui
BACKEND_API_URL="$BACKEND_API_URL" npm run prewarm
cd -
# Expect exit 0; CUST-001/002/004/005 (single-tool, <3000ms) + CUST-003 Elena (multi-tool, <2500ms)
# + follow-up route for CUST-001
# 3 warm passes per persona + 30s settle + follow-up warm + 15 measurement GETs + per-flow median summary.
```

- [ ] Exit code 0 on first attempt
- [ ] All 5 warm medians under per-flow gate
- [ ] No cold-start re-runs needed

### T-eval — Live eval gate (DEMO-03 tail)

```bash
BACKEND_API_URL="$BACKEND_API_URL" \
  .venv/bin/pytest tests/test_narrative_eval_live.py -m smoke 2>&1 | tail -15
# Expect "12 passed"
```

- [ ] `12 passed` — narrative-validator, `_narrative_source` marker-strip, AGENT-01 determinism, AGENT-02 hardship shape, WF-01 follow-up + memory isolation all green against live
- [ ] If failed: go/no-go decision — `?narrative=off` is the presenter-grade fallback (§5)

### T-0 — Go live (2 minutes before presenting)

1. **Open the Amplify-hosted UI:**
   Open `https://main.d1b6s4i8w2zlzo.amplifyapp.com` in the demo browser tab. Resize to 1280×800 if not already. Confirm the idle state renders (Retention Queue with "N customers at risk today").

2. **Ad-hoc warm** (belt-and-suspenders in case keepalive + prewarm haven't landed a recent tick):
   ```bash
   curl -s -o /dev/null "$BACKEND_API_URL/recommendations/CUST-001"
   ```

3. **Sanity-check the version indicator.** Bottom-right corner should show `v2.0 · <7-char-sha>` where the SHA matches `git rev-parse --short demo-v3.0^`.

4. **You are live.**

---

## 4. Presenter cheat sheet

### The demo personas (recommended order)

| ID | Persona | Expected Green | Expected Cheapest | Demo beat |
|----|---------|----------------|-------------------|-----------|
| CUST-001 | Sarah Chen — high usage | **$30.00/mo · $360.00/yr · EcoFlex 100** | **$55.00/mo · $660.00/yr · Value 12** | Flagship retention save — biggest delta, clearest story |
| CUST-002 | Marcus Webb — mid usage | **$16.90/mo · $202.80/yr · EcoFlex 100** | **$30.98/mo · $371.76/yr · Value 12** | Typical customer — moderate delta, both tracks viable |
| CUST-003 | Elena Vasquez — bill shock | **$14.00/mo · $168.00/yr · EcoFlex 100** | **$25.67/mo · $308.04/yr · Value 12** | **Multi-tool reasoning** — agent detects bill shock, reasoning trace visible |
| CUST-004 | Solar PV household | **$40.02/mo · $480.24/yr · EcoFlex 100** | **$76.03/mo · $912.36/yr · Solar Feed-in (SOL)** | Solar feed-in tariff archetype — export credits move the needle |
| CUST-005 | EV household | **$35.00/mo · $420.00/yr · EcoFlex 100** | **$84.00/mo · $1008.00/yr · EV Time-of-Use (EV-TOU)** | EV TOU tariff — off-peak charging unlocks biggest delta |
| CUST-006 | Hardship persona (legacy) | *(no recommendations)* | *(no recommendations)* | **Hardship short-circuit** — code-side guard, dignity-preserving routing, defaults to category "other" |
| CUST-007 | Hardship — payment difficulty | *(no recommendations)* | *(no recommendations)* | **Typed hardship** — payment plan flow, routing to hardship_team |
| CUST-008 | Hardship — medical equipment | *(no recommendations)* | *(no recommendations)* | **Typed hardship** — priority services routing, life-support guarantees |
| CUST-009 | Hardship — family violence | *(no recommendations)* | *(no recommendations)* | **Typed hardship** — safety-first isolation, zero financial terms, family_violence_team routing |
| CUST-010 | Hardship — other | *(no recommendations)* | *(no recommendations)* | **Typed hardship** — generic category, backward-compat proof |

All dollar values are byte-exact across freeze. If the live API returns something different for a persona, **something is wrong** — switch to the mock fallback (§5) before continuing.

### v3.0 demo flow (recommended 9-beat sequence)

1. **Retention Queue (idle state)** — open the tool with no customer selected. "Before the rep even picks a customer, the system shows a portfolio view — 'N customers at risk today' — ranked by a deterministic risk signal computed from bill-shock magnitude, usage trend, and hardship flags. No LLM involved in the ranking. Click any card to investigate."
2. **Sarah (CUST-001)** — flagship save. Show both cards, point out the narrative and call script. "The dollar values are pure Python; the narrative is LLM-generated with a banned-terms validator."
3. **Elena (CUST-003)** — multi-tool reasoning + streaming + actions. Watch the trace steps appear one by one as the agent works. "You can see the agent thinking in real time — checking the hardship flag, detecting a bill spike, computing savings. Each step streams to the UI as it completes via Server-Sent Events. Every number in those summaries comes from tool output, not the LLM." Then point out the Action Cards below the recommendations: "The agent also prepared three actions — a tariff switch, an SMS follow-up, and a payment plan offer. The rep confirms with one click. The dollar values in the payment plan come from the same deterministic engine; the SMS body is LLM-generated but validator-gated. If the SMS fails validation, a pre-approved fallback substitutes automatically."
4. **Action Card confirm/dismiss** — click Confirm on the tariff switch card. "One click — the action transitions to confirmed. The dismiss button collapses the card. If the action expires after 24 hours, the system tells the rep it's no longer valid. No silent failures."
5. **CUST-006** — hardship short-circuit. "This customer is flagged for hardship support. The system refuses to show tariff recommendations — that's a code-side guard, not a prompt instruction. The LLM never sees tariff context for this customer."
6. **CUST-009** — typed hardship (family violence). "This is a family violence case. The system routes immediately to the specialist safety team — no billing discussion, no account review, no payment mention. The compliance reviewer verifies zero financial terminology in the response. The category drives the routing target, the permitted tools, and the call script — all deterministic from the customer's PROFILE row, not inferred by the LLM."
7. **Compliance review** — after any recommendation, point out the `compliance_review` field in the response. "Every response goes through a deterministic ComplianceReviewer before it reaches the caller. Five AER NECF-aligned rules: reference-period disclosure, no upsell-to-disadvantage, hardship-flag cross-check, category tool restriction, and family violence financial isolation. It's pure Python — no LLM call, no latency cost. The `supervisor_trace` shows which specialist handled the request and why."
8. **Follow-up email** — after any recommendation, click "Draft follow-up email". "The agent remembers the prior recommendation via AgentCore Memory and drafts a personalised email the operator can edit before sending."
9. **Expanded tool gallery + conversational chat** — after showing Elena's recommendation, use the chat box to ask "Is there an outage near Elena's suburb?" or "What concessions is she eligible for?" Watch the agent pick the right tool from the expanded gallery. Then ask "Why did her bill jump?" — watch the reasoning trace stream in real time.
10. **Architecture story** — reference the presenter artefacts. "The agent started as a read-only advisor. Now it prepares actions, ranks a portfolio, decomposes bill shocks into root causes, and answers free-text questions — all with the same numeric integrity guarantee. The Salesforce adapter is a committed stub — same Protocol, same tests. Swapping the data source is a provider implementation, not a rewrite." (See DOC-03.)

### Follow-up email demo beat

After showing a recommendation for any persona (CUST-001 recommended):
1. Click "Draft follow-up email" below the cards
2. Wait for the email draft to load (uses AgentCore Memory to recall the recommendation)
3. Show the editable subject, body, and plan reference
4. Point out: "The operator can edit this before sending — the system drafts, the human decides"
5. Click "Copy to clipboard" to demonstrate the workflow endpoint

### Talking points

**Equal-cards framing (early, once, deliberately):**
> "We deliberately present Green and Cheapest side by side, with no ranking between them. The call-centre agent picks based on what the customer cares about — environmental preference or lowest bill. The system never decides for the customer."

**Determinism framing (when someone asks 'is that really an LLM doing the math?'):**
> "The dollar values are pure Python — a `simulate_savings` function with 29 pytest cases locked since v1.0. The LLM never sees the arithmetic. What the LLM produces is the narrative row and the call-script row. Both go through a Pydantic validator that hard-rejects digits, currency symbols, and a banned-terms list. If validation fails, we fall back to per-persona × per-card committed fallback strings we wrote by hand."

**Reasoning trace framing (after showing Elena's multi-tool flow):**
> "The reasoning trace shows exactly which tools the agent called and in what order. Every number in those summaries — the bill-shock delta, the billing history count, the savings figures — comes from tool output, not the LLM. The summaries are code-composed from pure Python formatters. This is the observability surface: the rep can see what the agent grounded on."

**Streaming framing (after showing progressive trace steps):**
> "What you just saw is real-time streaming — each tool completion pushes an SSE event to the browser before the final recommendation is ready. The 2–3 second agent latency feels responsive because the screen is alive. Under the hood it's a Lambda Function URL with response streaming — same Lambda, same agent, just a different invocation mode. The batch API Gateway path is still there as a fallback. If the streaming endpoint has an issue, the UI falls back to the batch path automatically — the operator never sees a broken state."

**Hardship framing (after showing CUST-006):**
> "When a customer is flagged for hardship support, the system refuses to present tariff recommendations. That's a code-side guard — the LLM never sees tariff plans or savings figures for this customer. Even if you removed the hardship instructions from the prompt, the guard still fires. The response is a dignity-preserving routing message, not a 404 or a 500."

**Typed hardship framing (after showing CUST-009 family violence):**
> "The hardship system isn't one-size-fits-all. Four categories — payment difficulty, medical equipment, family violence, and other — each drive distinct behaviour. A family violence customer gets immediate safety-first routing: the system connects them to the specialist safety team with zero financial terminology in any field. No mention of bills, payments, accounts, or plans. The compliance reviewer enforces this programmatically — it tokenizes the response and rejects any financial term. A medical equipment customer gets priority service guarantees. A payment difficulty customer gets flexible arrangement options. The category is stored on the customer's PROFILE row in DynamoDB — deterministic, auditable, not inferred by the LLM."

**Trust architecture framing (for a technical reviewer):**
> "We have a defence-in-depth stack: pure Python arithmetic at the bottom, banned-terms regex in the middle, fallback bank as the safety net, a ComplianceReviewer that signs off on every response, and a URL kill switch at the top. Every layer is independently testable and independently bypassable. The trust-architecture one-pager is committed to the repo — every claim links to a pytest file or code reference." (See DOC-01.)

**Multi-agent supervisor framing (for a technical reviewer):**
> "The monolithic agent is now three specialists behind a code-side Supervisor. The Supervisor is an `if/elif` router — zero additional LLM calls. The TariffSpecialist owns the recommendation flow. The HardshipSpecialist handles vulnerable customers with typed category routing — no access to tariff tools. The ComplianceReviewer runs five AER NECF-aligned checks as pure Python — reference-period disclosure, no upsell-to-disadvantage, hardship-flag cross-check, category tool restriction, and family violence financial isolation. It adds microseconds, not seconds. Every specialist satisfies an `AgentRole` Protocol with a single `handle()` method — same pattern as the `CustomerDataProvider` from Phase 12. Adding a new specialist is a class that implements `handle()`, not a prompt rewrite."

**Compliance review framing (when someone asks 'what stops a bad recommendation?'):**
> "Three things. First, the ComplianceReviewer checks every response before it leaves the system — reference-period disclosure, no upsell-to-disadvantage, hardship-flag cross-check, category tool restriction, and family violence financial isolation. Second, the narrative validators reject any text with digits, currency, or banned terms. Third, the hardship guard is code-side — the LLM never sees tariff data for flagged customers. For family violence specifically, the compliance reviewer tokenizes the entire response and rejects any financial terminology — dollar, payment, bill, tariff, plan, cost, price, save, switch, account, balance, debt, arrears, overdue. If the ComplianceReviewer fails a response, it attaches a warning but still returns the response — the D-04 never-500 contract takes precedence over compliance gating. The `compliance_review` field is visible in the API response so the operator and the audit trail both see it."

**CRM adapter framing (for a product stakeholder):**
> "The demo runs on DynamoDB today. The Salesforce adapter is a committed stub — same Protocol, same tests, same agent code. Swapping the data source is a provider implementation, not a rewrite." (See DOC-03.)

**Expanded tool gallery framing (after showing the 10-tool set):**
> "The agent started with 4 tariff-math tools. Now it has 10 — outage awareness, bill-shock decomposition with rate/usage/seasonal attribution, concession lookups, solar payback estimation, payment plan proposals, and callback scheduling. Every tool is deterministic and demo-safe — hardcoded seed data, no external API calls. The tool cap budget is 8 calls per invocation, so the agent can orchestrate multi-step workflows without hitting the ceiling. Each tool has a one-liner summary formatter that feeds the reasoning trace — code-composed, no LLM involved."

**Conversational chat framing (after showing the chat box):**
> "This is the same agent, same tools, same numeric integrity rules — but now the rep can ask anything. The LLM picks tools based on the question's intent, not a fixed script. 'Why did her bill jump?' triggers the bill-shock decomposition tool. 'What would solar save her?' triggers the solar payback estimator. The session carries context across turns so the rep can drill deeper without re-explaining. Sessions are scoped per-customer with a 15-minute TTL and 20-turn cap — no cross-customer leakage, no session accumulation."

**Agentic actions framing (after showing the Action Cards):**
> "The agent evolved from advisor to actor. After producing a recommendation, it prepares three actions — a tariff switch, an SMS follow-up, and a payment plan offer — and queues them for the rep to approve with one click. The dollar values in the tariff switch and payment plan come from the same deterministic engine that produces the recommendation cards — the LLM never touches those numbers. The SMS body is LLM-generated but goes through the same D-15 validator that gates the narrative text. If validation fails, a pre-approved fallback substitutes automatically. Actions expire after 24 hours — no stale approvals sitting in a queue."

**Retention queue framing (after showing the portfolio view):**
> "Before the rep picks a customer, the system shows who needs attention today. The risk signal is a weighted composite of bill-shock magnitude, usage trend direction, and hardship flag — all computed by the same deterministic Tools Lambda. No LLM involved in the ranking. Hardship customers get a score of zero — they're routed to the specialist team, not the retention queue. Click any card and you're in the full recommendation flow. This is the same system working at portfolio scale, not just on a known ID."

**Bill-shock decomposition framing (after showing Elena's enriched trace):**
> "The bill-shock tool now tells you *why* the bill spiked — not just that it did. It decomposes the delta into rate changes, usage spikes, seasonal variation, and billing-day differences. Each factor has a dollar amount and a percentage. The explanation sentence is code-composed from those factors — '$45.20 over baseline — 68% from usage spike, 32% from seasonal variation.' The rep can read that to the customer verbatim. Every number comes from the deterministic engine."

**Chat safety framing (for a security reviewer):**
> "The chat endpoint validates inputs before the agent sees them — customer ID format, message length cap at 2000 characters, HTML tag stripping, rate limiting at 10 messages per minute. The agent's system prompt instructs it to decline role-play requests and never disclose tool names or system internals. If the session store fails, it degrades to stateless single-turn mode — the D-04 never-500 contract holds. The `?narrative=off` kill switch hides the entire chat UI."

**Freeze framing (if asked about demo-day reliability):**
> "The environment is locked at T-48h. The 3 CloudFormation stacks have deny-Update:* policies and termination protection. Python dependencies are hash-pinned. We did a 5-step rollback drill. There's a kill switch at `?narrative=off` if the LLM layer misbehaves mid-demo; the UI collapses to v2.0 shape without a redeploy."

### Error paths to rehearse (show one or two if a reviewer asks)

- `cust999` (lowercase, no dash) → 400 alert:
  > "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits."
- `CUST-999` → 404 alert:
  > "No customer found for CUST-999. Check the ID and try again."
- `CUST-006` → hardship banner (not an error, but a distinct path):
  > "This customer is flagged for specialist support. No tariff recommendations shown."

Both error paths are baked into the UI and don't hit the LLM — fast, zero-cost, reliable to rehearse. The hardship path hits the agent but short-circuits before the LLM sees tariff context.

---

## 5. Fallback procedure

**Symptom A — single persona lookup stalls for >10s:** stack is cold. Do not wait. Keep talking (see §4 fallback framing), use `?narrative=off`, move on.

**Symptom B — narrative text visibly wrong (digits, currency, garbled):** LLM / validator layer broke. Use the **URL kill switch** — fastest recovery, no redeploy:

```
# Add ?narrative=off to the Amplify URL in your browser:
https://main.d1b6s4i8w2zlzo.amplifyapp.com?narrative=off
```

The UI collapses to v1.0 shape — both cards retain dollars, methodology, and track metadata; the narrative and call-script rows simply disappear. Loading-state skeletons also collapse so there is no layout shift when the flag is on. **v3.0 surfaces also collapse:** reasoning trace renders null, hardship banner renders null, follow-up email drawer renders null, `compliance_review` and `supervisor_trace` fields are omitted from the API response, chat input box and thread are hidden entirely, **Action Cards are hidden** (they contain LLM-generated SMS content). In streaming mode, `trace_step` SSE events are suppressed entirely. **The Retention Queue still displays** when `?narrative=off` is active — it contains no LLM-generated content (all risk signals are deterministic). Single flag, single rehearsal contract (LD-7).

**Symptom C — any other surprise (dollar values wrong, 5xx, blank page, Amplify 404):** fall back to local preview:

```bash
# Start local preview from the pre-built dist:
npm run preview --prefix ui
# Open http://localhost:4173/ in the browser
```

If the local dist is also broken, switch to mock dist:

```bash
npm run preview:mock --prefix ui
# Refresh the browser tab (preview:mock may bind a different port — check the terminal output)
```

What to say while you swap (keep talking, keep eye contact):
> "We're running on a live AWS deployment today, which occasionally has a propagation moment. Let me swap to our local mode so we can keep moving — the data and recommendations are identical; this is just a network-path substitution."

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

**Primary (Amplify-hosted, live API, narrative on):**
```
https://main.d1b6s4i8w2zlzo.amplifyapp.com
```

**Kill-switch URL:** append `?narrative=off` to the Amplify URL:
```
https://main.d1b6s4i8w2zlzo.amplifyapp.com?narrative=off
```

**Emergency local fallback (if Amplify is down):**
```bash
npm run preview --prefix ui
# http://localhost:4173/
```

**Emergency mock fallback (if live API is down):**
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

## 7. T-48h Freeze Ceremony — v3.0 (2026-05-04)

The v3.0 freeze ceremony was executed on 2026-05-04. **This section is a record of what was done**; do not re-run inside the 48-hour window unless something has broken.

**Result:** PASS. DEMO-04 + DEMO-06 + DEMO-08 satisfied.

### What the ceremony produced

- **CFN stack lock** — `Deny Update:*` policies on all 3 stacks (CustomerTariff, CustomerTariffAgent, CustomerTariffApi) via `aws cloudformation set-stack-policy`, plus `--enable-termination-protection` on all 3. Stack policy byte-equality: PASS on all 3 stacks. Termination protection: `True` on all 3 stacks.
- **Hash-pinned lockfiles** — `requirements.txt` (62+ entries incl. `bedrock-agentcore==1.6.3`) + `requirements-dev.txt` (33+ entries) with `--require-hashes` fresh-venv install gate PASSED (398 passed, 46 deselected)
- **DynamoDB freeze backup** — `arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777859824019-989beacf`, status AVAILABLE. Differs from v2.0 backup ARN (`01777208516554-e1bee933`) — single-backup-per-milestone invariant holds.
- **FREEZE-MANIFEST.md** — fully populated at `.planning/milestones/v3.0-phases/17-freeze-ceremony/FREEZE-MANIFEST.md`. All `<pending>` placeholders replaced; WN-2 self-consistent (`manifest.git.freeze_commit_sha == demo-v3.0^`)
- **Annotated `demo-v3.0` tag** — commit `d7c7853db23e66309eceb664c26ac8b598c84013`; `demo-v3.0^` = freeze commit `62c8adf1e1f9447b0bd923cd695776b1f5320d07`; pushed to origin
- **Rollback drill 5/5 PASS** — full log at `.planning/milestones/v3.0-phases/17-freeze-ceremony/17-DRILL-LOG.md`. Drill duration ~20 min.
- **v3.0 additions** (not present in v2.0 manifest): `memory_id` (`tariff_agent_memory-xVDAvVCTtU`), `agent_runtime_arn`, `api_endpoint`

### Rollback-drill evidence

| Step | What was drilled | Evidence | Verdict |
|------|------------------|----------|---------|
| 1 | `?narrative=off` kill switch — v3.0 surfaces collapse to v2.0 shape | Browser at 1280×800: reasoning trace null, hardship banner null, follow-up drawer null; API still returns narrative fields | PASS |
| 2 | `npm run build:mock` <10s + intra-HEAD hash determinism | 0.93s wall-clock; intra-HEAD determinism confirmed (D-16 softening) | PASS |
| 3 | `git checkout demo-v2.0` + fresh-clone pytest | 188 passed, 1 failed (seeder count — live table has v3.0 data), 34 deselected | PASS |
| 4 | DynamoDB restore from v3.0 backup + scan + spot-check | 73 items; 5 personas non-null `usage_kwh` at 2025-04 | PASS |
| 5 | Scratch table teardown | `tariff-billing-rollback-drill` → `ResourceNotFoundException` | PASS |

### Drill step 3 finding

Step 3 `test_table_has_36_items` expected 36 items but live table has 73 (post-Phase 11 extended data layer). Environmental artifact — all code-level tests pass. Same finding as v2.0 ceremony. The higher pass count (188 vs 87 in v2.0 drill) reflects the v2.0 tag including more test files than the v1.0 tag used in the v2.0 drill.

### v2.0 ceremony record (historical — Phase 10, 2026-04-26)

The v2.0 freeze ceremony was executed on 2026-04-26 (12:13:10–14:11:52 UTC). The `demo-v2.0` tag still exists and is pushed to origin. Key evidence:

- **Tag:** `demo-v2.0` — commit `a09c0867b8acc047f4ed64dc2cb4a81d64401e0e`; `demo-v2.0^` = `1a83a87c2e134bb264f38f809e33611486821be0`
- **Manifest:** `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`
- **Drill log:** `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-DRILL-LOG.md` — 5/5 PASS, ~36 min
- **DynamoDB backup:** `arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933` (36-row v2.0 snapshot — does NOT match current live state)
- **Rule 4 deviations:** R1 (lockfile scope extension), R2 (python3.13 + AWS_PROFILE codification), D-16 (dist hash softening to intra-HEAD determinism)
- **Full ceremony evidence:** `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-03-SUMMARY.md`

### Phase 11 amendment — live-deploy of extended data layer (2026-04-28)

After the v2.0 freeze held for two days, v3.0 Phase 11 required extending the CustomerTariff stack to add 3 personas, 2 tariff archetypes, a dispatcher refactor in `simulate_savings_pure`, and a PROFILE sentinel-SK row. Executed via the break-glass sequence — **scoped to CustomerTariff only**; sibling stacks (CustomerTariffAgent, CustomerTariffApi) were not touched.

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
- The v3.0 freeze ceremony (Phase 17) re-froze all 3 stacks with the full v3.0 surface deployed. The Phase 11 amendment is now subsumed by the v3.0 freeze.
- **Future re-seed risk:** if the seed grows past another 25-item chunk boundary (75, 100, …) the same Seeder1-Update-doesn't-fire bug is likely to recur. Pattern to reuse: bump phys-id, deploy, scan count, and `batch-write-item` backfill any deficit rather than relying on CDK's phys-id-change machinery alone. Warning captured in `.planning/phases/11-new-personas-tariff-archetypes/11-REVIEW.md`.

### Break-glass (if you ever need to unlock)

Only use if the freeze must be lifted post-ceremony (e.g., a critical bug requires an infra change). This is strictly human-gated; no automation. After unlocking, applying a fix, and relocking, re-run steps 2–7 of the ceremony and cut `demo-v3.0.1`.

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

# 3. Make your change, redeploy, cut a new tag (demo-v3.0.1), re-freeze.
```

---

## 8. Keep-Alive (DEMO-05) — start at T-30m

The `scripts/demo-keepalive.sh` shell loop pings `/recommendations/CUST-00X` every 10 minutes, rotating through all 5 recommendation personas. It beats AgentCore's 15-minute microVM idle timeout so the first live persona lookup in the demo is warm.

### Start it

```bash
tmux new-session -s keepalive
export AWS_PROFILE=cevo-dev25
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
bash scripts/demo-keepalive.sh
# First tick within ~1s: "<UTC> CUST-001 204 Nms ok"
# Subsequent ticks every 10 minutes, rotating CUST-001 → CUST-002 → CUST-003 → CUST-004 → CUST-005
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

`npm run prewarm` (a thin wrapper over `scripts/prewarm.py`) warms all 5 recommendation personas via Phase 7's `?prewarm=1` route, exercises the follow-up route for CUST-001, waits 30s for provisioned concurrency to settle, then runs 15 timed measurement GETs (3 per persona). It asserts every warm median is under the per-flow gate (3000ms single-tool, 2500ms multi-tool for CUST-003).

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

The smoke-gated live eval harness asserts (a) the Phase 6 narrative validator rules still hold end-to-end — no digits, no currency symbols, no banned terms in any of the 20 narrative/script fields across 5 personas × 2 tracks — AND (b) the Phase 7 `_narrative_source` marker is stripped from every response body — AND (c) v3.0 canaries: AGENT-01 multi-tool determinism, AGENT-02 hardship refusal shape, WF-01 follow-up route + cross-customer memory isolation.

### Run it

```bash
BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/" \
  .venv/bin/pytest tests/test_narrative_eval_live.py -m smoke 2>&1 | tail -15
```

### Expected output

```
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-001] PASSED
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-002] PASSED
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-003] PASSED
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-004] PASSED
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-005] PASSED
tests/test_narrative_eval_live.py::test_agent01_latency_floor PASSED
tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked PASSED
tests/test_narrative_eval_live.py::test_agent01_non_shock_stays_2_tools PASSED
tests/test_narrative_eval_live.py::test_agent02_hardship_refusal_shape PASSED
tests/test_narrative_eval_live.py::test_agent01_multi_tool_determinism PASSED
tests/test_narrative_eval_live.py::test_wf01_follow_up_route PASSED
tests/test_narrative_eval_live.py::test_wf01_cross_customer_memory_isolation PASSED
============ 12 passed in X.XXs ============
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
- API Gateway endpoint URL changes on redeploy — update `.planning/milestones/v1.0-phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` accordingly and, if the live URL changes materially, cut a new tag (e.g., `demo-v3.0.1`)
- **The freeze DynamoDB backup persists even after the table is deleted.** That backup ARN is the restore target if the stack is recreated and you want to come back to v3.0 demo state.

---

## 12. Troubleshooting playbook

| Symptom | Likely cause | Fast check | Remedy |
|---------|-------------|-----------|--------|
| First persona lookup spins >10s | AgentCore cold start; keepalive missed a window | Check keepalive pane for recent `ok` ticks | Fallback to `?narrative=off` or mock dist; don't wait |
| Narrative text has a digit or `$` | Validator bypass or regex miss | Run §10 live eval gate | `?narrative=off` for demo; capture bodies post-demo |
| Dollar values wrong for a persona | DynamoDB table content drift from post-Phase-16 baseline | `aws dynamodb scan --table-name tariff-billing --profile cevo-dev25 --select COUNT` (expect **125** post-Phase 16; 73 is the pre-AGENT-03 shape; 36 is the pre-Phase-11 v2.0 shape) | If ≠125 but ≥73: seed re-chunk deficit — see §7 amendment step 4 (`batch-write-item` backfill). If ≤36: restore from freeze backup rolls to v2.0 data, hard rollback to `demo-v1.0` for tag parity |
| Extended-persona lookup (CUST-004/005/006) returns 404 in mock mode | `build:mock` dist only covers the flagship 3 personas | `git describe --tags --exact-match` + check browser URL (`localhost:4174/?...`) | Pivot demo narrative back to CUST-001/002/003 (§5 caveat), or swap back to live preview if the live stack is healthy |
| Typed hardship persona (CUST-007/008/009/010) returns 404 | DynamoDB PROFILE rows not seeded (AGENT-03 seed data missing) | `aws dynamodb get-item --table-name tariff-billing --key '{"customer_id":{"S":"CUST-009"},"month":{"S":"PROFILE"}}' --profile cevo-dev25` | If missing: re-seed via `batch-write-item` with PROFILE_ITEMS from `billing_records.py`; if present but wrong category: check `hardship_category` attribute |
| Family violence response contains financial terms | Fallback script contaminated or wrong category-keyed script selected | `curl -s "$BACKEND_API_URL/recommendations/CUST-009" \| jq '.reason, .call_script'` — grep for financial terms | Check `agent/narrative/fallbacks.py` CUST-009 entry; verify `compliance_review` shows `family_violence_no_financial_content` rule ran |
| Live DynamoDB count is 59 (or any number between 36 and 73) | Seed re-chunk deficit — Seeder1 Update didn't re-fire its batchWriteItem after phys-id bump | `aws dynamodb scan --table-name tariff-billing --select COUNT --profile cevo-dev25` | `aws dynamodb batch-write-item` with the missing persona-month rows pulled from `DYNAMO_RECORDS` — documented pattern in §7 amendment |
| Version indicator missing / shows wrong SHA | Wrong dist in `ui/dist/` | `grep 'v2.0 · ' ui/dist/assets/*.js` | Rebuild: `VITE_API_URL="$BACKEND_API_URL" npm run build --prefix ui` |
| `?narrative=off` doesn't collapse the cards | Not on demo-v3.0; on demo-v1.0 (no narrative layer) | `git describe --tags --exact-match` | `git checkout demo-v3.0 && npm ci --prefix ui && rebuild` |
| `cdk diff` no longer `== 0` | Something touched the stack post-freeze (D-13 violation) | Run §3 T-48h verification block | Decision: revert the change + redeploy, or accept drift for the demo |
| Pytest fails on fresh clone | `AWS_PROFILE` stale OR system python too old | `echo $AWS_PROFILE; which python3` | `export AWS_PROFILE=cevo-dev25`; use `/opt/homebrew/bin/python3.13` (Rule 4 R2) |
| `npm run prewarm` exit 1 | Warm median ≥3000ms on a persona | Re-run once (cold-start artefact); then decide | `?narrative=off` for demo; investigate post-demo |
| `git push origin demo-v3.0` fails ("tag exists") | Tag already pushed during ceremony | `git ls-remote --tags origin` | No action needed; push is idempotent |
| Streaming trace steps don't appear (batch fallback fires) | `VITE_STREAMING_URL` not baked into dist, or Function URL misconfigured | Check `grep STREAMING ui/dist/assets/*.js`; check SSM `/customer-tariff/streaming-url` | Rebuild with `VITE_STREAMING_URL` set; or accept batch fallback — recommendations still work, just no progressive trace |
| SSE connection drops mid-stream | Lambda timeout or network interruption | Check CloudWatch logs for the Function URL invocation | UI auto-transitions to error state; retry the lookup — the batch path via API Gateway is unaffected |
| Chat box doesn't appear below cards | `?narrative=off` is active, or recommendations haven't loaded | Check URL for `narrative=off`; check Network tab for successful recommendation response | Remove `?narrative=off` from URL; ensure recommendations load first |
| Chat returns 400 on valid customer | Message validation failing (empty, >2000 chars, or HTML stripping left empty) | Check request body in Network tab — `message` field must be 1–2000 non-empty chars | Ensure message is non-empty after HTML stripping; check for invisible Unicode |
| Chat returns 429 | Rate limit hit (10 messages/minute/session) | Wait 60 seconds, or start a new session (switch customer and back) | Inform presenter to pace questions; rate limit resets per minute |
| Chat session context lost between turns | Lambda cold start evicted in-memory session store | Check if session_id in response differs from previous turn | Expected behavior on cold start — session degrades to stateless mode gracefully (D-04) |
| Agent picks wrong tool in chat | LLM intent routing mismatch — question ambiguous | Try rephrasing the question with clearer intent keywords | Not a bug — the LLM selects tools based on question semantics; clearer questions get better routing |
| Expanded tool returns error in chat | Seed data doesn't cover the queried customer/suburb | Check which customer_id is loaded; verify suburb exists in OUTAGE_DATA | Use known personas (CUST-001→Bondi, CUST-002→Parramatta, CUST-003→Marrickville) for outage demos |
| Retention Queue shows 0 customers at risk | `compute_risk_signals` returned all-zero scores (all hardship) or endpoint failed | `curl -s "$BACKEND_API_URL/retention-queue" \| jq '.customers_at_risk'` | If 502: Tools Lambda misconfigured; if 0: check hardship flags in DynamoDB (hardship caps score at 0) |
| Action Cards don't appear below recommendations | `pending_actions` empty in response (action preparation failed silently per D-04) | `curl -s "$BACKEND_API_URL/recommendations/CUST-003" \| jq '.pending_actions \| length'` | If 0: action preparation failed (non-fatal per D-04); recommendations still correct. Check Tools Lambda logs for `queue_action` errors |
| Action confirm returns 410 (expired) | Action was queued >24h ago (TTL expired) | Check `expires_at` field in the action response | Re-run the recommendation to queue fresh actions; actions have 24h TTL by design |
| Action confirm returns 409 (already processed) | Action was already confirmed or dismissed | Check `status` field — should be "pending" for confirm/dismiss to work | Expected behavior — each action can only be confirmed or dismissed once |
| Retention Queue visible but Action Cards hidden | `?narrative=off` is active — correct behavior (LD-7) | Check URL for `narrative=off` | Remove `?narrative=off` to see Action Cards; Retention Queue is intentionally visible in both modes |
| Payment plan offer not appearing for CUST-003 | Bill-shock delta ≤ $50 for this invocation | Check `total_delta_dollars` in the decomposition result | Payment plan only offered when `is_shock=true` AND `delta > $50`; verify Elena's billing data hasn't drifted |
| Amplify site returns 404 | CDK deploy uploaded zip but Amplify didn't extract it | `aws amplify list-jobs --app-id d1b6s4i8w2zlzo --branch-name main` — check latest job status | Use manual deployment: `aws amplify create-deployment` → upload zip → `aws amplify start-deployment` (see §2 step 5 redeploy instructions) |

---

## Cross-references

**Presenter artefacts (Phase 16 DOC-01/02/03):**
- Trust architecture: `.planning/docs/presenter/TRUST-ARCHITECTURE.md`
- Narrative tradeoffs: `.planning/docs/presenter/NARRATIVE-TRADEOFFS.md`
- Deferred roadmap: `.planning/docs/presenter/DEFERRED-ROADMAP.md`

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
| **Softphone / agent-assist** (this demo) | Built, frozen at `demo-v3.0`, drilled | Call-centre operator reads to customer | Operator's existing softphone session | Low — operator filters; `?narrative=off` kills it live |
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

Both mockups display **byte-exact Sarah Chen (CUST-001) data** fetched from the live `demo-v3.0` stack at build time:

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
3. Reuse the `demo-v3.0` API contract as the portal's backend; no backend changes needed for read-side

If the email channel is more urgent (e.g., retention campaign pressure):
1. Dedicated batch-send milestone — infrastructure is simpler but regulatory surface (AEMC / ACCC on savings claims in marketing) is heavier
2. Legal review of `call_script` copy for email use — the current validator passes but email copy has different standards than an operator reading live

---

*Last updated: 2026-05-05 after typed hardship categories (Phase 16 AGENT-03), expanded tool gallery (Phase 20), and conversational chat layer (Phase 21). Runbook upgraded to include: typed hardship categories with four category-specific routing paths (payment_difficulty → hardship_team, medical_equipment → priority_services_team, family_violence → family_violence_team, other → hardship_team), category-specific call scripts and permitted tool sets, two new compliance rules (hardship_category_tool_restriction, family_violence_no_financial_content), 4 new hardship personas (CUST-007 through CUST-010), DynamoDB seed data expanded to 125 records (10 personas × 12 months + 5 PROFILE rows). Also includes: 10-tool agent gallery (outage, bill-shock decomposition, concessions, solar payback, payment plans, callback scheduling), ToolCapHook budget raised to 8, conversational chat endpoint (POST /chat/{customer_id}) with SSE streaming and session management, chat UI components (ChatInputBox + ChatThread), and mock chat mode. All existing invariants preserved (SAV-03, REC-03, D-15, D-04, SC-3, LD-4). Prior updates: streaming reasoning trace (Phase 19), multi-agent supervisor (Phase 18).*
