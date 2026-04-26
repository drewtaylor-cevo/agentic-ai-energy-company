---
phase: 10-freeze-rollback-drill
artifact: freeze-manifest
status: template
created: 2026-04-26
---

# FREEZE-MANIFEST — Customer Tariff Demo v2.0

This manifest captures the byte-level identity of the v2.0 demo at T-48h. Every
hash here proves the corresponding artefact was frozen at the freeze commit and
has not drifted since. Operator populates the `<pending>` fields in plan 10-03;
the structure, break-glass block, and pre-filled literals (`bedrock_model_id`,
`dynamodb_backup.table_name`, `git.tag`) are locked here in 10-02.

**What this proves:** source → build → deploy reproducibility holds at freeze
time; same source + same lockfiles + same model + same CFN stacks → same demo.

**What invalidates this:** any non-zero `cdk diff`, any hash mismatch on
rebuild, any CloudFormation stack-policy or termination-protection drift, or
any silent Bedrock model swap between freeze and demo.

**Break-glass:** see `break_glass:` section below. All commands use
`--region us-east-1 --profile cevo-dev25`. After unlocking, applying a fix, and
relocking, re-run DEMO-RUNBOOK.md section 7 steps 2-7 and cut `demo-v2.0.1`.

```yaml
git:
  freeze_commit_sha: "<pending>"
  freeze_timestamp_utc: "<pending-UTC>"
  tag: demo-v2.0

lockfiles:
  requirements_txt: "sha256:<pending>"
  requirements_dev_txt: "sha256:<pending>"
  ui_package_lock_json: "sha256:<pending>"

dist_bundles:
  ui_dist: "sha256:<pending>"
  ui_dist_mock: "sha256:<pending>"

# Populated by 10-03 — one entry per cdk.out/asset.*/ directory.
# logical = asset logical ID from cdk.out/manifest.json (rename-immune).
# asset_hash = the CDK-generated content hash (matches cdk.out/asset.<hash>/ dir name).
# bundle_sha256 = scripts/hash_synth_assets.sh output for that asset dir (strips .pyc / __pycache__).
synth_assets:
  - logical: "<pending — e.g. FoundationStack/ToolsLambda>"
    asset_hash: "<pending>"
    bundle_sha256: "sha256:<pending>"

cloudformation:
  # Full StackId ARN format: arn:aws:cloudformation:us-east-1:588738606436:stack/<name>/<guid>
  FoundationStack: "<pending>"
  AgentCoreStack: "<pending>"
  BackendApiStack: "<pending>"

bedrock_model_id: "us.anthropic.claude-sonnet-4-6"

dynamodb_backup:
  table_name: tariff-billing
  backup_arn: "<pending>"
  backup_timestamp_utc: "<pending-UTC>"

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
    #   4. Commit the updated FREEZE-MANIFEST.md and cut a new annotated tag (demo-v2.0.1).
    # Full ceremony re-run is DEMO-RUNBOOK.md section 7 steps 2-7.
```

---

## References

- **Ceremony runbook:** `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`
  section 7 (T-48h Freeze Ceremony) — the 7-step sequence that populates every
  `<pending>` field above.
- **Drill evidence log:** `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` —
  rollback drill outcomes for the five drill steps; must be `PASS` overall before this
  manifest is finalised and the `demo-v2.0` tag is cut.
- **Stack-policy JSON bodies:** `infrastructure/stack-policies/*.json` — six files
  (three `-freeze.json` + three `-allow-all.json`) committed in plan 10-01.
- **Content-manifest hashers:** `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh`
  committed in plan 10-01; empirically cross-rebuild stable per 10-01-SUMMARY.md.
- **Bedrock model source of truth:** `agent/agent.py:309` (`us.anthropic.claude-sonnet-4-6`).
