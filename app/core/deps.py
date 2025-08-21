# app/core/deps.py
from functools import lru_cache
from fastapi import Header, HTTPException
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.ai_generator import AIGenerator
from app.services.learning_path import LearningPathService

def verify_service_token(x_service_token: str = Header(default="")) -> str:
    if x_service_token != settings.SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail={
            "code": "UNAUTHORIZED_SERVICE",
            "message": "invalid service token"
        })
    return x_service_token

@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService(model=settings.MODEL_CHAT, api_key=settings.OPENAI_API_KEY, temperature=settings.TEMPERATURE)

@lru_cache(maxsize=1)
def get_ai_generator() -> AIGenerator:
    return AIGenerator(model=settings.MODEL_PROBLEM, api_key=settings.OPENAI_API_KEY, temperature=settings.TEMPERATURE)

@lru_cache(maxsize=1)
def get_learning_path_service() -> LearningPathService:
    return LearningPathService(model=settings.MODEL_LP, api_key=settings.OPENAI_API_KEY, temperature=settings.TEMPERATURE)
