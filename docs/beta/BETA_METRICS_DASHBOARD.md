# DataForge Internal Beta Metrics Dashboard

Use this as the source of truth for weekly beta review.

## Core funnel

| Metric | Goal | Actual | Status |
|---|---:|---:|---|
| Invited users | 10 |  |  |
| Active users | >= 8 |  |  |
| Completed first scenario | >= 90% |  |  |
| Completed benchmark | >= 70% |  |  |
| Exported ground truth | >= 60% |  |  |
| Uploaded detector output | >= 60% |  |  |
| Saved template | >= 40% |  |  |
| Repeat users | >= 50% |  |  |

## Product quality

| Metric | Goal | Actual | Status |
|---|---:|---:|---|
| Average session duration | > 20 min |  |  |
| Crash rate | < 2% |  |  |
| Critical bugs | 0 |  |  |
| High bugs | < 3 |  |  |
| Average usability score | >= 4.2 / 5 |  |  |
| NPS | > 30 |  |  |
| Users willing to evaluate at work | >= 3 |  |  |

## Events to track

Session:

- session_started
- session_ended
- page_viewed
- beta_user_logged_in

Scenario workflow:

- scenario_selected
- required_tables_viewed
- failure_config_opened
- advanced_mode_opened
- failure_percentage_changed
- generation_preview_viewed
- scenario_generation_started
- scenario_generation_completed
- scenario_generation_failed

Ground truth / evidence:

- ground_truth_viewed
- evidence_viewed
- ground_truth_exported
- artifact_zip_downloaded

Templates:

- template_saved
- template_loaded
- template_rerun

Benchmarking:

- benchmark_created
- benchmark_run_started
- benchmark_waiting_for_detector
- detector_uploaded
- detector_upload_failed
- benchmark_evaluated
- benchmark_failed
- benchmark_cancelled
- benchmark_compared

UX:

- help_clicked
- generation_cancelled
- benchmark_abandoned
- page_exit_before_completion

## Weekly review questions

1. Where did users abandon the workflow?
2. Which scenarios were selected most?
3. Which features were ignored?
4. Which errors happened more than once?
5. Which parts required hand-holding?
6. Which features created business-value comments?
7. Which Phase 2 ideas are supported by repeated user evidence?

