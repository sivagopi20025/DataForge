from __future__ import annotations

from .banking.generators import BankingGenerator
from .banking.schemas import BANKING_SPEC
from .finance.generators import FinanceGenerator
from .finance.schemas import FINANCE_SPEC
from .healthcare.generators import HealthcareGenerator
from .healthcare.schemas import HEALTHCARE_SPEC
from .insurance.generators import InsuranceGenerator
from .insurance.schemas import INSURANCE_SPEC
from .logistics.generators import LogisticsGenerator
from .logistics.schemas import LOGISTICS_SPEC
from .retail.generators import RetailGenerator
from .retail.schemas import RETAIL_SPEC


DOMAIN_SPECS = {
    "retail": RETAIL_SPEC,
    "logistics": LOGISTICS_SPEC,
    "healthcare": HEALTHCARE_SPEC,
    "finance": FINANCE_SPEC,
    "insurance": INSURANCE_SPEC,
    "banking": BANKING_SPEC,
}

DOMAIN_GENERATORS = {
    "retail": RetailGenerator,
    "logistics": LogisticsGenerator,
    "healthcare": HealthcareGenerator,
    "finance": FinanceGenerator,
    "insurance": InsuranceGenerator,
    "banking": BankingGenerator,
}
