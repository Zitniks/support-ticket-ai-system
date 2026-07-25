import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    user_category = Column(String, nullable=True)
    predicted_category = Column(String, nullable=True)
    risk = Column(String, nullable=True)
    ml_confidence = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="new")
    response_text = Column(Text, nullable=True)
    gen_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), nullable=False)
    event = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
