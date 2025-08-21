from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    MODEL_CHAT: str = "gpt-4o-mini"
    MODEL_PROBLEM: str = "gpt-4o"
    MODEL_LP: str = "gpt-4o-mini"
    TEMPERATURE: float = 0.2
    SERVICE_TOKEN: str = "change-me"  # Express↔FastAPI 내부 인증
    MONGODB_URI: Optional[str] = None
    AURA_URI: Optional[str] = None
    AURA_USER: Optional[str] = None
    AURA_PASS: Optional[str] = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
