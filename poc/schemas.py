from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TicketCreate(BaseModel):
    channel: str
    text: str
    user_category: Optional[str] = None


class TicketResponse(BaseModel):
    id: UUID
    status: str
    predicted_category: Optional[str] = None
    risk: Optional[str] = None
    response_text: Optional[str] = None

    class Config:
        from_attributes = True
