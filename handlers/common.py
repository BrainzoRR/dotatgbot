# Регистрация и главное меню
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class RegStates(StatesGroup):
    choose_role = State()
    choose_team = State()   # для GM
    choose_org_name = State()  # для TO

MAIN_MENU_TEXT = (
    "🎮 *DOTA 2 FM*\n\n"
    "Добро пожаловать в менеджер про-сцены Dota 2!\n\n"
    "Текущая роль: *{role}*\n"
    "Команда/Организация: *{entity}*\n\n"
    "Используй /help для списка команд."
)

def role_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 General Manager (GM)",
                              callback_data="role_gm")],
        [InlineKeyboardButton(text="🏆 Tournament Organizer (TO)",
                              callback_data="role_to")],
        [InlineKeyboardButton(text="👁 Spectator",
                              callback_data="role_spectator")],
    ])

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    # Проверяем пользователя в БД (упрощённо — добавь реальный DB-вызов)
    await msg.answer(
        "👋 *Добро пожаловать в DOTA 2 FM!*\n\n"
        "Выбери свою роль:",
        reply_markup=role_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(RegStates.choose_role)

@router.callback_query(RegStates.choose_role, F.data.startswith("role_"))
async def cb_choose_role(cb, state: FSMContext):
    role = cb.data.split("_", 1)[1]
    await state.update_data(role=role)

    if role == "gm":
        await cb.message.edit_text(
            "🎯 Роль *General Manager* выбрана.\n\n"
            "Используй /team list для выбора команды,\n"
            "или /admin create_team для создания новой (только admin).",
            parse_mode="Markdown"
        )
        # TODO: сохранить role в БД
    elif role == "to":
        await cb.message.edit_text(
            "🏆 Роль *Tournament Organizer* выбрана.\n\n"
            "Используй /to register <Название> <ТЕГ> для регистрации.\n"
            "После этого Admin верифицирует твою заявку.",
            parse_mode="Markdown"
        )
    else:
        await cb.message.edit_text(
            "👁 Ты зарегистрирован как *Spectator*.\n"
            "Можешь смотреть статистику и рынок.",
            parse_mode="Markdown"
        )
    await state.clear()

@router.message(Command("help"))
async def cmd_help(msg: Message):
    text = (
        "📚 *Команды DOTA 2 FM*\n\n"
        "**Общие:**\n"
        "/start — регистрация / главное меню\n"
        "/me — мой профиль\n"
        "/team — информация о команде\n\n"
        "**GM:**\n"
        "/roster — состав команды\n"
        "/player <ник> — профиль игрока\n"
        "/market — свободные агенты\n"
        "/schedule — расписание матчей\n"
        "/results — последние результаты\n"
        "/train <тип> <интенсивность> — тренировка\n"
        "/budget — финансы\n\n"
        "**TO:**\n"
        "/to register <Название> <ТЕГ>\n"
        "/to tournament create\n"
        "/to profile\n\n"
        "**Admin:**\n"
        "/admin time status\n"
        "/admin time advance [n]\n"
        "/admin tournament pending\n"
        "/admin tournament approve <id>\n"
        "/admin backup now"
    )
    await msg.answer(text, parse_mode="Markdown")

@router.message(Command("me"))
async def cmd_me(msg: Message):
    # TODO: реальный DB-вызов
    await msg.answer(
        f"👤 *Профиль*\n\n"
        f"Telegram: @{msg.from_user.username}\n"
        f"ID: `{msg.from_user.id}`\n"
        f"Роль: *Spectator* (нет данных в БД)",
        parse_mode="Markdown"
    )
