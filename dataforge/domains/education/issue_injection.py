from __future__ import annotations

DATE_COLUMNS = {
    "institutions": "created_at",
    "campuses": "created_at",
    "departments": "created_at",
    "academic_programs": "created_at",
    "courses": "created_at",
    "instructors": "hire_date",
    "students": "admission_date",
    "class_sections": "created_at",
    "enrollments": "enrollment_date",
    "attendance": "attendance_date",
    "assignments": "assigned_date",
    "assignment_submissions": "submission_date",
    "examinations": "examination_date",
    "examination_results": "created_at",
    "fees_payments": "payment_date",
    "academic_standing_events": "event_date",
}

NUMERIC_COLUMNS = {
    "institutions": "established_year",
    "academic_programs": "credits_required",
    "courses": "credit_hours",
    "class_sections": "capacity",
    "attendance": "attendance_percentage",
    "assignments": "maximum_marks",
    "assignment_submissions": "marks_obtained",
    "examinations": "maximum_marks",
    "examination_results": "marks_obtained",
    "fees_payments": "amount_paid",
    "academic_standing_events": "gpa",
}

TYPE_MISMATCH_COLUMNS = {
    "institutions": "institution_type",
    "campuses": "status",
    "departments": "department_code",
    "academic_programs": "degree_level",
    "courses": "course_type",
    "instructors": "designation",
    "students": "gender",
    "class_sections": "semester",
    "enrollments": "enrollment_status",
    "attendance": "attendance_status",
    "assignments": "assignment_type",
    "assignment_submissions": "grading_status",
    "examinations": "examination_type",
    "examination_results": "grade",
    "fees_payments": "payment_status",
    "academic_standing_events": "standing_status",
}
