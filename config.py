from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    openai_api_key: str = "sk-mock"
    gemini_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    vision_provider: Literal["openai", "gemini"] = "openai"
    narration_cooldown_seconds: int = 25
    max_history_items: int = 50
    mock_mode: bool = False  # Set MOCK_MODE=true in .env to bypass all OpenAI calls

    class Config:
        env_file = ".env"


settings = Settings()
