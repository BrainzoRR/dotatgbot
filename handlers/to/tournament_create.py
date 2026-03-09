from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

log = logging.getLogger(__name__)
router = Router()

# ══════════════════════════════════════════════
# FSM States
# ══════════════════════════════════════════════
class TournamentCreateFSM(StatesGroup):
    name       = State()
    tier       = State()
    region     = State()
    format     = State()
    team_count = State()
    event_type = State()
    prize_pool = State()
    start_week = State()
    confirm    = State()

TIERS   = ["D", "C", "B", "A"]
REGIONS = ["WEU", "EEU", "NA", "SA", "CN", "SEA", "GLOBAL"]
FORMATS = ["RR", "GSL", "SE", "DE", "SWISS→DE"]
TEAM_COUNTS = ["8", "12", "16", "24"]

TIER_MIN_REP = {"D": 0, "C": 100, "B": 250, "A": 500}

def inline_kb(items: list, prefix: str, cols: int = 2):
    btns = [InlineKeyboardButton(text=i, callback_data=f"{prefix}:{i}") for i in items]
    rows = [btns[i:i+cols] for i in range(0, len(btns), cols)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ══════════════════════════════════════════════
# /to <subcommand>
# ══════════════════════════════════════════════
@router.message(Command("to"))
async def cmd_to_start(msg: Message, state: FSMContext):
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 2:
        return await msg.answer(
            "📋 <b>TO команды:</b>\n\n"
            "/to profile — профиль организатора\n"
            "/to tournament create — создать турнир\n"
            "/to tournament list — мои турниры"
        )

    sub = parts[1].lower()

    if sub == "profile":
        from sqlalchemy import select
        from database.session import async_session
        from database.models import User, Organizer
        async with async_session() as s:
            res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
            u = res.scalar_one_or_none()
            if not u or not u.organizer_id:
                return await msg.answer("❌ У тебя нет организации. Зарегистрируйся через /start.")
            o = await s.get(Organizer, u.organizer_id)
        verified = "✅ Верифицирован" if o.is_verified else "⏳ Ожидает верификации Admin"
        await msg.answer(
            f"{o.logo_emoji} <b>{o.name}</b> [{o.tag}]\n\n"
            f"Репутация: <b>{o.reputation:.0f}</b> (Tier {o.reputation_tier})\n"
            f"Статус: {verified}\n"
            f"Баланс: <b>${o.balance_usd:,.0f}</b>\n"
            f"Турниров проведено: <b>{o.total_tournaments_held}</b>"
        )

    elif sub == "tournament":
        action = parts[2].lower() if len(parts) > 2 else ""
        if action == "create":
            # Проверяем что пользователь TO и верифицирован
            from sqlalchemy import select
            from database.session import async_session
            from database.models import User, Organizer
            async with async_session() as s:
                res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
                u = res.scalar_one_or_none()
                if not u or u.role != "to":
                    return await msg.answer("❌ Эта команда только для Tournament Organizer.")
                if not u.organizer_id:
                    return await msg.answer("❌ У тебя нет организации.")
                o = await s.get(Organizer, u.organizer_id)
                if not o.is_verified:
                    return await msg.answer(
                        "⏳ Твоя организация ещё не верифицирована Admin.\n"
                        "Дождись подтверждения."
                    )
                await state.update_data(organizer_id=o.id, organizer_rep=o.reputation,
                                        organizer_tier=o.reputation_tier)

            # Теперь передаём реальный state — всё ок
            await _step_name(msg, state)

        elif action == "list":
            from sqlalchemy import select
            from database.session import async_session
            from database.models import User, Tournament, Organizer
            async with async_session() as s:
                res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
                u = res.scalar_one_or_none()
                if not u or not u.organizer_id:
                    return await msg.answer("❌ У тебя нет организации.")
                tres = await s.execute(
                    select(Tournament).where(Tournament.organizer_id == u.organizer_id)
                                      .order_by(Tournament.id.desc()).limit(10)
                )
                trns = tres.scalars().all()
            if not trns:
                return await msg.answer("📋 У тебя нет турниров.")
            text = "📋 <b>Мои турниры:</b>\n\n"
            STATUS_EMOJI = {
                "draft": "✏️", "pending_approval": "⏳", "approved": "✅",
                "rejected": "❌", "upcoming": "🔜", "finished": "🏁", "cancelled": "🚫"
            }
            for tr in trns:
                em = STATUS_EMOJI.get(tr.status, "❓")
                text += f"{em} <b>{tr.name}</b> [Tier {tr.tier}] | ${tr.prize_pool_usd:,.0f}\n"
            await msg.answer(text)
        else:
            await msg.answer("Использование: /to tournament create | list")
    else:
        await msg.answer(f"❓ Неизвестная команда: {sub}")

# ══════════════════════════════════════════════
# FSM шаги
# ══════════════════════════════════════════════
async def _step_name(msg: Message, state: FSMContext):
    await state.set_state(TournamentCreateFSM.name)
    await msg.answer(
        "🆕 <b>Создание турнира — Шаг 1/8</b>\n\n"
        "Введи название турнира:\n"
        "<i>Например: PGL Wallachia Season 4</i>"
    )

@router.message(TournamentCreateFSM.name)
async def fsm_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 3:
        return await msg.answer("❌ Слишком короткое название.")
    await state.update_data(name=name)
    await state.set_state(TournamentCreateFSM.tier)

    data = await state.get_data()
    org_tier = data.get("organizer_tier", "D")
    # Доступные тиры для этого TO
    available = [t for t in TIERS if TIER_MIN_REP[t] <= {"D":0,"C":100,"B":250,"A":500,"S":750}.get(org_tier, 0)]
    if not available:
        available = ["D"]

    await msg.answer(
        f"Название: <b>{name}</b>\n\n"
        f"<b>Шаг 2/8</b> — Выбери Тир турнира:\n"
        f"<i>Твой Тир TO: {org_tier}</i>",
        reply_markup=inline_kb(available, "tier")
    )

@router.callback_query(TournamentCreateFSM.tier, F.data.startswith("tier:"))
async def fsm_tier(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    tier = cb.data.split(":")[1]
    await state.update_data(tier=tier)
    await state.set_state(TournamentCreateFSM.region)
    await cb.message.edit_text(
        f"Тир: <b>{tier}</b>\n\n"
        f"<b>Шаг 3/8</b> — Выбери регион:",
        reply_markup=inline_kb(REGIONS, "region", cols=3)
    )

@router.callback_query(TournamentCreateFSM.region, F.data.startswith("region:"))
async def fsm_region(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    region = cb.data.split(":")[1]
    await state.update_data(region=region)
    await state.set_state(TournamentCreateFSM.format)
    await cb.message.edit_text(
        f"Регион: <b>{region}</b>\n\n"
        f"<b>Шаг 4/8</b> — Формат турнира:",
        reply_markup=inline_kb(FORMATS, "fmt", cols=2)
    )

@router.callback_query(TournamentCreateFSM.format, F.data.startswith("fmt:"))
async def fsm_format(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    fmt = cb.data.split(":")[1]
    await state.update_data(format=fmt)
    await state.set_state(TournamentCreateFSM.team_count)
    await cb.message.edit_text(
        f"Формат: <b>{fmt}</b>\n\n"
        f"<b>Шаг 5/8</b> — Количество команд:",
        reply_markup=inline_kb(TEAM_COUNTS, "tc", cols=4)
    )

@router.callback_query(TournamentCreateFSM.team_count, F.data.startswith("tc:"))
async def fsm_tc(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    tc = int(cb.data.split(":")[1])
    await state.update_data(team_count=tc)
    await state.set_state(TournamentCreateFSM.event_type)
    await cb.message.edit_text(
        f"Команд: <b>{tc}</b>\n\n"
        f"<b>Шаг 6/8</b> — Тип события:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🖥 Online", callback_data="evt:online"),
            InlineKeyboardButton(text="🏟 LAN",    callback_data="evt:lan"),
        ]])
    )

@router.callback_query(TournamentCreateFSM.event_type, F.data.startswith("evt:"))
async def fsm_event_type(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    evt = cb.data.split(":")[1]
    await state.update_data(event_type=evt)
    await state.set_state(TournamentCreateFSM.prize_pool)
    await cb.message.edit_text(
        f"Тип: <b>{'LAN 🏟' if evt == 'lan' else 'Online 🖥'}</b>\n\n"
        f"<b>Шаг 7/8</b> — Введи призовой пул в USD:\n"
        f"<i>Например: 50000</i>"
    )

@router.message(TournamentCreateFSM.prize_pool)
async def fsm_prize(msg: Message, state: FSMContext):
    try:
        prize = float(msg.text.replace(",", "").replace("$", "").replace(" ", ""))
        assert prize >= 0
    except (ValueError, AssertionError):
        return await msg.answer("❌ Введи число. Например: 50000")
    await state.update_data(prize_pool_usd=prize)
    await state.set_state(TournamentCreateFSM.start_week)
    await msg.answer(
        f"Призовой пул: <b>${prize:,.0f}</b>\n\n"
        f"<b>Шаг 8/8</b> — Введи стартовую неделю (1–28):"
    )

@router.message(TournamentCreateFSM.start_week)
async def fsm_week(msg: Message, state: FSMContext):
    try:
        week = int(msg.text.strip())
        assert 1 <= week <= 28
    except (ValueError, AssertionError):
        return await msg.answer("❌ Введи число от 1 до 28.")

    await state.update_data(start_week=week)
    await state.set_state(TournamentCreateFSM.confirm)
    data = await state.get_data()

    await msg.answer(
        f"📋 <b>Подтверждение турнира</b>\n\n"
        f"Название:  <b>{data['name']}</b>\n"
        f"Тир:       <b>{data['tier']}</b> | Регион: <b>{data['region']}</b>\n"
        f"Формат:    <b>{data['format']}</b> | Команд: <b>{data['team_count']}</b>\n"
        f"Тип:       <b>{data['event_type'].upper()}</b>\n"
        f"Призовые:  <b>${data['prize_pool_usd']:,.0f}</b>\n"
        f"Старт:     неделя <b>{week}</b>\n\n"
        f"Отправить на одобрение Admin?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Отправить", callback_data="trn_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена",    callback_data="trn_confirm:no"),
        ]])
    )

@router.callback_query(TournamentCreateFSM.confirm, F.data.startswith("trn_confirm:"))
async def fsm_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await cb.answer()
    action = cb.data.split(":")[1]

    if action == "no":
        await state.clear()
        return await cb.message.edit_text("❌ Создание турнира отменено.")

    data = await state.get_data()

    from sqlalchemy import select
    from database.session import async_session
    from database.models import Tournament, User
    from config import settings

    async with async_session() as s:
        trn = Tournament(
            name=data["name"],
            organizer_id=data.get("organizer_id"),
            is_system=False,
            tier=data["tier"],
            region=data["region"],
            format=data["format"],
            team_count=data["team_count"],
            event_type=data["event_type"],
            prize_pool_usd=data["prize_pool_usd"],
            start_week=data["start_week"],
            status="pending_approval",
            season=1,
        )
        s.add(trn)
        await s.flush()
        trn_id = trn.id

        # Данные организатора для уведомления
        res = await s.execute(select(User).where(User.telegram_id == cb.from_user.id))
        u = res.scalar_one_or_none()
        from database.models import Organizer
        org = await s.get(Organizer, u.organizer_id) if u and u.organizer_id else None
        org_name = org.name if org else "Неизвестно"
        org_tier = org.reputation_tier if org else "D"
        org_rep  = org.reputation if org else 0

        await s.commit()

    await state.clear()
    await cb.message.edit_text(
        f"✅ <b>Турнир отправлен на одобрение!</b>\n\n"
        f"Название: <b>{data['name']}</b>\n"
        f"ID: <code>#{trn_id}</code>\n"
        f"Статус: ⏳ <i>pending_approval</i>\n\n"
        f"Admin рассмотрит заявку и ты получишь уведомление."
    )

 

    notify_text = (
        f"📋 <b>НОВЫЙ ТУРНИР НА ОДОБРЕНИЕ #{trn_id}</b>\n\n"
        f"TO: <b>{org_name}</b> (Tier {org_tier}, Rep: {org_rep:.0f})\n"
        f"Название: <b>{data['name']}</b>\n"
        f"Тир: <b>{data['tier']}</b> | Регион: <b>{data['region']}</b>\n"
        f"Формат: <b>{data['format']}</b> | Команд: <b>{data['team_count']}</b>\n"
        f"Тип: <b>{data['event_type'].upper()}</b>\n"
        f"Призовые: <b>${data['prize_pool_usd']:,.0f}</b>\n"
        f"Старт: неделя <b>{data['start_week']}</b>"
    )
    approve_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"adm_trn_approve:{trn_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_trn_reject:{trn_id}"),
    ]])

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, notify_text, reply_markup=approve_kb)
        except Exception as e:
            log.warning(f"Не удалось уведомить Admin {admin_id}: {e}")
