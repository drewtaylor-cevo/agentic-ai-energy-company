---
phase: 17-freeze-ceremony
artifact: freeze-manifest
status: template
created: 2026-05-03
---

# FREEZE-MANIFEST — Customer Tariff Demo v3.0

This manifest captures the byte-level identity of the v3.0 demo at T-48h. Every
hash here proves the corresponding artefact was frozen at the freeze commit and
has not drifted since. Operator populates the `<pending>` fields in task 7.2;
the structure, break-glass block, and pre-filled literals (`bedrock_model_id`,
`dynamodb_backup.table_name`, `git.tag`, `agent_runtime_arn`, `api_endpoint`,
`memory_id`, CloudFormation stack ARNs) are locked here in task 7.1.

**What this proves:** source → build → deploy reproducibility holds at freeze
time; same source + same lockfiles + same model + same CFN stacks + same
AgentCore runtime + same Memory → same demo.

**What invalidates this:** any non-zero `cdk diff`, any hash mismatch on
rebuild, any CloudFormation stack-policy or termination-protection drift, any
silent Bedrock model swap between freeze and demo, or any AgentCore Memory /
runtime ARN drift.

**Break-glass:** see `break_glass:` section below. All commands use
`--region us-east-1 --profile cevo-dev25`. After unlocking, applying a fix, and
relocking, re-run DEMO-RUNBOOK.md section 7 steps 2-7 and cut `demo-v3.0.1`.

```yaml
git:
  freeze_commit_sha: "d9b5865b671b68e672b242a1ab470422aae96a1d"  # Task 7.3 two-commit pattern per WN-2: this commit is tag^ (one parent of demo-v3.0)
  freeze_timestamp_utc: "2026-05-04T02:42:06Z"
  tag: demo-v3.0

lockfiles:
  requirements_txt: "sha256:46826e3d523a9dab38b9451fbed1c4163ba24cb32dfdb4ad2eae5381f1f80e55"       # 62+ prod entries incl. bedrock-agentcore==1.6.4
  requirements_dev_txt: "sha256:893ff8f5500171ba82d8f262725c547f6cd437b16117ff664a78f45412cec8e7"   # 33+ dev entries
  ui_package_lock_json: "sha256:12a7b9efb73ea27c4b5f89b816c4702d60c36684d0ae8762c1347531d8e10a41"

# NOTE (Rule 4 D-16 softening — carried from v2.0):
# dist_bundles.* hashes are commit-bound snapshots captured at the freeze HEAD.
# They are NOT a fresh-clone reproducibility gate — vite.config.ts embeds the
# git short SHA into the bundle, so every commit produces a different hash.
# Cross-HEAD reproducibility is guarded by: (a) lockfile hashes (Python + npm
# require-hashes install), (b) synth_asset hashes (Lambda bundles), and
# (c) cdk diff == 0.
dist_bundles:
  ui_dist: "sha256:3956547cad29c3f904749abfac874ed9f3fd8d393b82758a5af1568b094299f4"
  ui_dist_mock: "sha256:7b210403c418c6ed0e5ca415cb2872fd638e6d5dd8a0c42254ee740dae6fd725"

# Populated by task 7.2 — one entry per cdk.out/asset.*/ directory.
# logical = asset logical ID from cdk.out/manifest.json (rename-immune).
# asset_hash = the CDK-generated content hash (matches cdk.out/asset.<hash>/ dir name).
# bundle_sha256 = scripts/hash_synth_assets.sh output for that asset dir (strips .pyc / __pycache__).
synth_assets:
  - logical: "CustomerTariff/ToolsLambda/TariffTools/Code"
    asset_hash: "65c0dfe51afb9276fe17a56613bd6d46753718bbfe4172b27c9ddf52cb9dd9f7"
    bundle_sha256: "sha256:00fcaf874615fdb7dd1d195d237b8e550e21cb5fe938ba0698480f86845dda08"
  - logical: "CustomerTariff/AWS679f53fac002430cb0da5b7982bd2287/Code"
    asset_hash: "56f7467bbde8a5efebcf57ae9e460027607099bab9f844669dcf5d800172ee5a"
    bundle_sha256: "sha256:62a98a12fb3edd2bfd8d69e645f241faa69c57b50a6ad60549f1004866dd295d"
  - logical: "CustomerTariffAgent/AgentRuntime/TariffAgentRuntime/AgentRuntimeArtifact"
    asset_hash: "e6c1307f98e4295233fdc0f231a845dfb39cd7ce78cf38ef04d8d83abd41b519"
    bundle_sha256: "sha256:009595d2000546531a327058dd70ce9661e9fc1264e3b2b40d00a765e5904b36"
  - logical: "CustomerTariffApi/BackendApi/TariffApiLambda/Code"
    asset_hash: "c98909f024049ee8127f95a107de57d2665a621fb419a6c9b2f54a750d736892"
    bundle_sha256: "sha256:527c5f84584d6cb14f08b5f078a798cb304152ef04b4e42e321f8e050913c73b"

cloudformation:
  # Full StackId ARN format: arn:aws:cloudformation:us-east-1:588738606436:stack/<name>/<guid>
  FoundationStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariff/642a1730-3f11-11f1-b95c-0e3dd0f0bb6b"
  AgentCoreStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffAgent/9b4763d0-3f1b-11f1-9085-0affd0ba2291"
  BackendApiStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffApi/8505daf0-3f90-11f1-b399-1252c9745d9f"

bedrock_model_id: "us.anthropic.claude-sonnet-4-6"

# v3.0 additions (not present in v2.0 manifest)
agent_runtime_arn: "arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V"
api_endpoint: "https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
memory_id: "tariff_agent_memory-xVDAvVCTtU"

dynamodb_backup:
  table_name: tariff-billing
  backup_arn: "arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777859824019-989beacf"
  backup_timestamp_utc: "2026-05-04T01:57:04Z"

break_glass:
  unlock_stack_policies: |
    # Apply allow-all policy to each stack (replaces the deny-Update:* freeze policy).
    # Each stack has its own policy file under infrastructure/stack-policies/.
    aws cloudformation set-stack-policy --stack-name CustomerTariff \
        --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json \
        --region us-east-1 --profile cevo-dev25
    aws cloudformation set-stack-policy --stack-name CustomerTariffAgent \
        --stack-policy-body file://infrastructure/stack-policies/agentcore-allow-all.json \
        --region us-east-1 --profile cevo-dev25
    aws cloudformation set-stack-policy --stack-name CustomerTariffApi \
        --stack-policy-body file://infrastructure/stack-policies/backend-api-allow-all.json \
        --region us-east-1 --profile cevo-dev25

  disable_termination_protection: |
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation update-termination-protection --no-enable-termination-protection \
          --stack-name "$stack" --region us-east-1 --profile cevo-dev25
    done

  after_fix: |
    # After applying the emergency fix:
    #   1. Reapply deny-Update:* policies by swapping -allow-all.json -> -freeze.json
    #      in the unlock_stack_policies commands above.
    #   2. Re-enable termination protection (swap --no-enable-termination-protection
    #      for --enable-termination-protection in the loop above).
    #   3. Recompute all manifest hashes (scripts/hash_dist.sh + scripts/hash_synth_assets.sh
    #      + sha256sum on lockfiles).
    #   4. Commit the updated FREEZE-MANIFEST.md and cut a new annotated tag (demo-v3.0.1).
    # Full ceremony re-run is DEMO-RUNBOOK.md section 7 steps 2-7.
```

---

## References

- **Ceremony runbook:** `DEMO-RUNBOOK.md` section 7 (T-48h Freeze Ceremony) — the
  scripted sequence that populates every `<pending>` field above.
- **Drill evidence log:** `.planning/milestones/v3.0-phases/17-freeze-ceremony/17-DRILL-LOG.md` —
  rollback drill outcomes for the five drill steps; must be `PASS` overall before this
  manifest is finalised and the `demo-v3.0` tag is cut.
- **Stack-policy JSON bodies:** `infrastructure/stack-policies/*.json` — six files
  (three `-freeze.json` + three `-allow-all.json`) committed in Phase 10.
- **Content-manifest hashers:** `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh`
  committed in Phase 10; empirically cross-rebuild stable per 10-01-SUMMARY.md.
- **Bedrock model source of truth:** `agent/agent.py:309` (`us.anthropic.claude-sonnet-4-6`).
- **AgentCore Memory:** provisioned in Phase 15; Memory ID from SSM `/customer-tariff/memory-id`.
- **v2.0 manifest (structural template):** `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`.
