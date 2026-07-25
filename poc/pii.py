"""
PII-редакция для PoC (placeholder вместо Presidio, см. docs/architecture.md).

Используется при записи текста тикета в audit_log — в самой БД тикетов
хранится исходный текст (нужен для обработки), редактируется только то,
что уходит в лог/аналитику.
"""
import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD_RE = re.compile(r"\b(?:\d[ \-]*?){13,19}\b")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = CARD_RE.sub("[CARD]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text
