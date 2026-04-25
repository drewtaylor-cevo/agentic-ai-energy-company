#!/usr/bin/env python3
"""Phase 6 sample capture — one-shot live dump to 06-SAMPLES.md.

Runs each persona through the deployed AgentCore runtime and writes the
response body into a Markdown file with one fenced JSON block per persona.
Committed artefact for design review.

Usage:
    AWS_DEFAULT_REGION=us-east-1 \\
    AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:... \\
    python3 scripts/capture_samples.py
"""
import json
import os
import sys
import uuid
from pathlib import Path


def main() -> int:
    arn = os.environ.get("AGENT_RUNTIME_ARN")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    if not arn:
        print("AGENT_RUNTIME_ARN not set", file=sys.stderr)
        return 2

    import boto3  # lazy — this script is AWS-only

    client = boto3.client("bedrock-agentcore", region_name=region)
    repo_root = Path(__file__).resolve().parent.parent
    out = repo_root / ".planning" / "phases" / "06-agent-narrative-guardrail" / "06-SAMPLES.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    personas = ["CUST-001", "CUST-002", "CUST-003"]
    with out.open("w") as f:
        f.write("# Phase 6 Live-Smoke Samples\n\n")
        f.write(f"Captured against `AGENT_RUNTIME_ARN={arn}` in `{region}`.\n\n")
        f.write("One live `invoke_agent_runtime` per persona. "
                "The `_narrative_source` marker is visible here because this capture "
                "bypasses the Phase 7 API Lambda (which strips it).\n\n")

        for cust in personas:
            print(f"Invoking {cust} ...", file=sys.stderr)
            resp = client.invoke_agent_runtime(
                agentRuntimeArn=arn,
                runtimeSessionId=str(uuid.uuid4()),
                payload=json.dumps({"customer_id": cust}).encode(),
            )
            body = json.loads(resp["response"].read())
            f.write(f"## {cust}\n\n")
            f.write("```json\n")
            f.write(json.dumps(body, indent=2, ensure_ascii=False))
            f.write("\n```\n\n")
    print(f"Wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
