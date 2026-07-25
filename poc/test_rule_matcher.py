"""Тесты L0RuleMatcher (перенесены из rule_matcher.ipynb)."""
import pytest

from rule_matcher import L0RuleMatcher

matcher = L0RuleMatcher()

TEST_CASES = [
    ("Не прошла оплата картой, уже три раза пробовал", "billing", False),
    ("У всех не работает сайт, ошибка 500", "outage", True),
    ("Webhook не отвечает, данные не синхронизируются", "integration", False),
    ("Как подключить интеграцию с вашим API?", None, False),  # ABSTAIN: setup, не проблема
    ("Работа в отделе оплаты, есть вакансии?", None, False),  # ABSTAIN: false positive
    ("Сайт работает, но кнопка 'Купить' не работает", None, False),  # ABSTAIN: partial outage = tech
    ("Верните деньги за прошлый месяц", "billing", False),
    ("У всех пользователей упал внешний сервис интеграции", "integration", True),
    ("Can't pay with my Visa card, keeps declining", "billing", False),
    ("The app is completely down for everyone", "outage", True),
]


@pytest.mark.parametrize("text,expected_category,expected_mass", TEST_CASES)
def test_match(text, expected_category, expected_mass):
    result = matcher.match(text)
    assert result.category == expected_category
    assert result.is_mass_incident == expected_mass
