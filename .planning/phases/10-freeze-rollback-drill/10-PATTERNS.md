# Phase 10: Freeze + Rollback Drill — Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 15 (12 create, 3 modify)
**Analogs found:** 11 / 15 strong-match in-repo; 4 have **no in-repo analog** and are flagged as fresh-convention.

Phase 10 is release-engineering artefact work — not runtime code. The strongest analogs sit in `scripts/` (Phase 6/9 CLI convention) and `.planning/phases/*/` (phase artefact format). The JSON stack-policy bodies and the `requirements*.in` source files have no in-repo predecessor; external-doc patterns are cited inline.

---

## File Classification

| Phase 10 File | Role | Closest Analog | Match Quality |
|---|---|---|---|
| `infrastructure/stack-policies/foundation-freeze.json` | infrastructure asset (CFN stack-policy JSON body) | **None in repo** — external AWS docs + RESEARCH.md §Q5 | fresh convention |
| `infrastructure/stack-policies/agentcore-freeze.json` | infrastructure asset (CFN stack-policy JSON body) | same | fresh convention |
| `infrastructure/stack-policies/backend-api-freeze.json` | infrastructure asset (CFN stack-policy JSON body) | same | fresh convention |
| `infrastructure/stack-policies/foundation-allow-all.json` | infrastructure asset (break-glass JSON body) | same | fresh convention |
| `infrastructure/stack-policies/agentcore-allow-all.json` | infrastructure asset (break-glass JSON body) | same | fresh convention |
| `infrastructure/stack-policies/backend-api-allow-all.json` | infrastructure asset (break-glass JSON body) | same | fresh convention |
| `scripts/hash_dist.sh` | shell helper (content-manifest hasher) | `scripts/demo-keepalive.sh` | role-match — only `.sh` analog in repo |
| `scripts/hash_synth_assets.sh` | shell helper (content-manifest hasher, strips `.pyc`) | `scripts/demo-keepalive.sh` | role-match |
| `requirements.in` | pip-compile source-of-truth | `requirements.txt` (current unpinned form) | role-match — same semantics, different file-extension convention |
| `requirements-dev.in` | pip-compile source-of-truth | `requirements-dev.txt` (current unpinned form) | role-match |
| `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` | phase artefact (sectioned YAML-in-fence manifest) | `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` (front-matter + fenced-content convention); `infrastructure/seed_data/tariff_plans.json` (structured-data-in-planning convention) | role-match — single-fence YAML is a new format; surrounding prose follows phase-doc convention |
| `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` | phase artefact (evidence log) | `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-VERIFICATION.md` | role-match — same "numbered-step, command + stdout + verdict" shape |
| `requirements.txt` (MODIFIED) | lockfile (hash-pinned output) | — (regenerated wholesale by `pip-compile --generate-hashes`; no template needed) | fresh convention — format is tool-dictated |
| `requirements-dev.txt` (MODIFIED) | lockfile (hash-pinned output) | same | fresh convention |
| `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` (MODIFIED) | markdown runbook (append §3–§6) | self-analog — existing §1, §2, §3, §4, §5, §6 headings + checklist-style sub-sections | exact — extension of existing file, tone + heading shape + checklist format already set |

Also mapped for planner reference (D-01 REVISED says these stacks are NOT modified; included here so the planner has context on the "why not"):

| Stack File (NOT modified) | Role | Analog | Relevance |
|---|---|---|---|
| `infrastructure/foundation_stack.py` | CDK root Stack | `infrastructure/foundation_stack.py` (self) | confirms D-01 REVISED — no `add_override` viable on root stack per RESEARCH §Q1 |
| `infrastructure/agentcore_stack.py` | CDK root Stack | same | same |
| `infrastructure/backend_api_stack.py` | CDK root Stack | same | same |

---

## Pattern Assignments

### `infrastructure/stack-policies/foundation-freeze.json` (plus `agentcore-freeze.json`, `backend-api-freeze.json`)

**Role:** CFN stack-policy JSON body — deny-Update:* body applied via `aws cloudformation set-stack-policy` at ceremony time (D-01 REVISED).

**Closest analog:** **None in repo.** `find . -maxdepth 4 -name "*.json" -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/cdk.out/*"` returns only:
- `cdk.json` (CDK config, wrong shape)
- `ui/tsconfig*.json`, `ui/package*.json`, `ui/components.json` (npm/TS config)
- `lambda/tariff_plans.json`, `infrastructure/seed_data/tariff_plans.json` (seed data — structured data)
- `.planning/config.json` (tooling config)

No existing `infrastructure/**/*.json` asset. Phase 10 establishes a fresh convention.

**Pattern source (external — RESEARCH.md §Q5, AWS CloudFormation docs):**

```json
{
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    }
  ]
}
```

**Apply to Phase 10 file:** Commit this exact JSON body, 2-space indent, trailing newline, identical shape across all three `-freeze.json` files. All three stacks get the same deny body — the policy is applied per-stack via `aws cloudformation set-stack-policy --stack-name <name> --stack-policy-body file://...`. File-name-per-stack (not one shared file) keeps the ceremony command explicit about *which* stack is being locked.

---

### `infrastructure/stack-policies/foundation-allow-all.json` (plus `agentcore-allow-all.json`, `backend-api-allow-all.json`)

**Role:** Break-glass relock body — inverse of the deny body, applied via the same `set-stack-policy` CLI during break-glass unlock (D-04).

**Closest analog:** None in repo (same search as above).

**Pattern source (external — RESEARCH.md §Q5 Break-glass block, AWS CloudFormation docs):**

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    }
  ]
}
```

**Apply to Phase 10 file:** Same file-per-stack posture as the `-freeze.json` set. Shape mirrors the deny body exactly — only `Effect` differs. Three identical-body files (one per stack) keep the break-glass command blocks in `FREEZE-MANIFEST.md` concrete (`file://infrastructure/stack-policies/foundation-allow-all.json` etc.) rather than forcing the operator to construct the JSON inline at 3 am.

---

### `scripts/hash_dist.sh` (shell helper — UI dist content-manifest hasher)

**Role:** Pure-bash helper invoked by the freeze ceremony + drill to compute a deterministic sha256 over the files inside a dist directory. Implements D-09 REVISED (no tar, mtime-independent).

**Closest analog:** `scripts/demo-keepalive.sh` (53 LOC — only `.sh` file in the repo; find confirmed in 09-PATTERNS.md "Bash analog search: find . -maxdepth 3 -name '*.sh' -not -path '*/node_modules/*' -not -path '*/.claude/*' → zero results" — still zero as of this map, other than demo-keepalive itself).

**Pattern excerpt — shebang + header + strict mode + fast-fail env check** (demo-keepalive.sh lines 1-19):

```bash
#!/usr/bin/env bash
# demo-keepalive.sh — 10-minute rotating-persona ping loop.
#
# Beats AgentCore's 15-minute microVM idle timeout by exercising the
# Phase 7 `?prewarm=1` hot path every 10 minutes, rotating through
# the three demo personas so the session pool stays warm evenly.
#
# Operator pattern (Phase 10 DEMO-RUNBOOK T-30m):
#   1. Open a tmux pane.
#   2. export BACKEND_API_URL=https://…
#   3. bash scripts/demo-keepalive.sh
#   4. Leave running through end of Q&A; Ctrl-C to stop.
#
# Exit: 0 via trap on INT/TERM/HUP. Non-zero on unset env var (set -u).
# Freeze surface: ~30 LOC, stdlib only; shellcheck zero-warning gate (D-21).

set -euo pipefail

: "${BACKEND_API_URL:?BACKEND_API_URL not set}"
```

**Apply to `scripts/hash_dist.sh`:**
- Identical shebang `#!/usr/bin/env bash`.
- Identical multi-line header comment block: one-line purpose, operator usage pattern, exit-code discipline, freeze-surface + shellcheck gate note.
- `set -euo pipefail` first executable line.
- Positional-arg fast-fail instead of env-var: `: "${1:?usage: hash_dist.sh <dist-dir>}"` — same `:?` pattern, adapted for `$1` instead of an env var.
- Phase 10 exit taxonomy inherited from Phase 9 convention (0 ok / 1 gate-fail / 2 setup-error) — `hash_dist.sh` uses 0 (happy) and 2 (missing/unreadable dir). No "gate-fail" semantic — the script *computes*, it doesn't *gate*.

**Pattern excerpt — command body shape** (D-09 REVISED from CONTEXT.md + RESEARCH §Q4 Example 1 fallback):

```bash
(cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
```

**Apply to `scripts/hash_dist.sh`:** wrap the one-liner above in the header-first shape from demo-keepalive.sh. Output is a single 64-char hex line on stdout (matches the shape that FREEZE-MANIFEST.md `dist_bundles:` entries consume). No trailing newlines from `find`/`sha256sum` leak because `awk '{print $1}'` terminates output cleanly. `LC_ALL=C sort -z` makes the sort byte-stable across locales (RESEARCH §Q4 Example 1 uses `LC_ALL=C sort`).

**Quality gate:** `shellcheck scripts/hash_dist.sh` → zero warnings (Phase 9 D-21 pattern — confirmed in 09-VERIFICATION.md line 72 `Exit 0, zero warnings, no suppression comments needed`).

---

### `scripts/hash_synth_assets.sh` (shell helper — cdk.out asset content-manifest hasher, strips `.pyc` / `__pycache__`)

**Role:** Same as `hash_dist.sh` but operates on `cdk.out/asset.<hash>/` directories and strips `.pyc` + `__pycache__` before hashing (D-08 REVISED — Python bytecode caches embed build timestamps, per RESEARCH §Q3 Pitfall 3).

**Closest analog:** `scripts/demo-keepalive.sh` (same rationale as `hash_dist.sh`).

**Apply to `scripts/hash_synth_assets.sh`:** identical header + shebang + `set -euo pipefail` shape as `hash_dist.sh`. Body diff vs `hash_dist.sh`:

```bash
# D-08 REVISED — strip .pyc and __pycache__ before hashing so Python bytecode
# cache files (which carry build timestamps in their headers) don't leak into
# the content manifest. See 10-RESEARCH.md §Q3 Pitfall 3.
(cd "$1" && find . -type f -not -name '*.pyc' -not -path '*/__pycache__/*' -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
```

Invocation contract: called once per `cdk.out/asset.*/` directory by the 10-03 ceremony. The outer loop that iterates assets lives in the ceremony Commands appendix, not in the script — keeps `hash_synth_assets.sh` a pure one-arg function-equivalent (composable, testable). Planner verifies this empirically in 10-01 (validation task 10-01-05 per 10-VALIDATION.md).

---

### `requirements.in` (pip-compile source-of-truth for production deps)

**Role:** Source file that `pip-compile --generate-hashes` consumes to produce a hash-pinned `requirements.txt` output.

**Closest analog:** `requirements.txt` (current unpinned form, 4 lines; same deps, same ordering, but `.in` is input to the tool rather than committed hash-pinned output).

**Pattern excerpt — current `requirements.txt`** (exactly the shape `.in` should adopt):

```
aws-cdk-lib>=2.250.0
aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0
constructs>=10.0.0
boto3>=1.42.0
```

**Apply to `requirements.in`:**
- Copy these 4 lines verbatim as the starting `.in` body (zero-delta over current floors).
- Optional per Claude's Discretion (CONTEXT.md line 134): rewrite `>=X` → `==<current-pip-freeze-version>` before compiling, so pip-compile hashes against live-deployed versions rather than re-resolving upward. RESEARCH Pitfall 6 (line 441) recommends this tactic.
- Trailing newline; no comments in the `.in` file unless pinning a specific floor (e.g. `# 2.250.0 is the first version with the agentcore alpha`). Keep it minimal.

**Format reference (external — RESEARCH §Q2 + pip-tools docs):** `.in` files accept the same syntax as `requirements.txt` (`>=`, `==`, `-c <file>`, `-r <file>`). No special header is required. `pip-compile` reads the file and emits a `.txt` with `--hash=sha256:...` annotations per resolved package.

---

### `requirements-dev.in` (pip-compile source-of-truth for dev deps with constraint on prod)

**Role:** Same as `requirements.in` but layers dev-only deps on top of prod; uses `-c requirements.txt` (constraint) so pip-compile reuses the exact versions prod pinned (RESEARCH §Q2 "Layered requirements" pattern).

**Closest analog:** `requirements-dev.txt` (current 4-line form, uses `-r requirements.txt` merge).

**Pattern excerpt — current `requirements-dev.txt`:**

```
-r requirements.txt
pytest>=7.0
pytest-mock>=3.0
requests>=2.28,<3
```

**Apply to `requirements-dev.in`:**

```
-c requirements.txt           # constraint (NOT -r merge) — reuses prod-pinned versions
pytest>=7.0
pytest-mock>=3.0
requests>=2.28,<3
```

**Key delta from current `requirements-dev.txt`:** `-r` → `-c`. RESEARCH §Q2 line 263: "`-c <file>` in `.in` = constraint. Dev deps get the same versions prod picked; no version drift across layers." Changing `-r` to `-c` is the layered-requirements idiom that lets `pip-compile --generate-hashes` produce a clean `requirements-dev.txt` that doesn't duplicate prod entries and that respects prod's resolved versions.

---

### `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` (sectioned YAML-in-fence manifest)

**Role:** Single Markdown file with one `yaml` code fence carrying all freeze evidence (D-07). Human-readable in GitHub; machine-parseable by `python3 -c "import yaml,re; ..."`. Outside the fence: short prose framing + break-glass guidance.

**Closest in-repo analog:** `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` (front-matter YAML + table-heavy body — confirms the front-matter-first convention). Structured-data-in-planning precedent set by `infrastructure/seed_data/tariff_plans.json`. The **single-fence-sectioned-YAML** shape is novel; planner assembles it from D-07 + D-10 + RESEARCH Example 2.

**Pattern excerpt — front-matter + purpose-prose convention** (10-VALIDATION.md lines 1-11):

```markdown
---
phase: 10
slug: freeze-rollback-drill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-26
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
```

**Apply to `FREEZE-MANIFEST.md`:**
- Opens with a `---`-delimited YAML front-matter block (optional — planner's call; D-07 says "single sectioned YAML-in-fence" which suggests the front-matter is separate from the main manifest fence).
- H1 heading first: `# FREEZE-MANIFEST — Customer Tariff Demo v2.0`.
- 2–4 lines of prose framing (what this is, when frozen, what invalidates it, where to find break-glass).
- One `yaml` code fence containing all 8 top-level keys from D-10: `git:`, `lockfiles:`, `dist_bundles:`, `synth_assets:`, `cloudformation:`, `bedrock_model_id:`, `dynamodb_backup:`, `break_glass:`.

**Full manifest YAML template (RESEARCH Example 2, lines 482-540 — already reviewed and matches D-07/D-10 exactly):**

```yaml
git:
  freeze_commit_sha: <40-char-sha>
  freeze_timestamp_utc: "2026-04-2XTXX:XX:XXZ"
  tag: demo-v2.0

lockfiles:
  requirements_txt: "sha256:<hex>"
  requirements_dev_txt: "sha256:<hex>"
  ui_package_lock_json: "sha256:<hex>"

dist_bundles:
  ui_dist: "sha256:<hex>"
  ui_dist_mock: "sha256:<hex>"

synth_assets:
  - logical: FoundationStack/ToolsLambda
    asset_hash: "<64-hex>"
    bundle_sha256: "sha256:<hex>"
  - logical: BackendApiStack/TariffApiLambda
    asset_hash: "<64-hex>"
    bundle_sha256: "sha256:<hex>"

cloudformation:
  FoundationStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariff/<guid>"
  AgentCoreStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffAgent/<guid>"
  BackendApiStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffApi/<guid>"

bedrock_model_id: "us.anthropic.claude-sonnet-4-6"

dynamodb_backup:
  table_name: tariff-billing
  backup_arn: "arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/<id>"
  backup_timestamp_utc: "2026-04-2XTXX:XX:XXZ"

break_glass:
  unlock_stack_policies: |
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation set-stack-policy --stack-name "$stack" \
          --stack-policy-body file://infrastructure/stack-policies/${stack,,}-allow-all.json \
          --region us-east-1 --profile cevo-dev25
    done
  disable_termination_protection: |
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation update-termination-protection --no-enable-termination-protection \
          --stack-name "$stack" --region us-east-1 --profile cevo-dev25
    done
  after_fix: |
    # Re-run DEMO-RUNBOOK §3 steps 2–7 (drift gate, drill, stack lock, backup, manifest, tag).
```

**Key deviations from RESEARCH Example 2 block worth noting:**
- D-01 REVISED says stack policies live under `infrastructure/stack-policies/*.json` (committed assets), NOT in `/tmp`. The `break_glass.unlock_stack_policies` block above uses `file://infrastructure/stack-policies/<name>-allow-all.json` — matches committed paths. Note the `${stack,,}` bash syntax assumes bash 4+ for lowercase expansion; the ceremony runs on an operator shell so this is safe, but planner may prefer an explicit case-to-file mapping for shell portability.
- 10-VALIDATION.md task 10-02-05 schema check expects all 8 top-level keys under the YAML fence — the template above satisfies that.

---

### `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` (rollback drill evidence log)

**Role:** Operator-populated evidence log — numbered drill steps, each with ISO-8601 UTC start timestamp, command(s), stdout excerpt, verdict (PASS/FAIL), deviations. `## Commands` appendix with copy-paste one-liners (D-14).

**Closest analog:** `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-VERIFICATION.md` (Phase 9 verification report — same "numbered-item, expected, why-human, PASS/FAIL evidence" shape; 160 LOC).

**Pattern excerpt — YAML front-matter + human-verification numbered items** (09-VERIFICATION.md lines 1-17):

```markdown
---
phase: 09-pre-warm-tooling-eval-harness-keep-alive
verified: 2026-04-26T19:15:00Z
status: human_needed
score: 4/4 structurally verified; 3 live-stack gates pending human run
overrides_applied: 0
human_verification:
  - test: "Live pre-warm run against deployed stack (D-22 step 1)"
    expected: "`BACKEND_API_URL=https://… npm run prewarm` from `ui/` exits 0; all 3 personas warm median < 3000ms; ..."
    why_human: "Requires BACKEND_API_URL exported and valid AWS creds against the live API Gateway → Lambda → AgentCore → Bedrock chain. Not runnable in-code."
---
```

**Pattern excerpt — numbered step block with command + expected + status** (09-VERIFICATION.md lines 108-122):

```markdown
### 1. Live Pre-Warm Run (D-22 step 1)

**Test:** Export `BACKEND_API_URL=https://<deployed-api-gateway-url>` (e.g. the Phase 7 API Gateway URL) and valid AWS creds, then from `ui/` run `npm run prewarm`.
**Expected:**
- Total wall time < 30 seconds (per ROADMAP SC-1).
- 3 warm calls printed as `prewarm CUST-00X: 204 Nms ok` lines.
- ...
- Process exits 0.
**Why human:** Requires the deployed API Gateway → Lambda → AgentCore → Bedrock chain. Not runnable in structural verification.
```

**Pattern excerpt — behavioral spot-check table (adapted for per-step drill rows)** (09-VERIFICATION.md lines 67-78):

```markdown
### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `scripts/prewarm.py` exit-2 path (missing env var) | `env -u BACKEND_API_URL python3 scripts/prewarm.py; echo $?` | `BACKEND_API_URL not set` on stderr; exit code `2`; stdout empty | ✓ PASS |
| `scripts/demo-keepalive.sh` shellcheck | `shellcheck scripts/demo-keepalive.sh; echo $?` | Exit 0, zero warnings, no suppression comments needed | ✓ PASS |
```

**Apply to `10-DRILL-LOG.md`:**
- Front-matter identical to 09-VERIFICATION.md shape: `phase: 10-freeze-rollback-drill`, `verified: <UTC>`, `status: pending|human_needed|complete`, `score: N/M`, `overrides_applied: 0`.
- H1 heading: `# Phase 10: Rollback Drill Log`.
- One `### <n>. <step name> (<requirement-ID>)` subsection per drill step, numbered 1 through N. Inside each: `**Test:**`, `**Expected:**`, `**Command(s):**`, `**Stdout:**` (truncated code fence), `**Verdict:** PASS|FAIL`, `**Deviations:**` (optional).
- Final section `## Drill Verdict` with one-line overall PASS/FAIL + drill duration + operator identity (matching 09-VERIFICATION.md Gaps Summary tone).
- `## Commands` appendix at the bottom — copy-paste one-liners from 10-VALIDATION.md rows 10-03-01 through 10-03-15, plus the restore / scan / spot-check / teardown sequence from D-12, the curl + build:mock one-liners from D-15 / D-16, and the fresh-clone pytest gate from D-13.
- Scaffolded in 10-02 (step headings + empty Expected/Stdout blocks + full Commands appendix), populated by operator in 10-03.

**Step ordering per D-14 + CONTEXT.md specifics line 238** (speed-first so operator-under-pressure sees cheapest recovery option first):
1. `?narrative=off` URL-flag drill (no deploy, no git — fastest)
2. `build:mock` <10s dist regeneration + hash-roundtrip (D-16)
3. `git checkout demo-v1.0` + pytest green (D-13)
4. DynamoDB restore-from-backup + scan + spot-check (D-12)
5. Scratch table teardown

---

### `requirements.txt` (MODIFIED — regenerated as hash-pinned output of pip-compile)

**Role:** Lockfile. Regenerated wholesale by `pip-compile --generate-hashes requirements.in`. Format is tool-dictated.

**Closest analog:** None — the pre-Phase-10 `requirements.txt` is unpinned `>=X` form; the post-Phase-10 form is the tool's output. No format precedent in repo.

**Pattern excerpt (external — RESEARCH §Q2 + pip-tools docs):**

```
# SHA256: <digest>-<digest>
aws-cdk-lib==2.250.0 \
    --hash=sha256:abc123... \
    --hash=sha256:def456...
boto3==1.42.95 \
    --hash=sha256:...
...
```

**Apply to Phase 10 file:** don't hand-author — run `pip-compile --generate-hashes --output-file requirements.txt requirements.in` and commit the output verbatim. Verify every non-comment, non-directive line carries a `--hash=sha256:` annotation per 10-VALIDATION.md task 10-02-02.

**Gotcha (RESEARCH Pitfall 6):** `>=X` floors get re-resolved to specific `==` versions during compile. If the planner wants zero version drift vs. currently-deployed Lambda, snapshot `pip freeze` first and rewrite `requirements.in` to `==<current-version>` before compiling.

---

### `requirements-dev.txt` (MODIFIED — regenerated hash-pinned)

Same pattern as `requirements.txt`. Generated by `pip-compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in` *after* `requirements.txt` exists (the `.in` uses `-c requirements.txt` constraint, so it needs the pinned prod file to be present first).

---

### `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` (MODIFIED — append §3–§6)

**Role:** Presenter-facing runbook. Existing file already has §1 Pre-demo setup, §2 Timed checklist (T-24h / T-2h / T-0), §3 Presenter cheat sheet, §4 Launch commands, §5 Fallback procedure, §6 Post-demo teardown.

**NOTE on CONTEXT.md D-20 section numbering:** CONTEXT.md D-20 calls for new `§3 T-48h Freeze Ceremony`, `§4 T-30m Keep-Alive Start`, `§5 T-10m Pre-Warm`, `§6 T-eval Live Eval Harness Gate` — but the **existing** file already uses §3, §4, §5, §6 for cheat-sheet / launch / fallback / teardown. Planner must resolve the collision: either renumber existing sections (disruptive — all T-0 ops references would need to follow), insert the new sections between existing §2 and §3 as sub-sections under a new §2-extension, or re-title the new additions as §7–§10. **Recommendation: re-title new additions as §7–§10** (append-only, no collision with operational prose the presenter has likely already memorised). Flag this to the user in the 10-02 plan summary.

**Closest analog:** the existing `DEMO-RUNBOOK.md` itself — §1 and §2 already establish tone + heading shape + checklist-with-code-fence format.

**Pattern excerpt — existing section heading + checklist shape** (DEMO-RUNBOOK.md lines 77-104):

```markdown
## 2. Timed checklist (D-19)

### T-24h

- [ ] `git tag --list demo-v1.0` shows the tag exists
- [ ] `05-DEPLOY-OUTPUTS.md` reflects the currently-deployed ARNs (re-run `aws cloudformation describe-stacks` and diff)
- [ ] **Visual rehearsal (closes D-14/D-15 gap):** open `http://localhost:4173/` in Chrome at 1280×800 with DevTools → Network open, run 2 passes (cold then warm, 30s apart) across all 3 personas plus the `cust999` and `CUST-999` error cases. Record per-persona warm median from DevTools Network Duration. Every warm median must be <3000ms; if not, treat as a gap against UI-02 before presenting.

### T-2h

- [ ] `ui/dist/index.html` exists and a grep confirms it contains the live hostname:
  ```bash
  grep -l 'execute-api.us-east-1.amazonaws.com' ui/dist/assets/*.js | head -1
  ```
```

**Pattern excerpt — section with code block + expected output comment** (DEMO-RUNBOOK.md lines 54-60):

```markdown
5. (Only if re-deploying) Deploy stacks in dependency order:
   ```bash
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariff      --require-approval never
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffAgent --require-approval never
   AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffApi   --require-approval never
   ```
   Then re-capture CfnOutputs into `05-DEPLOY-OUTPUTS.md` and cut a new tag (`demo-v1.0.1`).
```

**Apply to DEMO-RUNBOOK.md:** new §7 (T-48h Freeze Ceremony) through §10 (T-eval Live Eval Harness Gate) — per renumbering recommendation above. Each new section:
- `## <n>. <T-x title> (D-YY)` H2 heading (matches existing §1–§6 style).
- `### <sub-step>` H3 for timed sub-steps (matches existing `### T-24h` / `### T-2h` / `### T-0` pattern).
- Checklist items `- [ ]` for presenter/operator-actionable steps.
- `` ```bash `` fenced commands for copy-paste operations (already the file's default).
- Inline `#` comments inside bash blocks showing expected output (matches line 52 `# Account should match the one recorded in...`).
- Tone: presenter-adjacent, 3am-before-the-demo (Claude's Discretion from CONTEXT.md line 132).

Per D-20: single monolithic edit committed as part of 10-02 (Claude's Discretion recommendation line 136: "Recommend single edit committed as part of 10-02; the sections are tightly coupled").

---

## Shared Patterns

### ISO-8601 UTC timestamp format
**Source:** `scripts/demo-keepalive.sh` line 29, line 24 (trap format).
**Apply to:** `FREEZE-MANIFEST.md` (`git.freeze_timestamp_utc`, `dynamodb_backup.backup_timestamp_utc`), `10-DRILL-LOG.md` (every drill step), DEMO-RUNBOOK.md new §7–§10.
```bash
date -u +%Y-%m-%dT%H:%M:%SZ   # 2026-04-26T14:23:45Z
```
Works on both macOS BSD date and Linux GNU date (RESEARCH §Q8 verification). No subsecond precision (Claude's Discretion line 135 recommends `YYYY-MM-DDTHH:MM:SSZ` for readability).

### Shell script header + exit-code taxonomy
**Source:** `scripts/demo-keepalive.sh` lines 1-19 + 09-PATTERNS.md "0/1/2 exit taxonomy for CLI scripts".
**Apply to:** `scripts/hash_dist.sh`, `scripts/hash_synth_assets.sh`.
- Multi-line `#` header: purpose, operator usage pattern, exit-code discipline, freeze-surface note.
- `set -euo pipefail` first executable line.
- Fast-fail on missing input: `: "${1:?usage: <script> <arg>}"` or env-var equivalent.
- Exit 0 on happy path; exit 2 on setup error (missing arg, unreadable dir); no "gate-fail" semantic in these scripts (they compute, not gate — Phase 10 ceremony scripts in Commands appendix handle the assertions).
- Quality gate: `shellcheck <script>` zero warnings.

### stdlib-first + freeze-surface discipline
**Source:** `scripts/capture_samples.py` line 27 (lazy boto3 import with freeze-surface comment), `scripts/demo-keepalive.sh` line 15 (`~30 LOC, stdlib only; shellcheck zero-warning gate`).
**Apply to:** `scripts/hash_dist.sh`, `scripts/hash_synth_assets.sh`.
- Pure bash + POSIX utilities (`find`, `sort`, `xargs`, `sha256sum`, `awk`). No jq, no python, no curl.
- `sha256sum` is at `/sbin/sha256sum` on macOS per RESEARCH §Q0 env verification — no install step needed.
- Keep script bodies under ~30 LOC each; all complexity in the ceremony Commands appendix, not in the helpers.

### Phase artefact location + naming convention
**Source:** `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/` structure — `NN-CONTEXT.md`, `NN-DISCUSSION-LOG.md`, `NN-PATTERNS.md`, `NN-VALIDATION.md`, `NN-RESEARCH.md`, `NN-XX-PLAN.md`, `NN-XX-SUMMARY.md`, `NN-VERIFICATION.md`, `NN-REVIEW.md`, `NN-HUMAN-UAT.md`.
**Apply to:** `FREEZE-MANIFEST.md` and `10-DRILL-LOG.md`.
- `FREEZE-MANIFEST.md` — unprefixed (D-06 explicit): sits at `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`. Rationale (CONTEXT.md D-06): "phase-scoped evidence, not runtime config … not placed at repo root."
- `10-DRILL-LOG.md` — phase-prefixed per standard phase convention.

### YAML front-matter on planning docs
**Source:** `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` lines 1-8, `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-VERIFICATION.md` lines 1-17, `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` lines 1-10.
**Apply to:** `FREEZE-MANIFEST.md` (optional per D-07 — separate question from the main YAML fence), `10-DRILL-LOG.md` (mandatory — matches VERIFICATION.md sibling convention).
```yaml
---
phase: 10
slug: freeze-rollback-drill
artifact: <freeze-manifest|drill-log>
status: <draft|pending|human_needed|complete>
created: 2026-04-26
---
```

### Reference to canonical RESEARCH.md sections
**Source:** 09-PATTERNS.md cross-references RESEARCH.md sections throughout.
**Apply to:** all Phase 10 artefacts that encode research-derived patterns.
- `hash_dist.sh` header comment cites `10-RESEARCH.md §Q4`.
- `hash_synth_assets.sh` header comment cites `10-RESEARCH.md §Q3`.
- `FREEZE-MANIFEST.md` prose cites `10-RESEARCH.md §Q5` for break-glass provenance.
- `10-DRILL-LOG.md` step descriptions cite `10-VALIDATION.md` row IDs for each gate's automated command.
Makes future readers / reviewers able to trace every decision back to its source.

---

## No Analog Found

| Phase 10 File | Role | Reason | Fresh Convention |
|---|---|---|---|
| `infrastructure/stack-policies/*-freeze.json` (×3) | CFN stack-policy JSON body | No existing `infrastructure/**/*.json` asset in the repo — only `cdk.json`, UI config JSONs, seed-data JSONs, and `.planning/config.json` exist. | Commit the exact 5-line JSON body from RESEARCH §Q5 verbatim; one file per stack; 2-space indent; trailing newline; identical bodies across the three `-freeze.json` files. |
| `infrastructure/stack-policies/*-allow-all.json` (×3) | CFN break-glass JSON body | Same — no predecessor. | Same shape as `-freeze.json`, only `Effect: Allow`. Planner uses `file://infrastructure/stack-policies/<stack>-allow-all.json` in break-glass command blocks. |
| `requirements.txt` / `requirements-dev.txt` (hash-pinned form) | Tool-generated lockfile | No prior hash-pinned lockfile exists in repo; `pip-compile --generate-hashes` output format is tool-dictated. | Don't hand-author — run `pip-compile` and commit the output. Verify every package line carries `--hash=sha256:` per 10-VALIDATION.md task 10-02-02. |
| `FREEZE-MANIFEST.md` YAML-in-fence schema | Sectioned-YAML single-fence manifest | No prior single-fence-YAML document pattern in repo. 10-VALIDATION.md uses front-matter YAML, not a content-fence. | Planner assembles from D-07 + D-10 + RESEARCH.md Example 2 (lines 482-540); 8 top-level keys enforced by 10-VALIDATION.md task 10-02-05 schema check. |

---

## Metadata

**Analog search scope:**
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/scripts/` (3 files — 1 `.sh`, 2 `.py`)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/infrastructure/` (stack files + constructs + seed_data — no `.json` stack-policy precedent)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/.planning/phases/{06,07,08,09,10}-*/` (phase artefact conventions — front-matter, section shapes, VERIFICATION log format)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/.planning/milestones/v1.0-phases/05-demo-hardening/` (DEMO-RUNBOOK section shape, code-fence + checklist idiom)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/requirements*.txt` (current unpinned deps form)

**JSON search:** `find . -maxdepth 4 -type f -name "*.json" -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/cdk.out/*" -not -path "*/.claude/*"` — zero CFN-stack-policy-shaped JSON precedents. Confirms fresh convention for `infrastructure/stack-policies/`.

**Shell script search:** `find . -maxdepth 3 -name "*.sh" -not -path "*/node_modules/*" -not -path "*/.claude/*"` returns only `scripts/demo-keepalive.sh` (53 LOC). Same finding as 09-PATTERNS.md "Bash analog search" — `demo-keepalive.sh` is the sole `.sh` analog for the two new hashers.

**Files scanned for pattern extraction:**
1. `scripts/demo-keepalive.sh` (primary bash analog, 53 LOC)
2. `scripts/prewarm.py` (Phase 9 CLI convention reference, 131 LOC)
3. `scripts/capture_samples.py` (Phase 6 CLI convention reference, 57 LOC)
4. `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` (self-analog for §7–§10 amendments, 211 LOC)
5. `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-VERIFICATION.md` (analog for `10-DRILL-LOG.md`, 160 LOC)
6. `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-PATTERNS.md` (format precedent for this file, 446 LOC)
7. `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` (front-matter convention, 112 LOC)
8. `requirements.txt`, `requirements-dev.txt` (current unpinned form)
9. `infrastructure/seed_data/tariff_plans.json` (only structured-data-JSON-in-planning precedent)
10. `infrastructure/foundation_stack.py` (confirms D-01 REVISED — no `add_override` viable)

**Pattern extraction date:** 2026-04-26

---

## PATTERN MAPPING COMPLETE
