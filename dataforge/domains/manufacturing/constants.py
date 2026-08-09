from __future__ import annotations

FACTORY_TYPES = ("automotive", "electronics", "pharmaceutical", "food_processing", "textile", "industrial_equipment")
FACTORY_STATUSES = ("active", "maintenance", "closed")
PRODUCT_CATEGORIES = ("electronics", "automotive", "medical_device", "packaged_food", "textile", "industrial_part")
LINE_STATUSES = ("active", "maintenance", "idle")
MACHINE_TYPES = ("cnc", "assembly_robot", "conveyor", "packaging_machine", "welding_machine", "molding_machine", "inspection_station")
MACHINE_STATUSES = ("active", "maintenance", "offline", "retired")
SUPPLIER_STATUSES = ("active", "probation", "inactive")
MATERIAL_TYPES = ("metal", "plastic", "chemical", "electronic_component", "fabric", "packaging")
UNITS_OF_MEASURE = ("kg", "liter", "unit", "meter", "case")
WORK_ORDER_STATUSES = ("planned", "in_progress", "completed", "delayed", "cancelled")
BATCH_STATUSES = ("running", "completed", "failed", "quarantined")
QUALITY_CHECK_TYPES = ("incoming", "in_process", "final", "regulatory")
QUALITY_RESULTS = ("passed", "failed", "rework_required")
DEFECT_TYPES = ("surface_damage", "dimensional_error", "electrical_failure", "contamination", "missing_component", "packaging_defect")
SEVERITIES = ("low", "medium", "high", "critical")
ROOT_CAUSES = ("operator_error", "machine_wear", "supplier_quality", "process_variation", "environmental_condition")
MAINTENANCE_TYPES = ("preventive", "corrective", "emergency", "inspection")
MAINTENANCE_PRIORITIES = ("low", "medium", "high", "critical")
MAINTENANCE_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")
EMPLOYEE_ROLES = ("operator", "supervisor", "inspector", "technician", "manager")
SHIFTS = ("day", "swing", "night")
INVENTORY_TYPES = ("raw_material", "finished_good")

CITIES = (
    ("Detroit", "MI", "USA"),
    ("Austin", "TX", "USA"),
    ("Chicago", "IL", "USA"),
    ("Phoenix", "AZ", "USA"),
    ("Greenville", "SC", "USA"),
    ("Toronto", "ON", "Canada"),
    ("Monterrey", "NL", "Mexico"),
)

FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas", "Ivy", "Owen")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis", "Miller", "Nguyen")
MANUFACTURERS = ("Fanuc", "Siemens", "ABB", "Bosch", "Mitsubishi", "Honeywell")
