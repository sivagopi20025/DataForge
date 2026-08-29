# DataForge V1 Limited Beta Launch Plan

Status: V1 feature-frozen  
Recommended release label: `v1.0.0-beta`  
Beta model: controlled internal beta before external beta

## Purpose

Treat the V1 beta as a product validation program, not only a software test.

The beta should answer:

1. Do users understand DataForge?
2. Can users complete the scenario and benchmark workflow?
3. Would users return and reuse it?
4. Would users or teams pay for it?
5. What should V2 prioritize?

Success is not “no bugs.” Success is that users understand the workflow, complete benchmarks, return, request useful improvements, and show adoption or buying intent.

## Current V1 release baseline

- Backend regression: `378 passed, 3 skipped`
- Playwright staging validation: `72/72 checks passed`
- npm audit: `0 vulnerabilities`
- Python dependency audit: no known vulnerabilities
- Axe: `0 critical / 0 serious`
- Alembic migration head: `0009_benchmark_runs`
- Decision from staging validation: `READY FOR LIMITED BETA`

## Beta timeline

### Phase 0 — preparation, 2–3 days

Before inviting testers:

- Freeze features.
- Tag release: `v1.0.0-beta`.
- Deploy staging/beta environment.
- Seed example scenario runs.
- Seed benchmark examples.
- Create demo datasets.
- Create test API keys.
- Prepare documentation.
- Prepare support channel.
- Prepare feedback form.
- Prepare bug report form.
- Prepare known issues list.
- Prepare V2 roadmap capture board.

Deliverables:

- Beta URL
- Quick Start Guide
- Tester Mission Pack
- 5–10 minute video walkthrough
- Feedback Form
- Bug Report Template
- Feature Request Template
- Known Issues
- Roadmap / Phase 2 parking lot

### Phase 1 — internal team testing, week 1

Target: 5–10 technical users.

Participants:

- Founder / builder
- Friends
- Technical colleagues
- Developers
- QA engineers
- Data engineers
- ML engineers

Objective:

Break the product, identify confusing workflows, and verify that users can complete the core V1 loop.

### Phase 2 — focused internal beta, weeks 2–3

Target: 10–15 total users.

Objective:

Validate repeat use, benchmark comprehension, detector upload flow, artifact usefulness, and business value.

### Phase 3 — decision week, week 4

Objective:

Decide whether DataForge is ready for external beta, needs a short V1 patch cycle, or should pivot the V2 roadmap.

## Feature exposure during beta

Expose by default:

- Home / onboarding explanation
- Scenario Library
- Scenario Builder
- Featured V1 scenarios
- Failure injection controls
- Required table visibility
- Ground truth
- Evidence
- Benchmark creation
- Detector upload / evaluation
- Run History
- Saved templates
- Run comparison
- ZIP/artifact downloads

Keep restricted or secondary:

- Full 760-scenario catalog
- Internal/admin analytics
- Experimental scenario internals
- Advanced streaming claims
- Any feature not covered by the staging validation report

Recommended first beta exposure:

- 20–30 Featured V1 scenarios
- Remaining executable scenarios under Standard/Advanced/Internal visibility

## Recommended beta limits

- Dataset records: default 10,000; recommended max 100,000 for most testers
- Benchmark concurrency: 2
- Detector upload max: 5 MB
- Artifact retention: 30 days
- Users: invite-only
- API access: manually issued
- Support: direct channel

Do not market V1 as:

- distributed-worker durable
- enterprise multi-tenant
- restart-resilient benchmark orchestration
- production-grade external streaming infrastructure

## Tester mission pack

Do not tell testers only “test the app.” Give every tester explicit missions.

Suggested missions:

1. Generate a Retail duplicate order or duplicate payment dataset.
2. Generate a Healthcare duplicate claim or ghost provider scenario.
3. Create a benchmark, upload detector results, and review precision/recall/F1.
4. Create a multi-failure scenario.
5. Save a scenario template, load it, and run it again.
6. Export ground truth as JSON/JSONL/CSV.
7. Compare two benchmark or scenario runs.
8. Download the generated ZIP and inspect the README/report files.

See [Beta Tester Missions](./beta/BETA_TESTER_MISSIONS.md).

## Usage analytics to collect

Collect product usage, not personal data.

Session analytics:

- Session ID
- User ID or beta tester ID
- Login time
- Logout time
- Duration
- Browser
- OS
- Screen resolution
- Country
- Timezone

Feature usage:

- Scenario selected
- Domain
- Rows generated
- Generation time
- Failure types selected
- Failure percentages/counts
- Preview viewed
- Ground truth viewed
- Evidence viewed
- Template saved
- Benchmark created
- Detector uploaded
- Run compared
- Artifact downloaded

Error analytics:

- Backend errors
- Frontend errors
- API failures
- Validation failures
- Generation failures
- Benchmark failures
- Upload failures
- Timeouts

UX events:

- Clicked help
- Cancelled generation
- Changed percentage
- Opened advanced mode
- Never opened advanced mode
- Repeated same scenario
- Abandoned benchmark
- Page exits

## Beta success metrics

| Metric | Goal |
|---|---:|
| Invited users | 10 |
| Active users | >= 8 |
| Completed first scenario | >= 90% |
| Completed benchmark | >= 70% |
| Average session duration | > 20 min |
| Repeat users | >= 50% |
| Crash rate | < 2% |
| Critical bugs | 0 |
| High bugs | < 3 |
| Average usability score | >= 4.2 / 5 |
| NPS | > 30 |
| Users willing to evaluate at work | >= 3 |

## Weekly beta review

At the end of each week, categorize feedback:

Critical:

- Security issue
- Cross-user data exposure
- Data corruption
- Benchmark correctness failure

High:

- Users cannot finish core workflows
- Frequent crashes
- Major UX confusion
- Broken artifact download/export

Medium:

- Slow workflows
- Missing convenience features
- UI improvements
- Documentation gaps

Low:

- Cosmetic issues
- Nice-to-have requests
- Small copy changes

## External beta exit criteria

Move from internal beta to external beta only if:

- No Critical bugs remain.
- High-priority issues are resolved or have acceptable workarounds.
- At least 80% of internal testers complete the core workflow without assistance.
- Most testers rate usability positively, target >= 4 / 5.
- Multiple testers say they would use DataForge again.
- Multiple testers say their company/team would evaluate DataForge.
- Phase 2 roadmap is prioritized from real feedback, not assumptions.

## Limited beta decision framing

The most important beta question is no longer “Can we build more?”

It is:

> Do users understand the workflow and get enough value from it to return?

