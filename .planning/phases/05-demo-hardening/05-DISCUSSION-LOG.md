# Phase 5: Demo Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 05-demo-hardening
**Areas discussed:** Deploy posture, Run-mode on the day, Latency measurement, Environment lock scope, Rehearsal depth, No-CRM validation, Deliverables / runbook

---

## Deploy posture

**Q1 — What's the deploy posture for Phase 5 — do we stand up real AWS infrastructure?**

| Option | Description | Selected |
|---|---|---|
| Full live deploy | cdk deploy all 3 stacks to us-east-1; demo runs live | ✓ |
| Live deploy, demo on mock | Deploy infra for proof, demo day uses mock fallback | |
| Mock-only, no deploy | No AWS resources; code+rehearsal only | |

**User's choice:** Full live deploy (Recommended)

**Q2 — If we deploy live, which AWS account/region configuration?**

| Option | Description | Selected |
|---|---|---|
| us-east-1, same account used so far | app.py is already hardcoded; AgentCore Registry available | ✓ |
| us-east-1, fresh demo-specific account | Isolates demo account; extra bootstrap friction | |
| Let Claude match AWS_PROFILE active | No pinning; planner/user decide at deploy time | |

**User's choice:** us-east-1, same account used so far (Recommended)

**Q3 — What smoke verification has to pass after cdk deploy before Phase 5 closes?**

| Option | Description | Selected |
|---|---|---|
| All 3 personas succeed via curl AND via the UI | Phase 3 smoke + live UI against VITE_API_URL | ✓ |
| curl-only smoke is enough | Phase 3 smoke script only | |
| UI-only smoke against live endpoint | Skip curl; UI flow is the gate | |

**User's choice:** All 3 personas succeed via curl AND via the UI (Recommended)

**Q4 — Cold-start handling on demo day — do we pre-warm?**

| Option | Description | Selected |
|---|---|---|
| No pre-warm — accept first-hit latency | DEMO-03 stays v2; Phase 3 D-04 accepts cold start | ✓ |
| Ad-hoc warm-up call right before demo | Documented runbook step; no infrastructure | |
| Full pre-warm script (promote DEMO-03) | Scope creep — pull v2 requirement forward | |

**User's choice:** No pre-warm — accept first-hit latency (Recommended)

---

## Run-mode on the day

**Q5 — How is the UI configured on the presentation laptop at demo time?**

| Option | Description | Selected |
|---|---|---|
| Live API primary, mock as emergency switch | VITE_API_URL set; prebuilt mock dist as 10s fallback | ✓ |
| Live API only — no fallback | Single build; highest risk, cleanest story | |
| Mock only — live endpoint as separate proof | Live via curl pre-roll; UI stays on mock | |

**User's choice:** Live API primary, mock as emergency switch (Recommended)

**Q6 — How does the presenter actually launch the UI during the demo?**

| Option | Description | Selected |
|---|---|---|
| npm run preview from the ui/ directory | Phase 4 D-05 pattern; one command; localhost | ✓ |
| Static hosting (S3 + CloudFront) | Scope creep; deferred in 04-CONTEXT.md | |
| Open dist/index.html directly | No server; fragile Vite paths | |

**User's choice:** npm run preview from the ui/ directory (Recommended)

**Q7 — If live AWS goes down mid-demo, what's the documented recovery move?**

| Option | Description | Selected |
|---|---|---|
| Swap to the prebuilt mock dist/ | <10s pivot; ships two dist folders | ✓ |
| Verbally explain + show curl / Phase 2 smoke output | Pivot to narrative; no swap | |
| No fallback documented | Aligns with live-only; nothing to fail over to | |

**User's choice:** Swap to the prebuilt mock dist/ (Recommended)

---

## Latency measurement

**Q8 — How do we measure latency end-to-end against the live API?**

| Option | Description | Selected |
|---|---|---|
| Chrome DevTools Performance + stopwatch | Zero new code; human-grade evidence | ✓ |
| Lightweight performance.now() instrumentation | ~10 LOC; must not ship commented in final | |
| Automated latency script (Playwright) | New dev-dep Phase 4 D-14 rejected | |

**User's choice:** Chrome DevTools Performance + stopwatch (Recommended)

**Q9 — What threshold counts as 'pass' for the <3s criterion, given cold starts?**

| Option | Description | Selected |
|---|---|---|
| Warm-run median <3s, cold-run documented | Aligns with Phase 3 D-04 accepts-cold | ✓ |
| Every single run <3s including cold | Stricter; likely needs ad-hoc pre-warm | |
| <3s flagship only, others 'feel snappy' | Likely fails criterion 2 'all personas' | |

**User's choice:** Warm-run median <3s, cold-run documented (Recommended)

**Q10 — Where do latency results get recorded?**

| Option | Description | Selected |
|---|---|---|
| Short latency table in 05-VERIFICATION.md | Single source of truth for the gate | ✓ |
| Dedicated DATA-SOURCES.md | Overkill separate doc | |
| Just a verbal 'verified' note | Thin evidence | |

**User's choice:** Short latency table in 05-VERIFICATION.md (Recommended)

---

## Environment lock scope

**Q11 — What does 'environment locked' mean for Phase 5?**

| Option | Description | Selected |
|---|---|---|
| Lightweight lock: git tag + lockfiles verified + deployed ARNs captured | DEMO-04 stays v2; reproducible from tag | ✓ |
| Medium lock: + explicit 'do not touch' window | Discipline commitment without 48h freeze | |
| Full DEMO-04 freeze (promote from v2) | Scope creep | |

**User's choice:** Lightweight lock (Recommended)

**Q12 — How tightly are dependencies pinned during the lock?**

| Option | Description | Selected |
|---|---|---|
| Trust existing lockfiles, verify CDK toolchain | npm ci + fresh venv + cdk synth green | ✓ |
| Regenerate all lockfiles from scratch | Risk of accidental upgrade during regen | |
| No pinning effort | Weakest | |

**User's choice:** Trust existing lockfiles (Recommended)

**Q13 — Is the git tag the boundary, or do we freeze AWS resources too?**

| Option | Description | Selected |
|---|---|---|
| Git tag is the lock — AWS just 'don't touch' | Code-state lock, not AWS-state lock | ✓ |
| Git tag + CloudFormation drift check | More evidence, more friction | |
| Git tag + isolated demo branch | Git-hygiene win against accidental commits | |

**User's choice:** Git tag is the lock (Recommended)

---

## Rehearsal depth

**Q14 — How deep does the persona rehearsal go?**

| Option | Description | Selected |
|---|---|---|
| Golden path + 2 error paths | 3 personas + 400 + 404; bounded checklist | ✓ |
| Golden path only | 3 personas succeed; errors proven upstream | |
| Full matrix (3 personas × 5 errors × cold/warm) | 24-case; overkill | |

**User's choice:** Golden path + 2 error paths (Recommended)

**Q15 — How many end-to-end rehearsal passes?**

| Option | Description | Selected |
|---|---|---|
| Two passes: one cold, one warm | Exercises real cold-start; repeatable warm | ✓ |
| One full pass | Faster gate; cold/warm variance hidden | |
| Three+ passes across the day | Stress test; probably overkill | |

**User's choice:** Two passes (Recommended)

**Q16 — Who executes the rehearsal?**

| Option | Description | Selected |
|---|---|---|
| Human checkpoint — user runs, Claude records | Mirrors Phase 4 1280×800 smoke pattern | ✓ |
| Claude executes via scripts, user approves | Mixed model; UI still needs human at browser | |
| Claude executes and self-approves | Weak evidence for demo gate | |

**User's choice:** Human checkpoint (Recommended)

---

## No-CRM validation

**Q17 — How do we prove 'no live CRM connectivity'?**

| Option | Description | Selected |
|---|---|---|
| Code-path audit + architectural claim | Grep; enumerate data sources; structural proof | ✓ |
| Code audit + airplane-mode test on UI | Belt and braces | |
| Egress block on Lambda SG / IAM | Strongest proof; CDK work for non-problem | |

**User's choice:** Code-path audit + architectural claim (Recommended)

**Q18 — Where does the no-CRM proof get recorded?**

| Option | Description | Selected |
|---|---|---|
| Short section in 05-VERIFICATION.md | Same place as latency + rehearsal | ✓ |
| Dedicated DATA-SOURCES.md | Overkill for one paragraph | |
| Verbal mention only | Not enough for a gate | |

**User's choice:** Short section in 05-VERIFICATION.md (Recommended)

---

## Deliverables / runbook

**Q19 — What deliverable artifacts does Phase 5 produce?**

| Option | Description | Selected |
|---|---|---|
| Demo runbook + presenter cheat sheet | Single DEMO-RUNBOOK.md with checklist + script | ✓ |
| Runbook only, no cheat sheet | Operational only; presenter improvises | |
| README update + inline comments | Mixes project README with demo-specific | |
| No new docs | Rejected by phase goal | |

**User's choice:** Demo runbook + presenter cheat sheet (Recommended)

**Q20 — Does the runbook include teardown / cleanup steps?**

| Option | Description | Selected |
|---|---|---|
| Yes — cdk destroy post-demo | Documented not executed | ✓ |
| Teardown documented elsewhere | Cleaner separation | |
| No teardown — leave infra up | Risks forgotten AWS costs | |

**User's choice:** Yes — cdk destroy post-demo (Recommended)

**Q21 — Is there a 'demo day' timing checklist?**

| Option | Description | Selected |
|---|---|---|
| T-24h / T-2h / T-0 checklist | Lightweight timed sequencing | ✓ |
| Pre-demo checklist only, no timing | One list; presenter sequences | |
| No checklist | Less structured | |

**User's choice:** T-24h / T-2h / T-0 checklist (Recommended)

---

## Claude's Discretion

Items left to the planner (see CONTEXT.md §Claude's Discretion):
- Captured-ARNs artifact layout (filename vs inline block)
- Code-path audit presentation format (transcript vs summary)
- Rehearsal script format (Markdown steps vs numbered table)
- Presenter cheat-sheet narrative tone (drafted by planner, user confirms)
- Ad-hoc warm-up timing (T-2h vs T-0-minus-2-min)
- Mock fallback dist mechanism (committed artifact vs build script vs rebuild steps)
- CloudWatch retention settings for the demo deploy
- Phase 5 plan decomposition (~3 plans expected)

## Deferred Ideas

See CONTEXT.md §Deferred. Summary:
- DEMO-03 pre-warm script (stays v2)
- DEMO-04 48-hour freeze (stays v2)
- S3 + CloudFront UI hosting
- Playwright / automated latency harness
- performance.now() instrumentation
- Airplane-mode / VPC egress block
- CloudFormation drift check
- Isolated demo-v1.0 branch
- Structured JSON latency artifact
- Custom domain / branded URL
- Post-demo teardown automation
- Freezing the presenter's laptop OS state
