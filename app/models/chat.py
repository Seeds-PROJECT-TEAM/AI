from pydantic import BaseModel, Field
from typing import List, Literal

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(..., max_length=4000)

class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: List[ChatMessage]
    persona: str | None = "tutor"  # 예: "tutor", "coach"

class ChatResponse(BaseModel):
    reply: str