from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "postgresql+asyncpg://dota2fm:pass@localhost/dota2fm"
    redis_url: str = "redis://localhost:6379/0"
    admin_ids: List[int] = []
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
