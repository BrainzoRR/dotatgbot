from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("schedule"))
async def cmd_schedule(msg: Message):
    await msg.answer(
        "📅 *Расписание матчей*\n\n"
        "_Здесь будут ближайшие матчи твоей команды._",
        parse_mode="Markdown"
    )

@router.message(Command("results"))
async def cmd_results(msg: Message):
    await msg.answer(
        "📊 *Последние результаты*\n\n"
        "_История матчей команды._",
        parse_mode="Markdown"
    )

@router.message(Command("match"))
async def cmd_match(msg: Message):
    args = msg.text.split()
    if len(args) < 2:
        return await msg.answer("Использование: /match <id>")
    match_id = args[1]
    # TODO: get match + narrative from DB
    await msg.answer(
        f"🎮 *Матч #{match_id}*\n\n"
        "_Детальный отчёт будет здесь._",
        parse_mode="Markdown"
    )
