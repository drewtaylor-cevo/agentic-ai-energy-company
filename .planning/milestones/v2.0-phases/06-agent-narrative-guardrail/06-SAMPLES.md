# Phase 6 Live-Smoke Samples

Captured against `AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V` in `us-east-1`.

One live `invoke_agent_runtime` per persona. The `_narrative_source` marker is visible here because this capture bypasses the Phase 7 API Lambda (which strips it).

## CUST-001

```json
{
  "green": {
    "plan_id": "ECO",
    "plan_name": "EcoFlex 100",
    "saving_monthly": 30.0,
    "saving_annual": 360.0,
    "usage_narrative": "Heavy cool-season household with consistent year-round load across the family.",
    "call_script": "Ask about EcoFlex — an eco-aligned pick for a winter-heavy family home."
  },
  "cheapest": {
    "plan_id": "VAL",
    "plan_name": "Value 12",
    "saving_monthly": 55.0,
    "saving_annual": 660.0,
    "usage_narrative": "High-use winter-heavy household with strong year-round energy demand.",
    "call_script": "Bring up Value Twelve — a cost-led fit for a high-use winter-heavy home."
  },
  "_narrative_source": {
    "green": {
      "usage_narrative": "model",
      "call_script": "model"
    },
    "cheapest": {
      "usage_narrative": "model",
      "call_script": "model"
    }
  }
}
```

## CUST-002

```json
{
  "green": {
    "plan_id": "ECO",
    "plan_name": "EcoFlex 100",
    "saving_monthly": 16.9,
    "saving_annual": 202.8,
    "usage_narrative": "Mid-range household with steady consumption and an eco-aligned energy profile.",
    "call_script": "Ask about EcoFlex — an eco-aligned plan suited to a consistent mid-range household."
  },
  "cheapest": {
    "plan_id": "VAL",
    "plan_name": "Value 12",
    "saving_monthly": 30.98,
    "saving_annual": 371.76,
    "usage_narrative": "Cost-conscious mid-range household with even usage across warm and cool months.",
    "call_script": "Bring up Value Twelve — a cost-led fit for a steady, even-usage household."
  },
  "_narrative_source": {
    "green": {
      "usage_narrative": "model",
      "call_script": "model"
    },
    "cheapest": {
      "usage_narrative": "model",
      "call_script": "model"
    }
  }
}
```

## CUST-003

```json
{
  "green": {
    "plan_id": "ECO",
    "plan_name": "EcoFlex 100",
    "saving_monthly": 14.0,
    "saving_annual": 168.0,
    "usage_narrative": "Summer-peak household profile driven by warm-month cooling demand.",
    "call_script": "Ask about EcoFlex — an eco-aligned pick for a warm-season cooling pattern."
  },
  "cheapest": {
    "plan_id": "VAL",
    "plan_name": "Value 12",
    "saving_monthly": 25.67,
    "saving_annual": 308.04,
    "usage_narrative": "Cost-conscious summer-peak household with warm-month demand driving higher consumption.",
    "call_script": "Bring up Value Twelve — a cost-led fit for a warm-season, budget-focused home."
  },
  "_narrative_source": {
    "green": {
      "usage_narrative": "model",
      "call_script": "model"
    },
    "cheapest": {
      "usage_narrative": "model",
      "call_script": "model"
    }
  }
}
```

