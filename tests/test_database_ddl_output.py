import zipfile

from dataforge.ddl import generate_ddl_package
from dataforge.domains import DOMAIN_SPECS


DDL_FILES = {
    "ddl/schema.sql",
    "ddl/tables.sql",
    "ddl/indexes.sql",
    "ddl/constraints.sql",
    "ddl/foreign_keys.sql",
}


def _package_sql(tmp_path, domain: str, database_type: str) -> dict[str, str]:
    spec = DOMAIN_SPECS[domain]
    package = generate_ddl_package(
        output_dir=tmp_path,
        domain=domain,
        spec=spec,
        selected_tables=set(spec.schemas),
        database_type=database_type,
    )
    with zipfile.ZipFile(package.path) as archive:
        assert set(archive.namelist()) == DDL_FILES
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def test_postgresql_ddl_package_has_required_files_and_syntax(tmp_path):
    sql = _package_sql(tmp_path, "ecommerce", "postgresql")
    assert 'CREATE SCHEMA IF NOT EXISTS "dataforge_ecommerce";' in sql["ddl/schema.sql"]
    assert "BOOLEAN" in sql["ddl/tables.sql"]
    assert "TIMESTAMP" in sql["ddl/tables.sql"]
    assert 'CREATE TABLE "dataforge_ecommerce"."marketplace_customers"' in sql["ddl/tables.sql"]


def test_mssql_ddl_package_has_required_files_and_syntax(tmp_path):
    sql = _package_sql(tmp_path, "education", "mssql")
    assert "CREATE SCHEMA [dataforge_education]" in sql["ddl/schema.sql"]
    assert "NVARCHAR" in sql["ddl/tables.sql"]
    assert "BIT" in sql["ddl/tables.sql"]
    assert "DATETIME2" in sql["ddl/tables.sql"]
    assert "GO" in sql["ddl/schema.sql"]


def test_mysql_ddl_package_has_required_files_and_syntax(tmp_path):
    sql = _package_sql(tmp_path, "telecommunications", "mysql")
    assert "CREATE DATABASE IF NOT EXISTS `dataforge_telecommunications`;" in sql["ddl/schema.sql"]
    assert "BOOLEAN" in sql["ddl/tables.sql"]
    assert "DATETIME" in sql["ddl/tables.sql"]
    assert "USE `dataforge_telecommunications`;" in sql["ddl/schema.sql"]


def test_all_domains_support_database_ddl_output(tmp_path):
    for domain, spec in DOMAIN_SPECS.items():
        package = generate_ddl_package(
            output_dir=tmp_path / domain,
            domain=domain,
            spec=spec,
            selected_tables=set(spec.schemas),
            database_type="postgresql",
        )
        assert package.path.name == f"{domain}_postgresql_ddl.zip"
        with zipfile.ZipFile(package.path) as archive:
            assert set(archive.namelist()) == DDL_FILES


def test_foreign_key_sql_preserves_representative_domain_relationships(tmp_path):
    expectations = {
        "retail": ['FOREIGN KEY ("category_id") REFERENCES "dataforge_retail"."categories" ("category_id")'],
        "manufacturing": ['FOREIGN KEY ("factory_id") REFERENCES "dataforge_manufacturing"."factories" ("factory_id")'],
        "telecommunications": ['FOREIGN KEY ("subscription_id") REFERENCES "dataforge_telecommunications"."subscriptions" ("subscription_id")'],
        "education": ['FOREIGN KEY ("institution_id") REFERENCES "dataforge_education"."institutions" ("institution_id")'],
        "ecommerce": ['FOREIGN KEY ("customer_id") REFERENCES "dataforge_ecommerce"."marketplace_customers" ("customer_id")'],
    }
    for domain, fragments in expectations.items():
        sql = _package_sql(tmp_path / domain, domain, "postgresql")["ddl/foreign_keys.sql"]
        for fragment in fragments:
            assert fragment in sql
