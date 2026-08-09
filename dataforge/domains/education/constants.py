from __future__ import annotations

INSTITUTION_TYPES = ("school", "college", "university", "training_center", "online_university")
STATUSES = ("active", "inactive", "suspended")
DEGREE_LEVELS = ("diploma", "undergraduate", "postgraduate", "doctorate", "certification")
COURSE_TYPES = ("theory", "laboratory", "project", "seminar", "internship")
DESIGNATIONS = ("professor", "associate_professor", "assistant_professor", "lecturer", "teaching_assistant")
EMPLOYMENT_STATUSES = ("active", "retired", "contract")
GENDERS = ("male", "female", "other")
STUDENT_STATUSES = ("active", "graduated", "suspended", "dropped", "transferred")
ENROLLMENT_STATUSES = ("enrolled", "waitlisted", "cancelled", "withdrawn")
COMPLETION_STATUSES = ("completed", "incomplete", "failed", "withdrawn")
ATTENDANCE_STATUSES = ("present", "absent", "excused", "late")
ASSIGNMENT_TYPES = ("homework", "project", "lab", "presentation", "quiz")
GRADING_STATUSES = ("pending", "graded", "resubmission_required")
EXAMINATION_TYPES = ("midterm", "final", "practical", "viva", "quiz")
GRADES = ("A+", "A", "B+", "B", "C+", "C", "D", "F")
FEE_TYPES = ("tuition", "hostel", "transportation", "examination", "library", "miscellaneous")
PAYMENT_METHODS = ("cash", "card", "bank_transfer", "online", "scholarship")
PAYMENT_STATUSES = ("paid", "pending", "overdue", "partially_paid")

COUNTRIES = (
    ("Austin", "Texas", "USA"),
    ("Boston", "Massachusetts", "USA"),
    ("San Jose", "California", "USA"),
    ("Toronto", "Ontario", "Canada"),
    ("London", "England", "UK"),
    ("Bengaluru", "Karnataka", "India"),
)
DEPARTMENTS = (
    "Computer Science",
    "Business Administration",
    "Mathematics",
    "Biology",
    "Education",
    "Electrical Engineering",
    "Economics",
    "Data Science",
)
FIRST_NAMES = ("Ava", "Noah", "Mia", "Liam", "Sophia", "Ethan", "Isabella", "Lucas", "Amelia", "Mason")
LAST_NAMES = ("Patel", "Smith", "Garcia", "Chen", "Brown", "Kumar", "Davis", "Wilson", "Martinez", "Lee")
