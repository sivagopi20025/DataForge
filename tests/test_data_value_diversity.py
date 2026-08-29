from __future__ import annotations

import csv
from collections import Counter

from dataforge.domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.logistics.generators import LogisticsGenerator
from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.retail.generators import RetailGenerator
from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.exporter import export_run
from dataforge.modes import build_artifacts
from dataforge.synthetic_values import full_name


def _assert_no_small_sample_repetition(values: list[str]) -> None:
    counts = Counter(values)
    assert max(counts.values()) == 1


def test_synthetic_person_pool_does_not_repeat_like_tiny_fixtures():
    names_100 = [full_name(i, "retail") for i in range(1, 101)]
    names_100k = [full_name(i, "retail") for i in range(1, 100_001)]

    assert len(set(names_100)) == 100
    assert max(Counter(names_100k).values()) <= 8


def test_identity_values_are_diverse_across_domain_generators():
    cases = [
        (
            RetailGenerator(100, seed=11).generate()["customers"],
            lambda row: f"{row['first_name']} {row['last_name']}",
            "email",
        ),
        (
            HealthcareGenerator(100, seed=12).generate()["patients"],
            lambda row: f"{row['first_name']} {row['last_name']}",
            "email",
        ),
        (
            EcommerceGenerator(100, seed=13).generate()["marketplace_customers"],
            lambda row: row["customer_name"],
            "email",
        ),
        (
            FinanceGenerator(100, seed=14).generate()["customers"],
            lambda row: f"{row['first_name']} {row['last_name']}",
            "email",
        ),
        (
            InsuranceGenerator(100, seed=15).generate()["customers"],
            lambda row: f"{row['first_name']} {row['last_name']}",
            "email",
        ),
        (
            EducationGenerator(100, seed=16).generate()["students"],
            lambda row: row["student_name"],
            None,
        ),
        (
            TelecommunicationsGenerator(100, seed=17).generate()["telecom_customers"],
            lambda row: row["customer_name"],
            "email",
        ),
        (
            LogisticsGenerator(100, seed=18).generate()["drivers"],
            lambda row: row["driver_name"],
            None,
        ),
        (
            ManufacturingGenerator(100, seed=19).generate()["employees"],
            lambda row: row["employee_name"],
            None,
        ),
        (
            BankingGenerator(100, seed=20).generate()["customers"],
            lambda row: row["customer_name"],
            None,
        ),
    ]

    for rows, value_selector, email_column in cases:
        values = [value_selector(row) for row in rows]
        _assert_no_small_sample_repetition(values)
        if email_column:
            emails = [row[email_column] for row in rows]
            assert len(set(emails)) == len(emails)


def test_banking_business_customer_names_are_not_generic_client_placeholders():
    rows = BankingGenerator(100, seed=20).generate()["customers"]

    business_rows = [row for row in rows if row["customer_type"] != "Individual"]

    assert business_rows
    assert all(" Client " not in row["customer_name"] for row in business_rows)
    assert any("Capital" in row["customer_name"] or "Treasury" in row["customer_name"] for row in business_rows)


def test_generated_csv_exports_keep_headers_and_rows_aligned_for_all_domains(tmp_path):
    for domain, generator_type in DOMAIN_GENERATORS.items():
        spec = DOMAIN_SPECS[domain]
        data = generator_type(100, seed=31).generate()
        run_dir = tmp_path / domain
        export_run(
            run_dir,
            build_artifacts(data, "bulk", seed=31, spec=spec),
            ["csv"],
            {
                "run_id": f"{domain}-alignment",
                "domain": domain,
                "requested_records": 100,
                "realism_profile": "realistic",
                "load_type": "bulk",
                "output_formats": ["csv"],
                "selected_tables": sorted(data),
                "generated_at": "2026-08-15T00:00:00+00:00",
            },
            {},
            [],
            spec,
        )

        for path in (run_dir / "bulk").glob("*.csv"):
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader)
                for row_index, row in enumerate(reader, 1):
                    assert len(row) == len(header), f"{domain}/{path.name} row {row_index} has shifted columns"
