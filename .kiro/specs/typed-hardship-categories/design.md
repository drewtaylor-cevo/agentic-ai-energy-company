# Design: Typed Hardship Categories (AGENT-03)

## Overview

Extends the existing binary hardship gate (`hardship_flag: bool`) into a typed category system with four categories, each driving distinct call scripts, tool permissions, routing targets, and compliance checks. The design preserves the code-side-only principle (no LLM turn on the hardship path) and all existing invariants.

## Architecture

### Data Flow

```
invoke(payload)
  │
  ├─ get_hardship_flag(customer_id)
  │     └─ Returns: {hardship: bool, hardship_category: str | null, customer_id: str}
  │
  ├─ if hardship:
  │     category = hardship_category or "other"  (AC 1.2 backward compat)
  │     └─ HardshipSpecialist.handle(payload, category)
  │           ├─ Select category config (scripts, tools, routing_target)
  │           ├─ Execute permitted tools (if any for category)
  │           ├─ Build typed HardshipResponse
  │           └─ Return response
  │
  └─ ComplianceReviewer.review(response, context)
        ├─ Existing: hardship_no_tariff_data
        ├─ New: hardship_category_tool_restriction
        └─ New: family_violence_no_financial_content (if category == family_violence)
```

### Category Configuration Registry

A single `HARDSHIP_CATEGORIES` dict in a new module `agent/specialists/hardship_config.py` serves as the source of truth for all category-specific behaviour:

```python
from typing import Literal

HardshipCategory = Literal["payment_difficulty", "medical_equipment", "family_violence", "other"]

HARDSHIP_CATEGORIES: dict[HardshipCategory, dict] = {
    "payment_difficulty": {
        "routing_target": "hardship_team",
        "permitted_tools": frozenset({"propose_payment_plan", "get_billing_history", "schedule_callback"}),
        "permitted_actions": ["payment_plan", "billing_history", "schedule_callback"],
        "financial_terms_forbidden": False,
    },
    "medical_equipment": {
        "routing_target": "priority_services_team",
        "permitted_tools": frozenset({"schedule_callback", "lookup_concessions"}),
        "permitted_actions": ["concession_lookup", "schedule_callback"],
        "financial_terms_forbidden": False,
    },
    "family_violence": {
        "routing_target": "family_violence_team",
        "permitted_tools": frozenset({"schedule_callback"}),
        "permitted_actions": ["schedule_callback"],
        "financial_terms_forbidden": True,
    },
    "other": {
        "routing_target": "hardship_team",
        "permitted_tools": frozenset({"schedule_callback"}),
        "permitted_actions": ["schedule_callback"],
        "financial_terms_forbidden": False,
    },
}
```

### Component Changes

#### 1. `lambda/handler.py` — `get_hardship_flag_pure`

Add `hardship_category` to the return dict. Read from the PROFILE row's `hardship_category` attribute (DynamoDB sparse attribute — absent means `null`).

```python
def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    _validate_customer_id(customer_id)
    response = table_client.get_item(Key={"customer_id": customer_id, "month": "PROFILE"})
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "hardship_category": None, "customer_id": customer_id}
    return {
        "hardship": bool(item.get("hardship_flag", False)),
        "hardship_category": item.get("hardship_category"),  # None if absent
        "customer_id": customer_id,
    }
```

#### 2. `agent/agent.py` — `HardshipResponse` schema

Add `category` and `permitted_actions` fields:

```python
class HardshipResponse(BaseModel):
    kind: str = Field(default="hardship")
    customer_id: str
    category: Literal["payment_difficulty", "medical_equipment", "family_violence", "other"]
    reason: str = Field(max_length=USAGE_NARRATIVE_MAX_CHARS)
    routing_target: str
    call_script: str = Field(max_length=CALL_SCRIPT_MAX_CHARS)
    permitted_actions: list[str] = Field(default_factory=list)

    # Existing D-15 validators unchanged
```

#### 3. `agent/specialists/hardship.py` — `HardshipSpecialist`

Refactored to accept category and use the config registry:

```python
class HardshipSpecialist:
    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = payload["customer_id"]
        category = payload.get("hardship_category") or "other"  # AC 1.2

        config = HARDSHIP_CATEGORIES[category]
        body = _build_typed_hardship_response(customer_id, category, config)
        body["_narrative_source"] = {
            "hardship": {"reason": "fallback", "call_script": "fallback", "category": category},
        }
        return body
```

#### 4. `agent/specialists/compliance.py` — New rules

Two new check methods added to `ComplianceReviewer`:

```python
def _check_hardship_tool_restriction(self, response: dict) -> ComplianceCheckResult:
    """Verify reasoning_trace tools are within category's permitted set."""
    category = response.get("category", "other")
    config = HARDSHIP_CATEGORIES.get(category, HARDSHIP_CATEGORIES["other"])
    permitted = config["permitted_tools"]
    # ... check reasoning_trace entries against permitted set

def _check_family_violence_no_financial(self, response: dict) -> ComplianceCheckResult:
    """Verify family_violence responses contain no financial terminology."""
    # ... check reason, call_script, permitted_actions against FINANCIAL_TERMS
```

#### 5. `agent/narrative/fallbacks.py` — Category-keyed scripts

New hardship entries keyed by category within each hardship persona:

```python
"CUST-007": {
    "hardship": {
        "payment_difficulty": {
            "reason": "This customer is receiving dedicated support for managing their energy account.",
            "call_script": "I can see you have support in place — let me discuss flexible options that work for you.",
        },
        "medical_equipment": { ... },
        "family_violence": { ... },
        "other": { ... },
    },
}
```

#### 6. `infrastructure/seed_data/billing_records.py` — New personas

Four new hardship personas (one per category):

| Customer ID | Category | Demo Purpose |
|---|---|---|
| CUST-007 | `payment_difficulty` | Payment plan flow |
| CUST-008 | `medical_equipment` | Priority services routing |
| CUST-009 | `family_violence` | Safety-first isolation |
| CUST-010 | `other` | Generic (backward compat proof) |

Each has 12 months of billing records + a PROFILE row with `hardship_flag: true` and `hardship_category` set.

#### 7. `invoke()` routing change

Minimal change — pass `hardship_category` through to the specialist:

```python
if hardship:
    payload["hardship_category"] = hardship_result.get("hardship_category")
    response = _hardship_specialist.handle(payload)
```

### Invariant Preservation

| Invariant | Impact | Mitigation |
|---|---|---|
| SAV-03 | None — hardship path has no savings | No change |
| REC-03 | None — hardship path returns no tracks | No change |
| D-15 | Extended — new scripts must pass validators | All scripts pre-validated at import time |
| D-04 | Preserved — category detection wrapped in try/except, falls back to "other" | Same pattern as existing hardship_flag check |
| D-11 | None — no reasoning_trace summaries on hardship path | No change |
| Bi-mode imports | New module follows same try/except pattern | `hardship_config.py` uses no external deps |

### Error Handling

- `hardship_category` field missing from DynamoDB → default to `"other"` (AC 1.2, AC 6.2)
- `hardship_category` contains unexpected value → default to `"other"` (D-04)
- Tool invocation fails within hardship path → D-04 fallback (existing pattern)
- Compliance check raises → swallowed by existing `except Exception` in `invoke()` (D-04)

## File Changes Summary

| File | Change Type | Description |
|---|---|---|
| `agent/specialists/hardship_config.py` | **New** | Category registry (types, tool sets, routing targets) |
| `agent/specialists/hardship.py` | Modify | Accept category, use config registry, build typed response |
| `agent/agent.py` | Modify | `HardshipResponse` schema + `_build_hardship_response` → `_build_typed_hardship_response` |
| `agent/narrative/fallbacks.py` | Modify | Add category-keyed hardship scripts for new personas |
| `lambda/handler.py` | Modify | `get_hardship_flag_pure` returns `hardship_category` |
| `agent/specialists/compliance.py` | Modify | Two new compliance rules |
| `infrastructure/seed_data/billing_records.py` | Modify | Four new hardship personas (CUST-007 through CUST-010) |
| `infrastructure/foundation_stack.py` | Modify | Seed new personas into DynamoDB |
| `tests/test_hardship_categories.py` | **New** | Unit + property-based tests for all correctness properties |
