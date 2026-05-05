# Technical Demo Brief — Customer Tariff & Billing Optimisation Agent

**For:** Drew Taylor — presenter
**Audience:** System administrators + programmers (the people who'll operate, extend, or fork this codebase)
**Duration:** 45–60 minutes (30 min walkthrough + 15–30 min Q&A)
**Date:** Day after the CEO demo (2026-05-08)
**Companion docs:**
- `CLAUDE.md` (repo root) — invariants and pitfalls in one place
- `.planning/docs/presenter/TRUST-ARCHITECTURE.md` — the safety-pattern one-pager
- `.planning/docs/presenter/DEFERRED-ROADMAP.md` — what's source-only, what's next
- `DEMO-RUNBOOK.md` — operations checklist (stack policies, freeze ceremony, rollback drill)

> Read top-to-bottom. The CEO brief was a teleprompter; this one is a tour guide. You're showing engineers code, not numbers — they want to know **how**, **why**, and **what happens when it goes wrong**. The single most important framing: *the LLM is one component in a stack that includes deterministic engines, validators, fallback banks, and code-side guards. The LLM is not the system.*

---

## 0. Pre-demo setup (5 min before they arrive)

This audience will read code over your shoulder. Have it open and ready.

**Editor windows (one per file, in tab order):**

| Tab | File | Why |
|---|---|---|
| 1 | `agent/agent.py` (jump to line 1246 `_BASE_SYSTEM_PROMPT`) | The system prompt — the opening artefact |
| 2 | `lambda/handler.py` (jump to line 75 `simulate_savings_pure`) | The deterministic engine — SAV-03 |
| 3 | `agent/narrative/banned_terms.py` | The validator regex — 60 lines, fits on one screen |
| 4 | `agent/hooks/four_tool_cap.py` | The HookProvider pattern — Strands extension point |
| 5 | `agent/agent.py` (jump to line 1645 `def invoke`) | The supervisor / dispatcher — entry point |
| 6 | `api_lambda/handler.py` (jump to line 256 `def handler`) | The API edge — never-500 contract, UNKNOWN sentinel |
| 7 | `agent/providers.py` | The Protocol seam — production seam example |
| 8 | `agent/Dockerfile` | The container layout — explains the bi-mode imports |

**Terminal windows:**
- One running `pytest -m "not smoke"` (let it finish before they walk in — show "200+ passed" on screen)
- One ready to `curl` the live API
- One in `.planning/phases/` for the milestone history

**Browser tabs:**
- The Strands SDK docs: https://strandsagents.com (or open the github)
- Bedrock AgentCore overview: https://aws.amazon.com/bedrock/agentcore (if accessible)
- The trust-architecture doc rendered: `.planning/docs/presenter/TRUST-ARCHITECTURE.md`

---

## 1. The 60-second opening (set the frame)

> "What you're about to see isn't a chatbot wrapped around an API. It's an Agentic AI system, which means: one LLM agent with tool-calling autonomy, a deterministic engine doing the load-bearing arithmetic, a validator stack that filters every model output, and a code-side dispatcher that routes around the model entirely for safety-critical paths.
>
> I'm going to show you the architecture in seven stops. The order matters: I want you to see the *deterministic floor* before you see the *AI ceiling* — because everywhere this system makes a decision that matters, the answer is 'the AI didn't, the code did.'
>
> The stack is Strands SDK on AWS Bedrock AgentCore, model is Claude Sonnet 4.6 pinned by ID, deployed via four CDK stacks to one region. Code is at `…/Cevo/Customer-Tariff`, frozen at `demo-v3.0`. Anything you see in this codebase that I don't show you today — happy to dig into in Q&A or after."

---

## 2. The 7-stop technical walkthrough

Total: ~30 minutes. Each stop is 3–6 minutes — show the file, explain the *why*, point at the test that locks it.

### Stop 1 — The deterministic engine (`lambda/handler.py::simulate_savings_pure`)

**Open:** Tab 2, line 75.

> "This is where every dollar figure in the demo originates. It's a pure Python function — no I/O, no AWS calls, no LLM. Inputs are the customer's billing history and the tariff catalogue; output is the Green track and the Cheapest track with byte-exact savings.
>
> Three plan-types fan out at line 105: flat-rate green-premium, time-of-use (EV), and solar-feed-in. Each has its own projected-cost formula. The 'Green' track is `argmax(green_score)` over green-premium plans excluding the customer's current plan. The 'Cheapest' is `argmin(projected_cost)` over all candidate plans. Both savings figures are `round(current_cost - projected, 2)` — that's why you see numbers like Marcus's $16.90 and not $16.9012.
>
> Why does this matter? Because **the LLM never sees this function or its math**. The agent's tool list includes a `simulate_savings(customer_id)` Strands `@tool` that the agent invokes; that tool is a thin wrapper that calls the production Tools Lambda over boto3, which runs *this* function. The arithmetic boundary is enforced by deployment topology, not by the model's good behaviour."

**Show the test that locks it:** `tests/test_simulate_savings.py` — 270 lines, 29 cases, every persona's expected dollars asserted at the float level.

> "If anyone — me, the AI, a future contributor — changes the math, this file goes red. The freeze contract includes this test passing on a fresh checkout."

### Stop 2 — The system prompt (`agent/agent.py::_BASE_SYSTEM_PROMPT`)

**Open:** Tab 1, line 1246.

> "This is what we tell the model. Read the first paragraph: 'Your ONLY job is to retrieve savings data and present TWO recommendation tracks simultaneously.' That framing — narrow, single-purpose — is the first guardrail.
>
> The middle of this prompt is the *tool preference order* — `get_hardship_flag` first, optionally `detect_bill_shock`, optionally `get_billing_history`, always `simulate_savings` last. The model sees this as a numbered list with explanatory text. The system has 9 tools available; the prompt deliberately surfaces the 4 it expects to call.
>
> The block headed **ARITHMETIC INTEGRITY (SAV-03)** is the most heavily-tested clause in the entire prompt. It says: 'You are NOT permitted to estimate, recalculate, round, average, adjust, or otherwise modify them — even if they look wrong, even if they conflict with prior context'. This is *belt*. The validator stack you'll see in the next stop is *braces*. The deterministic engine you just saw is the floor. Three layers; any one is sufficient on its own."

**Point at the SHORT-CIRCUIT RULE (line 1276):**

> "This is interesting because it's a *latency* optimisation expressed in natural language to the model. The deployed agent runs in ~11 seconds; every extra tool call adds ~400-700ms. By telling the model 'non-shock customers stop at 2 tools, shock customers go to 3', we trim a tool call for the common case. Phase 13.1 found this didn't fully land — Elena (the shock persona) sometimes still returns a 2-step trace instead of 3. We left the prompt rule in place because the *outcome* is correct (savings byte-exact) and tightened the prompt is cheaper than tightening the model."

### Stop 3 — The validator stack (`agent/narrative/banned_terms.py` + `validators.py`)

**Open:** Tab 3.

> "Two compiled regexes, sixty lines of Python, run on every model output before it reaches the API response.
>
> `NUMERIC_REGEX` rejects any digit, `$`, `£`, `€`, or `%`. That single line — `[\d$£€%]` — is what stops the model from putting '$30' or '15%' in a narrative field. It's not a safety blanket; it's a wall.
>
> `BANNED_REGEX` is a word-boundary alternation over three tuples: competitor names (Origin, AGL, EnergyAustralia, Red Energy, Alinta, Momentum), switch verbs (switch, switching, transfer, swap, etc.), and environmental superlatives (greenest, carbon-neutral, net-zero). The competitor list is locked — D-12 in CLAUDE.md says we don't expand inside a freeze window. Switch verbs are why the call scripts say 'ask about EcoFlex' instead of 'switch to EcoFlex'."

**Switch to `validators.py`:** show the Pydantic `field_validator` decorators.

> "The validators are mounted on `TrackInfo` in `agent/agent.py:208` — `_validate_usage_narrative` and `_validate_call_script`. They run inside Pydantic's `output_model(**dict)` call inside `BedrockModel.structured_output`. If the model output fails any rule, Pydantic raises `ValidationError`. The agent's `invoke()` catches that and routes to a per-persona × per-card fallback string in `agent/narrative/fallbacks.py` — hand-written copy that ships when the model misbehaves. The user sees a recommendation either way."

**Show the rejection order at line 40:**

> "Order matters: numerics before banned terms before word cap. This matches the test fixtures in `test_narrative_validator.py`. If you reorder them you'll get different error messages, and the test suite goes red. That's deliberate — the rejection reason is part of our observability surface."

### Stop 4 — The HookProvider pattern (`agent/hooks/four_tool_cap.py`)

**Open:** Tab 4. Whole file fits on one screen — read it together.

> "This is a 76-line file solving a problem you'll hit on every Strands or LangGraph or AutoGen agent you build: how do you cap the agent's tool-call budget?
>
> The naïve answer is `Agent(max_iterations=4)`. Strands 1.37.0 doesn't have that parameter. Pitfall 2 in CLAUDE.md says: pass `max_iterations` and you get a silent ignore or a TypeError. Either way the cap doesn't fire.
>
> The Strands answer is `HookProvider`. You subscribe to lifecycle events — here, `AfterToolCallEvent`. You increment a counter. When the counter exceeds budget, you call `event.agent.cancel()`, which is the documented Strands cancellation API. The cancellation surfaces in the next loop iteration as `agent_result.stop_reason == 'cancelled'`, which `invoke()` reads at line 676 and routes through the existing D-04 fallback path.
>
> Why does this matter? Because **the agent loop is bounded by code, not by the model deciding it's done**. A misbehaving model that wants to call tools forever gets stopped at call 8. The cap is not a polite request in the prompt — it's an asyncio event from Python land that interrupts the tool-call loop."

**Point at the `reset()` method:**

> "This is the most important line of the file. The hook holds *instance-level* state — `self.used`. Across invocations the same hook instance is reused for warm-start preservation. If you forget to `reset()` at the top of `invoke()`, your second customer lookup runs with the budget already half-spent from the first. The fix is one line: `_four_tool_cap.reset()`. The bug it would cause if missing is invisible until call ~5 of the day. Pattern: every module-level cache must have a per-invocation reset."

### Stop 5 — The dispatcher (`agent/agent.py::invoke`)

**Open:** Tab 5, line 1645.

> "This is the AgentCore entrypoint. Every customer lookup lands here. Read the docstring — three routes: `follow_up`, `chat`, default `recommend`. We're going to follow the recommend path.
>
> Line 1683 — `get_provider().get_hardship_flag(customer_id)`. **The hardship check happens before the LLM ever runs.** This is the code-side guard CLAUDE.md calls 'Phase 14 AGENT-02'. If the flag is true, line 1695 dispatches to `HardshipSpecialist.handle()`, which is pure Python — no Agent, no model, no tools. The customer's call routes to specialist support without the LLM ever seeing tariff data."

**Open `agent/specialists/hardship.py` quickly to show how short it is.**

> "Sixty-eight lines. No model. The hardship path is faster than the non-hardship path by an order of magnitude — about 1.3 seconds versus 11 seconds. That gap is your second observability surface: if hardship is suddenly slow, the dispatcher is broken."

**Back to `invoke()`:**

> "Lines 1703–1714 — the `ComplianceReviewer.review()` and `supervisor_trace`. These are post-dispatch surfaces. *Note for this audience:* these were added in Phase 18 and are present in the source but not deployed in the live `demo-v3.0` runtime — the API responses you saw yesterday don't have these fields. Phase 18 ships in the next deployment cycle. Same pattern though: deterministic Python, no LLM."

### Stop 6 — The API edge (`api_lambda/handler.py::handler`)

**Open:** Tab 6, line 256.

> "This Lambda sits in front of the AgentCore runtime. Two interesting things to call out.
>
> **First** — line 62-63: `Config(read_timeout=25, connect_timeout=5)`. Default boto3 read timeout is 60 seconds. The Lambda's overall timeout is 30 seconds. If you don't override the boto3 timeout, the Lambda dies before boto3 does — meaning the 504 'gateway timeout' branch at line 372 is **unreachable**. CLAUDE.md flags this as 'do not remove'. It's a five-character config that took three pages of post-mortem to find. Watch for this pattern in your own systems: layered timeouts must descend, not ascend.
>
> **Second** — line 308: the prewarm branch. `?prewarm=1` returns 204 on success and 204 on failure. That's deliberate — D-04 says we never expose 5xx to the UI's keep-alive script. The shell script in `scripts/demo-keepalive.sh` hits this every 10 minutes to keep the AgentCore microVM warm. If the prewarm fails it logs and returns 204; the keepalive script keeps trying.
>
> **Third** — line 392-404: the customer-not-found heuristic. The agent's fallback path returns `{"errorMessage": "..."}` with no `green` or `cheapest` keys. We treat 'no green or cheapest keys in body' as 404. *But* — line 417 — defence in depth. We also check for `plan_id == "UNKNOWN"` on either track, because Sonnet 4.6 once emitted that string when the prompt's STOP-on-empty-billing rule didn't fire. If the model regresses, we fail loudly (404) instead of silently (200 with placeholder tracks)."

**The phrase to emphasise:** "Defence in depth means you assume each layer will eventually fail."

### Stop 7 — The Protocol seam (`agent/providers.py`)

**Open:** Tab 7.

> "Last stop. This is how we keep the system swappable.
>
> `CustomerDataProvider` is a `runtime_checkable` Protocol with three methods: `get_customer`, `get_billing_history`, `get_hardship_flag`. Three implementations satisfy it: `ToolsLambdaProvider` (production — issues boto3 invokes), `InMemoryProvider` (offline tests — reads the same seed data the live DynamoDB seeder uses), and `SalesforceCustomerDataProvider` (a stub that raises `NotImplementedError` with a breadcrumb to the deferred-roadmap doc).
>
> Why does this matter? **The agent code calls `get_provider().get_hardship_flag(customer_id)`.** It doesn't know — and shouldn't know — whether the data is in DynamoDB, Salesforce, or a Python dict. When you want to migrate to Salesforce, you implement the third class. The agent code, the system prompt, the validators, the test suite — none of it changes. CLAUDE.md calls this the 'strangler-fig seam'.
>
> Also notice what the Protocol *deliberately excludes*: `simulate_savings`. Arithmetic stays in Tools Lambda by design (D-04, SAV-03). If you put simulate_savings on the Protocol, every adapter has to re-implement the math, every adapter is a new place to introduce a bug. The math has one home."

---

## 3. Architecture in 90 seconds (whiteboard moment)

After the 7 stops, draw this on the whiteboard or pull up an existing diagram.

```
                       ┌─────────────────────────────────┐
                       │     React UI (Amplify)          │
                       │     ?narrative=off kill switch  │
                       └────────────┬────────────────────┘
                                    │ HTTPS
                                    ▼
                       ┌─────────────────────────────────┐
   API Gateway ────►   │   API Lambda (api_lambda/)      │
   HTTP API v2         │   - never-500 contract (D-04)   │
                       │   - prewarm branch returns 204  │
                       │   - UNKNOWN-sentinel → 404      │
                       │   - boto3 read_timeout=25s      │
                       └────────────┬────────────────────┘
                                    │ bedrock-agentcore.invoke_agent_runtime
                                    ▼
                       ┌─────────────────────────────────┐
                       │   AgentCore Runtime (Strands)   │
                       │   ARM64 Python 3.12 container   │
                       │                                 │
                       │   invoke() dispatcher           │
                       │   ├── follow_up → draft_email   │
                       │   ├── chat      → handle_chat   │
                       │   └── recommend (default)       │
                       │       ├── hardship guard (code) │
                       │       ├── TariffSpecialist      │
                       │       │   └── Strands Agent     │
                       │       │       (Claude Sonnet    │
                       │       │        4.6 pinned)      │
                       │       │       + 9 @tool fns     │
                       │       │       + FourToolCapHook │
                       │       │   → Pydantic validators │
                       │       │   → fallback bank       │
                       │       └── ComplianceReviewer    │
                       └────────┬────────────────────────┘
                                │ boto3 lambda.invoke
                                ▼
                       ┌─────────────────────────────────┐
                       │   Tools Lambda (lambda/)        │
                       │   simulate_savings_pure() ◄─── SAV-03 boundary
                       │   detect_bill_shock_pure()      │
                       │   get_hardship_flag_pure()      │
                       └────────┬────────────────────────┘
                                │ boto3 dynamodb
                                ▼
                       ┌─────────────────────────────────┐
                       │   DynamoDB (tariff-billing)     │
                       │   PROFILE rows + monthly        │
                       │   billing rows per customer     │
                       └─────────────────────────────────┘
```

**Talking points off the diagram:**

- **Cross-stack wiring is SSM, not CloudFormation Exports.** Exports lock — once another stack imports an export, you can't change it. SSM is read-by-value at deploy time. `infrastructure/foundation_stack.py` writes the Tools Lambda ARN to SSM; `agentcore_stack.py` reads it back. Each of the three stacks (Foundation, Agent, API) can be redeployed independently.
- **The four CDK stacks deploy in dependency order:** `CustomerTariff` (DynamoDB + Tools Lambda + seeder), `CustomerTariffAgent` (AgentCore Runtime + Memory + container build), `CustomerTariffApi` (API Gateway + API Lambda), `CustomerTariffFrontend` (Amplify Hosting). Frontend is fully independent of the other three — the UI can be redeployed without touching any backend.
- **Region is hardcoded.** `app.py` overrides any local profile default to `us-east-1`. AgentCore Agent Registry is not available in `ap-southeast-2`, so this is a real constraint, not a stylistic choice.

---

## 4. The bi-mode imports — 60-second sidebar

This is going to come up. Be ready for it.

**Open `agent/agent.py` lines 23–53** alongside `agent/Dockerfile`.

> "Look at this `try/except ImportError` at the top. Two import paths for the same package. Why?
>
> The Dockerfile copies `narrative/` to `/app/narrative/` — a top-level package in the container. So inside the runtime, `from narrative.fallbacks import FALLBACKS` is correct. But in the repo, `narrative/` lives under `agent/narrative/` — so for offline pytest, `from agent.narrative.fallbacks import FALLBACKS` is correct.
>
> Both are wrong-by-other-context. We try the container layout first because that's the hot path; the import failure on the repo side is silent and we fall back. CLAUDE.md flags this with 'Don't simplify by removing one branch'. Several contributors have tried to.
>
> The cleaner fix is restructuring the package layout to be identical in both contexts, but that requires changing the Dockerfile, the test paths, and the import statements all atomically. We took the cheap fix in Phase 6 and never paid the cost back. Worth knowing if you fork this — your first refactor is probably this."

---

## 5. The freeze contract (operational hardening)

> "If you take one operational lesson from this codebase, take this. We have a thing called a 'demo freeze' — a tag and a CFN stack policy combination that locks the deployment so nothing changes between the freeze ceremony and the demo. Three components:"

1. **Annotated git tag** (`demo-v3.0`) pointing at a specific commit. Pushed to origin. The tag's annotation body names the freeze commit SHA — self-consistency check.
2. **CFN stack policies** with `Effect: Deny, Action: Update:*` on all three production stacks. Termination protection on top. To make any change, you have to lift the policy explicitly via `aws cloudformation set-stack-policy`. There's no slack-channel-stand-up that bypasses it.
3. **Hash-pinned Python deps.** `requirements.txt` and `requirements-dev.txt` are generated by `pip-compile` and installed with `pip install --require-hashes`. If anyone regenerates the lockfile and a transitive dependency drifts, fresh-clone install fails — the freeze contract is broken loudly, not silently.

> "We also did a 5-step rollback drill — full log at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/10-DRILL-LOG.md`. Take 10 minutes some afternoon and read it. The cheapest insurance you'll buy this quarter.
>
> *Caveat for full disclosure:* I checked stack policies during yesterday's dry run — they're currently absent on all three stacks. Termination protection is still on, so nothing can be deleted, but `Update:*` is allowed. We'd want to re-apply the deny policies before the next demo cycle. Calling that out because hiding operational debt from this audience is exactly the wrong move."

---

## 6. The testing strategy

```bash
pytest                         # ~200 offline tests by default — smoke marker excluded
pytest -m "not smoke"          # explicit offline-only
pytest -m smoke                # live AWS smoke tests (requires deployed stack)
pytest tests/test_simulate_savings.py::test_byte_exact_marcus  # one test
```

**Three tiers:**

| Tier | Marker | Where | Speed |
|---|---|---|---|
| Unit / pure-fn | (no marker) | `test_simulate_savings.py`, `test_narrative_validator.py` | Milliseconds |
| Construction / synth | (no marker) | `test_agent_construction.py`, `test_cdk_synth.py` | Seconds |
| Live smoke | `smoke` | `test_narrative_eval_live.py`, `test_backend_api_smoke.py` | Slow (real AWS) |

> "The pure-function tests are the load-bearing tier. They lock SAV-03 — every persona's expected dollars at the float level. The validator tests lock the rejection order. The construction tests lock that you can build an `Agent(...)` with the real `BedrockModel` shape (catches the 'Strands removed `max_iterations`' class of breakage). The smoke tier exercises the live stack and is opt-in.
>
> The cross-persona canary (`test_bill_shock_flow.py::TestCrossPersonaCanary`) is worth a special call-out. It verifies that **two different personas produce different reasoning traces**. Why? Because the cheapest way for the model to fabricate is to copy the previous response. If Marcus and Elena both came back with identical traces, that's the fabrication signature. Locked by code."

---

## 7. What's in source but not deployed (the 'next deployment' set)

This is actually useful for this audience — they want to know what they're inheriting.

> "Yesterday's CEO demo ran on the v3.0 freeze. Source has gone further — there's about 26k lines of code in two post-freeze commits implementing seven additional phases that we deliberately did not deploy ahead of the CEO demo. They are:

| Source-only feature | Spec | Why deferred |
|---|---|---|
| Multi-agent supervisor (Phase 18) | `.kiro/specs/multi-agent-supervisor/` | `compliance_review` + `supervisor_trace` need another live evaluation pass |
| Streaming SSE reasoning trace (Phase 19) | `.kiro/specs/streaming-reasoning-trace/` | Needs Lambda Function URL deploy + UI bundle rebuild |
| Expanded tool gallery (Phase 20) | `.kiro/specs/expanded-tool-gallery/` | New tools' seed data needs DynamoDB extension |
| Conversational chat layer (Phase 21) | `.kiro/specs/conversational-chat-layer/` | Chat session store + rate limit need infrastructure decisions |
| Agentic actions portfolio (Phase 22) | `.kiro/specs/agentic-actions-portfolio/` | Action queue table + 24h TTL + confirm/dismiss endpoints |
| Typed hardship categories (Phase 16 AGENT-03) | `.kiro/specs/typed-hardship-categories/` | DynamoDB seed needs CUST-007/008/009/010 PROFILE rows |

> "Each Kiro spec has `requirements.md`, `design.md`, and `tasks.md`. They're already designed and partially built — what's needed is a deployment phase, not a build phase. Reference architecture for the deployment cycle is in `.planning/docs/presenter/DEFERRED-ROADMAP.md` — that's the doc to start from."

---

## 8. Anticipated questions — answers ready

**Q: Why Strands and not LangGraph / AutoGen / CrewAI / OpenAI Assistants?**
> "Strands is AWS's first-party SDK for Bedrock AgentCore. The deployment story is the simplest of the agent SDKs we evaluated — write the agent as a Python class, point a Dockerfile at it, deploy via CDK as an AgentCore Runtime. The structured-output integration via Pydantic is also tighter than the alternatives at the time. For a non-AWS shop, we'd evaluate differently — LangGraph in particular has gotten very mature."

**Q: Why pin the model literal? What about model upgrades?**
> "Pinning is the freeze contract for AI behaviour. Phase 06.1 caught a Sonnet 4.6 tool-use regression that broke our byte-exact-savings tests — the *only* way we caught it was that the model literal forced an explicit upgrade phase rather than silent drift. CLAUDE.md D-22 says any minor or major bump of `strands-agents` requires a dedicated decimal phase, including re-running the cross-persona canary. Pinning makes upgrade a deliberate event."

**Q: How do you debug an agent that's misbehaving in production?**
> "Three observability surfaces, in order of usefulness:
> 1. The `_narrative_source` marker — internal field stripped by the API Lambda but logged before stripping. Tells us per-invocation whether the narrative came from the model or the fallback bank. Log query: `narrative_source.usage_narrative == 'fallback'` rate over time = is the validator firing more than usual?
> 2. The `reasoning_trace` field — public surface; tells us the tool-call sequence and what each tool returned. CLAUDE.md D-11 exempts it from the digit/currency validator on purpose because *that's its value* — the rep sees the numbers the agent grounded on.
> 3. CloudWatch invocation counter on the Tools Lambda. If we see <1s response on a multi-tool turn AND zero Tools Lambda invocations, the model is fabricating. That signal triggers the freeze backup restore."

**Q: What about prompt injection? The customer-id is user input.**
> "The customer-id never reaches the model verbatim. It's regex-validated at the API edge (`_CUSTOMER_ID_PATTERN`) — `CUST-` followed by 3-6 digits. That's the only string from outside that the agent sees. The actual conversation context — billing data, hardship flag, plan catalogue — comes from inside the trust boundary via Tools Lambda invocations. The 'system prompt vs user prompt' distinction is preserved.
>
> The chat layer (Phase 21, source-only) is where prompt-injection becomes a real concern — that's why its `requirements.md` has a whole section on input validation, message length caps, HTML stripping, rate limiting, and a system-prompt instruction to decline role-play. Read that spec before deploying chat."

**Q: What happens when AgentCore Memory hits its TTL mid-call?**
> "Memory is short-term only — 12-hour TTL configured at `agentcore_stack.py:34`. The follow-up email path reads the prior recommendation from Memory; if Memory has expired or doesn't exist, the path returns a generic email body without the personalisation. That's by design — the never-500 contract takes precedence. The customer always gets a draft, possibly less personalised. CLAUDE.md frames this as 'D-04 takes precedence over compliance gating' — same pattern."

**Q: Why DynamoDB for billing records and not RDS?**
> "Three reasons. (1) Read pattern is point-lookup by customer_id — DynamoDB's native shape. (2) The seeder runs as a CDK custom resource at deploy time; DynamoDB's BatchWriteItem is straightforward whereas seeding RDS at CDK time is awkward. (3) For the production migration, the data lives in Salesforce or the existing CRM — DynamoDB is just the demo data layer. The Protocol seam at `providers.py` means the choice is reversible."

**Q: How does the prewarm work — what's the point of `?prewarm=1`?**
> "AgentCore microVMs go cold after about 15 minutes of idle. Cold start is ~17 seconds; warm is ~11. The prewarm branch in `api_lambda/handler.py:308` issues a real agent invocation (full hot path) and returns 204. The shell loop `scripts/demo-keepalive.sh` hits this every 10 minutes during the demo window. Note: warm latency is still 11 seconds on this configuration — we have a path to halve it with Provisioned Concurrency on the API Lambda alias, gated by the `-c demo_pc=N` CDK context flag."

**Q: How big is the test suite and how long does it take?**
> "200+ tests, ~30 seconds offline. The smoke tier (live AWS) is ~3 minutes including the AgentCore round-trip per test. Branching pattern: `pytest -m 'not smoke'` is what runs in pre-commit; smoke runs explicitly at T-eval before the demo and is the gate that decides go / no-go. The narrative-validator live eval at `tests/test_narrative_eval_live.py` is the most paranoid test we own — 12 fields × 5 personas × 2 tracks × 2 field-types = 240 individual assertions per run, all real model output."

**Q: What's the worst bug you've shipped on this codebase?**
> "Phase 11 seeder bug. We bumped DynamoDB seed from 36 rows to 73 rows. CDK's `AwsCustomResource` phys-id-change machinery should have re-fired the `batchWriteItem` with the new payload. It didn't. We ended up with 59 rows in production — half the personas had partial data. Caught by `aws dynamodb scan --select COUNT` in the post-deploy verification. Mitigation was a direct `batch-write-item` for the 14 missing rows. CLAUDE.md captures it under §7 Phase 11 amendment with the warning that any future re-seed past a 25-item chunk boundary is likely to re-trigger the bug. Lesson: trust your `--select COUNT`, not your CDK construct's docstring."

**Q: How would I extend this with a new tool?**
> "Five steps:
> 1. Add a `_pure(...)` function to `lambda/handler.py` — pure Python, no I/O, fully tested.
> 2. Add a `dispatcher` action to the Tools Lambda handler so it routes `{"action": "your_tool", ...}` payloads.
> 3. Add a `@tool` wrapper in `agent/agent.py` that calls the production Tools Lambda over the Provider seam (or directly via boto3 if the data isn't in DynamoDB).
> 4. Add the tool to the `tools=[...]` list in the `Agent(...)` construction.
> 5. Add an entry to the system prompt's tool preference order, OR don't — the model can use a tool that's available without prompt mention.
>
> Adding to the prompt's tool list is the difference between 'recommended' and 'available'. The 9 deployed tools are all `@tool`-decorated; only 4 are in the prompt's preference order. That's the kind of decision you make per-tool."

**Q: How do you know the AI is actually using your tools and not making up answers?**
> "Three witnesses, all in `tests/test_narrative_eval_live.py`:
> 1. **Latency floor** — sub-1s response on a multi-tool turn is impossible if the agent actually called a Lambda tool. If we see <1s, fabrication signature.
> 2. **CloudWatch invocation counter** on the Tools Lambda. Zero invocations in window = LLM skipped tools.
> 3. **Cross-persona canary** — Marcus and Elena's reasoning traces must differ. If they're identical, the model is just repeating cached output.
>
> Each is observable separately and fails loudly. We run all three on every smoke gate."

---

## 9. Closing 60 seconds

> "If you take one architectural pattern away from this: **separate the deterministic floor from the AI ceiling**. The thing the LLM is good at — composing one-sentence narratives that match a customer's tone — is what the LLM does. The thing computers are good at — arithmetic, regex validation, dispatcher routing — is what computers do. We don't ask the model to be reliable; we ask it to be expressive, and we wrap it in a stack that *makes* it reliable.
>
> If you take one operational pattern away: **freeze before you demo, drill before you freeze**. The 5-step rollback drill is in the repo; the cost of running it is one afternoon. The cost of skipping it is finding out at T-0 that your demo URL is dead.
>
> If you take one prompt-engineering pattern away: **the prompt is documentation for the model, not control flow**. The SAV-03 'never do arithmetic' clause is in the prompt because we want the model to understand the constraint. The actual enforcement is the deterministic engine sitting *outside* the prompt. The prompt is belt; the code is braces; the validator is the floor.
>
> Happy to take questions, walk through any file in detail, or pair on a 'how would I extend this' exercise."

---

## 10. Quick reference (have this open)

```
Repo:                 ~/Documents/Cevo/Customer-Tariff/
Freeze tag:           demo-v3.0 → 62c8adf
Live demo URL:        https://main.d1b6s4i8w2zlzo.amplifyapp.com
Backend API:          https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
AWS account/profile:  588738606436 / cevo-dev25
Region:               us-east-1 (hardcoded — do not "fix")
Bedrock model:        us.anthropic.claude-sonnet-4-6 (pinned at agent/agent.py:1337)
Strands SDK:          1.37.0 (pinned in requirements.txt; D-22 protects upgrades)
Python (runtime):     3.12 (container) / 3.13 (local — system 3.9 too old)
Tools deployed:       9 @tool functions in agent/agent.py
ToolCapHook budget:   8 calls per invocation (FourToolCapHook)
CDK stacks:           CustomerTariff · CustomerTariffAgent · CustomerTariffApi
                      · CustomerTariffFrontend (Amplify, independent)
Cross-stack wiring:   SSM parameters (NOT CFN exports — supports independent redeploy)
Dockerfile:           agent/Dockerfile · arm64 python:3.12-slim · /app workdir
Test count:           ~200 offline · 12 smoke (live AWS gate)
Test markers:         (none) = offline · smoke = live
Run all offline:      pytest -m "not smoke"
Run live smoke:       BACKEND_API_URL=... pytest -m smoke
Personas:             CUST-001 Sarah · 002 Marcus · 003 Elena · 004 Solar · 005 EV · 006 Hardship
                      007/008/009/010 are spec'd but not seeded (Phase 16 AGENT-03 not deployed)
Kill switch URL:      https://main.d1b6s4i8w2zlzo.amplifyapp.com?narrative=off
                      (UI-side — collapses LLM-touched fields, preserves dollars)
Freeze policies:      infrastructure/stack-policies/*.json (NB: not currently applied — see §5)
DynamoDB backup:      arn:aws:dynamodb:...:backup/01777859824019-989beacf (AVAILABLE)
Pitfalls index:       CLAUDE.md "Things to know before changing things"
Trust patterns:       .planning/docs/presenter/TRUST-ARCHITECTURE.md
Roadmap:              .planning/docs/presenter/DEFERRED-ROADMAP.md
```
