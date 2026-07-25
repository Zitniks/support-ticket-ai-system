# PoC

Черновая реализация монолита из `docs/architecture.md` (раздел «Что упрощено в PoC»):
один процесс, одна БД PostgreSQL, без Kafka и без отдельных сервисов.
`classify_stub` реально использует `L0RuleMatcher` (regex), при ABSTAIN — placeholder вместо L1.
`generate_stub` — заглушка вместо LLM+RAG.

## Запуск через Docker (рекомендуется)

```
docker compose up --build
```

Поднимет Postgres и API на `http://localhost:8000`.

## Запуск локально

```
pip install -r requirements.txt
docker compose up -d db   # только Postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/support_poc
uvicorn main:app --reload
```

## Эндпоинты

- `POST /tickets` — создать тикет; заголовок `Idempotency-Key` опционален
  (повторный запрос с тем же ключом возвращает исходный тикет, не создаёт новый).
  Синхронно проходит `classify_stub` →
  (`risk=high` → escalate) | (`generate_stub` → confidence low → escalate / confidence high → ответ).
- `GET /tickets/{id}` — получить статус тикета.
- `GET /tickets/{id}/audit` — лог решений по тикету (audit trail).

Текст тикета в `audit_log` проходит PII-редакцию (`pii.py`, placeholder вместо Presidio) —
в самой таблице `tickets` хранится исходный текст, он нужен для обработки.

## Пример

```
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"channel": "chat", "text": "Не прошла оплата картой", "user_category": "billing"}'
```
