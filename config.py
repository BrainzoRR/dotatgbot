from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "postgresql+asyncpg://dota2fm:pass@localhost/dota2fm"
    redis_url: str = "redis://localhost:6379/0"
    admin_ids: List[int] = []
    debug: bool = False

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        # Если уже список — ок
        if isinstance(v, list):
            return v
        # Если строка "123,456" или просто "123"
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        # Если одно число
        if isinstance(v, int):
            return [v]
        return v

    class Config:
        env_file = ".env"

settings = Settings()
