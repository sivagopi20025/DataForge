from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import (
    ASSIGNMENT_TYPES,
    ATTENDANCE_STATUSES,
    COMPLETION_STATUSES,
    COURSE_TYPES,
    DEGREE_LEVELS,
    DESIGNATIONS,
    EMPLOYMENT_STATUSES,
    ENROLLMENT_STATUSES,
    EXAMINATION_TYPES,
    FEE_TYPES,
    GENDERS,
    GRADES,
    GRADING_STATUSES,
    INSTITUTION_TYPES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    STATUSES,
    STUDENT_STATUSES,
)


def _date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def valid_value_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    checks = (
        ("institution_type_valid", "institutions", "institution_type", INSTITUTION_TYPES),
        ("institution_status_valid", "institutions", "status", STATUSES),
        ("campus_status_valid", "campuses", "status", STATUSES),
        ("department_status_valid", "departments", "status", STATUSES),
        ("program_degree_level_valid", "academic_programs", "degree_level", DEGREE_LEVELS),
        ("program_status_valid", "academic_programs", "status", STATUSES),
        ("course_type_valid", "courses", "course_type", COURSE_TYPES),
        ("course_status_valid", "courses", "status", STATUSES),
        ("instructor_designation_valid", "instructors", "designation", DESIGNATIONS),
        ("instructor_employment_status_valid", "instructors", "employment_status", EMPLOYMENT_STATUSES),
        ("student_gender_valid", "students", "gender", GENDERS),
        ("student_status_valid", "students", "status", STUDENT_STATUSES),
        ("enrollment_status_valid", "enrollments", "enrollment_status", ENROLLMENT_STATUSES),
        ("completion_status_valid", "enrollments", "completion_status", COMPLETION_STATUSES),
        ("attendance_status_valid", "attendance", "attendance_status", ATTENDANCE_STATUSES),
        ("assignment_type_valid", "assignments", "assignment_type", ASSIGNMENT_TYPES),
        ("grading_status_valid", "assignment_submissions", "grading_status", GRADING_STATUSES),
        ("examination_type_valid", "examinations", "examination_type", EXAMINATION_TYPES),
        ("grade_valid", "examination_results", "grade", GRADES),
        ("fee_type_valid", "fees_payments", "fee_type", FEE_TYPES),
        ("payment_method_valid", "fees_payments", "payment_method", PAYMENT_METHODS),
        ("payment_status_valid", "fees_payments", "payment_status", PAYMENT_STATUSES),
    )
    return [
        {"check": name, "table": table, "failures": sum(1 for row in data.get(table, []) if row.get(column) not in allowed)}
        for name, table, column, allowed in checks
    ]


def student_dates_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("students", []):
        try:
            failures += _date(row["admission_date"]) >= _date(row["expected_graduation_date"])
            failures += _date(row["birth_date"]) >= _date(row["admission_date"])
        except (KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "student_admission_before_graduation", "table": "students", "failures": failures}]


def assignment_dates_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    assignments = {row["assignment_id"]: row for row in data.get("assignments", []) if "assignment_id" in row}
    failures = 0
    for assignment in assignments.values():
        try:
            failures += _date(assignment["due_date"]) <= _date(assignment["assigned_date"])
        except (KeyError, ValueError, TypeError):
            failures += 1
    for submission in data.get("assignment_submissions", []):
        try:
            assignment = assignments[submission["assignment_id"]]
            failures += _date(submission["submission_date"]) < _date(assignment["assigned_date"])
            failures += _decimal(submission["marks_obtained"]) > _decimal(assignment["maximum_marks"])
            failures += _decimal(submission["marks_obtained"]) < 0
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "assignment_dates_and_marks_valid", "table": "assignment_submissions", "failures": failures}]


def examination_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    enrollments = {row["student_id"]: row for row in data.get("enrollments", []) if "student_id" in row}
    examinations = {row["examination_id"]: row for row in data.get("examinations", []) if "examination_id" in row}
    failures = 0
    for result in data.get("examination_results", []):
        try:
            exam = examinations[result["examination_id"]]
            enrollment = enrollments[result["student_id"]]
            failures += _date(exam["examination_date"]) < _date(enrollment["enrollment_date"])
            failures += _decimal(result["marks_obtained"]) > _decimal(exam["maximum_marks"])
            failures += _decimal(result["marks_obtained"]) < 0
            failures += bool(result["pass_flag"]) != (_decimal(result["marks_obtained"]) >= _decimal(exam["maximum_marks"]) * Decimal("0.50"))
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "examination_results_valid", "table": "examination_results", "failures": failures}]


def attendance_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("attendance", []):
        try:
            value = _decimal(row["attendance_percentage"])
            failures += value < 0 or value > 100
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "attendance_percentage_between_0_and_100", "table": "attendance", "failures": failures}]


def fees_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("fees_payments", []):
        try:
            total = _decimal(row["total_fee"])
            paid = _decimal(row["amount_paid"])
            failures += paid < 0 or total < 0 or paid > total
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "fee_payment_amount_not_above_total", "table": "fees_payments", "failures": failures}]


def final_grade_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    passing_students = {row.get("student_id") for row in data.get("examination_results", []) if row.get("pass_flag") is True}
    failures = sum(
        1
        for row in data.get("enrollments", [])
        if row.get("completion_status") == "completed" and row.get("final_grade") == "F" and row.get("student_id") in passing_students
    )
    return [{"check": "final_grade_aligns_with_results", "table": "enrollments", "failures": failures}]


def academic_standing_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    valid_statuses = {"good_standing", "probation", "suspension"}
    failures = 0
    for row in data.get("academic_standing_events", []):
        try:
            status = row.get("standing_status")
            gpa = _decimal(row["gpa"])
            attempted = int(row["credits_attempted"])
            earned = int(row["credits_earned"])
            failures += status not in valid_statuses
            failures += gpa < 0 or gpa > 4
            failures += attempted < 0 or earned < 0 or earned > attempted
            if status == "good_standing":
                failures += row.get("reason_code") != "not_applicable"
                failures += gpa < Decimal("2.00")
            else:
                failures += row.get("reason_code") == "not_applicable"
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "academic_standing_status_gpa_and_credits_valid", "table": "academic_standing_events", "failures": failures}]


BUSINESS_RULES = (
    valid_value_validation,
    student_dates_validation,
    assignment_dates_validation,
    examination_validation,
    attendance_validation,
    fees_validation,
    final_grade_validation,
    academic_standing_validation,
)
