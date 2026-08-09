# Education scenario research

Common workflows: institutions, campuses, departments, programs, courses, instructors, students, sections, enrollments, attendance, assignments, exams, and fees.

Common data failures: attendance drops, duplicate enrollment, grade calculation error, fee hold, graduation eligibility failure, missing submissions, and invalid marks.

Business-rule failures: marks above maximum, completion status inconsistent with grade, fee payment above total, registration hold mismatch, and invalid enrollment lifecycle.

Pipeline failures: duplicate enrollment load, delayed gradebook extract, dropped attendance records, and fee status mismatch.

Expected validations: enrollment FK integrity, attendance/grade correlation, marks range, fee reconciliation, date sequence, duplicate enrollment detection, and eligibility checks.

References:

- IPEDS — National Center for Education Statistics — https://nces.ed.gov/ipeds/ — reviewed 2026-07-11 — government statistics reference only — derived institution/enrollment/completion/finance patterns — no_copied_rows=true
- Common Education Data Standards — U.S. Department of Education — https://ceds.ed.gov/ — reviewed 2026-07-11 — public standard reference — derived entity and outcome consistency concepts — no_copied_rows=true

Assumptions: graduation eligibility is approximated with enrollment/grade fields in the current schema.

Unresolved questions: future schema may need credits/transcripts.

