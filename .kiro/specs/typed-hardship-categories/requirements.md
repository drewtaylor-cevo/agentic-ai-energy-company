# Requirements: Typed Hardship Categories (AGENT-03)

## Introduction

The current hardship handling is a binary gate: `hardship_flag: bool` on the customer PROFILE row routes to a monolithic `HardshipSpecialist` that returns a single dignity-preserving response regardless of the hardship type. This is insufficient for a regulated energy retailer — the AER National Energy Customer Framework (NECF) imposes materially different obligations depending on the nature of the customer's hardship. A customer experiencing family violence requires immediate safety-first routing and must never be asked about payment arrangements; a customer on life-support medical equipment requires priority reconnection guarantees; a customer in payment difficulty needs a tailored payment plan proposal.

This feature replaces the monolithic hardship path with a typed triage system that categorises hardship into `payment_difficulty`, `medical_equipment`, `family_violence`, and `other`, then selects category-specific call scripts, tool invocations, and compliance checks. The agent remains code-side (no LLM turn on the hardship path) — category detection is deterministic from customer data, not inferred by the model.

## Glossary

- **Hardship_Category**: One of four typed categories: `payment_difficulty`, `medical_equipment`, `family_violence`, `other`. Stored on the customer PROFILE row in DynamoDB.
- **AER_NECF**: Australian Energy Regulator National Energy Customer Framework — the regulatory framework governing energy retail customer protections. Referenced as an architectural alignment target, not a legal compliance claim.
- **Category_Script**: A category-specific `call_script` string the rep reads verbatim. Each category has distinct language, tone, and permitted/forbidden content.
- **Category_Tool_Set**: The subset of agent tools available for a given hardship category. E.g. `payment_difficulty` may invoke `propose_payment_plan`; `family_violence` must NOT invoke any billing tools.
- **Dignity_Preserving**: Language that avoids blame, financial detail, or pressure — particularly critical for `family_violence` and `medical_equipment` categories.
- **Safety_First_Routing**: For `family_violence` — immediate transfer to a specialist team with no billing discussion, no account review, no payment mention.

## Requirements

### Requirement 1: Hardship Category Data Model

**User Story:** As a system administrator, I want hardship categories stored as typed enum values on customer profiles so that routing decisions are deterministic and auditable.

**Acceptance Criteria:**
- AC 1.1: The DynamoDB PROFILE row supports a `hardship_category` field with allowed values: `payment_difficulty`, `medical_equipment`, `family_violence`, `other`, or `null` (no hardship).
- AC 1.2: The existing `hardship_flag: bool` field is preserved for backward compatibility — `hardship_flag: true` with `hardship_category: null` defaults to category `other`.
- AC 1.3: The `get_hardship_flag` tool (Lambda pure helper) returns both `hardship: bool` and `hardship_category: str | null` in its response dict.
- AC 1.4: Seed data includes at least one persona per category for demo coverage.

### Requirement 2: Category-Specific Call Scripts

**User Story:** As a call-centre representative, I want the system to provide me with a call script tailored to the customer's specific hardship type so that I respond appropriately to their situation.

**Acceptance Criteria:**
- AC 2.1: Each hardship category has a distinct `call_script` that passes D-15 validation (no digits, currency, %, switch verbs, competitor names, environmental superlatives; ≤22 words).
- AC 2.2: The `family_violence` script contains ONLY safety-first language — no reference to accounts, billing, plans, or payments.
- AC 2.3: The `medical_equipment` script references priority service guarantees without disclosing specific plan details.
- AC 2.4: The `payment_difficulty` script acknowledges difficulty and offers to discuss flexible arrangements without quoting figures.
- AC 2.5: The `other` script is the current generic hardship script (backward compatible).
- AC 2.6: All scripts are code-composed (not LLM-generated) and stored in `agent/narrative/fallbacks.py` keyed by category.

### Requirement 3: Category-Specific Tool Selection

**User Story:** As a system architect, I want tool availability to be restricted by hardship category so that sensitive categories never trigger inappropriate tool calls.

**Acceptance Criteria:**
- AC 3.1: `family_violence` category MUST NOT invoke any billing, payment, or tariff tools (`simulate_savings`, `propose_payment_plan`, `get_billing_history`, `detect_bill_shock`, `decompose_bill_shock`, `lookup_concessions`, `estimate_solar_payback`). Only `schedule_callback` is permitted.
- AC 3.2: `medical_equipment` category may invoke `schedule_callback` and `lookup_concessions` (life-support concession lookup). No tariff comparison tools.
- AC 3.3: `payment_difficulty` category may invoke `propose_payment_plan`, `get_billing_history`, and `schedule_callback`. No tariff switching tools.
- AC 3.4: `other` category uses the current generic hardship path (no tariff tools, `schedule_callback` only).
- AC 3.5: Tool restriction is enforced code-side in the `HardshipSpecialist`, not via prompt engineering.

### Requirement 4: Typed HardshipResponse Schema

**User Story:** As a frontend developer, I want the API response to include the hardship category so that the UI can render category-appropriate messaging and routing indicators.

**Acceptance Criteria:**
- AC 4.1: `HardshipResponse` Pydantic model gains a `category` field typed as a `Literal["payment_difficulty", "medical_equipment", "family_violence", "other"]`.
- AC 4.2: The `routing_target` field becomes category-dependent: `family_violence` → `"family_violence_team"`, `medical_equipment` → `"priority_services_team"`, `payment_difficulty` → `"hardship_team"`, `other` → `"hardship_team"`.
- AC 4.3: The `reason` field remains dignity-preserving and category-appropriate (different wording per category), validated by D-15.
- AC 4.4: The response includes a `permitted_actions` list indicating what the rep may discuss (e.g. `["schedule_callback"]` for family_violence, `["payment_plan", "schedule_callback"]` for payment_difficulty).

### Requirement 5: Compliance Reviewer Extension

**User Story:** As a compliance officer, I want the ComplianceReviewer to validate category-specific constraints so that regulatory obligations are enforced programmatically.

**Acceptance Criteria:**
- AC 5.1: New compliance rule `hardship_category_tool_restriction` (Req 4.4): verifies that no tool in `reasoning_trace` violates the category's permitted tool set.
- AC 5.2: New compliance rule `family_violence_no_financial_content` (Req 4.5): for `family_violence` responses, verifies that `reason`, `call_script`, and any `permitted_actions` contain zero financial terminology.
- AC 5.3: Existing rule `hardship_no_tariff_data` (Req 4.3) continues to apply to ALL hardship categories unchanged.
- AC 5.4: `ComplianceReview` response includes the new rules in `rules_checked` when the response kind is `hardship`.

### Requirement 6: Backward Compatibility & Invariant Preservation

**User Story:** As the demo operator, I want the typed hardship system to preserve all existing invariants so that the frozen demo paths remain unaffected.

**Acceptance Criteria:**
- AC 6.1: Existing personas (CUST-001 Sarah, CUST-002 Marcus, CUST-003 Elena) are NOT hardship-flagged and their recommendation paths are completely unchanged.
- AC 6.2: A customer with `hardship_flag: true` but no `hardship_category` field defaults to category `other` with the current generic response.
- AC 6.3: D-04 never-500 contract is preserved — any failure in category detection falls back to `other`.
- AC 6.4: `?narrative=off` kill-switch strips `compliance_review` and `supervisor_trace` from hardship responses identically to recommendation responses.
- AC 6.5: The `_narrative_source` marker is attached to hardship responses with category info and stripped by `api_lambda/handler.py` before client delivery.
- AC 6.6: SAV-03 is trivially preserved (hardship path has no savings arithmetic).

## Correctness Properties

The following properties must be validated via property-based testing:

- **CP-1 (Category Completeness):** For any valid `hardship_category` value, `_build_hardship_response` produces a valid `HardshipResponse` that passes Pydantic validation and D-15 content rules.
- **CP-2 (Tool Restriction Enforcement):** For any `family_violence` customer, no tool in the response's `reasoning_trace` is outside `{"schedule_callback"}`. For any `medical_equipment` customer, no tool is outside `{"schedule_callback", "lookup_concessions"}`.
- **CP-3 (Family Violence Financial Isolation):** For any `family_violence` response, the concatenation of `reason + call_script + str(permitted_actions)` contains zero tokens from the financial terminology set (dollar, payment, bill, tariff, plan, cost, price, save, switch, account, balance, debt, arrears, overdue).
- **CP-4 (Backward Compatibility):** For any customer with `hardship_flag: true` and `hardship_category: null`, the response is byte-identical to the current `_build_hardship_response` output for that customer_id.
- **CP-5 (Routing Target Determinism):** `routing_target` is a pure function of `hardship_category` — same category always produces same routing target, regardless of customer_id or other payload fields.

## Non-Functional Requirements

- **NFR-1 (Latency):** Category triage adds zero LLM calls. The hardship path remains code-side only. Total added latency ≤ 5ms (one additional DynamoDB attribute read, already fetched in the existing `get_hardship_flag` call).
- **NFR-2 (Testability):** All category logic is pure-function testable via the existing `get_hardship_flag_pure` pattern (injectable table_client, no network I/O in tests).
- **NFR-3 (Extensibility):** Adding a new category requires: (1) add to the Literal type, (2) add a script in fallbacks, (3) add a tool-set entry, (4) add a compliance rule. No changes to the routing logic or Supervisor.
