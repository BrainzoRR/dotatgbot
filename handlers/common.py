from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

log = logging.getLogger(__name__)
router = Router()

class RegStates(StatesGroup):
    choose_role = State()

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
    await state.set_state(RegStates.choose_role)
    await msg.answer(
        "👋 *Добро пожаловать в DOTA 2 FM!*\n\nВыбери свою роль:",
        reply_markup=role_kb(),
        parse_mode="Markdown"
    )

@router.callback_query(RegStates.choose_role, F.data.startswith("role_"))
async def cb_choose_role(cb: CallbackQuery, state: FSMContext):
    # Сразу отвечаем Telegram — кнопка перестаёт "грузиться"
    await cb.answer()

    try:
        role = cb.data.split("_", 1)[1]
        await state.update_data(role=role)

        if role == "gm":
            text = (
                "🎯 Роль General Manager выбрана.\n\n"
                "Используй /team для информации о команде,\n"
                "или /roster для просмотра состава."
            )
        elif role == "to":
            text = (
                "🏆 Роль Tournament Organizer выбрана.\n\n"
                "Используй /to register Название ТЕГ для регистрации.\n"
                "После этого Admin верифицирует твою заявку."
            )
        else:
            text = (
                "👁 Ты зарегистрирован как Spectator.\n"
                "Можешь смотреть статистику и рынок."
            )

        await cb.message.edit_text(text)
        await state.clear()

    except Exception as e:
        log.error(f"Ошибка в cb_choose_role: {e}", exc_info=True)
        await cb.message.answer(f"❌ Ошибка: {e}")

@router.message(Command("help"))
async def cmd_help(msg: Message):
    text = (
        "📚 Команды DOTA 2 FM\n\n"
        "Общие:\n"
        "/start — регистрация / главное меню\n"
        "/me — мой профиль\n\n"
        "GM:\n"
        "/roster — состав команды\n"
        "/player ник — профиль игрока\n"
        "/market — свободные агенты\n"
        "/schedule — расписание матчей\n"
        "/results — последние результаты\n\n"
        "TO:\n"
        "/to register Название ТЕГ\n"
        "/to tournament create\n"
        "/to profile\n\n"
        "Admin:\n"
        "/admin time status\n"
        "/admin time advance\n"
        "/admin tournament pending\n"
        "/admin backup now"
    )
    await msg.answer(text)

@router.message(Command("me"))
async def cmd_me(msg: Message):
    await msg.answer(
        f"👤 Профиль\n\n"
        f"Telegram: @{msg.from_user.username}\n"
        f"ID: {msg.from_user.id}\n"
        f"Роль: Spectator (нет данных в БД)"
    )
