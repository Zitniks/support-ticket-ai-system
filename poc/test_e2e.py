"""
E2E-тесты API (вместо ручных curl): поднимают приложение через TestClient
и проверяют не только HTTP-ответ, но и что реально записалось в БД
(tickets, audit_log).

Требуют доступную Postgres по DATABASE_URL (см. db.py) — например,
`docker compose up -d db` перед запуском.
"""
from fastapi.testclient import TestClient

from db import SessionLocal
from main import app
import models

client = TestClient(app)


def _db_ticket(ticket_id):
    db = SessionLocal()
    try:
        return db.query(models.Ticket).filter_by(id=ticket_id).one()
    finally:
        db.close()


def _db_audit_events(ticket_id):
    db = SessionLocal()
    try:
        return (
            db.query(models.AuditLog)
            .filter_by(ticket_id=ticket_id)
            .order_by(models.AuditLog.created_at)
            .all()
        )
    finally:
        db.close()


def test_billing_ticket_auto_resolves_and_persists():
    resp = client.post(
        "/tickets",
        json={"channel": "chat", "text": "Не прошла оплата картой, деньги списали дважды"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved_auto"
    assert body["predicted_category"] == "billing"
    assert body["risk"] == "low"
    assert body["response_text"]

    # Проверяем, что реально записалось в tickets
    ticket = _db_ticket(body["id"])
    assert ticket.status == "resolved_auto"
    assert ticket.predicted_category == "billing"
    assert ticket.text == "Не прошла оплата картой, деньги списали дважды"
    assert ticket.response_text == body["response_text"]

    # И что записалось в audit_log — вся цепочка решений
    events = [e.event for e in _db_audit_events(body["id"])]
    assert events == ["ticket_received", "classified", "auto_responded"]


def test_mass_outage_escalates_and_persists():
    resp = client.post(
        "/tickets",
        json={"channel": "web", "text": "У всех не работает сайт, ошибка 500"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "escalated"
    assert body["predicted_category"] == "outage"
    assert body["risk"] == "high"
    assert body["response_text"] is None

    ticket = _db_ticket(body["id"])
    assert ticket.status == "escalated"
    assert ticket.risk == "high"
    assert ticket.response_text is None

    events = [e.event for e in _db_audit_events(body["id"])]
    assert events == ["ticket_received", "classified", "escalated"]


def test_idempotency_key_returns_same_ticket_and_no_duplicate_row():
    headers = {"Idempotency-Key": "e2e-test-key-1"}
    payload = {"channel": "chat", "text": "Верните деньги за прошлый месяц"}

    first = client.post("/tickets", json=payload, headers=headers).json()
    second = client.post("/tickets", json=payload, headers=headers).json()

    assert first["id"] == second["id"]

    db = SessionLocal()
    try:
        count = db.query(models.Ticket).filter_by(idempotency_key="e2e-test-key-1").count()
    finally:
        db.close()
    assert count == 1


def test_pii_redacted_in_audit_log_but_not_in_raw_ticket():
    raw_text = "Мой email ivan@example.com, карта 4111 1111 1111 1111 не работает"
    resp = client.post("/tickets", json={"channel": "email", "text": raw_text})
    body = resp.json()

    # В самой таблице tickets хранится исходный (нередактированный) текст — нужен для обработки
    ticket = _db_ticket(body["id"])
    assert ticket.text == raw_text

    # А в audit_log — редактированная версия
    events = _db_audit_events(body["id"])
    received = next(e for e in events if e.event == "ticket_received")
    assert "ivan@example.com" not in received.details
    assert "4111" not in received.details
    assert "[EMAIL]" in received.details
    assert "[CARD]" in received.details


def test_audit_endpoint_matches_db_order():
    create = client.post(
        "/tickets",
        json={"channel": "chat", "text": "Не прошла оплата картой"},
    ).json()

    resp = client.get(f"/tickets/{create['id']}/audit")
    assert resp.status_code == 200
    api_events = [e["event"] for e in resp.json()]

    db_events = [e.event for e in _db_audit_events(create["id"])]
    assert api_events == db_events
