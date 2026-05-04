# Deferred Roadmap — Architecture with Stubs

> **Audience:** Presenter, technical reviewer, product stakeholder.
> **Purpose:** Show what is built, what is stubbed, and what comes next — framed as an architecture that was designed for extension, not a prototype that needs rewriting.

---

## Current State: v3.0 (Agentic Depth & Workflow Assist)

The v3.0 demo surface includes:

| Capability | Status | Key Files |
|-----------|--------|-----------|
| Deterministic savings engine (5 personas, 6 tariff archetypes) | **Live** | `lambda/handler.py::simulate_savings_pure` |
| LLM narrative with dual-gate validation | **Live** | `agent/narrative/validators.py`, `agent/narrative/banned_terms.py` |
| Multi-tool reasoning trace (bill-shock detection) | **Live** | `agent/agent.py`, `agent/reasoning/summaries.py` |
| Hardship short-circuit (code-side pre-LLM guard) | **Live** | `agent/agent.py::invoke()` → `_build_hardship_response()` |
| Follow-up email draft via AgentCore Memory | **Live** | `agent/memory/config.py`, API route at `/recommendations/{id}/follow-up` |
| CustomerDataProvider Protocol (3-method interface) | **Live** | `agent/providers.py::CustomerDataProvider` |
| DynamoDB implementation of the Protocol | **Live** | `agent/providers.py::ToolsLambdaProvider` |
| InMemory test double | **Live** | `agent/providers.py::InMemoryProvider` |
| Salesforce CRM adapter | **Stub** | `agent/providers.py::SalesforceCustomerDataProvider` |

---

## The Production-Shaped Seam: CustomerDataProvider

The `CustomerDataProvider` Protocol ([`agent/providers.py`](../../../agent/providers.py)) is the architectural seam between the agent and its data source. It defines exactly three methods:

```python
@runtime_checkable
class CustomerDataProvider(Protocol):
    def get_customer(self, customer_id: str) -> dict[str, Any]: ...
    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]: ...
    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]: ...
```

### What is deliberately excluded (LD-5)
- `simulate_savings` — arithmetic stays in the Tools Lambda by design (SAV-03). The Protocol wraps data access, not computation.
- `get_tariff_catalog` — the tariff catalog is a static asset bundled with the Lambda, not a per-customer data fetch.
- Consent flags (`consent_marketing`, `consent_data_share`) — deferred to PROD-03.
- Audit trail (who accessed what when) — deferred to PROD-04.
- Circuit breaker for downstream CRM failures — deferred to PROD-05.

### Three implementations today

**1. ToolsLambdaProvider (production)**
Each method issues a `boto3 lambda.invoke` with an `{action, customer_id}` payload to the Tools Lambda. The Lambda reads from DynamoDB. This is the live path in the deployed AgentCore container.

**2. InMemoryProvider (test double)**
Seeds from the same `infrastructure/seed_data/billing_records.py` that feeds the live DynamoDB seeder. Used by all offline pytest tests — no AWS credentials needed, no network calls, sub-millisecond per assertion.

**3. SalesforceCustomerDataProvider (presenter stub)**
Every method raises `NotImplementedError`:

```python
class SalesforceCustomerDataProvider:
    """Presenter stub — DOC-03 artefact.

    Demonstrates the Protocol's extension point for a real CRM integration.
    All three methods raise NotImplementedError with a breadcrumb to the
    deferred-roadmap document.
    """
    def get_customer(self, customer_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Salesforce integration is a v3.1+ deliverable. "
            "See .planning/docs/presenter/DEFERRED-ROADMAP.md"
        )
    # ... (same pattern for get_billing_history, get_hardship_flag)
```

This stub is not dead code — it is a **committed architectural signal** that the system was designed for CRM integration from the start. The Protocol is runtime-checkable: `isinstance(SalesforceCustomerDataProvider(), CustomerDataProvider)` returns `True` in offline tests, confirming the stub satisfies the interface contract.

---

## What Comes Next

### Near-Term: v3.1 — CRM Integration + Customer Portal

| Requirement | Description | Depends On | Complexity |
|-------------|-------------|------------|------------|
| **PROD-02** | Customer-facing self-service portal | OIDC/MFA auth layer (new), responsive layout (375–428px) | High — authentication is the load-bearing new work |
| **PROD-03** | Consent flags on CustomerDataProvider | PROD-02 (portal needs consent before showing data) | Medium |
| **PROD-04** | Audit trail (who accessed what when) | PROD-01 (Protocol extension) | Medium |
| **PROD-05** | Circuit breaker for downstream CRM failures | Salesforce adapter (real impl) | Medium |

**The Salesforce adapter path:**
1. Replace `NotImplementedError` with real Salesforce API calls (SOQL queries for customer, billing, hardship flag)
2. The Protocol's 3-method shape means the agent code does not change — only the provider implementation swaps
3. `set_provider()` at startup selects DynamoDB or Salesforce based on environment configuration
4. The InMemory test double continues to serve offline tests — no Salesforce sandbox needed for CI

### Medium-Term: Workflow Depth

| Requirement | Description | Status |
|-------------|-------------|--------|
| **WF-02** | Long-term / cross-session Memory | Deferred — v3.0 uses same-day short-term only |
| **WF-03** | Multi-rep handoff Memory | Deferred — v3.0 is single-rep |
| **AGENT-03** | Typed hardship categories (payment_difficulty, medical, family_violence) | Deferred — v3.0 uses monolithic `hardship_flag: bool` |
| **AGENT-04** | Proactive agent actions (auto-send email, tariff-switch prep) | Deferred — v3.0 remains rep-confirmed |

### Longer-Term: Channel Expansion

The same deterministic savings engine + validated narrative can drive three distinct customer-experience surfaces (see DEMO-RUNBOOK §13):

1. **Softphone / agent-assist** (this demo) — built, frozen, drilled
2. **Customer portal tile / mobile** — mockup at `demo/mockups/portal-tile.html`; requires OIDC + MFA + session scoping
3. **Proactive email nudge** — mockup at `demo/mockups/email-nudge.html`; requires batch scheduler + opt-in + material-delta filter

---

## Architecture Decisions That Enable Extension

| Decision | What It Enables | Where It Lives |
|----------|----------------|----------------|
| Protocol-based data access (PROD-01) | Swap DynamoDB for Salesforce without touching agent code | `agent/providers.py` |
| Discriminated union response (`kind: recommendation \| hardship`) | Add new response types (e.g., `kind: "pending_review"`) without breaking existing clients | `agent/agent.py::RecommendationResponse`, `HardshipResponse` |
| Deterministic savings in Tools Lambda (SAV-03) | New tariff archetypes (solar, EV, TOU) added without LLM changes | `lambda/handler.py::simulate_savings_pure` |
| Banned-terms regex (D-15) | New competitors or regulatory terms added to a single list | `agent/narrative/banned_terms.py` |
| `?narrative=off` kill switch (LD-7) | Emergency collapse of any LLM surface without redeploy | `ui/src/lib/flags.ts` |
| AgentCore Memory with actor + session scoping | Cross-session workflows (WF-02) add retention strategies, not new isolation primitives | `agent/memory/config.py` |

---

## The Presenter's One-Liner

> "The demo runs on DynamoDB today. The Salesforce adapter is a committed stub — same Protocol, same tests, same agent code. Swapping the data source is a provider implementation, not a rewrite. That is the architecture claim."

---

*Document: DOC-03 (REQUIREMENTS.md). Committed as part of Phase 16 (Presenter Artefacts + Operational Consolidation).*
*References: `agent/providers.py::SalesforceCustomerDataProvider` (Phase 12 PROD-01c), REQUIREMENTS.md §Deferred to v3.1 or later.*
