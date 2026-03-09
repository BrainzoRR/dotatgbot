from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "postgresql://bothost_db_fb7fd4a9fe82:Lq_YVEBqJNRR932WuY2ho4fV7otNcUnMuT6WXCLXZ8M@node1.pghost.ru:32803/bothost_db_fb7fd4a9fe82"
    redis_url: str = "redis://localhost:6379/0"
    admin_ids: List[int] = []
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
