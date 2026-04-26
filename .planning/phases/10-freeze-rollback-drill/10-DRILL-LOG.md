---
phase: 10-freeze-rollback-drill
artifact: drill-log
verified: "<pending-UTC>"
status: pending
score: 0/5
overrides_applied: 0
created: 2026-04-26
human_verification:
  - test: "D-15 visual narrative-off proof"
    expected: "Open https://<frontend-url>/?narrative=off in desktop browser at 1280x800; visually confirm narrative rows absent in both loading and success states; capture a screenshot and attach under Step 1 Screenshot field."
    why_human: "Flag is client-side URL-param JS; HTML bundle is identical with/without the flag. Playwright/headless-browser automation was rejected in D-15 in favour of a presenter-friendly manual browser check. Screenshot is the operator's attestation."
---

# Phase 10: Rollback Drill Log

Drill evidence populated at T-48h per DEMO-RUNBOOK.md section 7 step 3. Steps
are ordered by **recovery speed** (cheapest lever first) so the operator under
pressure sees the cheapest recovery option at the top.

**Drill gate:** Phase 10 does NOT close until every step below has `Verdict:
PASS` and the final Drill Verdict is overall `PASS`. A failed step blocks the
`demo-v2.0` tag cut — never tag a commit whose drill failed or is pending.

**Command source of truth:** every one-liner below is mirrored in the
`## Commands` appendix at the bottom of this file. Operator copy-pastes from
the appendix; per-step blocks record what was run and what came back.

---

## Drill Step 1. ?narrative=off URL-flag proof (D-15)

**Test:** `?narrative=off` kill-switch collapses the UI to v1.0 shape (loading
+ success states) while the live API continues returning narrative fields.
Three-part proof: (a) curl green path returns a non-null `usage_narrative`
string; (b) browser at `?narrative=off` hides narrative rows; (c) screenshot
attached.

**Expected:**
- `curl -sf "$BACKEND_API_URL/recommendations/CUST-001" | jq -e '.green.usage_narrative | strings'`
  exits 0 and prints the narrative string (non-null, non-empty).
- Browser at `https://<frontend-url>/?narrative=off` shows the two recommendation
  cards with NO narrative paragraph and NO call-script quote block.
- Screenshot captured at 1280x800; filename recorded below.

**Command(s):**
```bash
<pending — paste from ## Commands appendix section "### Step 1 commands">
```

**Stdout:**
```
<pending — operator pastes curl output>
```

**Screenshot:** `<pending — e.g. 10-DRILL-LOG-screenshots/step1-narrative-off-1280x800.png>`

**Started:** `<pending-UTC>`
**Verdict:** pending
**Deviations:** (none expected)

---

## Drill Step 2. build:mock <10s regeneration + hash-roundtrip (D-16)

**Test:** `npm run build:mock` regenerates `ui/dist-mock/` in under 10 seconds
wall-clock AND the regenerated dist hashes to the `dist_bundles.ui_dist_mock`
value captured in FREEZE-MANIFEST.md. This is the emergency <10s UI swap
reproducibility gate — if the hash drifts, the freeze reproducibility claim is
invalid.

**Expected:**
- `/usr/bin/time -p npm run build:mock` completes with `real ≤ 10.0` seconds.
- `scripts/hash_dist.sh ui/dist-mock` output equals `FREEZE-MANIFEST.md`
  `dist_bundles.ui_dist_mock` field (minus the `sha256:` prefix).
- `ui/dist-mock/index.html` exists; no live-API hostname grep match in
  `ui/dist-mock/assets/*.js`.

**Command(s):**
```bash
<pending — paste from ## Commands appendix section "### Step 2 commands">
```

**Stdout:**
```
<pending — operator pastes /usr/bin/time output + hash comparison>
```

**Started:** `<pending-UTC>`
**Verdict:** pending
**Deviations:** (none expected)

---

## Drill Step 3. git checkout demo-v1.0 + pytest green from fresh clone (D-13)

**Test:** From a fresh `git clone`, check out `demo-v1.0`, install
hash-pinned deps into a fresh venv, run `pytest -m "not smoke"`. Green exit
(matching the v1.0 baseline) proves the tag-revert rollback path still works.
Commit SHA at `demo-v1.0` must be `aba3a99c67994f39d9d496ddfd29c9116b756928`
per STATE.md environment-lock section.

**Expected:**
- `git rev-parse HEAD` at the tag prints `aba3a99c67994f39d9d496ddfd29c9116b756928`.
- `.venv/bin/pytest -m "not smoke"` exits 0 with `81 passed, 6 skipped`
  (v1.0-era baseline; Phase 10 adds no code, so the tag baseline is unchanged).
- `pip install --require-hashes -r requirements-dev.txt` exits 0 (proves the
  v1.0 lockfile hashes still resolve — unlikely to regress but drilled).

**Command(s):**
```bash
<pending — paste from ## Commands appendix section "### Step 3 commands">
```

**Stdout:**
```
<pending — operator pastes git rev-parse + pytest tail>
```

**Started:** `<pending-UTC>`
**Verdict:** pending
**Deviations:** (none expected)

---

## Drill Step 4. DynamoDB restore-from-backup + scan + spot-check (D-12)

**Test:** Restore `tariff-billing` backup (ARN from FREEZE-MANIFEST.md
`dynamodb_backup.backup_arn`) into a scratch table named
`tariff-billing-rollback-drill` in the same region/account. Scan returns 36
items (3 personas x 12 months). Spot-check one month per persona (CUST-001,
CUST-002, CUST-003 at `2025-04`) returns kWh readings. Table lives only for
the drill; deleted in Step 5.

**Expected:**
- `aws dynamodb restore-table-from-backup ...` returns 200-class exit and
  `wait table-exists` succeeds within ~5 minutes.
- `aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT`
  returns `Count: 36`.
- `aws dynamodb get-item` for (CUST-001, 2025-04), (CUST-002, 2025-04),
  (CUST-003, 2025-04) each returns an Item with a non-null `kwh` field.

**Command(s):**
```bash
<pending — paste from ## Commands appendix section "### Step 4 commands">
```

**Stdout:**
```
<pending — operator pastes restore confirmation + scan Count + 3 get-item outputs>
```

**Started:** `<pending-UTC>`
**Verdict:** pending
**Deviations:** (none expected)

---

## Drill Step 5. Scratch table teardown (D-12 cleanup)

**Test:** Delete the scratch `tariff-billing-rollback-drill` table so no
residual drill artefact lives in the account past the drill window. Verify
deletion by asserting `describe-table` returns `ResourceNotFoundException`.

**Expected:**
- `aws dynamodb delete-table --table-name tariff-billing-rollback-drill` exits 0.
- `aws dynamodb wait table-not-exists --table-name tariff-billing-rollback-drill` exits 0.
- `aws dynamodb describe-table --table-name tariff-billing-rollback-drill` 2>&1
  contains `ResourceNotFoundException`.

**Command(s):**
```bash
<pending — paste from ## Commands appendix section "### Step 5 commands">
```

**Stdout:**
```
<pending — operator pastes delete-table + describe-table ResourceNotFoundException>
```

**Started:** `<pending-UTC>`
**Verdict:** pending
**Deviations:** (none expected)

---

## Drill Verdict

- **Overall:** `pending`
- **Drill duration:** `<pending>` (start-to-last-step elapsed)
- **Operator:** `<pending>`
- **Notes:** `<pending>`

---

## Commands

Copy-paste one-liners for every drill step. Operator runs from the repo root
unless otherwise noted. Every AWS CLI command uses
`--profile cevo-dev25 --region us-east-1`. `BACKEND_API_URL` and `FRONTEND_URL`
are assumed exported to the live Phase 7 / Phase 8 deployment URLs.

### Step 1 commands (?narrative=off) — row 10-03-11

```bash
# (a) curl — asserts the live API still returns a non-null narrative on the green card
curl -sf "$BACKEND_API_URL/recommendations/CUST-001" | jq -e '.green.usage_narrative | strings'
# Expect: exit 0; stdout = the narrative sentence (quoted string).

# (b) Browser — paste URL into Chrome at 1280x800 desktop viewport
#   https://<frontend-url>/?narrative=off
# Expect: two cards render with dollar amounts + track labels but NO narrative
#         paragraph and NO call-script quote block in either green or cheapest card.
# Capture: 1280x800 screenshot, save under 10-DRILL-LOG-screenshots/ or similar.
```

### Step 2 commands (build:mock timing + hash-roundtrip) — rows 10-03-12 + 10-03-13

```bash
# Timed build — /usr/bin/time -p gives POSIX `real` wall-clock; npm's builtin is flakier.
cd ui && rm -rf dist-mock && /usr/bin/time -p npm run build:mock 2>&1 | tee /tmp/build-mock-time.txt
cd ..
# Expect: dist-mock/ regenerated; 'real' line < 10.0 seconds.

# Assert wall-time < 10s
awk '/^real/ { if ($2 > 10.0) { print "FAIL: build:mock took " $2 "s (>10s gate)"; exit 1 } else { print "PASS: build:mock took " $2 "s" } }' /tmp/build-mock-time.txt

# Hash-roundtrip — regenerated dist must hash to the manifest's ui_dist_mock value
REBUILD_HASH=$(scripts/hash_dist.sh ui/dist-mock)
FROZEN_HASH=$(python3 -c "import yaml, re; src=open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(); m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', src, re.S).group(1)); print(m['dist_bundles']['ui_dist_mock'].split(':', 1)[-1])")
[ "$REBUILD_HASH" = "$FROZEN_HASH" ] && echo "PASS: hash-roundtrip ($REBUILD_HASH)" || { echo "FAIL: rebuild=$REBUILD_HASH frozen=$FROZEN_HASH"; exit 1; }
```

### Step 3 commands (git checkout demo-v1.0 + pytest) — row 10-03-10

```bash
# Fresh clone from THIS repo path, NOT origin — the drill validates the local source tree.
rm -rf /tmp/freeze-repro
git clone . /tmp/freeze-repro
cd /tmp/freeze-repro

# Checkout the v1.0 tag
git checkout demo-v1.0

# Assert tag points at the STATE.md environment-lock commit
[ "$(git rev-parse HEAD)" = "aba3a99c67994f39d9d496ddfd29c9116b756928" ] \
  && echo "PASS: demo-v1.0 at aba3a99" \
  || { echo "FAIL: tag drifted"; exit 1; }

# Fresh venv + hash-pinned install (D-19 reproducibility precondition)
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt
# Expect: exit 0

# pytest baseline — v1.0 baseline is 81 passed / 6 skipped
.venv/bin/pytest -m "not smoke" 2>&1 | tail -5
# Expect: final summary line matches "81 passed, 6 skipped"

# Return to Phase 10 working directory
cd -
```

### Step 4 commands (DynamoDB restore + scan + spot-check) — row 10-03-09

```bash
# Extract backup ARN from manifest
BACKUP_ARN=$(python3 -c "import yaml, re; src=open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(); m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', src, re.S).group(1)); print(m['dynamodb_backup']['backup_arn'])")
echo "Restoring from: $BACKUP_ARN"

# Restore into scratch table
aws dynamodb restore-table-from-backup \
  --target-table-name tariff-billing-rollback-drill \
  --backup-arn "$BACKUP_ARN" \
  --region us-east-1 --profile cevo-dev25

# Wait for restored table to be ACTIVE (can take ~5 min)
aws dynamodb wait table-exists \
  --table-name tariff-billing-rollback-drill \
  --region us-east-1 --profile cevo-dev25

# Assert 36 items (3 personas x 12 months)
COUNT=$(aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT \
  --region us-east-1 --profile cevo-dev25 --query 'Count' --output text)
[ "$COUNT" = "36" ] && echo "PASS: 36 items" || { echo "FAIL: $COUNT items, expected 36"; exit 1; }

# Spot-check: one month (2025-04) for each persona — kwh must be present
for CUSTOMER in CUST-001 CUST-002 CUST-003; do
  aws dynamodb get-item --table-name tariff-billing-rollback-drill \
    --key "{\"customer_id\": {\"S\": \"$CUSTOMER\"}, \"month\": {\"S\": \"2025-04\"}}" \
    --region us-east-1 --profile cevo-dev25 \
    --query 'Item.kwh' --output text
  # Expect: a numeric string per persona (not None)
done
```

### Step 5 commands (scratch teardown) — row 10-03-15

```bash
# Delete the scratch table
aws dynamodb delete-table --table-name tariff-billing-rollback-drill \
  --region us-east-1 --profile cevo-dev25

# Wait for deletion
aws dynamodb wait table-not-exists --table-name tariff-billing-rollback-drill \
  --region us-east-1 --profile cevo-dev25

# Assert ResourceNotFoundException on describe-table — proves the table is gone
aws dynamodb describe-table --table-name tariff-billing-rollback-drill \
  --region us-east-1 --profile cevo-dev25 2>&1 | grep -q ResourceNotFoundException \
  && echo "PASS: scratch table cleaned up" \
  || { echo "FAIL: table still exists or other error"; exit 1; }
```
