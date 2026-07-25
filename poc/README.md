# PoC

Черновая реализация монолита из `docs/architecture.md` (раздел «Что упрощено в PoC»):
один процесс, одна БД PostgreSQL, без Kafka и без отдельных сервисов.
`classify_stub` и `generate_stub` — заглушки с контрактом входа/выхода целевых
ML Service и Generation Service, без реальных моделей.

## Запуск

```
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/support_poc
uvicorn main:app --reload
```

## Эндпоинты

- `POST /tickets` — создать тикет; синхронно проходит `classify_stub` →
  (`risk=high` → escalate) | (`generate_stub` → confidence low → escalate / confidence high → ответ).
- `GET /tickets/{id}` — получить статус тикета.

Каждый шаг маршрутизации пишется в `audit_log`.
