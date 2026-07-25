"""
ML Service и Generation Service для PoC.

Классификация: L0 Rule Matcher (rule_matcher.py) — реальная рабочая логика.
Если L0 ABSTAIN (не поймал по regex), в проде тикет идёт в L1 (E5-large + CatBoost,
см. docs/ml.md) — L1 в PoC не реализован, поэтому здесь используется placeholder.
Generation Service (LLM + RAG) — по-прежнему заглушка.
"""
import random
from dataclasses import dataclass
from typing import Optional

from rule_matcher import L0RuleMatcher

HIGH_RISK_KEYWORDS = ("возврат денег", "суд", "жалоба в цб", "мошенничество", "утечка данных")

_l0_matcher = L0RuleMatcher()


@dataclass
class ClassificationResult:
    category: str
    risk: str  # "low" | "medium" | "high"
    confidence: float


@dataclass
class GenerationResult:
    response_text: str
    confidence: float


def classify_stub(text: str, user_category: Optional[str] = None) -> ClassificationResult:
    text_lower = text.lower()
    l0_result = _l0_matcher.match(text)

    if l0_result.category is not None:
        # L0 поймал по regex с confidence 0.98 — L1 не вызывается
        category = l0_result.category
        confidence = l0_result.confidence
    else:
        # ABSTAIN → в проде уходит в L1; L1 не реализован в PoC, placeholder
        category = user_category or "other"
        confidence = round(random.uniform(0.55, 0.95), 2)

    if l0_result.is_mass_incident or any(kw in text_lower for kw in HIGH_RISK_KEYWORDS):
        risk = "high"
    elif l0_result.category is not None:
        risk = "low"
    else:
        risk = random.choice(["low", "medium"])  # L1 не реализован — placeholder

    return ClassificationResult(category=category, risk=risk, confidence=confidence)


def generate_stub(text: str, category: str) -> GenerationResult:
    response_text = f"[draft] Спасибо за обращение по категории «{category}». Мы разбираемся в вопросе."
    confidence = round(random.uniform(0.4, 0.9), 2)
    return GenerationResult(response_text=response_text, confidence=confidence)
