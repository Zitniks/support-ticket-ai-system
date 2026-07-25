# PoC

Черновая реализация монолита из `docs/architecture.md` (раздел «Что упрощено в PoC»):
один процесс, одна БД PostgreSQL, без Kafka и без отдельных сервисов.
`classify_stub` реально использует `L0RuleMatcher` (regex), при ABSTAIN — placeholder вместо L1.
`generate_stub` — заглушка вместо LLM+RAG.

## Запуск через Docker (рекомендуется)

```
cd poc
docker compose up --build
```

Поднимет Postgres и API на `http://localhost:8000`.

## Запуск локально

```
cd poc
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

## Тесты

`test_rule_matcher.py` — юнит-тесты L0RuleMatcher (не требуют БД):

```
cd poc
pip install -r requirements-dev.txt
pytest test_rule_matcher.py -v
```

`test_e2e.py` — гоняет API через `TestClient` и проверяет не только HTTP-ответ,
но и что реально записалось в `tickets`/`audit_log`. Требует поднятую Postgres:

```
cd poc
docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/support_poc pytest test_e2e.py -v
```

Либо внутри контейнера api (там уже есть доступ к `db` по имени сервиса):

```
cd poc
docker compose up -d
docker compose exec api pip install pytest httpx
docker compose exec -e DATABASE_URL=postgresql://postgres:postgres@db:5432/support_poc api pytest test_e2e.py -v
```
