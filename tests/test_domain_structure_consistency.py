from pathlib import Path


def test_all_domains_have_standard_folder_structure():
    root = Path("dataforge/domains")
    expected = {
        "__init__.py",
        "schemas.py",
        "generators.py",
        "relationships.py",
        "validations.py",
        "issue_injection.py",
        "fixtures.py",
        "constants.py",
    }
    for domain in ("retail", "logistics", "healthcare", "finance", "insurance", "banking"):
        files = {path.name for path in (root / domain).glob("*.py")}
        assert expected <= files
