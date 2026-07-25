"""
Заглушки ML Service и Generation Service для PoC.

Контракт входа/выхода соответствует целевой архитектуре (docs/architecture.md);
внутренняя логика — placeholder, без реальных моделей (L0/L1/L2/L3, LLM+RAG).
"""
import random
from dataclasses import dataclass
from typing import Optional

HIGH_RISK_KEYWORDS = ("возврат денег", "суд", "жалоба в цб", "мошенничество", "утечка данных")


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
    risk = "high" if any(kw in text_lower for kw in HIGH_RISK_KEYWORDS) else random.choice(["low", "medium"])
    category = user_category or "other"
    confidence = round(random.uniform(0.55, 0.95), 2)
    return ClassificationResult(category=category, risk=risk, confidence=confidence)


def generate_stub(text: str, category: str) -> GenerationResult:
    response_text = f"[draft] Спасибо за обращение по категории «{category}». Мы разбираемся в вопросе."
    confidence = round(random.uniform(0.4, 0.9), 2)
    return GenerationResult(response_text=response_text, confidence=confidence)
