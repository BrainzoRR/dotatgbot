import asyncio
import logging
import sys
import os

# Добавляем корень проекта в sys.path чтобы все импорты работали
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import settings
from database.models import Base
from database.session import engine, async_session

from handlers.common import router as common_router
from handlers.gm.roster import router as gm_roster_router
from handlers.gm.match import router as gm_match_router
from handlers.to.tournament_create import router as to_create_router
from handlers.admin.time_control import router as admin_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def main():
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=storage)

    dp.include_router(common_router)
    dp.include_router(gm_roster_router)
    dp.include_router(gm_match_router)
    dp.include_router(to_create_router)
    dp.include_router(admin_router)

    # Создать таблицы в БД
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("✅ Таблицы БД созданы/проверены")

    # Засеять начальные данные
    try:
        from data.seed_data import seed_all
        async with async_session() as s:
            await seed_all(s)
    except Exception as e:
        log.warning(f"⚠️ Seed пропущен: {e}")

    log.info("🎮 DOTA 2 FM запущен!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
