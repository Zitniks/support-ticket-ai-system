"""
L0 Rule Matcher — продовая версия rule_matcher.ipynb.

Ловит типовые тикеты по regex-подстрокам без обращения к ML-моделям
(см. docs/ml.md, раздел «Этап L0 — поиск по подстрокам»).
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleResult:
    category: Optional[str] = None      # "billing", "outage", "integration", None
    is_mass_incident: bool = False
    confidence: float = 0.0
    matched_pattern: str = ""


class L0RuleMatcher:
    # Класс 1: Проблемы с оплатой
    BILLING_RU = re.compile(
        r"(не прошла|не проходит|ошибка)\s+(оплата|плат[ёе]ж|оплатить)|"
        r"(сняли|списали)\s+(деньги|средства)|"
        r"(карта|картой)\s+(не принимается|отклонена|declined)|"
        r"(двойное|повторное)\s+списание|"
        r"(верните|возврат)\s+(деньги|средства|оплату)|"
        r"двойн(ая|ое)\s+(оплата|списание)|"
        r"не могу\s+оплатить",
        re.IGNORECASE
    )

    BILLING_EN = re.compile(
        r"(payment|charge)\s+(failed|declined|error)|"
        r"(money|funds)\s+(deducted|withdrawn|charged)|"
        r"(card|credit card)\s+(declined|not working)|"
        r"(double|duplicate)\s+charge|"
        r"(refund|money back)|"
        r"can't\s+pay",
        re.IGNORECASE
    )

    # Класс 2: Недоступность сервиса
    OUTAGE_RU = re.compile(
        r"(сайт|приложение|сервис|платформа)\s+(не работает|недоступен|лежит|down|упал)|"
        r"(ошибка|код)\s+(500|503|502|504)|"
        r"не (открывается|грузится)\s+(сайт|приложение|страница)|"
        r"(полный|массовый)\s+сбой\s+(сервиса|сайта)|"
        r"висит\s+(на|при)\s+загрузке",
        re.IGNORECASE
    )

    OUTAGE_EN = re.compile(
        r"(site|app|service|platform)\s+(is down|not working|unavailable|crashed)|"
        r"(error|code)\s+(500|503|502|504)|"
        r"(can't access|unable to reach)|"
        r"(complete|total)\s+outage|"
        r"stuck\s+on\s+loading",
        re.IGNORECASE
    )

    # Класс 3: Недоступность внешних интеграций
    INTEGRATION_RU = re.compile(
        r"(интеграция|внешний сервис|сторонний сервис|api|вебхук|webhook)\s+"
        r"(не работает|недоступен|ошибка|не отвечает|не синхронизируется|упал)|"
        r"(не подключается|ошибка соединения|connection error)\s+"
        r"(интеграция|api|внешний)|"
        r"не приходят\s+(данные|запросы)\s+из\s+(внешнего|стороннего)",
        re.IGNORECASE
    )

    INTEGRATION_EN = re.compile(
        r"(integration|external service|third.party|webhook|api)\s+"
        r"(is down|not working|error|failed|not responding|not syncing)|"
        r"(connection error|failed to connect)\s+(integration|api)|"
        r"not receiving\s+(data|requests)\s+from\s+(external|third.party)",
        re.IGNORECASE
    )

    # Индикаторы массового сбоя (модификаторы)
    MASS_RU = re.compile(
        r"(у всех|всем|массово|весь|полностью|никто не может|все пользователи|везде|повсеместно)",
        re.IGNORECASE
    )
    MASS_EN = re.compile(
        r"(everyone|all users|widespread|completely|nobody can|all over|everywhere)",
        re.IGNORECASE
    )

    # Negative patterns (исключаем false positives)
    NEGATIVE_BILLING = re.compile(
        r"(отдел\s+(оплаты|billing)|способ\s+(оплаты|payment)|"
        r"история\s+(оплаты|payments)|работа\s+в\s+(оплате|billing)|"
        r"оплата\s+прошла\s+успешно)",
        re.IGNORECASE
    )

    NEGATIVE_OUTAGE = re.compile(
        r"(сайт\s+работает|приложение\s+работает|"
        r"не\s+работает\s+(кнопка|фильтр|поиск|функция))",
        re.IGNORECASE
    )

    NEGATIVE_INTEGRATION = re.compile(
        r"(интеграция\s+успешно\s+(завершена|настроена)|"
        r"подключить\s+интеграцию|новая\s+интеграция)",
        re.IGNORECASE
    )

    def match(self, text: str) -> RuleResult:
        text_lower = text.lower()

        # Сначала проверяем массовость (модификатор)
        is_mass = bool(self.MASS_RU.search(text_lower) or self.MASS_EN.search(text_lower))

        # Класс 1: Billing
        if not self.NEGATIVE_BILLING.search(text_lower):
            if self.BILLING_RU.search(text_lower) or self.BILLING_EN.search(text_lower):
                return RuleResult(
                    category="billing",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="billing_strict"
                )

        # Класс 2: Outage
        if not self.NEGATIVE_OUTAGE.search(text_lower):
            if self.OUTAGE_RU.search(text_lower) or self.OUTAGE_EN.search(text_lower):
                return RuleResult(
                    category="outage",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="outage_strict"
                )

        # Класс 3: Integration
        if not self.NEGATIVE_INTEGRATION.search(text_lower):
            if self.INTEGRATION_RU.search(text_lower) or self.INTEGRATION_EN.search(text_lower):
                return RuleResult(
                    category="integration",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="integration_strict"
                )

        # ABSTAIN → идём в L1 (BERT)
        return RuleResult(
            category=None,
            is_mass_incident=is_mass,  # даже если класс не определён, массовость может быть сигналом
            confidence=0.0,
            matched_pattern="abstain"
        )
