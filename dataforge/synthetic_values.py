from __future__ import annotations

import re
import zlib


# Expanded synthetic pools inspired by public demographic/name-distribution
# references. These are generated values only; no public dataset rows are copied.
FIRST_NAMES: tuple[str, ...] = (
    "Aaliyah", "Aaron", "Abigail", "Adam", "Adrian", "Aisha", "Akira", "Alex",
    "Amara", "Amelia", "Andre", "Anika", "Aria", "Arjun", "Asha", "Ava",
    "Ben", "Bianca", "Caleb", "Camila", "Carlos", "Chloe", "Daniel", "Dev",
    "Diego", "Elena", "Eli", "Emma", "Ethan", "Fatima", "Felix", "Gabriel",
    "Grace", "Hana", "Harper", "Hiro", "Ibrahim", "Imani", "Isabella", "Ivan",
    "Jada", "Jamal", "James", "Jasmine", "Kai", "Kavya", "Kevin", "Layla",
    "Leo", "Liam", "Lina", "Logan", "Lucas", "Lucia", "Mateo", "Maya",
    "Mia", "Mila", "Mina", "Naomi", "Nia", "Noah", "Nora", "Olivia",
    "Omar", "Priya", "Quinn", "Rafael", "Riya", "Saanvi", "Sam", "Sara",
    "Sofia", "Tara", "Theo", "Uma", "Valeria", "Victor", "Yara", "Zara",
    "Aiden", "Anaya", "Beatrice", "Bryce", "Celine", "Darius", "Elijah", "Freya",
    "Gianna", "Hassan", "Iris", "Jonah", "Keiko", "Leila", "Malik", "Nolan",
    "Owen", "Parker", "Rohan", "Sienna", "Talia", "Vikram", "Willow", "Zoe",
    "Mason", "Sophia", "Evelyn", "Henry", "Nikhil", "Mei", "Noemi", "Ezra",
    "Ivy", "Owen", "Anjali", "Avery", "Carter", "Dylan", "Elise", "Farah",
    "Gavin", "Hazel", "Isaac", "Jun", "Kiran", "Luca", "Mira", "Nadia",
)

LAST_NAMES: tuple[str, ...] = (
    "Adams", "Ahmed", "Anderson", "Baker", "Banerjee", "Bennett", "Brooks", "Brown",
    "Campbell", "Carter", "Castillo", "Chandra", "Chang", "Chen", "Clark", "Collins",
    "Cooper", "Cruz", "Davis", "Diaz", "Edwards", "Evans", "Fisher", "Flores",
    "Foster", "Garcia", "Gomez", "Gonzalez", "Gray", "Green", "Gupta", "Hall",
    "Harris", "Hernandez", "Hill", "Howard", "Hughes", "Jackson", "Jain", "Johnson",
    "Jones", "Kapoor", "Khan", "Kim", "King", "Kumar", "Lee", "Lewis",
    "Li", "Lopez", "Martin", "Martinez", "Mehta", "Miller", "Mitchell", "Moore",
    "Morgan", "Murphy", "Nair", "Nelson", "Nguyen", "O'Brien", "Ortiz", "Pandey",
    "Parker", "Patel", "Perez", "Phillips", "Price", "Rao", "Reed", "Reyes",
    "Rivera", "Roberts", "Robinson", "Rodriguez", "Ross", "Roy", "Russell", "Sanchez",
    "Scott", "Shah", "Sharma", "Singh", "Smith", "Stewart", "Taylor", "Thomas",
    "Thompson", "Torres", "Turner", "Verma", "Walker", "Ward", "Watson", "White",
    "Williams", "Wilson", "Wong", "Wood", "Wright", "Young", "Zhang", "Zimmerman",
    "Iyer", "Das", "Morris", "Kelly", "Raman", "Chopra", "Bose", "Sato",
    "Tanaka", "Yamamoto", "Okafor", "Mensah", "Diallo", "Silva", "Costa", "Alvarez",
    "Romero", "Morales", "Peterson", "Bailey", "Coleman", "Jenkins", "Powell", "Sullivan",
    "Bell", "Hayes", "Long", "Bryant", "Alexander", "Russell", "Griffin", "Butler",
    "Simmons", "Foster", "Gonzales", "Bryan", "Hamilton", "Graham", "Wallace", "Woods",
    "Cole", "West", "Jordan", "Owens", "Reynolds", "Ferguson", "Murray", "Freeman",
    "Wells", "Webb", "Simpson", "Stevens", "Tucker", "Porter", "Hunter", "Hicks",
)

COMPANY_PREFIXES: tuple[str, ...] = (
    "Apex", "Bright", "Cedar", "Civic", "Coastal", "Core", "Crescent", "Evergreen",
    "Frontier", "Harbor", "Keystone", "Liberty", "Metro", "Northstar", "Pioneer",
    "Riverbend", "Summit", "Terra", "Union", "Vertex", "Willow", "Zenith",
)

COMPANY_SUFFIXES: tuple[str, ...] = (
    "Analytics", "Commerce", "Distribution", "Goods", "Holdings", "Industries",
    "Logistics", "Marketplace", "Manufacturing", "Networks", "Partners", "Services",
    "Systems", "Trading", "Ventures", "Works",
)


def _namespace_offset(namespace: str) -> int:
    return zlib.crc32(namespace.encode("utf-8")) & 0xFFFFFFFF


def person_name(index: int, namespace: str = "default") -> tuple[str, str]:
    """Return a deterministic, high-cardinality synthetic person name.

    The first/last-name cross product is intentionally large enough that
    duplicate full names should be rare in small samples while still naturally
    recurring at high volumes.
    """

    base = max(0, index - 1) + _namespace_offset(namespace)
    first_index = base % len(FIRST_NAMES)
    last_index = ((base // len(FIRST_NAMES)) + first_index * 17) % len(LAST_NAMES)
    cycle = base // (len(FIRST_NAMES) * len(LAST_NAMES))
    first = FIRST_NAMES[first_index]
    last = LAST_NAMES[last_index]
    if cycle:
        secondary = LAST_NAMES[(last_index + cycle * 31) % len(LAST_NAMES)]
        if secondary != last:
            last = f"{last}-{secondary}"
    return first, last


def full_name(index: int, namespace: str = "default") -> str:
    first, last = person_name(index, namespace)
    return f"{first} {last}"


def business_name(index: int, namespace: str = "business", suffix: str | None = None, *, include_index: bool = True) -> str:
    base = max(0, index - 1) + _namespace_offset(namespace)
    prefix = COMPANY_PREFIXES[(base * 19 + 5) % len(COMPANY_PREFIXES)]
    middle = LAST_NAMES[(base * 53 + 11) % len(LAST_NAMES)]
    ending = suffix or COMPANY_SUFFIXES[(base * 29 + 7) % len(COMPANY_SUFFIXES)]
    name = f"{prefix} {middle} {ending}"
    return f"{name} {index:05d}" if include_index else name


def unique_email(first_name: str, last_name: str, entity_id: int | str, namespace: str = "dataforge") -> str:
    local_first = _slug(first_name)
    local_last = _slug(last_name)
    token = _slug(str(entity_id))
    return f"{local_first}.{local_last}.{token}@{namespace}.example.test"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".")
    return cleaned or "entity"
