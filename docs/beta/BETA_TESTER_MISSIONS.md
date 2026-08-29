# DataForge Beta Tester Missions

Use this mission pack for internal beta testers. Each tester should complete at least missions 1–5. Missions 6–8 are recommended for advanced users.

## Before starting

Ask the tester to record:

- role
- years of experience
- industry
- browser and OS
- whether they have used synthetic data tools before

Ask them to think aloud or write down confusion points while using the product.

## Mission 1 — first scenario dataset

Goal: verify first-run comprehension.

Task:

1. Open DataForge.
2. Go to Scenario Library / Scenario Builder.
3. Choose a Featured Retail scenario, such as duplicate order/payment.
4. Generate a dataset with the default settings.
5. Open the generated run.
6. Download the ZIP.

Questions:

- Did you understand what scenario you selected?
- Did you understand what failure was injected?
- Did the generated artifacts make sense?

## Mission 2 — healthcare scenario

Goal: validate whether domain-specific scenarios feel realistic.

Task:

1. Select a Healthcare scenario, such as duplicate claim or ghost provider.
2. Review required tables.
3. Generate 10,000 rows.
4. Open validation/evidence.
5. Download ground truth.

Questions:

- Did the healthcare scenario feel realistic?
- Did the evidence explain the issue clearly?
- Did you trust the validation outcome?

## Mission 3 — benchmark flow

Goal: validate the benchmark execution loop.

Task:

1. Create a benchmark from a generated scenario run.
2. Export ground truth.
3. Upload detector output.
4. Review precision, recall, F1, and PASS/FAIL.

Questions:

- Did you understand what the detector was being evaluated against?
- Were the metrics clear?
- Would this be useful for testing your own data quality detector?

## Mission 4 — multi-failure configuration

Goal: validate advanced failure configuration.

Task:

1. Open a scenario in advanced mode.
2. Add more than one failure.
3. Configure percentage or exact count.
4. Generate a dataset.
5. Review expected vs detected counts.

Questions:

- Was percentage vs exact count clear?
- Did overlap behavior make sense?
- Were the resulting reports understandable?

## Mission 5 — saved template and rerun

Goal: validate repeat-use behavior.

Task:

1. Save a scenario configuration as a template.
2. Load the template.
3. Run it again.
4. Compare the new run with a previous run.

Questions:

- Would you use saved templates again?
- Was rerun/compare useful?
- Did deterministic seed behavior make sense?

## Mission 6 — artifact inspection

Goal: validate package usability outside the app.

Task:

1. Download a generated ZIP.
2. Inspect data files.
3. Inspect README.
4. Inspect run summary.
5. Inspect issue manifest.
6. Inspect validation/realism/ground-truth reports.

Questions:

- Could you use these files in your own pipeline?
- Was anything missing from the package?
- Were intentionally injected failures documented clearly?

## Mission 7 — detector upload variations

Goal: validate detector input flexibility.

Task:

1. Upload detector results as JSON.
2. Upload detector results as JSONL.
3. Upload detector results as CSV.
4. Try one intentionally malformed upload and confirm a clean error.

Questions:

- Which format would your team prefer?
- Was the upload contract clear?
- Was the error message helpful?

## Mission 8 — business-value interview

Goal: collect product-market signal.

Ask:

- What current problem could DataForge solve for you?
- What tool/process would DataForge replace or improve?
- Would your team evaluate this?
- Would you use it monthly?
- Would you pay for it?
- What one feature would make it dramatically more useful?

