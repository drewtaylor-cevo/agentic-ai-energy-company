# Deferred Items — Phase 06

Items discovered during execution that are out of scope for the current plan.

## Plan 06-02 (2026-04-25)

### Pre-existing environmental issue — CDK alpha module rename

- **Test:** `tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter`
- **Failure:** `ImportError: cannot import name 'aws_bedrock_agentcore_alpha' from 'aws_cdk'`
- **Root cause:** `infrastructure/constructs/agent_runtime.py:17` imports `aws_bedrock_agentcore_alpha` — this module was renamed (suggested replacement: `aws_bedrockagentcore`) in newer aws-cdk-lib releases.
- **Status:** Pre-existing — verified present on Plan 02 base commit (18071ce) BEFORE Plan 02 changes, and unchanged by Plan 02. Not caused by Plan 02 scope (narrative-validator + invoke() retry/fallback). Python `agent/agent.py` does not touch `infrastructure/constructs/agent_runtime.py`.
- **Disposition:** Out of scope for Plan 02. Observed only in this worktree's ephemeral python3.13 environment where aws-cdk-lib was freshly installed — the pinned demo-v1.0 `requirements.txt` pins cdk versions that still carry the alpha module. Real environment (`.venv` with pinned deps) does not exhibit this. A future Phase 6-03 container/deploy or a Phase 10 freeze revisit should either:
  1. Pin aws-cdk-lib in `requirements-dev.txt` to a version that carries `aws_bedrock_agentcore_alpha`, or
  2. Rename the import to `aws_bedrockagentcore` if the module was renamed upstream.
- **Why not fix now:** Plan 02's scope is agent/agent.py + narrative validator wiring. Touching CDK construct imports would blur scope and requires infra-side decision (see D-11 DEMO-04 freeze boundaries).
