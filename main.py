
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from config import settings

# Импорт роутеров (раскомментируй в реальном проекте)
from handlers.common import router as common_router
from handlers.gm.roster import router as gm_roster_router
from handlers.gm.match import router as gm_match_router
from handlers.to.tournament_create import router as to_create_router
from handlers.admin.time_control import router as admin_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def main():
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(token=settings.bot_token, parse_mode="Markdown")
    dp = Dispatcher(storage=storage)
    
    dp.include_router(common_router)
    dp.include_router(gm_roster_router)
    dp.include_router(gm_match_router)
    dp.include_router(to_create_router)
    dp.include_router(admin_router)
    
  # Создать таблицы
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

# Засеять данные (один раз)
from data.seed_data import seed_all
async with async_session() as s:
    await seed_all(s)
    
    log.info("🎮 DOTA 2 FM запущен!")
    await dp.start_polling(bot, skip_updates=True)
    print("Раскомментируй main() для запуска. Добавь settings в config.py.")

if __name__ == "__main__":
    asyncio.run(main())
