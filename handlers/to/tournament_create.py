# FSM — пошаговое создание турнира
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class TournamentCreateFSM(StatesGroup):
    name        = State()
    tier        = State()
    region      = State()
    format      = State()
    team_count  = State()
    selection   = State()
    event_type  = State()
    prize_pool  = State()
    start_week  = State()
    confirm     = State()

TIERS = ["D", "C", "B", "A"]  # S- требует репутации
REGIONS = ["WEU", "EEU", "NA", "SA", "CN", "SEA", "GLOBAL"]
FORMATS = ["RR", "GSL", "SE", "DE", "SWISS→DE"]
TEAM_COUNTS = ["8", "12", "16", "24"]
TIERS_REP = {"D": 0, "C": 100, "B": 250, "A": 500, "S-": 750}

def inline_kb(items, prefix, cols=2):
    btns = [InlineKeyboardButton(text=i, callback_data=f"{prefix}:{i}")
            for i in items]
    rows = [btns[i:i+cols] for i in range(0, len(btns), cols)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(Command("to"))
async def cmd_to_start(msg: Message):
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 2:
        return await msg.answer("Использование: /to <команда>\nНапример: /to profile, /to tournament create")

    sub = parts[1].lower()
    if sub == "register" and len(parts) >= 3:
        rest = parts[2].split()
        if len(rest) < 2:
            return await msg.answer("Использование: /to register <Название> <ТЕГ>")
        name, tag = " ".join(rest[:-1]), rest[-1].upper()
        # TODO: создать Organizer в БД + уведомить Admin
        await msg.answer(
            f"✅ Заявка организатора *{name}* [{tag}] отправлена.\n"
            f"Ожидай верификации Admin.",
            parse_mode="Markdown"
        )
    elif sub == "profile":
        await msg.answer("🏆 *Профиль TO*\n\n_Нет данных в БД._", parse_mode="Markdown")
    elif sub == "tournament" and len(parts) >= 3 and parts[2] == "create":
        await start_tournament_create(msg, FSMContext)  # передай реальный state

async def start_tournament_create(msg: Message, state: FSMContext):
    await state.set_state(TournamentCreateFSM.name)
    await msg.answer(
        "🆕 *Создание турнира — Шаг 1/9*\n\n"
        "Введите *название* турнира:",
        parse_mode="Markdown"
    )

@router.message(TournamentCreateFSM.name)
async def fsm_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(TournamentCreateFSM.tier)
    # TODO: получить reputation_tier TO из БД для фильтрации
    await msg.answer(
        f"📋 Название: *{msg.text}*\n\n"
        "*Шаг 2/9* — Выберите Тир турнира:",
        reply_markup=inline_kb(TIERS, "tier"),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.tier, F.data.startswith("tier:"))
async def fsm_tier(cb: CallbackQuery, state: FSMContext):
    tier = cb.data.split(":")[1]
    await state.update_data(tier=tier)
    await state.set_state(TournamentCreateFSM.region)
    await cb.message.edit_text(
        f"Тир: *{tier}*\n\n*Шаг 3/9* — Выберите регион:",
        reply_markup=inline_kb(REGIONS, "region", cols=3),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.region, F.data.startswith("region:"))
async def fsm_region(cb: CallbackQuery, state: FSMContext):
    region = cb.data.split(":")[1]
    await state.update_data(region=region)
    await state.set_state(TournamentCreateFSM.format)
    await cb.message.edit_text(
        f"Регион: *{region}*\n\n*Шаг 4/9* — Формат:",
        reply_markup=inline_kb(FORMATS, "fmt", cols=2),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.format, F.data.startswith("fmt:"))
async def fsm_format(cb: CallbackQuery, state: FSMContext):
    fmt = cb.data.split(":")[1]
    await state.update_data(format=fmt)
    await state.set_state(TournamentCreateFSM.team_count)
    await cb.message.edit_text(
        f"Формат: *{fmt}*\n\n*Шаг 5/9* — Количество команд:",
        reply_markup=inline_kb(TEAM_COUNTS, "tc", cols=4),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.team_count, F.data.startswith("tc:"))
async def fsm_tc(cb: CallbackQuery, state: FSMContext):
    tc = int(cb.data.split(":")[1])
    await state.update_data(team_count=tc)
    await state.set_state(TournamentCreateFSM.event_type)
    await cb.message.edit_text(
        f"Команд: *{tc}*\n\n*Шаг 6/9* — Тип события:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🖥 Online", callback_data="evt:online"),
            InlineKeyboardButton(text="🏟 LAN", callback_data="evt:lan"),
        ]]),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.event_type, F.data.startswith("evt:"))
async def fsm_event_type(cb: CallbackQuery, state: FSMContext):
    evt = cb.data.split(":")[1]
    await state.update_data(event_type=evt)
    await state.set_state(TournamentCreateFSM.prize_pool)
    await cb.message.edit_text(
        f"Тип: *{'LAN 🏟' if evt == 'lan' else 'Online 🖥'}*\n\n"
        "*Шаг 7/9* — Введите призовой пул в USD:\n"
        "_Например: 50000_",
        parse_mode="Markdown"
    )

@router.message(TournamentCreateFSM.prize_pool)
async def fsm_prize(msg: Message, state: FSMContext):
    try:
        prize = float(msg.text.replace(",", "").replace("$", ""))
    except ValueError:
        return await msg.answer("❌ Введи число. Например: 50000")
    await state.update_data(prize_pool_usd=prize)
    await state.set_state(TournamentCreateFSM.start_week)
    await msg.answer(
        f"Призовой пул: *${prize:,.0f}*\n\n"
        "*Шаг 8/9* — Введите стартовую неделю (1-28):",
        parse_mode="Markdown"
    )

@router.message(TournamentCreateFSM.start_week)
async def fsm_week(msg: Message, state: FSMContext):
    try:
        week = int(msg.text)
        assert 1 <= week <= 28
    except (ValueError, AssertionError):
        return await msg.answer("❌ Неделя должна быть числом от 1 до 28.")
    await state.update_data(start_week=week)
    await state.set_state(TournamentCreateFSM.confirm)

    data = await state.get_data()
    summary = (
        "📋 *Подтверждение турнира — Шаг 9/9*\n\n"
        f"Название: *{data.get('name')}*\n"
        f"Тир: *{data.get('tier')}* | Регион: *{data.get('region')}*\n"
        f"Формат: *{data.get('format')}* | Команд: *{data.get('team_count')}*\n"
        f"Тип: *{data.get('event_type', '').upper()}*\n"
        f"Призовой пул: *${data.get('prize_pool_usd', 0):,.0f}*\n"
        f"Старт: неделя *{week}*\n\n"
        "Отправить на одобрение Admin?"
    )
    await msg.answer(
        summary,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Отправить", callback_data="trn_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="trn_confirm:no"),
        ]]),
        parse_mode="Markdown"
    )

@router.callback_query(TournamentCreateFSM.confirm, F.data.startswith("trn_confirm:"))
async def fsm_confirm(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]
    if action == "no":
        await state.clear()
        return await cb.message.edit_text("❌ Создание турнира отменено.")

    data = await state.get_data()
    # TODO: сохранить Tournament в БД со статусом pending_approval
    # TODO: уведомить всех Admin
    await state.clear()
    await cb.message.edit_text(
        "✅ *Турнир отправлен на одобрение!*\n\n"
        f"Название: *{data.get('name')}*\n"
        "Статус: `pending_approval`\n\n"
        "Admin получит уведомление и рассмотрит заявку.",
        parse_mode="Markdown"
    )
