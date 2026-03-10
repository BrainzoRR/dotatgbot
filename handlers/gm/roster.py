from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

ROLE_NAMES = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Soft Sup", 5: "Hard Sup"}
FORM_EMOJI = {
    range(1, 31):  "🔴",
    range(31, 51): "🟠",
    range(51, 71): "🟡",
    range(71, 86): "🟢",
    range(86, 101):"⭐",
}

def get_form_emoji(form: float) -> str:
    for r, e in FORM_EMOJI.items():
        if int(form) in r:
            return e
    return "🟡"

def format_player_card(p, detailed=False) -> str:
    fe = get_form_emoji(p.form)
    card = (
        f"**[{ROLE_NAMES.get(p.primary_role, '?')}] {p.nickname}**\n"
        f"  Форма: {fe} {p.form:.0f} | "
        f"Возраст: {p.age} | {p.nationality or '??'}\n"
        f"  💵 ${p.salary_per_month:,.0f}/мес\n"
    )
    if detailed:
        card += (
            f"\n  📊 *Характеристики:*\n"
            f"  Mechanics: {p.mechanics:.0f} | Laning: {p.laning:.0f}\n"
            f"  GameSense: {p.game_sense:.0f} | Teamfight: {p.teamfight:.0f}\n"
            f"  DraftIQ: {p.draft_iq:.0f} | Clutch: {p.clutch:.0f}\n"
            f"  Comm: {p.communication:.0f} | Consistency: {p.consistency:.0f}\n"
            f"  Mental: {p.mental:.0f} | Physical: {p.physical:.0f}\n"
        )
    return card

@router.message(Command("roster"))
async def cmd_roster(msg: Message):
    # TODO: получить team через DB по user_id
    # Пример без реальной БД:
    await msg.answer(
        "📋 *Ростер команды*\n\n"
        "_Нет данных. Убедись что ты GM и твоя команда в БД._",
        parse_mode="HTML"
    )



