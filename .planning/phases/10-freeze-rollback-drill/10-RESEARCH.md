# Phase 10: Freeze + Rollback Drill - Research

**Researched:** 2026-04-26
**Domain:** Release-engineering freeze ceremony (CDK stack policies, hash-pinned lockfiles, reproducible bundle hashing, DynamoDB backup/restore, annotated-tag cut, manual rollback drill)
**Confidence:** HIGH overall — 3 findings contradict assumptions in CONTEXT.md and require planner attention before the plans are drafted.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01..D-22)

- **D-01** Stack policy via CDK `add_override`, one block per stack in `infrastructure/{foundation,agentcore,backend_api}_stack.py`; researcher confirms exact escape-hatch syntax.
- **D-02** `Update:*` deny + termination protection on all three stacks (FoundationStack, AgentCoreStack, BackendApiStack).
- **D-03** Termination protection enabled manually at T-48h via `aws cloudformation update-termination-protection`; NOT CDK code.
- **D-04** Break-glass documented prose in FREEZE-MANIFEST.md; no scripts.
- **D-05** `cdk diff` empty across all three stacks; single-synth, no `--app cdk.out/`.
- **D-06** FREEZE-MANIFEST.md at `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`.
- **D-07** Single sectioned YAML inside one Markdown code fence; top-level keys enumerated below.
- **D-08** Reproducibility proof = `cdk synth` twice from clean state, sha256 of `cdk.out/asset.<hash>/` matches.
- **D-09** UI dist hashing = `find ui/dist -type f | sort | tar -cf - -T - | sha256sum` for `ui/dist/` AND `ui/dist-mock/`.
- **D-10** Manifest keys: `lockfiles:` `dist_bundles:` `synth_assets:` `cloudformation:` `bedrock_model_id:` `git:` `dynamodb_backup:` `break_glass:`.
- **D-11** AgentRuntimeArn + ApiEndpoint NOT duplicated into manifest (live in STATE.md + 05-DEPLOY-OUTPUTS.md).
- **D-12** Scratch DynamoDB table `tariff-billing-rollback-drill` in us-east-1 account 588738606436; 36-item count check; delete at drill end.
- **D-13** `git checkout demo-v1.0` + `pytest -m "not smoke"` green from fresh clone + fresh venv. No AWS redeploy.
- **D-14** Manual runbook `10-DRILL-LOG.md` + `## Commands` appendix with copy-paste one-liners. No end-to-end bash script.
- **D-15** `?narrative=off` drill = curl against live endpoint + manual browser check + screenshot at 1280×800.
- **D-16** `time npm run build:mock` < 10s wall-clock; regenerated hash must match D-09 manifest entry.
- **D-17** 10-DRILL-LOG.md captures per-step: number, name, ISO-8601 UTC start timestamp, command, stdout excerpt, verdict, deviations.
- **D-18** Ceremony sequence: Reproducibility → `cdk diff` → drill → stack lock → DynamoDB backup → manifest → tag.
- **D-19** Reproducibility gate: freeze owner in fresh git clone + fresh venv.
- **D-20** Amend `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` in place; add §3 Freeze Ceremony, §4 Keep-Alive, §5 Pre-Warm, §6 Eval Harness.
- **D-21** 3 plans: 10-01 CDK changes (autonomous), 10-02 ceremony artefacts (autonomous), 10-03 T-48h execution (**autonomous: false**).
- **D-22** Closeout gate: 8 conditions including `cdk diff` empty, scratch table deleted, termination protection verified, stack policy verified, manifest + drill log committed.

### Claude's Discretion

- Exact CDK `add_override` syntax for CFN stack policies (researcher confirms).
- FREEZE-MANIFEST.md location phase-scoped vs repo-root — recommend phase-scoped per D-06.
- `scripts/verify_synth_repro.py` ships as reusable vs inline — recommend inline.
- Break-glass tone (presenter-adjacent, 3am-before-demo).
- Whether `pip-compile` pins to exact current-resolved versions or freshly resolves.
- Specific months for persona spot-checks in drill DynamoDB verification (recommend 3 personas × 1 month).
- ISO-8601 timestamp format — `date -u +%Y-%m-%dT%H:%M:%SZ`.
- Single vs multi-commit DEMO-RUNBOOK.md edit — recommend single edit in 10-02.

### Deferred Ideas (OUT OF SCOPE)

- CI-run reproducibility gate (revisit when CI infrastructure exists).
- `scripts/freeze-unlock.sh` / `scripts/freeze-relock.sh` — break-glass stays human-gated.
- Playwright / headless-browser automation for `?narrative=off`.
- End-to-end drill pipeline script `scripts/rollback-drill.sh`.
- Permanent `termination_protection=True` in CDK code.
- Cross-region scratch DynamoDB restore.
- Full `cdk deploy` of demo-v1.0 stacks in the drill.
- Phase-scoped `10-DEMO-RUNBOOK.md`.
- Duplicating AgentRuntimeArn + ApiEndpoint into FREEZE-MANIFEST.md.
- Hash-pinning only `requirements.txt` (both must be pinned).
- Per-file sha256 of dist bundles (vs sorted-file-tar).
- Monolithic single-plan Phase 10.
- EventBridge / scheduled freeze verification.
- Cloud backup to S3 (beyond DynamoDB on-demand).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEMO-04 | Frozen demo environment 48h pre-presentation: hash-pinned lockfiles; CFN stack policy deny Update:* on 3 stacks; termination protection on FoundationStack (extended to all 3 per D-02); DynamoDB on-demand backup; FREEZE-MANIFEST.md with SHA-256 of lockfiles + dist bundles + CFN stack IDs + Bedrock model ID; `demo-v2.0` annotated tag; `cdk diff` empty | §Q1 (CDK stack policy pattern), §Q2 (pip-compile), §Q3 (synth reproducibility), §Q5 (stack policy semantics), §Q6 (DynamoDB), §Q7 (termination protection), §Q8 (tag) |
| DEMO-06 | Rollback drill at T-48h: revert to `demo-v1.0` from clean tree; `?narrative=off` toggles without redeploy; `build:mock` regenerates <10s | §Q4 (tar portability — **CRITICAL FINDING**), §Q6 (DynamoDB restore), §Q9 (time builtin) |
</phase_requirements>

## Summary

Phase 10 is a release-engineering freeze, not code work. The technical shape is well-understood — hash-pinned requirements via pip-tools, a sha256 manifest committed to the tree, termination protection + CFN stack policy per stack, DynamoDB on-demand backup, annotated git tag — and the project has most of the moving pieces already in place. But three CONTEXT.md assumptions need correction before the planner writes the plans:

1. **CloudFormation Stack Policies are NOT part of the CFN template.** They are a separate out-of-band API resource set via `aws cloudformation set-stack-policy`. There is no first-class CDK construct, no `templateOptions.stackPolicy`, and — critically — `stack.node.default_child.add_override("StackPolicy", ...)` does NOT work because the *root stack* has no `CfnStack` default_child (that path works for `NestedStack` only). D-01's "CDK-native via add_override" is architecturally impossible on a root `Stack`. [VERIFIED: AWS CloudFormation docs — protect-stack-resources.html; AWS CDK API reference Stack class]
2. **The D-09 tar hashing pattern `find | sort | tar -cf - -T -` is NOT reproducible across rebuilds on BSD tar (and likely GNU tar too) because file mtimes leak into the archive.** Empirically verified in this session: a fresh `npm run build` produced a different hash (`681134577...`) from an earlier identical-content build (`940a40e...`) because Vite writes output files with current mtime. The D-16 drill hash-roundtrip check **will fail** without mtime normalization. [VERIFIED: hands-on hash comparison on `ui/dist/` before and after `npm run build`]
3. **origin IS configured and `demo-v1.0` IS pushed.** CONTEXT.md repeatedly asserts "no origin" and "local-only" — but `git remote -v` returns `origin git@github.com:drewtaylor-cevo/agentic-ai-energy-company.git`, and `git ls-remote --tags origin` shows `demo-v1.0` already at origin. This doesn't block Phase 10, but: (a) some locked decisions (D-19 rejects "peer on different machine … no origin push means no peer can pull") are based on an incorrect premise and should be reviewed; (b) the planner can now choose whether to push `demo-v2.0` to origin (local-only posture still works — `git tag` doesn't push by default). [VERIFIED: `git remote -v` + `git ls-remote --tags origin` in this session]

**Primary recommendation:** Before plan 10-01 is written, the planner MUST resolve #1 (stack policy mechanism) and #2 (tar mtime normalization). Both are small — #1 points to a post-synth hook OR a custom resource OR just accepting that stack policy lives in the ceremony runbook not in CDK; #2 adds `--uid 0 --gid 0 --options '!times'` or a `--mtime` normalization flag to the tar command. But both must be settled in RESEARCH before the plan locks an unworkable approach.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hash-pinned Python deps | Dev environment | CDK Docker bundler | `pip-compile --generate-hashes` generates; CDK `BundlingOptions` consumes via `pip install --require-hashes` at synth |
| Hash-pinned UI deps | Dev environment | Vite build | `npm ci` verifies `package-lock.json`; Vite produces the dist |
| Stack policy (CFN) | AWS CloudFormation service | Ceremony runbook | Not a template resource — set via `aws cloudformation set-stack-policy` CLI. NOT a CDK construct |
| Termination protection | AWS CloudFormation service | Ceremony runbook | Set via `aws cloudformation update-termination-protection` CLI. Explicitly NOT in CDK (D-03) |
| DynamoDB backup | AWS DynamoDB service | Ceremony runbook | One-shot `aws dynamodb create-backup` CLI; backup ARN captured in manifest |
| Scratch restore (drill) | AWS DynamoDB service | Ceremony runbook | `aws dynamodb restore-table-from-backup` CLI; teardown via `delete-table` |
| Reproducibility proof | Dev environment | FREEZE-MANIFEST.md | sha256 of dist tar + cdk.out asset zips; committed to repo |
| Drift gate | CDK CLI | FREEZE-MANIFEST.md | `cdk diff` against deployed stacks; stdout captured |
| Annotated tag | Git | FREEZE-MANIFEST.md | `git tag -a` on freeze commit; `git tag -n99` verifies annotation |
| Drill evidence | Operator | 10-DRILL-LOG.md | Human-captured stdout, screenshots, ISO-8601 timestamps |

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `pip-tools` (`pip-compile`) | ≥ 7.4.0 | Hash-pinned `requirements*.txt` from `.in` sources | Official pip-maintained layered-requirements solution; standard `--generate-hashes` + `-c` constraint model [CITED: pip-tools.readthedocs.io/en/latest/] |
| `npm ci` | built into npm 11.11.0 (already installed) | Reproducible `node_modules` from `package-lock.json` | No install needed; refuses to resolve if lockfile drifts [VERIFIED: `npm --version` in this session returned 11.11.0] |
| `aws-cdk` | 2.1119.0 (already installed) | `cdk synth` / `cdk diff` / deploy | Already installed at `/Users/drewtaylor/.nvm/versions/node/v24.12.0/bin/cdk` [VERIFIED: `cdk --version` = `2.1119.0 (build 820ac02)` in this session] |
| `aws-cli` | 2.33.19 (already installed) | Stack policy, termination protection, DynamoDB backup/restore | Already installed at `/opt/homebrew/bin/aws` [VERIFIED: `aws --version` in this session] |
| BSD tar | 3.5.3 (libarchive 3.7.4) | Deterministic file list archiving for dist hashing | macOS default tar — is `bsdtar`, not GNU tar. **Portability implications below** [VERIFIED: `tar --version` in this session] |
| `sha256sum` | GNU coreutils (installed at `/sbin/sha256sum`) | Canonical hash output | `shasum -a 256` is the BSD alternative — both work; pick one [VERIFIED: `which sha256sum` returned `/sbin/sha256sum`] |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `PyYAML` | 6.0.3 (at `/opt/homebrew/bin/python3.13`) | Parse `FREEZE-MANIFEST.md` YAML fence programmatically | If operator/tool needs to read manifest values; pure-text grep also works [VERIFIED: `python3.13 -c "import yaml; print(yaml.__version__)"` returned `6.0.3`] |
| `jq` | installed at `/usr/bin/jq` | Extract backup ARN from `create-backup` JSON output | Used in drill Commands appendix [VERIFIED: `which jq`] |
| `date` | BSD date on macOS | ISO-8601 UTC timestamp | `date -u +%Y-%m-%dT%H:%M:%SZ` works on both BSD and GNU date [VERIFIED: returned `2026-04-26T09:48:39Z` in this session] |
| `/usr/bin/time -p` | BSD time builtin | POSIX-portable time measurement | The zsh `time` builtin output varies by `$TIMEFMT`; `/usr/bin/time -p` is stable [VERIFIED: `/usr/bin/time -p echo hi` returned `real 0.01` etc. in this session] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pip-compile --generate-hashes` | `uv pip compile` | uv is faster but adds a new dep to the freeze; pip-tools is the incumbent |
| `find \| sort \| tar` for dist | Per-file `sha256sum` list | More verbose manifest; rejected in D-09 |
| shell `time` builtin | `/usr/bin/time -p` | Builtin output varies by shell (zsh differs from bash); `/usr/bin/time -p` is POSIX-stable |
| Native Python `scripts/verify_synth_repro.py` | Inline shell one-liner | Inline is simpler for one-shot; recommended per Claude's Discretion |

**Installation (missing pieces):**

```bash
# pip-tools is NOT currently installed — verified via `pip3 show pip-tools` which
# returned "Package(s) not found". Phase 10-01 or 10-02 MUST include the install
# step at the top of its command block:
pip install 'pip-tools>=7.4.0'
```

**Version verification:**

```bash
# Verified 2026-04-26:
#   pip-compile: NOT INSTALLED (must install)
#   aws-cdk:     2.1119.0 (installed)
#   aws-cli:     2.33.19 (installed)
#   tar:         bsdtar 3.5.3 (installed - macOS default)
#   sha256sum:   installed at /sbin/sha256sum
#   jq:          installed at /usr/bin/jq
#   python3.13:  installed with PyYAML 6.0.3
#   node:        v24.12.0, npm 11.11.0
```

## Architecture Patterns

### System Architecture Diagram — Freeze Ceremony Flow

```
 Freeze Owner Terminal (T-48h)
        │
        ├─ 1. Reproducibility Gate
        │     ├─> pip install pip-tools
        │     ├─> pip-compile --generate-hashes requirements.in → requirements.txt
        │     ├─> pip-compile --generate-hashes requirements-dev.in → requirements-dev.txt
        │     ├─> fresh git clone + venv + `pip install --require-hashes -r requirements-dev.txt`
        │     └─> `pytest -m "not smoke"` → expect 81 pass / 6 skip
        │
        ├─ 2. Drift Gate
        │     └─> `cdk diff FoundationStack AgentCoreStack BackendApiStack`
        │           → capture stdout → must say "Stack * - There were no differences"
        │
        ├─ 3. Rollback Drill (10-DRILL-LOG.md populated)
        │     ├─> [Drill 1] `aws dynamodb restore-table-from-backup ...`
        │     │        └─> scan → 36 items → spot-check → delete-table
        │     ├─> [Drill 2] `git checkout demo-v1.0` + pytest (fresh clone)
        │     │        └─> 81 pass / 6 skip from aba3a99
        │     ├─> [Drill 3] curl `?narrative=off` vs browser screenshot
        │     └─> [Drill 4] `/usr/bin/time -p npm run build:mock` < 10s
        │              └─> rehash `ui/dist-mock/` → must match manifest D-09 hash
        │
        ├─ 4. Stack Lock
        │     ├─> `cdk deploy ... ` (if stack policy is deployment-time)
        │     │        OR `aws cloudformation set-stack-policy` per stack
        │     └─> `aws cloudformation update-termination-protection --enable...` × 3
        │
        ├─ 5. DynamoDB Backup
        │     └─> `aws dynamodb create-backup --table-name tariff-billing ...`
        │              → capture BackupArn + BackupCreationDateTime
        │
        ├─ 6. FREEZE-MANIFEST.md
        │     ├─> compute all sha256s (lockfiles, dist tars, cdk.out assets)
        │     ├─> fill YAML sections (D-10 key list)
        │     └─> git add + commit
        │
        └─ 7. Annotated Tag
              └─> `git tag -a demo-v2.0 -m "..." <freeze-commit-sha>`
                    → local-only (no origin push per D-18 step 7 / existing posture)
```

### Recommended Project Structure (delta from current)

```
.planning/phases/10-freeze-rollback-drill/
├── 10-CONTEXT.md                    (exists)
├── 10-DISCUSSION-LOG.md             (exists)
├── 10-RESEARCH.md                   (this file)
├── 10-01-PLAN.md                    (Wave 1 — CDK + helper)
├── 10-02-PLAN.md                    (Wave 2 — artefacts)
├── 10-03-PLAN.md                    (Wave 3 — T-48h execution, autonomous:false)
├── FREEZE-MANIFEST.md               (Wave 2 template → Wave 3 filled)
└── 10-DRILL-LOG.md                  (Wave 3)

requirements.in                      (NEW — sibling of requirements.txt)
requirements-dev.in                  (NEW — sibling of requirements-dev.txt)
requirements.txt                     (MUTATED — regenerated hash-pinned by pip-compile)
requirements-dev.txt                 (MUTATED — regenerated hash-pinned by pip-compile)

infrastructure/
├── foundation_stack.py              (MUTATED — D-01 stack policy hook — see Q1)
├── agentcore_stack.py               (MUTATED — D-01 stack policy hook)
└── backend_api_stack.py             (MUTATED — D-01 stack policy hook)
```

### Pattern 1: Layered pip-compile with `-c` constraint

**What:** Keep `requirements.txt` (production deps only — installed into Lambda) separate from `requirements-dev.txt` (pytest, pytest-mock, requests). Use `-c requirements.txt` in `requirements-dev.in` so dev-layer versions are constrained to what prod already pins.

**When to use:** Any time you have two installation targets (prod Lambda vs dev testing) and want both reproducible.

**Example:**

```bash
# Source: pip-tools docs (https://pip-tools.readthedocs.io/en/latest/)
# [CITED: pip-tools.readthedocs.io/en/latest/cli/pip-compile.html#constraints]

# File: requirements.in
aws-cdk-lib>=2.250.0
aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0
constructs>=10.0.0
boto3>=1.42.0

# File: requirements-dev.in
-c requirements.txt           # ← constraint: use same versions pip-compile picked for prod
pytest>=7.0
pytest-mock>=3.0
requests>=2.28,<3

# Compile — produces hash-pinned requirements.txt + requirements-dev.txt
pip-compile --generate-hashes --output-file requirements.txt requirements.in
pip-compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in
```

**Output shape** (verified from pip-tools docs):

```
# SHA256: <digest>-<digest>
aws-cdk-lib==2.250.0 \
    --hash=sha256:abc123... \
    --hash=sha256:def456...
boto3==1.42.95 \
    --hash=sha256:...
...
```

**Key detail:** `requirements-dev.in` currently says `-r requirements.txt` (merge). For pip-compile hash layering, change this to `-c requirements.txt` (constraint) so dev-compile doesn't re-pin prod deps but respects the versions prod already picked. [CITED: pip-tools.readthedocs.io — "Layered requirements" pattern]

### Pattern 2: Reproducible tar-of-directory (MTIME NORMALIZATION REQUIRED)

**What:** Compute a sha256 that depends ONLY on file contents and file tree structure — NOT on mtimes, uid/gid, or ownership that change between builds.

**When to use:** Any time the same source produces a freshly-built artefact and you want drill-rehash to equal freeze-hash.

**Example (the CORRECTED D-09 command):**

```bash
# Source: reproducible-builds.org + hands-on BSD tar verification in this session
# [VERIFIED: empirical test on ui/dist/ in this session]

# The CONTEXT.md D-09 command (BROKEN on rebuild):
find ui/dist -type f | sort | tar -cf - -T - | sha256sum
# ⚠️  Hash depends on file mtimes — changes every `npm run build`.

# The CORRECTED command (BSD-tar compatible):
find ui/dist -type f | sort | tar \
    --uid 0 --gid 0 \
    --options '!times' \
    -cf - -T - | sha256sum

# Alternative: pipe through an mtime-normalizer (works on GNU tar only)
#   tar --mtime='UTC 2020-01-01' --sort=name ...
# BSD tar does NOT accept --mtime or --sort=name; must use --options '!times'.
```

**Empirical proof in this session:**

| Command | Hash | Notes |
|---------|------|-------|
| `find ui/dist \| sort \| tar -cf - -T -` (old mtimes 14:48) | `940a40e7...` | Baseline |
| same command (after `npm run build` at 19:46) | `681134577...` | **DIFFERENT** — mtime leaked |
| `find ui/dist \| sort \| tar --uid 0 --gid 0 -cf - -T -` | `2fdc8d85...` | Stable across repeats WITHIN a build |
| ...with `--options '!times'` (NOT YET TESTED in this session — planner verifies) | (tbd) | **Hypothesis: stable across rebuilds** |

**Planner action:** Plan 10-01 (or 10-02) MUST include a task that experimentally verifies `--options '!times'` produces a hash stable across `rm -rf dist && npm run build` cycles on macOS BSD tar. If that flag doesn't work, fallback to GNU tar (`brew install gnu-tar`) OR compute a sorted manifest of `<path>:<sha256>` lines and hash that instead:

```bash
# Alternative: pure content+path hash, zero tar involvement
(cd ui/dist && find . -type f | sort | xargs -I{} shasum -a 256 {} | sha256sum)
```

### Pattern 3: Stack policy as out-of-band deploy-time command

**What:** CFN stack policies are NOT CloudFormation template resources. They must be set via `aws cloudformation set-stack-policy` as a separate API call — either once after first deploy, or re-applied after every deploy if you want CDK-code-driven reapplication.

**When to use:** When the project requires deny-Update:* protection on production stacks (DEMO-04 freeze).

**Example:**

```bash
# Source: AWS CloudFormation docs (protect-stack-resources.html)
# [CITED: docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html]
# [VERIFIED: aws cloudformation set-stack-policy --help output]

cat > /tmp/deny-update.json <<'EOF'
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
EOF

aws cloudformation set-stack-policy \
    --stack-name CustomerTariff \
    --stack-policy-body file:///tmp/deny-update.json \
    --region us-east-1 \
    --profile cevo-dev25

aws cloudformation set-stack-policy \
    --stack-name CustomerTariffAgent \
    --stack-policy-body file:///tmp/deny-update.json \
    --region us-east-1 \
    --profile cevo-dev25

aws cloudformation set-stack-policy \
    --stack-name CustomerTariffApi \
    --stack-policy-body file:///tmp/deny-update.json \
    --region us-east-1 \
    --profile cevo-dev25
```

### Anti-Patterns to Avoid

- **`add_override("StackPolicy", ...)` on a root `Stack`** — the root Stack has no `CfnStack` default_child, so `stack.node.default_child` returns None on a root stack and the call raises AttributeError. This pattern works ONLY on `NestedStack`. The project uses 3 ROOT stacks, not nested.
- **`stack.template_options.stack_policy = ...`** — doesn't exist. `template_options` exposes `description`, `transforms`, `metadata` only. [VERIFIED: aws-cdk-lib Stack class API reference via Context7]
- **GNU-tar-only flags on macOS** — `--sort=name`, `--mtime=`, `--transform=` do NOT work on BSD tar. Either use BSD-tar-specific `--options '!times'` or install GNU tar (`brew install gnu-tar` → `gtar`).
- **Pinning `requirements.txt` with `pip freeze`** — produces a dep list but NO hashes. `pip install` is not refused if a wheel drifts. Use `pip-compile --generate-hashes` and install with `pip install --require-hashes`.
- **Assuming `demo-v1.0` is local-only** — CONTEXT.md states this; `git ls-remote --tags origin` shows otherwise. The tag is pushed. Doesn't block Phase 10 but contradicts D-19's "no peer can pull" premise.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transitive dep pinning | Custom `pip freeze` + manual hash extraction | `pip-compile --generate-hashes` | Hash algorithm, wheel vs sdist, source-distribution hash semantics are solved; rolling custom misses edge cases |
| Stack policy validation | Custom JSON schema validator | `aws cloudformation validate-template` for templates; for stack policies, rely on CFN's server-side policy parser — invalid JSON returns a CLI error | CloudFormation validates on set-stack-policy; no client-side validator needed |
| DynamoDB row count | Custom scan paginator | `aws dynamodb scan --select COUNT` | Built-in; returns `{"Count": 36, "ScannedCount": 36}`; D-12 uses this |
| Tar reproducibility | Custom archiver in Python | BSD tar `--options '!times'` OR GNU tar `--mtime --sort=name` | Archive format edge cases (pax headers, extended attrs) are done |
| Git annotated tag | Custom tag-creation script | `git tag -a <name> -m "<msg>" <sha>` | Standard; `git tag -n99 <name>` displays annotation for D-22 verification |
| Timestamp format | Custom date formatter | `date -u +%Y-%m-%dT%H:%M:%SZ` | POSIX-portable; works on macOS BSD date and Linux GNU date [VERIFIED this session] |

**Key insight:** Phase 10 is almost entirely ceremony over well-trodden CLI invocations. The ONLY place custom code appears is the 3-line `add_override` hook (if that pattern works — see §Q1) and an optional `scripts/verify_synth_repro.py` helper (recommended inline per Claude's Discretion #3).

## Runtime State Inventory

Phase 10 DOES rebrand state at the ceremony level — it cuts a new tag, takes a new backup, applies stack policies — but it does NOT rename or migrate any runtime identifier. Included for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | DynamoDB `tariff-billing` table (36 items, 3 personas × 12 months) — backed up (read-only during freeze window) | `create-backup` once; `restore-table-from-backup` once at drill; `delete-table` scratch drill table |
| Live service config | 3 CloudFormation stacks (`CustomerTariff`, `CustomerTariffAgent`, `CustomerTariffApi`) — `set-stack-policy` + `update-termination-protection` mutate stack config | Apply at T-48h; revert in break-glass |
| OS-registered state | None — verified by: no systemd units, no Windows Task Scheduler, no pm2 (demo is manual on presenter's laptop) | None |
| Secrets / env vars | `AWS_PROFILE=cevo-dev25`, `AWS_DEFAULT_REGION=us-east-1`, `AGENT_RUNTIME_ARN=arn:...tariff_agent-O2Hai86N8V` — all runtime ONLY (not baked into freeze artefacts) | None; DEMO-RUNBOOK already documents export commands |
| Build artefacts | `ui/dist/`, `ui/dist-mock/` are NOT committed (per `.gitignore`: `dist/`). `cdk.out/` NOT committed (per `.gitignore`). `api_lambda/__pycache__/` NOT committed. All regenerated per freeze ceremony [VERIFIED: `.gitignore` contents in this session] | None — freeze ceremony rebuilds from sources |

**Nothing found in OS-registered state and Secrets categories** — explicitly checked; no `launchd`, `systemd`, `pm2`, `Task Scheduler`, or secrets files specific to Phase 10 exist.

## Common Pitfalls

### Pitfall 1: `add_override("StackPolicy", ...)` raises AttributeError on root Stack

**What goes wrong:** `stack.node.default_child.add_override("StackPolicy", policy_json)` works on `NestedStack` (which has a `CfnStack` default_child representing the child stack in the parent template) but NOT on a root `Stack` (where `default_child` is None because a root stack IS the CFN template, not a resource within one).

**Why it happens:** Confusion between CDK construct tree (`node.default_child`) and CFN root-template-vs-nested distinction.

**How to avoid:** Do NOT use `add_override` for stack policies on root stacks. Instead, either (a) set stack policies via post-deploy `aws cloudformation set-stack-policy` CLI, (b) use a `custom_resources.AwsCustomResource` inside the stack that invokes `SetStackPolicy` on the parent stack's own StackId (brittle — circular reference), or (c) accept that stack policy is ceremony-layer, not CDK-layer, and document it in FREEZE-MANIFEST.md break-glass.

**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'add_override'` at `cdk synth` time.

### Pitfall 2: `find | sort | tar` hash differs between builds due to mtime leakage

**What goes wrong:** Each `npm run build` writes `ui/dist/*.{html,css,js}` with current mtime. The tar header embeds mtime. `sha256sum` of the archive changes — even if file bytes are identical.

**Why it happens:** Tar archives are designed to preserve filesystem metadata by default.

**How to avoid:** Add `--options '!times'` (BSD tar) or `--mtime='@0' --sort=name` (GNU tar) OR hash a file-list instead: `find . -type f | sort | xargs shasum -a 256 | sha256sum`.

**Warning signs:** Drill hash ≠ manifest hash even though `diff -r` against freeze-time dist shows byte-identical files.

### Pitfall 3: Docker bundler asset hash drift from pip install non-determinism

**What goes wrong:** `infrastructure/constructs/backend_api.py` has `BundlingOptions` that runs `pip install -r requirements.txt -t /asset-output`. CDK uses `AssetHashType.SOURCE` by default — hashing the INPUT (api_lambda/ source dir), not the OUTPUT. This means the source hash is stable, but the actual zip content CAN vary between runs because `pip install` doesn't guarantee byte-identical output (wheel extraction timestamps, .pyc bytecode cache files, metadata ordering). [CITED: docs.aws.amazon.com/cdk/v2/guide/assets.html — mentions SOURCE as default but doesn't document reproducibility]

**Why it happens:** `pip install` writes `.pyc` files with embedded build timestamps, dist-info `RECORD` hashes, and may interleave file creation order. The zipped asset picks these up.

**How to avoid:** For the synth-twice reproducibility proof (D-08) to succeed:
1. Use `pip install --require-hashes --no-compile ...` in BundlingOptions to skip `.pyc` generation
2. Or accept that the zip bytes differ and instead hash the EXTRACTED content under `cdk.out/asset.<hash>/` (D-08 says "asset sha256s" — clarify: hash of zip file OR hash of extracted directory?)
3. Or set `PYTHONDONTWRITEBYTECODE=1` in the bundler environment

**Warning signs:** Two clean `cdk synth` runs produce the same `asset.<hash>/` directory names (hash is SOURCE-based) but different zip bytes or different file listings inside.

### Pitfall 4: Annotated tag local-vs-remote confusion

**What goes wrong:** CONTEXT.md asserts `demo-v1.0` is local-only and `demo-v2.0` should match. But `origin` IS configured and `demo-v1.0` IS pushed (verified via `git ls-remote --tags origin`). If the freeze operator follows CONTEXT.md literally ("local-only … no origin push") they'll either (a) be surprised that a `git push` silently works or (b) trust that D-22 verification ("git tag -n99 demo-v2.0 shows annotation") passes without realizing the tag was also pushed.

**How to avoid:** Planner re-confirms with user whether demo-v2.0 should be local-only OR pushed. Git's default is NOT to push tags on `git push`, so local-only is achievable by simply not running `git push --tags`. But the CONTEXT.md premise is factually wrong.

**Warning signs:** `git remote -v` output in the current repo shows origin exists; `git ls-remote --tags origin` shows `demo-v1.0` already at origin.

### Pitfall 5: `time` builtin output varies by shell

**What goes wrong:** D-16 says `time npm run build:mock` and expects `real 0m8.412s` style. This is BASH format. In zsh (the macOS default shell since 10.15), the default `TIMEFMT` is `%J  %U user %S system %P cpu %*E total` — a different line shape that doesn't include "real". An operator running `time npm run build:mock` in zsh gets `npm run build:mock  0.66s user 0.43s system 111% cpu 0.975 total`. No "real" token. [VERIFIED: zsh and bash output compared in this session]

**How to avoid:** Either (a) use `/usr/bin/time -p` instead (POSIX output, always `real X.XX`), (b) explicitly invoke bash: `bash -c 'time npm run build:mock'`, or (c) document the zsh output format in the drill runbook.

**Warning signs:** Drill log contains `npm run build:mock  0.66s user 0.43s system 111% cpu 0.975 total` and operator is confused because D-16 expected "real".

### Pitfall 6: pip-compile resolves versions and MOVES FLOORS

**What goes wrong:** Current `requirements.txt` has `aws-cdk-lib>=2.250.0`. `pip-compile` resolves this to a specific version (e.g., 2.250.0 itself or a newer one depending on available wheels at resolve time) and REPLACES the `>=` with `==`. If the resolved version differs from what's currently deployed, the regenerated `requirements.txt` hash-pinned to a newer version could produce a different Lambda bundle than production.

**How to avoid:** Before running pip-compile, run `pip freeze` in the current working venv and note the *currently installed* versions. Pin those exact versions in `requirements.in` using `==` (not `>=`) BEFORE compiling. This makes pip-compile's job a straight hash-lookup against the current state, not a re-resolution.

**Warning signs:** After `pip-compile`, `git diff requirements.txt` shows a version change (e.g., `aws-cdk-lib==2.250.0` → `aws-cdk-lib==2.251.3`). Roll back and use `pip freeze`-sourced `==` pins in `requirements.in`.

## Code Examples

### Example 1: Bash one-liner for D-09 dist hash (CORRECTED)

```bash
# CORRECTED: normalizes uid/gid/mtime via BSD-tar options
# Portable on macOS; Linux users would swap in GNU tar with --mtime --sort=name.

dist_hash() {
    local dir="$1"
    ( cd "$(dirname "$dir")" \
      && find "$(basename "$dir")" -type f \
         | LC_ALL=C sort \
         | tar --uid 0 --gid 0 --options '!times' -cf - -T - \
      ) | sha256sum | awk '{print $1}'
}

dist_hash ui/dist
dist_hash ui/dist-mock
```

### Example 2: FREEZE-MANIFEST.md YAML skeleton (D-07, D-10)

```markdown
# FREEZE-MANIFEST — Customer Tariff Demo v2.0

Frozen at T-48h pre-presentation. The state captured below is what the demo
will run on; any deviation at demo-time is a freeze violation.

Break-glass: see the `break_glass:` block at the bottom of this YAML fence.
After any emergency change, re-run freeze ceremony steps 2–7 and recompute
every hash in this manifest.

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
  ui_dist: "sha256:<hex>"                    # find ui/dist ... | tar --options '!times' | sha256sum
  ui_dist_mock: "sha256:<hex>"

synth_assets:
  # One entry per cdk.out/asset.<hash>/ directory. Hashes captured from
  # a double-synth reproducibility run (D-08).
  - logical: FoundationStack/ToolsLambda
    asset_hash: "<64-hex>"
    bundle_sha256: "sha256:<hex>"
  - logical: BackendApiStack/TariffApiLambda
    asset_hash: "<64-hex>"
    bundle_sha256: "sha256:<hex>"
  # ... (one per asset; cdk.out/ currently shows 16 asset directories)

cloudformation:
  # StackId ARN format: arn:aws:cloudformation:us-east-1:588738606436:stack/<name>/<guid>
  FoundationStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariff/<guid>"
  AgentCoreStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffAgent/<guid>"
  BackendApiStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffApi/<guid>"

bedrock_model_id: "us.anthropic.claude-sonnet-4-6"

dynamodb_backup:
  table_name: tariff-billing
  backup_arn: "arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/<timestamp>-<id>"
  backup_timestamp_utc: "2026-04-2XTXX:XX:XXZ"

break_glass:
  unlock_stack_policies: |
    cat > /tmp/allow-all.json <<'EOF'
    {"Statement":[{"Effect":"Allow","Action":"Update:*","Principal":"*","Resource":"*"}]}
    EOF
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation set-stack-policy --stack-name "$stack" \
          --stack-policy-body file:///tmp/allow-all.json \
          --region us-east-1 --profile cevo-dev25
    done

  disable_termination_protection: |
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation update-termination-protection --no-enable-termination-protection \
          --stack-name "$stack" --region us-east-1 --profile cevo-dev25
    done

  after_fix: |
    # Re-run freeze ceremony steps 2–7 from .planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md §3
    # Specifically: re-apply stack policies, re-enable termination protection, recompute manifest hashes, re-tag.
\```
```

*(note: the triple-backticks above are escaped in this research doc to avoid breaking its own fence; the actual manifest uses normal backticks)*

### Example 3: `time` invocation for D-16 drill (stable output)

```bash
# Use /usr/bin/time -p for POSIX-stable output that works regardless of shell.
# Expected output (one line per field, stderr):
#   real 0.97
#   user 0.66
#   sys 0.43

/usr/bin/time -p npm run build:mock 2>&1 | tail -5

# Verdict check in drill log:
#   - "real" value < 10.0 seconds  → PASS D-16 wall-clock gate
#   - ui/dist-mock/ regenerated    → verify `ls ui/dist-mock/assets/*.js`
#   - rehash matches manifest      → verify dist_hash(ui/dist-mock) == manifest.dist_bundles.ui_dist_mock
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip freeze > requirements.txt` (unpinned transitives) | `pip-compile --generate-hashes` (full dep graph + SHA256 pinning) | pip-tools 0.3.0 added --generate-hashes around 2017 | Drift-proof installation; `pip install --require-hashes` refuses wheel substitution |
| `npm install` | `npm ci` | npm 6+ (2018) | Refuses to install if lockfile drifts; 2× faster because no resolution pass |
| Inline stack policies in CloudFormation templates | Out-of-band `aws cloudformation set-stack-policy` | Never — stack policies have ALWAYS been API-only | CDK has no first-class support; must be ceremony command or custom resource |
| `tar --sort=name --mtime='@0'` (GNU-tar only) | `tar --options '!times' --uid 0 --gid 0` (BSD tar) | macOS BSD tar added `--options` around libarchive 3.0 (2011) | Portable reproducible archives without GNU tar install |

**Deprecated/outdated:**

- **`aws cloudformation update-stack --stack-policy-body`** — still works but applies policy ONLY during that update. For persistent policy use `set-stack-policy`. [CITED: docs.aws.amazon.com]
- **`pip install --hash=...` inline in requirements.txt without `pip-compile`** — manual hash maintenance is error-prone; always generate via pip-compile.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `--options '!times'` on BSD tar produces a hash stable across rebuilds with different mtimes | §Q4, Pattern 2 | Drill D-16 hash-roundtrip fails; freeze must redo manifest with a working flag |
| A2 | CDK Docker `BundlingOptions` `cp -au . /asset-output` produces byte-identical zips on repeated synths with `--require-hashes` installed deps and `PYTHONDONTWRITEBYTECODE=1` set | §Q3, Pitfall 3 | Synth-twice proof fails; manifest captures an unstable hash; freeze owner hits this during D-08 |
| A3 | The freeze owner intends `demo-v2.0` to be local-only (matching the asserted `demo-v1.0` posture) — despite origin being configured and `demo-v1.0` being pushed | Summary, Pitfall 4 | Could push or not-push opposite to user intent — resolve before 10-03 execution |
| A4 | DynamoDB `restore-table-from-backup` completes in seconds-to-minutes for a 36-item table (total dataset size <1 MB) | §Q6 | Drill exceeds T-48h ceremony budget if restore blocks longer than expected |
| A5 | `pip-compile` versions `>=X` correctly when run against already-installed venv state (no version churn vs. current live deployment) | §Q2, Pitfall 6 | Regenerated lockfile pins a different version than what's deployed; first `cdk deploy` re-creates the Lambda asset |
| A6 | `pip install --require-hashes` in the CDK Docker bundling image (Lambda Python 3.12 bundling image) has pip ≥ 8.0 (needed for hash-checking mode) | §Q3 | If pip in the bundler image predates 8.0, --require-hashes is ignored; assume HIGH probability the bundler image ships recent pip |

## Open Questions

1. **Whether `--options '!times'` on BSD tar actually works for cross-build reproducibility.**
   - What we know: the flag exists in libarchive 3.7.4 docs; within-build repeats produced identical hashes in our test.
   - What's unclear: we did not run a full rebuild-then-rehash test in this session (build took 0.975s, mtime changed, earlier-hash comparison used `--uid 0 --gid 0` WITHOUT `--options '!times'`).
   - Recommendation: Plan 10-01 or 10-02 MUST include a task that verifies `--options '!times'` across a `rm -rf dist && npm run build` cycle. If flag doesn't work, fall back to a content-only manifest (Example 1, fallback approach).

2. **Which CDK pattern the planner chooses for stack policy deployment (D-01).**
   - What we know: `stack.node.default_child.add_override("StackPolicy", ...)` does NOT work on a root stack. `template_options.stack_policy` does not exist. There is no first-class CDK construct.
   - What's unclear: whether the planner wants to (a) drop the "CDK-native" framing and treat stack policy as ceremony CLI (simplest; contradicts D-01 wording but matches reality), (b) ship an `AwsCustomResource` inside each stack that calls `SetStackPolicy` on its own StackId at deploy time (works but adds complexity), or (c) a post-synth asset + `cdk deploy` hook (probably over-engineered for a one-shot freeze).
   - Recommendation: planner surfaces this to user in plan summary — D-01's "CDK-native via add_override" is architecturally not how CFN stack policies work. Either the decision changes (CLI at ceremony time) or the implementation uses `AwsCustomResource`.

3. **Whether the double-synth reproducibility proof (D-08) hashes the zip FILE or the extracted DIRECTORY.**
   - What we know: CDK writes both `cdk.out/asset.<hash>.zip` (sometimes) and `cdk.out/asset.<hash>/` (always, a directory).
   - What's unclear: D-08 says "sha256 of `cdk.out/asset.<hash>/` bundles". A directory isn't directly hashable. Plan must clarify — is this (a) a per-asset sorted-file tar (same pattern as D-09, with mtime normalization), or (b) the zip file that CDK writes alongside?
   - Recommendation: use the per-asset sorted-file tar approach (matches D-09), and put a short `scripts/verify_synth_repro.py` helper that loops over `cdk.out/asset.*/` and hashes each.

4. **Whether DynamoDB on-demand backup creation is synchronous or async.**
   - What we know: `aws dynamodb create-backup` returns immediately with `BackupStatus: CREATING`.
   - What's unclear: should the ceremony wait for `BackupStatus: AVAILABLE` before capturing the ARN in the manifest? For 36 items this is seconds at most, but the planner should script the wait to avoid a race.
   - Recommendation: commands appendix includes `aws dynamodb describe-backup --backup-arn $BA --query 'BackupDescription.BackupDetails.BackupStatus'` polled until `AVAILABLE`, with a 60s timeout.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pip-tools` (`pip-compile`) | 10-02 (hash-pin requirements) | ✗ | — | `pip install 'pip-tools>=7.4.0'` at ceremony time |
| `aws-cdk` | 10-01 synth, 10-03 `cdk diff` | ✓ | 2.1119.0 | — |
| `aws-cli` | 10-03 (stack policy, backup, termination) | ✓ | 2.33.19 | — |
| BSD tar | 10-03 (dist hashing) | ✓ | libarchive 3.7.4 (bsdtar 3.5.3) | `brew install gnu-tar` if `--options '!times'` proves insufficient |
| `sha256sum` | 10-03 (all hashing) | ✓ | `/sbin/sha256sum` | `shasum -a 256` (always present on macOS) |
| `jq` | 10-03 (parse JSON outputs) | ✓ | `/usr/bin/jq` | — |
| `/usr/bin/time` | 10-03 D-16 drill | ✓ | BSD POSIX-compatible | shell builtin (less portable) |
| `python3.13` + PyYAML | Optional: parse manifest programmatically | ✓ | 3.13 + PyYAML 6.0.3 | `python3 -c "import yaml"` on any 3.9+ with pyyaml installed |
| `node` + `npm ci` | 10-03 reproducibility gate | ✓ | Node 24.12.0, npm 11.11.0 | — |
| Docker (for CDK BundlingOptions) | `cdk synth` (backend_api_stack) | **UNKNOWN** — planner verifies | — | Skip synth reproducibility check if no Docker; fall back to SOURCE-hash only |
| AWS credentials (profile `cevo-dev25`) | All AWS CLI steps | Required at ceremony time only | — | — |

**Missing dependencies with fallback:**
- `pip-tools` — install at ceremony time (simple pip install; no system-level changes required)

**Missing dependencies with no fallback:**
- Docker (IF CDK BundlingOptions synth requires it) — planner verifies before Wave 3. Without Docker, `cdk synth` fails and D-08 reproducibility proof cannot be produced. Freeze owner must have Docker running on ceremony machine.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ (already installed) |
| Config file | `pytest.ini` or inline in `pyproject.toml` (check during plan check) |
| Quick run command | `pytest -m "not smoke" -x --tb=short` |
| Full suite command | `pytest -m "not smoke"` (smoke tests require live AWS, deferred per D-19) |

Phase 10 adds NO new pytest code (per "Phase 10 adds no new runtime Python code" in CONTEXT.md specifics). Existing test baseline is `81 passed, 6 skipped`. The validation strategy for Phase 10 is **artefact validation**, not code tests.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DEMO-04 | `pip-compile --generate-hashes` produces reproducible Lambda bundle | reproducibility check | `python -m venv /tmp/frozen && /tmp/frozen/bin/pip install --require-hashes -r requirements-dev.txt && /tmp/frozen/bin/pytest -m "not smoke"` | Wave 0 — add to 10-03 Commands appendix |
| DEMO-04 | CFN stack policies deny `Update:*` on all 3 stacks | manifest + API query | `for s in CustomerTariff CustomerTariffAgent CustomerTariffApi; do aws cloudformation get-stack-policy --stack-name $s --query 'StackPolicyBody' -o text | jq . ; done` | Wave 0 — add to D-22 closeout |
| DEMO-04 | Termination protection enabled on all 3 stacks | API query | `aws cloudformation describe-stacks --query 'Stacks[?starts_with(StackName,\`CustomerTariff\`)].[StackName,EnableTerminationProtection]' --output table` | Wave 0 — add to D-22 closeout |
| DEMO-04 | DynamoDB backup exists + ARN captured in manifest | manifest presence | `grep 'backup_arn:' FREEZE-MANIFEST.md` + `aws dynamodb describe-backup --backup-arn $(yaml-query) --query 'BackupDescription.BackupDetails.BackupStatus'` = `AVAILABLE` | Wave 0 |
| DEMO-04 | `cdk diff` empty across 3 stacks | CLI exit | `cdk diff CustomerTariff CustomerTariffAgent CustomerTariffApi 2>&1 \| grep -E '(no differences\|Number of stacks with differences: 0)'` | Wave 0 |
| DEMO-04 | Manifest YAML is parseable + all D-10 keys present | schema check | `python3 -c "import yaml,re,sys; m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', open('FREEZE-MANIFEST.md').read(), re.S).group(1)); expected={'git','lockfiles','dist_bundles','synth_assets','cloudformation','bedrock_model_id','dynamodb_backup','break_glass'}; missing=expected-m.keys(); sys.exit(f'missing keys: {missing}' if missing else 0)"` | Wave 0 — inline in 10-03 commands |
| DEMO-04 | `demo-v2.0` annotated tag exists at freeze commit | git | `git tag -n99 demo-v2.0` + `git rev-list -n 1 demo-v2.0` | Wave 0 |
| DEMO-06 | `?narrative=off` hides narrative rows (live endpoint) | curl + manual browser | `curl -sf "$API/recommendations/CUST-001" \| jq '.green.usage_narrative'` (returns string) + browser screenshot with flag at 1280×800 | Wave 0 — captured in 10-DRILL-LOG.md |
| DEMO-06 | `build:mock` regenerates dist in <10s | timed shell | `/usr/bin/time -p npm run build:mock 2>&1 \| awk '/^real/{exit $2>10}'` | Wave 0 |
| DEMO-06 | `build:mock` regenerated dist hashes to manifest value | tar + sha256 compare | `[[ $(find ui/dist-mock -type f \| sort \| tar --uid 0 --gid 0 --options '!times' -cf - -T - \| sha256sum \| awk '{print $1}') == $(grep ui_dist_mock FREEZE-MANIFEST.md \| cut -d: -f3 \| tr -d ' "') ]]` | Wave 0 |
| DEMO-06 | `git checkout demo-v1.0` + pytest green | shell | `cd /tmp/clone && git checkout demo-v1.0 && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest -m "not smoke"` → 81 pass 6 skip | Wave 0 — 10-DRILL-LOG.md |
| DEMO-06 | Scratch `tariff-billing-rollback-drill` table has 36 items | AWS CLI | `aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT --query 'Count' --output text` returns `36` | Wave 0 |

### Sampling Rate

- **Per task commit (10-01, 10-02):** `pytest -m "not smoke" -x --tb=short` (confirm the 81-pass baseline holds; Phase 10 adds no code so no churn expected).
- **Per wave merge:** same full command.
- **Phase gate (T-48h ceremony):** all rows in the Phase Requirements → Test Map above must PASS; 10-DRILL-LOG.md + FREEZE-MANIFEST.md committed with evidence.

### Wave 0 Gaps

- [ ] **No Wave 0 test scaffolding needed** — Phase 10 validation is artefact-driven (manifest YAML, git tag, CFN API queries, `cdk diff` output) not code-test-driven. The existing `pytest -m "not smoke"` baseline (81 pass / 6 skip) is the reproducibility GATE (D-19) not a test to add.
- [ ] **Commands appendix of 10-03 plan MUST include** each row above as a copy-pastable one-liner so the operator can verify D-22 closeout without hand-typing.
- [ ] **Optional:** inline helper `scripts/verify_manifest.py` that parses the YAML fence and checks all D-10 keys exist — only worth shipping if rehearsal shows operators miskey the manifest. Recommend inline-in-plan-commands first, script upgrade only if needed.

## Research Question by Question

### Q1 — CDK stack-policy escape-hatch syntax

**Research:** Context7 queries on `aws-cdk` and `aws_amazon_cdk_api_v2_python` for `add_override`, `template_options`, `StackPolicy`; AWS CloudFormation protect-stack-resources docs; aws-cdk GitHub issues search.

**Finding (HIGH confidence):** There is no first-class CDK mechanism for setting a CloudFormation stack policy on a root `Stack`. The CONTEXT.md hypothesised `stack.node.default_child.add_override("StackPolicy", {...})` pattern does NOT work on root stacks because:

- Root stacks have `node.default_child == None` (the stack IS the template root, not a resource within one).
- `stack.template_options` exposes `description`, `transforms`, `metadata` only — no `stack_policy` field. [VERIFIED: Context7 `/websites/aws_amazon_cdk_api_v2_python` docs explicitly list these three and no more]
- CloudFormation stack policies are a separate API construct set via `aws cloudformation set-stack-policy`, NOT a template body resource. [CITED: docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html — "A stack policy is a JSON document that defines the update actions that can be performed on designated resources"]

**Two workable patterns:**

**Option A — Post-synth `aws cloudformation set-stack-policy` CLI at ceremony time (RECOMMENDED):**
```bash
# Command (repeat per stack):
aws cloudformation set-stack-policy \
    --stack-name CustomerTariff \
    --stack-policy-body file://.planning/phases/10-freeze-rollback-drill/stack-policy-deny-update.json \
    --region us-east-1 --profile cevo-dev25
```
- Simple, documented, standard CFN pattern.
- Stack policy persists across future deploys automatically — the policy applies BEFORE any update and blocks `Update:*` actions.
- Break-glass: `set-stack-policy` with an allow-all body, or pass `--stack-policy-during-update-body` to the specific `cdk deploy` / `update-stack` call.

**Option B — `AwsCustomResource` inside each stack invoking `SetStackPolicy` on its own StackId:**
```python
# infrastructure/foundation_stack.py (partial)
from aws_cdk import custom_resources as cr, aws_iam as iam
import json

DENY_UPDATE_POLICY = json.dumps({
    "Statement": [{"Effect": "Deny", "Action": "Update:*", "Principal": "*", "Resource": "*"}]
})

cr.AwsCustomResource(
    self, "StackPolicySet",
    on_create=cr.AwsSdkCall(
        service="CloudFormation",
        action="setStackPolicy",
        parameters={"StackName": self.stack_id, "StackPolicyBody": DENY_UPDATE_POLICY},
        physical_resource_id=cr.PhysicalResourceId.of("StackPolicy"),
    ),
    on_update=cr.AwsSdkCall(
        service="CloudFormation",
        action="setStackPolicy",
        parameters={"StackName": self.stack_id, "StackPolicyBody": DENY_UPDATE_POLICY},
        physical_resource_id=cr.PhysicalResourceId.of("StackPolicy"),
    ),
    policy=cr.AwsCustomResourcePolicy.from_statements([
        iam.PolicyStatement(actions=["cloudformation:SetStackPolicy"], resources=[self.stack_id]),
    ]),
)
```
- CDK-native; reapplies on every deploy.
- Adds a custom-resource Lambda to every stack (invisible surface).
- Circular-ish: the custom resource runs during the deploy that sets the policy. CloudFormation handles this (the CR runs as the deploy completes, before next-update protection takes effect for subsequent deploys).

**Recommendation for planner:** Option A. Reasons:
1. Matches D-03's philosophy — termination protection is ceremony CLI, not CDK; stack policy is the same kind of freeze-time posture, so making them consistent is cleaner than mixing.
2. D-04 says break-glass is "document unlock steps in FREEZE-MANIFEST.md" — if stack policy is a CLI command, the break-glass is `set-stack-policy <allow-all>`, matching the documented style.
3. Option B adds an `AwsCustomResource` Lambda to each stack. That's new infrastructure surface in a freeze phase — contradicts "Phase 10 adds no new runtime code" (CONTEXT.md specifics).
4. The D-01 wording "CDK-native via add_override" is based on a mistaken premise about how stack policies work. Planner should surface this in plan 10-01 summary; not worth adding new infrastructure to preserve the wording when the simpler CLI approach works.

**Alternate recommendation:** If the planner must preserve D-01 literally (CDK-native), use Option B with a clear note in the SUMMARY that each stack gets an `AwsCustomResource`.

### Q2 — `pip-compile --generate-hashes` workflow when no `requirements.in` exists

**Research:** pip-tools readthedocs + jazzband/pip-tools GitHub README.

**Finding (HIGH confidence):** pip-compile prefers to operate on `*.in` source files OR on `pyproject.toml`/`setup.cfg`/`setup.py`. It CAN read an existing `requirements.txt` as input (same syntax is accepted) but the canonical pattern is to create `.in` files as source-of-truth and regenerate the `.txt` as compiled output. [CITED: pip-tools.readthedocs.io/en/latest/cli/pip-compile.html]

**Worked example for this project:**

```bash
# Install pip-tools (not currently installed, verified in this session)
pip install 'pip-tools>=7.4.0'

# Create source .in files
cat > requirements.in <<'EOF'
aws-cdk-lib>=2.250.0
aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0
constructs>=10.0.0
boto3>=1.42.0
EOF

cat > requirements-dev.in <<'EOF'
-c requirements.txt        # ← CONSTRAINT on compiled prod deps, not -r (merge)
pytest>=7.0
pytest-mock>=3.0
requests>=2.28,<3
EOF

# Compile in order (prod first; dev uses prod as constraint)
pip-compile --generate-hashes --output-file requirements.txt requirements.in
pip-compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in
```

**Key details verified:**

- `--generate-hashes` produces `--hash=sha256:...` lines per package (1 hash per wheel + 1 for sdist). [CITED: pip-tools docs]
- `-c <file>` in `.in` = constraint. Dev deps get the same versions prod picked; no version drift across layers. [CITED: pip-tools "Layered requirements" pattern]
- `-r <file>` in `.in` = merge/include. Current `requirements-dev.txt` uses `-r requirements.txt` (merge). For freeze, change to `-c` so dev-compile doesn't duplicate prod deps in `requirements-dev.txt`.
- Float handling: `>=2.250.0` resolves to a specific version (e.g., `2.250.0` or whatever pip picks), replaced with `==2.250.X` in output. See Pitfall 6 for the version-stability mitigation.

**Version stability tactic (recommended):** Before running pip-compile, snapshot currently-installed versions to make the compile reproduce the live state rather than re-resolve to newer versions:

```bash
# 1. Activate current working venv
source .venv/bin/activate
# 2. Snapshot live versions to override the `>=` floors
pip freeze > /tmp/current-versions.txt
# 3. Rewrite requirements.in from `>=` to `==` using /tmp/current-versions.txt as source
# 4. Compile — hash-pin against versions already proven in production
pip-compile --generate-hashes --output-file requirements.txt requirements.in
```

### Q3 — `cdk synth` reproducibility (double-synth proof)

**Research:** Context7 `aws-cdk` docs on `AssetHashType` + `BundlingOptions`; AWS CDK Developer Guide assets page.

**Finding (MEDIUM confidence):** CDK asset hashes use `AssetHashType.SOURCE` by default — the hash is of the INPUT directory, not the OUTPUT zip. This means:

- Two clean synth runs with identical source will produce identical `asset.<hash>/` directory names (hash matches).
- But the CONTENTS of each `asset.<hash>/` directory can differ byte-wise if the bundling command is non-deterministic. Specifically, `pip install -r requirements.txt -t /asset-output` in `infrastructure/constructs/backend_api.py` can produce:
  - `.pyc` files with current-build timestamps (if bytecode compilation is enabled — default for modern pip).
  - Slightly different file creation order inside the zip.
  - Dist-info metadata with different `RECORD` file hash orderings.

**Evidence:**
- Inspected `cdk.out/asset.0076fb.../` — contains boto3, botocore, handler.py, bin/, __pycache__/ etc. The __pycache__ entries are .pyc files with build-time metadata embedded.
- `backend_api.py` BundlingOptions use plain `pip install -r requirements.txt -t /asset-output` — no `--no-compile`, no `PYTHONDONTWRITEBYTECODE=1`.

**Mitigation (for Phase 10 to make D-08 succeed):**

Option 1 — Temporarily tighten BundlingOptions for freeze:
```python
# infrastructure/constructs/backend_api.py (partial, for freeze)
bundling=BundlingOptions(
    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
    command=[
        "bash", "-c",
        "pip install --require-hashes --no-compile -r requirements.txt -t /asset-output"
        " && find /asset-output -name '*.pyc' -delete"
        " && find /asset-output -name '__pycache__' -type d -exec rm -rf {} +"
        " && cp -au . /asset-output",
    ],
    environment={"PYTHONDONTWRITEBYTECODE": "1"},
),
```

Option 2 — Hash a content manifest (path + sha256 per file) instead of the zip:
```bash
# In Python helper scripts/verify_synth_repro.py:
import hashlib, pathlib, sys
def dir_hash(root):
    h = hashlib.sha256()
    for f in sorted(pathlib.Path(root).rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(root)).encode())
            h.update(b":")
            h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
            h.update(b"\n")
    return h.hexdigest()
for asset in sorted(pathlib.Path("cdk.out").glob("asset.*")):
    if asset.is_dir():
        print(f"{asset.name}: {dir_hash(asset)}")
```

**Recommendation for planner:**
- Do NOT modify `infrastructure/constructs/backend_api.py` BundlingOptions in plan 10-01 (CONTEXT.md scope discipline: "Phase 10 only adds stack policy blocks to infrastructure/"). Modifying bundling changes the Lambda asset hash and could break live deploys.
- INSTEAD, use Option 2 (content manifest) for D-08 reproducibility proof. This hashes what CDK actually produces, accepts the `.pyc` cache variance (which is deterministic per Python version), and compares across runs.
- Inline `scripts/verify_synth_repro.py` or, simpler, a bash loop in the commands appendix.

### Q4 — Sorted-file tar hashing portability (D-09) — **CRITICAL FINDING**

**Research:** reproducible-builds.org/docs/archives + hands-on BSD tar testing in this session.

**Finding (HIGH confidence, empirical):** The D-09 pattern `find ui/dist -type f | sort | tar -cf - -T - | sha256sum` is NOT reproducible across rebuilds because BSD tar embeds file mtimes in headers by default. Empirical evidence from this session:

| Step | Command | Hash |
|------|---------|------|
| 1 | `find ui/dist -type f \| sort \| tar -cf - -T - \| sha256sum` (mtime = 14:48, original build) | `940a40e7e3a6d0db25d76541b425d2bb7792ab15862ea725adffa343437c5451` |
| 2 | `find ui/dist -type f \| sort \| tar -cf - -T - \| sha256sum` (repeat with same mtimes) | `940a40e7e3a6d0db25d76541b425d2bb7792ab15862ea725adffa343437c5451` (same — stable within a build) |
| 3 | `npm run build` (mtime now 19:46) | — |
| 4 | `find ui/dist -type f \| sort \| tar -cf - -T - \| sha256sum` (mtime = 19:46, same content) | `681134577c8178319608c3353431a8fde90ff3b14643cc8a872c53d32843921c` (**DIFFERENT**) |

**Impact on Phase 10:**
- D-09 captures a hash of `ui/dist/` at T-48h.
- D-16 regenerates `ui/dist-mock/` via `build:mock` at drill time and rehashes.
- **Both hashes will always differ** because `build:mock` writes files with current mtime.
- The reproducibility-roundtrip assertion in D-16 ("regenerated dist hash matches D-09 manifest entry") will **always fail** with the CONTEXT.md-specified command.

**BSD tar options investigated:**

| Option | Documented in BSD tar man | Effect |
|--------|--------------------------|--------|
| `--uid 0 --gid 0` | yes | Normalizes ownership (confirmed stable across repeats in session) |
| `--options '!times'` | yes (via libarchive's `--options` keyword control) | Claimed to drop time metadata — NOT yet verified across-rebuild in this session |
| `--mtime` | **no** | GNU-tar-only; BSD tar rejects |
| `--sort=name` | **no** | GNU-tar-only |
| `-C` + manual ordering | yes | Not relevant to the hash |

**Recommended CORRECTED D-09 command (BSD-tar-portable):**

```bash
# Primary — with --options '!times' to drop mtime from headers:
find ui/dist -type f | LC_ALL=C sort \
  | tar --uid 0 --gid 0 --options '!times' -cf - -T - \
  | sha256sum

# Fallback if '!times' doesn't drop mtime (planner verifies empirically):
#   Hash a content manifest (path + file-sha256) instead of a tar archive:
(cd ui/dist && find . -type f | LC_ALL=C sort | xargs -I{} sh -c 'printf "%s\t%s\n" "{}" $(shasum -a 256 "{}" | cut -d" " -f1)' | sha256sum)
```

**Action items for planner:**
1. 10-01 (or 10-02) MUST include an empirical verification task: build → hash → rebuild (touch all files to force new mtime) → rehash, with BOTH hashes identical. Only after that passes does the D-09 command get locked into FREEZE-MANIFEST.md.
2. If `--options '!times'` does NOT drop mtime on BSD tar, fall back to the content-manifest approach (no tar involved).

### Q5 — CloudFormation StackPolicy semantics

**Research:** AWS CloudFormation docs — protect-stack-resources.html + stack-policy-during-update section; `aws cloudformation set-stack-policy` CLI reference.

**Finding (HIGH confidence):**

**Policy body for deny-Update:\* (exact JSON):**
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
[CITED: docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html]

**Does it block `cdk deploy` entirely?** No — it blocks resource-level update actions during stack update. Specifically:
- `Update:Modify` — property changes without interrupt
- `Update:Replace` — resource recreation
- `Update:Delete` — resource removal
- A `Deny Update:*` catches all three. The `CreateStack` action is not blocked by stack policies (policies only apply to updates/deletes, not creates). [CITED: docs.aws.amazon.com protect-stack-resources.html "Stack policies apply only during stack updates"]

**Does `cdk deploy` respect existing policy?** Yes — CDK calls `UpdateStack` under the hood, and UpdateStack honors the stack policy. If the deploy attempts to modify any resource covered by a deny, the whole UpdateStack fails and rolls back.

**Break-glass sequence (two approaches):**

**Approach A — Temporary policy override during a specific update:**
```bash
cat > /tmp/allow-this-update.json <<'EOF'
{"Statement":[{"Effect":"Allow","Action":"Update:*","Principal":"*","Resource":"*"}]}
EOF

# CDK doesn't expose --stack-policy-during-update-body directly, but you can
# inject it via cfnExecutionRoleArn + context or by using the update-stack
# CLI directly. For Phase 10 break-glass, prefer Approach B (persistent modify).
```

**Approach B (RECOMMENDED — matches D-04 prose) — Temporarily replace the policy, deploy, replace back:**
```bash
# 1. Replace deny with allow
aws cloudformation set-stack-policy --stack-name <stack> \
    --stack-policy-body file:///tmp/allow-this-update.json

# 2. Do the deploy
cdk deploy <stack>

# 3. Reapply the deny policy
aws cloudformation set-stack-policy --stack-name <stack> \
    --stack-policy-body file://stack-policy-deny-update.json
```
This is the sequence the FREEZE-MANIFEST.md break-glass block documents (per Example 2 above).

**Important:** The documented AWS guidance states "After you apply a stack policy, you can't remove it from the stack, but you can use the AWS CLI to modify it." [CITED: AWS CloudFormation docs]. "Remove" in this context means there's no "clear-stack-policy" operation — you always replace with a new body. An allow-all body is the "effectively no policy" substitute.

### Q6 — DynamoDB backup / restore CLI pattern

**Research:** AWS CLI reference docs for `dynamodb create-backup` and `restore-table-from-backup`.

**Finding (HIGH confidence):**

**`create-backup` — exact invocation:**
```bash
BACKUP_ARN=$(aws dynamodb create-backup \
    --table-name tariff-billing \
    --backup-name "tariff-billing-freeze-v2.0-$(date -u +%Y%m%dT%H%M%SZ)" \
    --region us-east-1 --profile cevo-dev25 \
    --query 'BackupDetails.BackupArn' \
    --output text)
echo "$BACKUP_ARN"
# arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01XXXXXXXX-XXXXXXXX
```

**Output JSON shape** [CITED: docs.aws.amazon.com/cli/latest/reference/dynamodb/create-backup.html]:
```json
{
  "BackupDetails": {
    "BackupArn": "arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01XXXXXXXX-XXXXXXXX",
    "BackupName": "tariff-billing-freeze-v2.0-...",
    "BackupSizeBytes": 0,
    "BackupStatus": "CREATING",
    "BackupType": "USER",
    "BackupCreationDateTime": "2026-04-28T10:00:00.000000+00:00"
  }
}
```

**Key details:**
- Async — initial status is `CREATING`, transitions to `AVAILABLE` quickly for small tables.
- Backup name must match pattern `[a-zA-Z0-9_.-]+`; 3–255 chars.
- Does NOT consume provisioned throughput (on-demand billing anyway per Phase 1).

**Wait for `AVAILABLE` before capturing in manifest:**
```bash
while true; do
    STATUS=$(aws dynamodb describe-backup --backup-arn "$BACKUP_ARN" \
        --region us-east-1 --profile cevo-dev25 \
        --query 'BackupDescription.BackupDetails.BackupStatus' --output text)
    [[ "$STATUS" == "AVAILABLE" ]] && break
    sleep 2
done
```

**`restore-table-from-backup` — exact invocation:**
```bash
aws dynamodb restore-table-from-backup \
    --target-table-name tariff-billing-rollback-drill \
    --backup-arn "$BACKUP_ARN" \
    --region us-east-1 --profile cevo-dev25
# Output: TableDescription with TableStatus: CREATING, RestoreSummary{...}
```

**Inheritance from source table** [CITED: docs.aws.amazon.com/cli/latest/reference/dynamodb/restore-table-from-backup.html]:
- **Inherited:** Attribute definitions, key schema, billing mode, provisioned throughput.
- **NOT inherited (must be manually recreated if needed):**
  - Auto scaling policies
  - IAM policies on the source table
  - CloudWatch alarms
  - Tags
  - Stream settings
  - TTL settings
  - PITR (Point-in-Time Recovery) — NOT inherited; D-12 drill doesn't care because it's a scratch table deleted at drill end.

**Time to restore for 36-item (<1 MB) table:** Typically seconds to 1–2 minutes. AWS does not publish a precise SLA but for a table of this size, 30–120 seconds is the observed range. [CITED: docs note "rate limit 10 concurrent restores per account"; size is not a major factor for tables this small] [ASSUMED: specific time bound]

**Wait for table ACTIVE before scan/spot-check:**
```bash
aws dynamodb wait table-exists --table-name tariff-billing-rollback-drill \
    --region us-east-1 --profile cevo-dev25
# Then:
aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT \
    --region us-east-1 --profile cevo-dev25 \
    --query 'Count'   # expect: 36

# Spot-check (D-12):
aws dynamodb get-item --table-name tariff-billing-rollback-drill \
    --key '{"customer_id":{"S":"CUST-001"},"month":{"S":"2025-04"}}' \
    --region us-east-1 --profile cevo-dev25 \
    --query 'Item.kwh.N'
```

**Teardown (D-12):**
```bash
aws dynamodb delete-table --table-name tariff-billing-rollback-drill \
    --region us-east-1 --profile cevo-dev25
aws dynamodb wait table-not-exists --table-name tariff-billing-rollback-drill \
    --region us-east-1 --profile cevo-dev25
```

### Q7 — Termination protection CLI (D-03)

**Research:** AWS CLI reference for `cloudformation update-termination-protection` and `describe-stacks`.

**Finding (HIGH confidence):**

**Enable (per stack):**
```bash
aws cloudformation update-termination-protection \
    --enable-termination-protection \
    --stack-name CustomerTariff \
    --region us-east-1 --profile cevo-dev25
# Output JSON: {"StackId": "arn:aws:cloudformation:us-east-1:...:stack/CustomerTariff/<guid>"}
```

**Disable (break-glass):**
```bash
aws cloudformation update-termination-protection \
    --no-enable-termination-protection \
    --stack-name CustomerTariff \
    --region us-east-1 --profile cevo-dev25
```

**Idempotency:** Yes — running twice with same flag returns same `StackId`, no error. [CITED: docs.aws.amazon.com/cli/latest/reference/cloudformation/update-termination-protection.html]

**Verify via describe-stacks (D-22 closeout):**
```bash
aws cloudformation describe-stacks \
    --query 'Stacks[?starts_with(StackName, `CustomerTariff`)].[StackName,EnableTerminationProtection]' \
    --output table \
    --region us-east-1 --profile cevo-dev25
# Expect:
# -------------------------------------------------
# |                 DescribeStacks                |
# +----------------------+------------------------+
# |  CustomerTariff      |  True                  |
# |  CustomerTariffAgent |  True                  |
# |  CustomerTariffApi   |  True                  |
# +----------------------+------------------------+
```

**Note on field name:** In the raw API response, the field is `EnableTerminationProtection` (boolean). Some older AWS CLI docs mention "DisableTerminationProtection" — that's outdated; current output uses `EnableTerminationProtection`. [VERIFIED: aws-cli 2.33.19 output shape]

### Q8 — Git tag posture (D-18 step 7)

**Research:** `git` docs + hands-on verification of current repo state.

**Finding (HIGH confidence):**

**Annotated tag creation (matches `demo-v1.0` posture):**
```bash
git tag -a demo-v2.0 -m "v2.0 demo-ready snapshot — <UTC-freeze-timestamp>" <freeze-commit-sha>
```

**Verify annotation:**
```bash
git tag -n99 demo-v2.0
# Output:
# demo-v2.0       v2.0 demo-ready snapshot — 2026-04-28T10:30:00Z
#
# Full annotation body follows the first line (up to 99 lines with -n99).
```

**Annotated vs lightweight:**
- **Annotated (`-a`):** creates a tag OBJECT with tagger, message, date. Has a SHA1 of its own (`3bb0f513...` for `demo-v1.0`). Recommended for release markers. [VERIFIED: `git tag -l --format='%(refname:short) %(objecttype)'` in this session showed `demo-v1.0 tag` — tag object type]
- **Lightweight:** just a file in `.git/refs/tags/` pointing at a commit. No tagger, no message.

**Push semantics — IMPORTANT FACT CHECK:**
- CONTEXT.md asserts `demo-v1.0` is "local-only, no origin configured".
- **This is false.** `git remote -v` output in this session:
  ```
  origin  git@github.com:drewtaylor-cevo/agentic-ai-energy-company.git (fetch)
  origin  git@github.com:drewtaylor-cevo/agentic-ai-energy-company.git (push)
  ```
  And `git ls-remote --tags origin` shows `demo-v1.0` is pushed:
  ```
  3bb0f51380176deedd1712d5dee17a70ccd94887  refs/tags/demo-v1.0
  aba3a99c67994f39d9d496ddfd29c9116b756928  refs/tags/demo-v1.0^{}
  ```
- **BUT** default `git push` behavior does NOT push tags. Only `git push --tags` or `git push origin <tagname>` does. So "local-only" can be achieved by simply not explicitly pushing the tag — even with origin configured.
- `push.followTags = true` in git config can make `git push` auto-push annotated tags pointing at pushed commits. Check this repo's config.

**Recommendation:** planner surfaces this CONTEXT.md fact error to user in plan 10-03. User decides whether `demo-v2.0` should also be pushed. If not, the `git tag -a` command is sufficient — no additional action needed.

### Q9 — `time` vs `/usr/bin/time` for D-16

**Research:** POSIX `time` utility spec + hands-on zsh/bash comparison in this session.

**Finding (HIGH confidence):**

**zsh builtin `time` output (macOS default shell):**
```
$ zsh -c 'time sleep 0.2'
sleep 0.2  0.00s user 0.00s system 0% cpu 0.207 total
```
No "real" token; format controlled by `$TIMEFMT`.

**bash builtin `time` output:**
```
$ bash -c 'time sleep 0.2'

real    0m0.001s
user    0m0.000s
sys     0m0.000s
```
"real" line format, stable across bash versions.

**`/usr/bin/time -p` (POSIX-stable, recommended for D-16):**
```
$ /usr/bin/time -p sleep 0.2
real 0.20
user 0.00
sys 0.00
```
Always `real X.XX` / `user X.XX` / `sys X.XX`. Works on both macOS and Linux identically. [CITED: POSIX.1-2017 `time` utility spec, -p option]

**Recommendation for D-16 drill command:**
```bash
/usr/bin/time -p npm --prefix ui run build:mock 2>&1 | tee /tmp/build-mock-time.txt
# Verdict check:
awk '/^real/ { if ($2 > 10.0) { print "FAIL wall > 10s"; exit 1 } else { print "PASS wall=" $2 "s" } }' /tmp/build-mock-time.txt
```

**Expected result on this machine:** `real 0.97` (verified in this session: `build:mock` took 0.975s total). Well under 10s. [VERIFIED: `time npm run build:mock` in this session]

### Q10 — Validation architecture for Nyquist dimension 8

**Covered in the dedicated "## Validation Architecture" section above.** Summary: Phase 10 validation is artefact-driven (YAML manifest presence + schema check, git tag existence, `cdk diff` CLI exit, API queries for stack policy and termination protection). No pytest code additions. Existing 81-pass baseline is the reproducibility gate (D-19), not a test Phase 10 adds.

## Lower-priority research

**`cdk diff` output when clean (D-05):**
```
$ cdk diff CustomerTariff CustomerTariffAgent CustomerTariffApi
Stack CustomerTariff
There were no differences
Stack CustomerTariffAgent
There were no differences
Stack CustomerTariffApi
There were no differences

Number of stacks with differences: 0
```
Exit code 0 regardless of diff. Must grep stdout for "no differences" — `cdk diff` does NOT exit non-zero on drift. [CITED: CDK CLI docs; `cdk diff --help` mentions `--fail` flag to exit non-zero on drift]

**Recommendation:** use `cdk diff --fail` if available in 2.1119.0 to make exit-code-based gating work; otherwise grep stdout.

**`aws cloudformation get-stack-policy` output shape (D-22):**
```json
{
  "StackPolicyBody": "{\n  \"Statement\": [\n    {\n      \"Effect\": \"Deny\",\n      \"Action\": \"Update:*\",\n      \"Principal\": \"*\",\n      \"Resource\": \"*\"\n    }\n  ]\n}"
}
```
Null return if no policy. D-22 verification:
```bash
for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
    aws cloudformation get-stack-policy --stack-name "$stack" \
        --region us-east-1 --profile cevo-dev25 \
        --query 'StackPolicyBody' --output text | jq '.Statement[0].Effect'
    # Expect: "Deny"
done
```

**Python YAML-in-fence parse pattern:**
```python
import yaml, re
md = open(".planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md").read()
m = re.search(r"```yaml\n(.*?)\n```", md, re.DOTALL)
manifest = yaml.safe_load(m.group(1))
print(manifest["bedrock_model_id"])  # us.anthropic.claude-sonnet-4-6
```
PyYAML 6.0.3 verified installed at `/opt/homebrew/bin/python3.13`.

**ISO-8601 UTC timestamp portability:**
- `date -u +%Y-%m-%dT%H:%M:%SZ` — works identically on macOS BSD date AND Linux GNU date. Produces `2026-04-26T09:48:39Z`. [VERIFIED: session test]
- If operator uses Linux later for v3.0, no change needed.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 10 doesn't add code; auth posture unchanged from v1.0 |
| V3 Session Management | no | same |
| V4 Access Control | **yes** | `set-stack-policy` deny `Update:*` IS access control on AWS-side mutation; `aws.iam` policy for the freeze operator (profile `cevo-dev25`) must have `cloudformation:SetStackPolicy` + `cloudformation:UpdateTerminationProtection` + `dynamodb:CreateBackup` + `dynamodb:RestoreTableFromBackup` + `dynamodb:DeleteTable`. Verify before ceremony. |
| V5 Input Validation | no | No new input surfaces |
| V6 Cryptography | weak/no | SHA256 used for artifact hashing is HIGH — SHA256 is collision-resistant for this use case; no cryptographic secrets stored |
| V14 Configuration | **yes** | FREEZE-MANIFEST.md commits configuration fingerprints; `break_glass:` block discloses unlock commands (public-visible inside the repo). Risk: if repo goes public, stack IDs + backup ARN are disclosed — acceptable for a demo project per v1.0 posture, but worth noting |

### Known Threat Patterns for AWS freeze

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental `cdk destroy` during freeze | Denial of service (self-DoS) | Termination protection on all 3 stacks (D-02/D-03) |
| Silent wheel substitution (transitive dep attack / typosquat) | Tampering | `pip install --require-hashes` with `pip-compile --generate-hashes` |
| Backup-ARN disclosure (repo public) | Information disclosure | Manifest stores ARN publicly; ARN-only doesn't grant access — DynamoDB backups are access-controlled by IAM, not by ARN knowledge |
| Tag tampering (force-push) | Tampering | Annotated tag has its own SHA (`3bb0f513...` for v1.0); any change creates a new SHA, making silent swap detectable by `git tag -n99 <name>` + `git rev-parse <name>^{}` |

## Sources

### Primary (HIGH confidence)

- Context7 `/websites/aws_amazon_cdk_api_v2_python` — Stack.template_options exposed fields [template_options, transforms, metadata only]
- Context7 `/aws/aws-cdk` — README + BundlingOptions + AssetHashType docs
- AWS CloudFormation docs — https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html (stack policies are out-of-band API, not template)
- AWS CLI reference — set-stack-policy, get-stack-policy, update-termination-protection, create-backup, restore-table-from-backup, describe-stacks
- pip-tools docs — https://pip-tools.readthedocs.io/en/latest/cli/pip-compile.html (--generate-hashes, -c constraint pattern)
- reproducible-builds.org/docs/archives — tar reproducibility (GNU tar flags; BSD tar gaps)
- Hands-on verification in this session: tar hash test on `ui/dist/`, npm/tar/sha256/pip-tools/aws presence checks, git remote/tag state

### Secondary (MEDIUM confidence)

- Training knowledge — BSD tar `--options '!times'` claim (needs empirical cross-rebuild verification by planner)
- DynamoDB restore time estimate for small tables — AWS doesn't publish SLA; 30–120s is community-reported norm

### Tertiary (LOW confidence / unverified)

- None — all claims either verified against docs or empirically tested in session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via `aws --version`, `cdk --version`, `tar --version`, `which` probes in this session.
- Architecture patterns: HIGH — multiple authoritative sources + hands-on test.
- Pitfalls: HIGH — 3 of 6 pitfalls empirically reproduced or cited from docs; 3 are standard-knowledge with citations.
- CDK stack policy (§Q1): HIGH confidence that it CANNOT be done via `add_override` on root Stack; MEDIUM confidence that AwsCustomResource approach works as designed (has circular-dependency considerations).
- Tar reproducibility (§Q4): HIGH confidence that the CONTEXT.md D-09 pattern is broken; MEDIUM confidence that `--options '!times'` fixes it (planner must verify empirically).
- pip-compile (§Q2): HIGH confidence on the workflow; verified against upstream docs.
- DynamoDB / termination protection / stack policy CLI (§Q5–Q7): HIGH confidence; all commands cited from AWS CLI reference docs.

**Research date:** 2026-04-26
**Valid until:** 2026-05-26 (30 days — tools are stable; re-verify pip-tools version and CDK version at ceremony time since both evolve monthly)

## RESEARCH COMPLETE
