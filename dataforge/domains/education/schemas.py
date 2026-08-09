from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "institutions": TableSchema("institution_id", ("institution_id", "institution_name", "institution_type", "country", "state", "city", "established_year", "accreditation", "status", "created_at")),
    "campuses": TableSchema("campus_id", ("campus_id", "institution_id", "campus_name", "address", "city", "state", "country", "status", "created_at"), (ForeignKey("institution_id", "institutions", "institution_id"),)),
    "departments": TableSchema("department_id", ("department_id", "campus_id", "department_name", "department_code", "head_of_department", "status", "created_at"), (ForeignKey("campus_id", "campuses", "campus_id"),)),
    "academic_programs": TableSchema("program_id", ("program_id", "department_id", "program_name", "degree_level", "duration_years", "credits_required", "status", "created_at"), (ForeignKey("department_id", "departments", "department_id"),)),
    "courses": TableSchema("course_id", ("course_id", "department_id", "course_code", "course_name", "credit_hours", "semester", "course_type", "status", "created_at"), (ForeignKey("department_id", "departments", "department_id"),)),
    "instructors": TableSchema("instructor_id", ("instructor_id", "department_id", "instructor_name", "designation", "hire_date", "specialization", "employment_status", "created_at"), (ForeignKey("department_id", "departments", "department_id"),)),
    "students": TableSchema("student_id", ("student_id", "program_id", "student_name", "gender", "birth_date", "admission_date", "expected_graduation_date", "academic_year", "status", "created_at"), (ForeignKey("program_id", "academic_programs", "program_id"),)),
    "class_sections": TableSchema("section_id", ("section_id", "course_id", "instructor_id", "section_name", "semester", "academic_year", "classroom", "capacity", "schedule", "created_at"), (ForeignKey("course_id", "courses", "course_id"), ForeignKey("instructor_id", "instructors", "instructor_id"))),
    "enrollments": TableSchema("enrollment_id", ("enrollment_id", "student_id", "section_id", "enrollment_date", "enrollment_status", "final_grade", "completion_status", "created_at"), (ForeignKey("student_id", "students", "student_id"), ForeignKey("section_id", "class_sections", "section_id"))),
    "attendance": TableSchema("attendance_id", ("attendance_id", "enrollment_id", "attendance_date", "attendance_status", "attendance_percentage", "created_at"), (ForeignKey("enrollment_id", "enrollments", "enrollment_id"),)),
    "assignments": TableSchema("assignment_id", ("assignment_id", "section_id", "assignment_title", "assignment_type", "assigned_date", "due_date", "maximum_marks", "created_at"), (ForeignKey("section_id", "class_sections", "section_id"),)),
    "assignment_submissions": TableSchema("submission_id", ("submission_id", "assignment_id", "student_id", "submission_date", "marks_obtained", "grading_status", "created_at"), (ForeignKey("assignment_id", "assignments", "assignment_id"), ForeignKey("student_id", "students", "student_id"))),
    "examinations": TableSchema("examination_id", ("examination_id", "section_id", "examination_name", "examination_type", "examination_date", "maximum_marks", "created_at"), (ForeignKey("section_id", "class_sections", "section_id"),)),
    "examination_results": TableSchema("result_id", ("result_id", "examination_id", "student_id", "marks_obtained", "grade", "pass_flag", "created_at"), (ForeignKey("examination_id", "examinations", "examination_id"), ForeignKey("student_id", "students", "student_id"))),
    "fees_payments": TableSchema("payment_id", ("payment_id", "student_id", "academic_year", "fee_type", "total_fee", "amount_paid", "payment_method", "payment_date", "payment_status", "created_at"), (ForeignKey("student_id", "students", "student_id"),)),
    "academic_standing_events": TableSchema("academic_standing_event_id", ("academic_standing_event_id", "student_id", "program_id", "event_date", "standing_status", "gpa", "credits_attempted", "credits_earned", "reason_code"), (ForeignKey("student_id", "students", "student_id"), ForeignKey("program_id", "academic_programs", "program_id"))),
}

FACT_TABLES = {"enrollments", "attendance", "assignment_submissions", "examination_results", "fees_payments", "academic_standing_events"}
DIMENSION_TABLES = {"institutions", "campuses", "departments", "academic_programs", "courses", "instructors", "students", "class_sections", "assignments", "examinations"}

EDUCATION_SPEC = DomainSpec(
    name="education",
    source_system="DATAFORGE_EDUCATION",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "enrollments": "enrollment_date",
        "attendance": "attendance_date",
        "assignment_submissions": "submission_date",
        "examination_results": "created_at",
        "fees_payments": "payment_date",
        "academic_standing_events": "event_date",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("enrollment_event", "enrollments", "ENROLLMENT_UPDATED", "enrollment_id", "enrollment_date"),
        EventDefinition("attendance_event", "attendance", "ATTENDANCE_RECORDED", "attendance_id", "attendance_date"),
        EventDefinition("assignment_submission_event", "assignment_submissions", "ASSIGNMENT_SUBMITTED", "submission_id", "submission_date"),
        EventDefinition("examination_result_event", "examination_results", "RESULT_PUBLISHED", "result_id", "created_at"),
        EventDefinition("fee_payment_event", "fees_payments", "FEE_PAYMENT_UPDATED", "payment_id", "payment_date"),
        EventDefinition("academic_standing_event", "academic_standing_events", "ACADEMIC_STANDING_UPDATED", "academic_standing_event_id", "event_date"),
    ),
    cdc_tables=("students", "enrollments", "attendance", "assignment_submissions", "examination_results", "fees_payments", "academic_standing_events"),
    business_rules=BUSINESS_RULES,
)
