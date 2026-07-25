"""
PoC-монолит: FastAPI + PostgreSQL, без Kafka и отдельных сервисов.

Роутинг — последовательный код, повторяющий целевую схему из docs/architecture.md
(раздел «Что упрощено в PoC»):

    Клиент -> API -> classify_stub -> (risk high -> escalate)
                                    -> (risk low/medium -> generate_stub -> (confidence low -> escalate)
                                                                          -> (confidence high -> ответ клиенту))
"""
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

import models
from db import Base, engine, get_db
from ml_stub import classify_stub, generate_stub
from schemas import TicketCreate, TicketResponse

GENERATION_CONFIDENCE_THRESHOLD = 0.6

app = FastAPI(title="Support Ticket AI System — PoC")

Base.metadata.create_all(bind=engine)


def log_event(db: Session, ticket_id, event: str, details: str = ""):
    db.add(models.AuditLog(ticket_id=ticket_id, event=event, details=details))
    db.commit()


@app.post("/tickets", response_model=TicketResponse)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = models.Ticket(
        channel=payload.channel,
        text=payload.text,
        user_category=payload.user_category,
        status="processing",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    log_event(db, ticket.id, "ticket_received", payload.channel)

    classification = classify_stub(payload.text, payload.user_category)
    ticket.predicted_category = classification.category
    ticket.risk = classification.risk
    ticket.ml_confidence = classification.confidence
    db.commit()
    log_event(
        db, ticket.id, "classified",
        f"category={classification.category} risk={classification.risk} confidence={classification.confidence}",
    )

    if classification.risk == "high":
        ticket.status = "escalated"
        db.commit()
        log_event(db, ticket.id, "escalated", "risk=high")
        return ticket

    generation = generate_stub(payload.text, classification.category)
    ticket.gen_confidence = generation.confidence

    if generation.confidence < GENERATION_CONFIDENCE_THRESHOLD:
        ticket.status = "escalated"
        db.commit()
        log_event(
            db, ticket.id, "escalated",
            f"generation_confidence={generation.confidence} < {GENERATION_CONFIDENCE_THRESHOLD}",
        )
        return ticket

    ticket.response_text = generation.response_text
    ticket.status = "resolved_auto"
    db.commit()
    log_event(db, ticket.id, "auto_responded", f"confidence={generation.confidence}")
    return ticket


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id, db: Session = Depends(get_db)):
    return db.query(models.Ticket).get(ticket_id)
