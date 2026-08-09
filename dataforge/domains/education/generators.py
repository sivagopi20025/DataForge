from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import full_name
from .constants import (
    ASSIGNMENT_TYPES,
    ATTENDANCE_STATUSES,
    COMPLETION_STATUSES,
    COUNTRIES,
    COURSE_TYPES,
    DEGREE_LEVELS,
    DEPARTMENTS,
    DESIGNATIONS,
    EMPLOYMENT_STATUSES,
    ENROLLMENT_STATUSES,
    EXAMINATION_TYPES,
    FEE_TYPES,
    FIRST_NAMES,
    GENDERS,
    GRADES,
    GRADING_STATUSES,
    INSTITUTION_TYPES,
    LAST_NAMES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    STATUSES,
    STUDENT_STATUSES,
)
from .schemas import EDUCATION_SPEC


class EducationGenerator:
    def __init__(self, enrollment_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if enrollment_records < 1:
            raise ValueError("records must be at least 1")
        self.enrollment_records = enrollment_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.enrollment_records * ratio))
        return min(value, maximum) if maximum else value

    def _name(self, index: int) -> str:
        return full_name(index, "education")

    def _money(self, value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01")))

    def _grade_for_score(self, score: Decimal, maximum: Decimal) -> str:
        percentage = (score / maximum) * Decimal("100") if maximum else Decimal("0")
        if percentage >= 95:
            return "A+"
        if percentage >= 88:
            return "A"
        if percentage >= 80:
            return "B+"
        if percentage >= 72:
            return "B"
        if percentage >= 65:
            return "C+"
        if percentage >= 58:
            return "C"
        if percentage >= 50:
            return "D"
        return "F"

    def _required_tables(self) -> set[str]:
        if not self.selected_tables:
            return set(EDUCATION_SPEC.schemas)
        required = set(self.selected_tables)
        dependencies = {
            "campuses": {"institutions"},
            "departments": {"campuses"},
            "academic_programs": {"departments"},
            "courses": {"departments"},
            "instructors": {"departments"},
            "students": {"academic_programs"},
            "class_sections": {"courses", "instructors"},
            "enrollments": {"students", "class_sections"},
            "attendance": {"enrollments"},
            "assignments": {"class_sections"},
            "assignment_submissions": {"assignments", "students"},
            "examinations": {"class_sections"},
            "examination_results": {"examinations", "students"},
            "fees_payments": {"students"},
            "academic_standing_events": {"students", "academic_programs"},
        }
        changed = True
        while changed:
            changed = False
            for table in tuple(required):
                missing = dependencies.get(table, set()) - required
                if missing:
                    required.update(missing)
                    changed = True
        return required

    def generate(self) -> Dataset:
        required = self._required_tables()

        def need(table: str) -> bool:
            return table in required

        institution_count = self._count(0.01, 3, 500)
        campus_count = self._count(0.03, 6, 2000)
        department_count = self._count(0.08, 12, 10000)
        program_count = self._count(0.12, 20, 25000)
        course_count = self._count(0.18, 30, 75000)
        instructor_count = self._count(0.12, 25, 50000)
        student_count = self._count(0.45, 120, 250000)
        section_count = self._count(0.25, 45, 120000)
        attendance_count = max(1, int(self.enrollment_records * 1.4))
        assignment_count = self._count(0.20, 40, 120000)
        submission_count = max(1, int(self.enrollment_records * 1.1))
        examination_count = self._count(0.16, 30, 100000)
        result_count = max(1, int(self.enrollment_records * 1.0))
        payment_count = self._count(0.50, 100, 250000)
        standing_count = self._count(0.30, 40, 200000)
        base = date(2026, 1, 8) if self.load_type == "bulk" else date(2026, 6, 1)
        data: Dataset = {}

        if need("institutions"):
            data["institutions"] = []
            for i in range(1, institution_count + 1):
                city, state, country = COUNTRIES[i % len(COUNTRIES)]
                data["institutions"].append({
                    "institution_id": 1000000 + i,
                    "institution_name": f"DataForge {INSTITUTION_TYPES[i % len(INSTITUTION_TYPES)].replace('_', ' ').title()} {i:03d}",
                    "institution_type": INSTITUTION_TYPES[i % len(INSTITUTION_TYPES)],
                    "country": country,
                    "state": state,
                    "city": city,
                    "established_year": 1950 + i % 70,
                    "accreditation": f"ACC-{country[:2].upper()}-{i:04d}",
                    "status": "active" if i % 29 else STATUSES[i % len(STATUSES)],
                    "created_at": str(base - timedelta(days=2000 + i)),
                })

        if need("campuses"):
            data["campuses"] = []
            for i in range(1, campus_count + 1):
                institution = data["institutions"][(i - 1) % len(data["institutions"])]
                data["campuses"].append({
                    "campus_id": 2000000 + i,
                    "institution_id": institution["institution_id"],
                    "campus_name": f"{institution['city']} Campus {i:03d}",
                    "address": f"{100 + i % 9000} Learning Avenue",
                    "city": institution["city"],
                    "state": institution["state"],
                    "country": institution["country"],
                    "status": "active" if i % 31 else STATUSES[i % len(STATUSES)],
                    "created_at": str(base - timedelta(days=1500 + i)),
                })

        if need("departments"):
            data["departments"] = []
            for i in range(1, department_count + 1):
                campus = data["campuses"][(i - 1) % len(data["campuses"])]
                department_name = DEPARTMENTS[i % len(DEPARTMENTS)]
                data["departments"].append({
                    "department_id": 3000000 + i,
                    "campus_id": campus["campus_id"],
                    "department_name": department_name,
                    "department_code": "".join(part[0] for part in department_name.split()) + f"{i:03d}",
                    "head_of_department": self._name(i),
                    "status": "active" if i % 37 else STATUSES[i % len(STATUSES)],
                    "created_at": str(base - timedelta(days=1200 + i)),
                })

        if need("academic_programs"):
            data["academic_programs"] = []
            for i in range(1, program_count + 1):
                department = data["departments"][(i - 1) % len(data["departments"])]
                level = DEGREE_LEVELS[i % len(DEGREE_LEVELS)]
                duration = {"diploma": 2, "undergraduate": 4, "postgraduate": 2, "doctorate": 5, "certification": 1}[level]
                data["academic_programs"].append({
                    "program_id": 4000000 + i,
                    "department_id": department["department_id"],
                    "program_name": f"{level.replace('_', ' ').title()} in {department['department_name']}",
                    "degree_level": level,
                    "duration_years": duration,
                    "credits_required": 30 * duration,
                    "status": "active" if i % 41 else STATUSES[i % len(STATUSES)],
                    "created_at": str(base - timedelta(days=900 + i)),
                })

        if need("courses"):
            data["courses"] = []
            for i in range(1, course_count + 1):
                department = data["departments"][(i - 1) % len(data["departments"])]
                data["courses"].append({
                    "course_id": 5000000 + i,
                    "department_id": department["department_id"],
                    "course_code": f"{department['department_code'][:3].upper()}-{100 + i % 800}",
                    "course_name": f"{department['department_name']} Course {i:04d}",
                    "credit_hours": 1 + i % 5,
                    "semester": f"Semester {1 + i % 8}",
                    "course_type": COURSE_TYPES[i % len(COURSE_TYPES)],
                    "status": "active" if i % 43 else STATUSES[i % len(STATUSES)],
                    "created_at": str(base - timedelta(days=750 + i)),
                })

        if need("instructors"):
            data["instructors"] = []
            for i in range(1, instructor_count + 1):
                department = data["departments"][(i - 1) % len(data["departments"])]
                hire_date = base - timedelta(days=365 + i % 5000)
                data["instructors"].append({
                    "instructor_id": 6000000 + i,
                    "department_id": department["department_id"],
                    "instructor_name": self._name(i + 2000),
                    "designation": DESIGNATIONS[i % len(DESIGNATIONS)],
                    "hire_date": hire_date.isoformat(),
                    "specialization": department["department_name"],
                    "employment_status": "active" if i % 47 else EMPLOYMENT_STATUSES[i % len(EMPLOYMENT_STATUSES)],
                    "created_at": hire_date.isoformat(),
                })

        if need("students"):
            data["students"] = []
            for i in range(1, student_count + 1):
                program = data["academic_programs"][(i - 1) % len(data["academic_programs"])]
                admission = base - timedelta(days=30 + i % 900)
                duration = int(program["duration_years"])
                data["students"].append({
                    "student_id": 7000000 + i,
                    "program_id": program["program_id"],
                    "student_name": self._name(i + 5000),
                    "gender": GENDERS[i % len(GENDERS)],
                    "birth_date": str(admission - timedelta(days=18 * 365 + i % 2500)),
                    "admission_date": admission.isoformat(),
                    "expected_graduation_date": (admission + timedelta(days=365 * duration)).isoformat(),
                    "academic_year": f"{2022 + i % 5}-{2023 + i % 5}",
                    "status": "active" if i % 23 else STUDENT_STATUSES[i % len(STUDENT_STATUSES)],
                    "created_at": admission.isoformat(),
                })

        if need("class_sections"):
            data["class_sections"] = []
            for i in range(1, section_count + 1):
                course = data["courses"][(i - 1) % len(data["courses"])]
                instructor = data["instructors"][(i - 1) % len(data["instructors"])]
                data["class_sections"].append({
                    "section_id": 8000000 + i,
                    "course_id": course["course_id"],
                    "instructor_id": instructor["instructor_id"],
                    "section_name": f"{course['course_code']}-SEC-{1 + i % 12:02d}",
                    "semester": course["semester"],
                    "academic_year": f"{2025 + i % 2}-{2026 + i % 2}",
                    "classroom": f"Room-{100 + i % 500}",
                    "capacity": 20 + i % 80,
                    "schedule": ("Mon/Wed 09:00", "Tue/Thu 11:00", "Fri 14:00", "Online Async")[i % 4],
                    "created_at": str(base - timedelta(days=60 + i % 120)),
                })

        if need("enrollments"):
            data["enrollments"] = []
            for i in range(1, self.enrollment_records + 1):
                student = data["students"][(i - 1) % len(data["students"])]
                section = data["class_sections"][(i - 1) % len(data["class_sections"])]
                score = Decimal(55 + i % 45)
                grade = self._grade_for_score(score, Decimal("100"))
                data["enrollments"].append({
                    "enrollment_id": 9000000 + i,
                    "student_id": student["student_id"],
                    "section_id": section["section_id"],
                    "enrollment_date": (base + timedelta(days=i % 30)).isoformat(),
                    "enrollment_status": "enrolled" if i % 19 else ENROLLMENT_STATUSES[i % len(ENROLLMENT_STATUSES)],
                    "final_grade": grade,
                    "completion_status": "completed" if grade != "F" else COMPLETION_STATUSES[2],
                    "created_at": (base + timedelta(days=i % 30)).isoformat(),
                })

        if need("attendance"):
            data["attendance"] = []
            for i in range(1, attendance_count + 1):
                enrollment = data["enrollments"][(i - 1) % len(data["enrollments"])]
                percentage = Decimal(70 + i % 31)
                data["attendance"].append({
                    "attendance_id": 10000000 + i,
                    "enrollment_id": enrollment["enrollment_id"],
                    "attendance_date": (date.fromisoformat(enrollment["enrollment_date"]) + timedelta(days=1 + i % 90)).isoformat(),
                    "attendance_status": "present" if i % 7 else ATTENDANCE_STATUSES[i % len(ATTENDANCE_STATUSES)],
                    "attendance_percentage": self._money(percentage),
                    "created_at": (date.fromisoformat(enrollment["enrollment_date"]) + timedelta(days=1 + i % 90)).isoformat(),
                })

        if need("assignments"):
            data["assignments"] = []
            for i in range(1, assignment_count + 1):
                section = data["class_sections"][(i - 1) % len(data["class_sections"])]
                assigned = base + timedelta(days=10 + i % 90)
                data["assignments"].append({
                    "assignment_id": 11000000 + i,
                    "section_id": section["section_id"],
                    "assignment_title": f"Assignment {i:04d}",
                    "assignment_type": ASSIGNMENT_TYPES[i % len(ASSIGNMENT_TYPES)],
                    "assigned_date": assigned.isoformat(),
                    "due_date": (assigned + timedelta(days=7 + i % 14)).isoformat(),
                    "maximum_marks": "100.00",
                    "created_at": assigned.isoformat(),
                })

        if need("assignment_submissions"):
            data["assignment_submissions"] = []
            for i in range(1, submission_count + 1):
                assignment = data["assignments"][(i - 1) % len(data["assignments"])]
                student = data["students"][(i - 1) % len(data["students"])]
                marks = Decimal(45 + i % 56)
                data["assignment_submissions"].append({
                    "submission_id": 12000000 + i,
                    "assignment_id": assignment["assignment_id"],
                    "student_id": student["student_id"],
                    "submission_date": (date.fromisoformat(assignment["assigned_date"]) + timedelta(days=1 + i % 10)).isoformat(),
                    "marks_obtained": self._money(marks),
                    "grading_status": "graded" if i % 13 else GRADING_STATUSES[i % len(GRADING_STATUSES)],
                    "created_at": (date.fromisoformat(assignment["assigned_date"]) + timedelta(days=1 + i % 10)).isoformat(),
                })

        if need("examinations"):
            data["examinations"] = []
            for i in range(1, examination_count + 1):
                section = data["class_sections"][(i - 1) % len(data["class_sections"])]
                exam_date = base + timedelta(days=60 + i % 120)
                data["examinations"].append({
                    "examination_id": 13000000 + i,
                    "section_id": section["section_id"],
                    "examination_name": f"{EXAMINATION_TYPES[i % len(EXAMINATION_TYPES)].title()} Exam {i:04d}",
                    "examination_type": EXAMINATION_TYPES[i % len(EXAMINATION_TYPES)],
                    "examination_date": exam_date.isoformat(),
                    "maximum_marks": "100.00",
                    "created_at": exam_date.isoformat(),
                })

        if need("examination_results"):
            data["examination_results"] = []
            for i in range(1, result_count + 1):
                examination = data["examinations"][(i - 1) % len(data["examinations"])]
                student = data["students"][(i - 1) % len(data["students"])]
                marks = Decimal(45 + i % 56)
                data["examination_results"].append({
                    "result_id": 14000000 + i,
                    "examination_id": examination["examination_id"],
                    "student_id": student["student_id"],
                    "marks_obtained": self._money(marks),
                    "grade": self._grade_for_score(marks, Decimal("100")),
                    "pass_flag": marks >= Decimal("50"),
                    "created_at": (date.fromisoformat(examination["examination_date"]) + timedelta(days=5)).isoformat(),
                })

        if need("fees_payments"):
            data["fees_payments"] = []
            for i in range(1, payment_count + 1):
                student = data["students"][(i - 1) % len(data["students"])]
                total = Decimal(5000 + (i % 15000))
                paid = total if i % 5 else total / Decimal("2")
                data["fees_payments"].append({
                    "payment_id": 15000000 + i,
                    "student_id": student["student_id"],
                    "academic_year": student["academic_year"],
                    "fee_type": FEE_TYPES[i % len(FEE_TYPES)],
                    "total_fee": self._money(total),
                    "amount_paid": self._money(paid),
                    "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                    "payment_date": (date.fromisoformat(student["admission_date"]) + timedelta(days=10 + i % 60)).isoformat(),
                    "payment_status": "paid" if paid == total else PAYMENT_STATUSES[-1],
                    "created_at": (date.fromisoformat(student["admission_date"]) + timedelta(days=10 + i % 60)).isoformat(),
                })

        if need("academic_standing_events"):
            data["academic_standing_events"] = []
            for i in range(1, standing_count + 1):
                student = data["students"][(i - 1) % len(data["students"])]
                program = data["academic_programs"][(i - 1) % len(data["academic_programs"])]
                event_date = date.fromisoformat(student["admission_date"]) + timedelta(days=120 + i % 365)
                if i % 41 == 0:
                    status = "suspension"
                    gpa = Decimal("1.45") + Decimal(i % 25) / Decimal("100")
                    reason = "low_gpa"
                elif i % 11 == 0:
                    status = "probation"
                    gpa = Decimal("1.80") + Decimal(i % 70) / Decimal("100")
                    reason = "insufficient_credits" if i % 2 else "low_gpa"
                else:
                    status = "good_standing"
                    gpa = Decimal("2.70") + Decimal(i % 130) / Decimal("100")
                    reason = "not_applicable"
                credits_attempted = 12 + i % 108
                credits_earned = credits_attempted if status == "good_standing" else max(0, credits_attempted - (3 + i % 18))
                data["academic_standing_events"].append({
                    "academic_standing_event_id": 16000000 + i,
                    "student_id": student["student_id"],
                    "program_id": program["program_id"],
                    "event_date": event_date.isoformat(),
                    "standing_status": status,
                    "gpa": self._money(gpa),
                    "credits_attempted": credits_attempted,
                    "credits_earned": credits_earned,
                    "reason_code": reason,
                })

        return enrich_dataset(data, self.load_type, self.scd_type, EDUCATION_SPEC)
