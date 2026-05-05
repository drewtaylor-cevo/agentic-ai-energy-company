"""Unit tests for agent/specialists/hardship_config.py — Task 1.4.

Verifies:
- All four categories present in HARDSHIP_CATEGORIES
- Each category has the required keys
- permitted_tools values are frozensets
- family_violence has financial_terms_forbidden=True
- FINANCIAL_TERMS is a frozenset with expected members
"""
from agent.specialists.hardship_config import (
    HARDSHIP_CATEGORIES,
    FINANCIAL_TERMS,
    HardshipCategory,
)

EXPECTED_CATEGORIES = {"payment_difficulty", "medical_equipment", "family_violence", "other"}
REQUIRED_KEYS = {"routing_target", "permitted_tools", "permitted_actions", "financial_terms_forbidden"}


class TestHardshipCategoriesPresence:
    """All four categories are present in the registry."""

    def test_all_four_categories_present(self):
        assert set(HARDSHIP_CATEGORIES.keys()) == EXPECTED_CATEGORIES

    def test_no_extra_categories(self):
        assert len(HARDSHIP_CATEGORIES) == 4


class TestCategoryRequiredKeys:
    """Each category dict has the required keys."""

    def test_payment_difficulty_has_required_keys(self):
        assert REQUIRED_KEYS.issubset(HARDSHIP_CATEGORIES["payment_difficulty"].keys())

    def test_medical_equipment_has_required_keys(self):
        assert REQUIRED_KEYS.issubset(HARDSHIP_CATEGORIES["medical_equipment"].keys())

    def test_family_violence_has_required_keys(self):
        assert REQUIRED_KEYS.issubset(HARDSHIP_CATEGORIES["family_violence"].keys())

    def test_other_has_required_keys(self):
        assert REQUIRED_KEYS.issubset(HARDSHIP_CATEGORIES["other"].keys())


class TestPermittedToolsAreFrozensets:
    """permitted_tools values must be frozensets (immutable at runtime)."""

    def test_payment_difficulty_permitted_tools_is_frozenset(self):
        assert isinstance(HARDSHIP_CATEGORIES["payment_difficulty"]["permitted_tools"], frozenset)

    def test_medical_equipment_permitted_tools_is_frozenset(self):
        assert isinstance(HARDSHIP_CATEGORIES["medical_equipment"]["permitted_tools"], frozenset)

    def test_family_violence_permitted_tools_is_frozenset(self):
        assert isinstance(HARDSHIP_CATEGORIES["family_violence"]["permitted_tools"], frozenset)

    def test_other_permitted_tools_is_frozenset(self):
        assert isinstance(HARDSHIP_CATEGORIES["other"]["permitted_tools"], frozenset)


class TestFamilyViolenceFinancialTermsForbidden:
    """family_violence category must have financial_terms_forbidden=True."""

    def test_family_violence_financial_terms_forbidden_is_true(self):
        assert HARDSHIP_CATEGORIES["family_violence"]["financial_terms_forbidden"] is True

    def test_other_categories_not_all_forbidden(self):
        """At least one non-family_violence category has financial_terms_forbidden=False."""
        non_fv = {k: v for k, v in HARDSHIP_CATEGORIES.items() if k != "family_violence"}
        assert any(not v["financial_terms_forbidden"] for v in non_fv.values())


class TestFinancialTerms:
    """FINANCIAL_TERMS frozenset contains the expected forbidden terminology."""

    def test_financial_terms_is_frozenset(self):
        assert isinstance(FINANCIAL_TERMS, frozenset)

    def test_financial_terms_contains_expected_members(self):
        expected = {
            "dollar", "payment", "bill", "tariff", "plan",
            "cost", "price", "save", "switch", "account",
            "balance", "debt", "arrears", "overdue",
        }
        assert FINANCIAL_TERMS == expected

    def test_financial_terms_count(self):
        assert len(FINANCIAL_TERMS) == 14
