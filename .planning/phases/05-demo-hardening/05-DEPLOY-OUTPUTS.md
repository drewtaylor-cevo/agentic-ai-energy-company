---
phase: 05-demo-hardening
artifact: deploy-outputs
captured_at: 2026-04-25T22:15:32Z
git_sha: 1ac43c1ea2504479d3c7658597674c1e787b5f77
region: us-east-1
account_last4: "6436"
---

# Phase 5 — Deployed Environment Record

**Captured:** 2026-04-25T22:15:32Z
**Git SHA:** `1ac43c1ea2504479d3c7658597674c1e787b5f77` (will be tagged `demo-v1.0` in Plan 07)
**Region:** us-east-1 (hardcoded in `app.py` line 19)
**AWS Account:** ending in `6436`

## CfnOutputs

| Stack | Output | Value |
|-------|--------|-------|
| CustomerTariff       | BillingTableName    | `tariff-billing` |
| CustomerTariff       | BillingTableArn     | `arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing` |
| CustomerTariff       | ToolsLambdaName     | `tariff-tools` |
| CustomerTariff       | ToolsLambdaArn      | `arn:aws:lambda:us-east-1:588738606436:function:tariff-tools` |
| CustomerTariffAgent  | AgentRuntimeArn     | `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V` |
| CustomerTariffAgent  | AgentRuntimeId      | `tariff_agent-O2Hai86N8V` |
| CustomerTariffApi    | ApiEndpoint         | `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/` |

## SSM Cross-Stack Parameter

| Parameter Name | Value |
|----------------|-------|
| `/customer-tariff/agent-runtime-arn` | `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V` |

## Tool Versions

| Tool    | Version                | Command                          |
|---------|------------------------|----------------------------------|
| CDK CLI | `2.1119.0 (build 820ac02)` | `npx aws-cdk@latest --version`   |
| Node    | `v24.12.0`             | `node --version`                 |
| Python  | `Python 3.9.6`         | `python3 --version`              |
| Docker  | `Docker version 29.2.1, build a5c7197d72` | `docker --version` |

## Reproducibility — Re-runnable capture commands

```bash
aws cloudformation describe-stacks --stack-name CustomerTariff      --region us-east-1 --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --stack-name CustomerTariffAgent --region us-east-1 --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --stack-name CustomerTariffApi   --region us-east-1 --query 'Stacks[0].Outputs'
aws ssm get-parameter --name /customer-tariff/agent-runtime-arn --region us-east-1
```

## Invariants (verified at capture time)

- [x] SSM `/customer-tariff/agent-runtime-arn` value EQUALS `CustomerTariffAgent.AgentRuntimeArn` CfnOutput
  - Both read: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`
- [x] `CustomerTariffApi.ApiEndpoint` starts with `https://` and contains `.execute-api.us-east-1.amazonaws.com`
  - Value: `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/`
- [x] `CustomerTariffAgent.AgentRuntimeArn` starts with `arn:aws:bedrock-agentcore:us-east-1:`
  - Value: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`
