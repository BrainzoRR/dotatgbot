"""
handlers/gm/transfer.py — Трансферный рынок GM
Команды: /market, /sign, /release, /transfer
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.session import async_session
from database.models import Player, Team, User, Transfer, Contract, Finance
from database.crud.players import get_free_agents, get_player_by_nick, calc_player_rating
from database.crud.teams import get_team_by_owner, get_team
import logging

log = logging.getLogger(__name__)
router = Router()

ROLE_NAMES = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Soft Sup", 5: "Hard Sup"}


# ═══════════════════════════════════════
# FSM: подписание свободного агента
# ═══════════════════════════════════════

class SignFSM(StatesGroup):
    salary   = State()
    duration = State()
    confirm  = State()


class TransferOfferFSM(StatesGroup):
    target_nick = State()
    fee         = State()
    salary      = State()
    duration    = State()
    confirm     = State()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _player_short(p) -> str:
    role = ROLE_NAMES.get(p.primary_role, "?")
    rating = calc_player_rating(p)
    return (
        f"[{role}] <b>{p.nickname}</b> "
        f"({p.nationality or '??'}, {p.age}л) "
        f"— рейтинг {rating:.0f} | 💵${p.salary_per_month:,.0f}/мес"
    )


async def _get_gm_team(session, telegram_id: int):
    """Возвращает (user, team) для GM или (None, None)."""
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    u = res.scalar_one_or_none()
    if not u or u.role != "gm":
        return None, None
    team = await get_team_by_owner(session, u.id)
    return u, team


# ─── /market ────────────────────────────────────────────────────────────────

@router.message(Command("market"))
async def cmd_market(msg: Message):
    """Показывает свободных агентов с фильтрами."""
    args = msg.text.split()[1:]  # role / region

    async with async_session() as s:
        agents = await get_free_agents(s)

    if not agents:
        return await msg.answer("🛒 Рынок пуст — нет свободных агентов.")

    # Фильтрация
    role_filter   = None
    region_filter = None
    for a in args:
        if a.isdigit() and 1 <= int(a) <= 5:
            role_filter = int(a)
        elif a.upper() in ("WEU", "EEU", "NA", "SA", "CN", "SEA"):
            region_filter = a.upper()

    filtered = agents
    if role_filter:
        filtered = [p for p in filtered if p.primary_role == role_filter]
    if region_filter:
        filtered = [p for p in filtered if (p.nationality or "").startswith(region_filter[:2])]

    if not filtered:
        filtered = agents  # показать всех если ничего не нашлось

    # Сортировка по рейтингу
    filtered.sort(key=lambda p: calc_player_rating(p), reverse=True)
    show = filtered[:15]

    lines = ["🛒 <b>Свободные агенты</b>"]
    if role_filter or region_filter:
        lines[0] += f" (фильтр: {ROLE_NAMES.get(role_filter,'')} {region_filter or ''})"
    lines.append(f"<i>Показано {len(show)} из {len(filtered)}</i>\n")

    for p in show:
        lines.append(_player_short(p))

    lines.append(
        "\n💡 <i>/sign &lt;ник&gt; — подписать игрока\n"
        "/market 1 — только Carry\n"
        "/player &lt;ник&gt; — подробный профиль</i>"
    )
    await msg.answer("\n".join(lines))


# ─── /player <ник> ──────────────────────────────────────────────────────────

@router.message(Command("player"))
async def cmd_player(msg: Message):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer("Использование: /player <ник>")
    nick = args[1].strip()

    async with async_session() as s:
        p = await get_player_by_nick(s, nick)
        if not p:
            return await msg.answer(f"❌ Игрок <b>{nick}</b> не найден.")
        team_name = "Свободный агент"
        if p.team_id:
            t = await get_team(s, p.team_id)
            team_name = t.name if t else "Неизвестная команда"

    from database.crud.players import calc_player_rating
    rating = calc_player_rating(p)
    form_emoji = "🔴" if p.form < 31 else "🟠" if p.form < 51 else "🟡" if p.form < 71 else "🟢" if p.form < 86 else "⭐"

    text = (
        f"👤 <b>{p.nickname}</b> ({p.real_name or '?'})\n"
        f"🏳 {p.nationality or '??'} | Возраст: {p.age}\n"
        f"🎯 Роль: <b>{ROLE_NAMES.get(p.primary_role, '?')}</b>\n"
        f"🏠 Команда: <b>{team_name}</b>\n"
        f"💵 Зарплата: <b>${p.salary_per_month:,.0f}/мес</b>\n"
        f"⭐ Рейтинг: <b>{rating:.0f}</b>\n"
        f"Форма: {form_emoji} {p.form:.0f}\n\n"
        f"📊 <b>Характеристики:</b>\n"
        f"Mechanics: <b>{p.mechanics:.0f}</b>  Laning: <b>{p.laning:.0f}</b>\n"
        f"GameSense: <b>{p.game_sense:.0f}</b>  Teamfight: <b>{p.teamfight:.0f}</b>\n"
        f"DraftIQ:   <b>{p.draft_iq:.0f}</b>   Clutch: <b>{p.clutch:.0f}</b>\n"
        f"Comm:      <b>{p.communication:.0f}</b>  Consistency: <b>{p.consistency:.0f}</b>\n"
        f"Mental:    <b>{p.mental:.0f}</b>   Physical: <b>{p.physical:.0f}</b>\n"
    )
    if p.hero_ratings:
        top_heroes = sorted(p.hero_ratings.items(), key=lambda x: x[1], reverse=True)[:3]
        text += "\n🎮 Топ-герои: " + ", ".join(f"{h} ({r})" for h, r in top_heroes)

    await msg.answer(text)


# ─── /sign <ник> ────────────────────────────────────────────────────────────

@router.message(Command("sign"))
async def cmd_sign(msg: Message, state: FSMContext):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer("Использование: /sign <ник>")
    nick = args[1].strip()

    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")

        p = await get_player_by_nick(s, nick)
        if not p:
            return await msg.answer(f"❌ Игрок <b>{nick}</b> не найден.")
        if p.team_id:
            return await msg.answer(f"❌ <b>{nick}</b> уже в команде. Используй /transfer offer для сделки.")

        # Считаем текущий состав
        from database.crud.players import get_team_players
        roster = await get_team_players(s, team.id)
        if len(roster) >= 7:
            return await msg.answer("❌ В составе уже 7 игроков — максимум достигнут.")

    # Рекомендованная зарплата
    from database.crud.players import calc_player_rating
    rating = calc_player_rating(p)
    rec_salary = max(2000, int(rating * 200))

    await state.update_data(player_id=p.id, player_nick=nick,
                            team_id=team.id, team_budget=team.budget_current,
                            rec_salary=rec_salary)
    await state.set_state(SignFSM.salary)
    await msg.answer(
        f"✍️ <b>Подписание {nick}</b>\n\n"
        f"Рейтинг: <b>{rating:.0f}</b>\n"
        f"Рекомендованная зарплата: <b>${rec_salary:,.0f}/мес</b>\n"
        f"Твой бюджет: <b>${team.budget_current:,.0f}</b>\n\n"
        f"Введи предлагаемую зарплату в USD/мес:"
    )


@router.message(SignFSM.salary)
async def fsm_sign_salary(msg: Message, state: FSMContext):
    try:
        salary = float(msg.text.replace(",", "").replace("$", "").replace(" ", ""))
        assert salary >= 1000
    except (ValueError, AssertionError):
        return await msg.answer("❌ Введи число ≥ 1000. Например: 10000")

    await state.update_data(salary=salary)
    await state.set_state(SignFSM.duration)
    await msg.answer(
        f"💵 Зарплата: <b>${salary:,.0f}/мес</b>\n\n"
        f"На сколько сезонов контракт? (1–3):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="1 сезон", callback_data="sign_dur:1"),
            InlineKeyboardButton(text="2 сезона", callback_data="sign_dur:2"),
            InlineKeyboardButton(text="3 сезона", callback_data="sign_dur:3"),
        ]])
    )


@router.callback_query(SignFSM.duration, F.data.startswith("sign_dur:"))
async def fsm_sign_duration(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    dur = int(cb.data.split(":")[1])
    data = await state.get_data()
    await state.update_data(duration=dur)
    await state.set_state(SignFSM.confirm)

    total_cost = data["salary"] * 4 * dur  # ~4 месяца/сезон
    await cb.message.edit_text(
        f"📋 <b>Подтверждение контракта</b>\n\n"
        f"Игрок: <b>{data['player_nick']}</b>\n"
        f"Зарплата: <b>${data['salary']:,.0f}/мес</b>\n"
        f"Срок: <b>{dur} сез.</b> (~${total_cost:,.0f} итого)\n\n"
        f"Подписать?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подписать", callback_data="sign_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена",   callback_data="sign_confirm:no"),
        ]])
    )


@router.callback_query(SignFSM.confirm, F.data.startswith("sign_confirm:"))
async def fsm_sign_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    if cb.data.split(":")[1] == "no":
        await state.clear()
        return await cb.message.edit_text("❌ Подписание отменено.")

    data = await state.get_data()
    await state.clear()

    async with async_session() as s:
        p = await s.get(Player, data["player_id"])
        team = await s.get(Team, data["team_id"])
        if not p or not team:
            return await cb.message.edit_text("❌ Ошибка: игрок или команда не найдены.")
        if p.team_id:
            return await cb.message.edit_text("❌ Игрок уже подписан другой командой.")

        from database.models import GameState
        from sqlalchemy import select
        gs_res = await s.execute(select(GameState))
        gs = gs_res.scalar_one_or_none()
        season = gs.current_season if gs else 1

        p.team_id = team.id
        p.salary_per_month = data["salary"]
        p.contract_end_season = season + data["duration"]

        contract = Contract(
            player_id=p.id, team_id=team.id,
            salary_per_month=data["salary"],
            duration_seasons=data["duration"],
            start_season=season,
            end_season=season + data["duration"],
            status="active"
        )
        s.add(contract)

        fin = Finance(
            team_id=team.id, type="expense", category="transfer",
            amount_usd=0,
            description=f"Подписание {p.nickname} (${data['salary']:,.0f}/мес × {data['duration']} сез.)",
            season=season
        )
        s.add(fin)
        await s.commit()

    await cb.message.edit_text(
        f"✅ <b>{data['player_nick']} подписан!</b>\n\n"
        f"Зарплата: ${data['salary']:,.0f}/мес\n"
        f"Контракт до конца сезона {season + data['duration']}\n\n"
        f"/roster — посмотреть состав"
    )


# ─── /release <ник> ─────────────────────────────────────────────────────────

@router.message(Command("release"))
async def cmd_release(msg: Message):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer("Использование: /release <ник>")
    nick = args[1].strip()

    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")
        p = await get_player_by_nick(s, nick)
        if not p or p.team_id != team.id:
            return await msg.answer(f"❌ {nick} не в твоей команде.")

        p.team_id = None
        # Закрыть активный контракт
        from sqlalchemy import update
        await s.execute(
            update(Contract)
            .where(Contract.player_id == p.id, Contract.status == "active")
            .values(status="terminated")
        )
        await s.commit()

    await msg.answer(f"✅ <b>{nick}</b> отпущен и стал свободным агентом.")


# ─── /transfer offer <ник> ──────────────────────────────────────────────────

@router.message(Command("transfer"))
async def cmd_transfer(msg: Message, state: FSMContext):
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 2:
        return await msg.answer(
            "📤 <b>Transfer команды:</b>\n\n"
            "/transfer offer &lt;ник&gt; — предложить сделку\n"
            "/transfer history — история трансферов\n"
            "/transfer accept &lt;id&gt; — принять оффер\n"
            "/transfer reject &lt;id&gt; — отклонить оффер"
        )

    sub = parts[1].lower()

    if sub == "offer":
        nick = parts[2].strip() if len(parts) > 2 else None
        if not nick:
            return await msg.answer("Использование: /transfer offer <ник>")

        async with async_session() as s:
            u, team = await _get_gm_team(s, msg.from_user.id)
            if not team:
                return await msg.answer("❌ Ты не GM или у тебя нет команды.")
            p = await get_player_by_nick(s, nick)
            if not p:
                return await msg.answer(f"❌ Игрок {nick} не найден.")
            if not p.team_id:
                return await msg.answer(f"❌ {nick} — свободный агент. Используй /sign.")
            if p.team_id == team.id:
                return await msg.answer(f"❌ {nick} уже в твоей команде.")

        await state.update_data(player_id=p.id, player_nick=nick,
                                from_team_id=p.team_id, to_team_id=team.id,
                                user_id=u.id)
        await state.set_state(TransferOfferFSM.fee)
        await msg.answer(
            f"💼 <b>Трансферный оффер для {nick}</b>\n\n"
            f"Введи трансферный сбор (fee) в USD (0 если бесплатно):"
        )

    elif sub == "history":
        async with async_session() as s:
            u, team = await _get_gm_team(s, msg.from_user.id)
            if not team:
                return await msg.answer("❌ Ты не GM.")
            res = await s.execute(
                select(Transfer)
                .where((Transfer.from_team_id == team.id) | (Transfer.to_team_id == team.id))
                .order_by(Transfer.id.desc()).limit(10)
            )
            transfers = res.scalars().all()

        if not transfers:
            return await msg.answer("📋 История трансферов пуста.")

        STATUS_EMOJI = {"pending": "⏳", "accepted": "✅", "rejected": "❌", "expired": "⏰"}
        text = "📋 <b>История трансферов:</b>\n\n"
        for t in transfers:
            em = STATUS_EMOJI.get(t.status, "❓")
            text += (
                f"{em} #{t.id} | Игрок ID:{t.player_id} | "
                f"Fee: ${t.transfer_fee_usd:,.0f} | "
                f"Зарплата: ${t.salary_usd:,.0f}/мес\n"
            )
        await msg.answer(text)

    elif sub == "accept":
        tid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if not tid:
            return await msg.answer("Использование: /transfer accept <id>")
        await _handle_transfer_decision(msg, tid, "accepted")

    elif sub == "reject":
        tid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if not tid:
            return await msg.answer("Использование: /transfer reject <id>")
        await _handle_transfer_decision(msg, tid, "rejected")

    else:
        await msg.answer(f"❓ Неизвестная sub-команда: {sub}")


@router.message(TransferOfferFSM.fee)
async def fsm_transfer_fee(msg: Message, state: FSMContext):
    try:
        fee = float(msg.text.replace(",", "").replace("$", "").replace(" ", ""))
        assert fee >= 0
    except (ValueError, AssertionError):
        return await msg.answer("❌ Введи число ≥ 0.")
    await state.update_data(fee=fee)
    await state.set_state(TransferOfferFSM.salary)
    await msg.answer(f"Fee: <b>${fee:,.0f}</b>\n\nВведи предлагаемую зарплату (USD/мес):")


@router.message(TransferOfferFSM.salary)
async def fsm_transfer_salary(msg: Message, state: FSMContext):
    try:
        salary = float(msg.text.replace(",", "").replace("$", "").replace(" ", ""))
        assert salary >= 1000
    except (ValueError, AssertionError):
        return await msg.answer("❌ Введи число ≥ 1000.")
    await state.update_data(salary=salary)
    await state.set_state(TransferOfferFSM.duration)
    await msg.answer(
        f"Зарплата: <b>${salary:,.0f}/мес</b>\n\nДлительность контракта:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="1 сезон", callback_data="tr_dur:1"),
            InlineKeyboardButton(text="2 сезона", callback_data="tr_dur:2"),
            InlineKeyboardButton(text="3 сезона", callback_data="tr_dur:3"),
        ]])
    )


@router.callback_query(TransferOfferFSM.duration, F.data.startswith("tr_dur:"))
async def fsm_transfer_duration(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    dur = int(cb.data.split(":")[1])
    data = await state.get_data()
    await state.update_data(duration=dur)
    await state.set_state(TransferOfferFSM.confirm)
    await cb.message.edit_text(
        f"📋 <b>Трансферный оффер</b>\n\n"
        f"Игрок: <b>{data['player_nick']}</b>\n"
        f"Трансферный сбор: <b>${data['fee']:,.0f}</b>\n"
        f"Зарплата: <b>${data['salary']:,.0f}/мес × {dur} сез.</b>\n\n"
        f"Отправить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Отправить", callback_data="tr_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена",   callback_data="tr_confirm:no"),
        ]])
    )


@router.callback_query(TransferOfferFSM.confirm, F.data.startswith("tr_confirm:"))
async def fsm_transfer_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await cb.answer()
    if cb.data.split(":")[1] == "no":
        await state.clear()
        return await cb.message.edit_text("❌ Оффер отменён.")

    data = await state.get_data()
    await state.clear()

    async with async_session() as s:
        from database.models import GameState
        gs_res = await s.execute(select(GameState))
        gs = gs_res.scalar_one_or_none()
        season = gs.current_season if gs else 1

        from datetime import datetime, timedelta
        tr = Transfer(
            player_id=data["player_id"],
            from_team_id=data["from_team_id"],
            to_team_id=data["to_team_id"],
            transfer_fee_usd=data["fee"],
            salary_usd=data["salary"],
            offer_expires_at=datetime.utcnow() + timedelta(days=3),
            status="pending",
            initiated_by_user_id=data["user_id"],
            season=season,
        )
        s.add(tr)
        await s.flush()
        tr_id = tr.id

        # Найти GM принимающей команды
        res = await s.execute(
            select(User).where(User.team_id == data["from_team_id"])
        )
        target_gm = res.scalar_one_or_none()
        await s.commit()

    await cb.message.edit_text(
        f"✅ Трансферный оффер #{tr_id} отправлен!\n\n"
        f"Игрок: <b>{data['player_nick']}</b>\n"
        f"Статус: ⏳ ожидание ответа\n\n"
        f"Оффер действителен 3 дня."
    )

    # Уведомить владельца команды
    if target_gm:
        try:
            to_team = await _get_team_name(data["to_team_id"])
            await bot.send_message(
                target_gm.telegram_id,
                f"💼 <b>Новый трансферный оффер #{tr_id}</b>\n\n"
                f"Команда <b>{to_team}</b> хочет подписать "
                f"<b>{data['player_nick']}</b>\n"
                f"Сбор: ${data['fee']:,.0f} | "
                f"Зарплата: ${data['salary']:,.0f}/мес × {data['duration']} сез.\n\n"
                f"/transfer accept {tr_id} — принять\n"
                f"/transfer reject {tr_id} — отклонить"
            )
        except Exception as e:
            log.warning(f"Не удалось уведомить GM: {e}")


async def _get_team_name(team_id: int) -> str:
    async with async_session() as s:
        t = await get_team(s, team_id)
        return t.name if t else f"Команда #{team_id}"


async def _handle_transfer_decision(msg: Message, transfer_id: int, decision: str):
    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM.")

        res = await s.execute(select(Transfer).where(Transfer.id == transfer_id))
        tr = res.scalar_one_or_none()
        if not tr:
            return await msg.answer(f"❌ Оффер #{transfer_id} не найден.")
        if tr.from_team_id != team.id:
            return await msg.answer("❌ Этот оффер не твоей команде.")
        if tr.status != "pending":
            return await msg.answer(f"❌ Оффер уже {tr.status}.")

        tr.status = decision

        if decision == "accepted":
            p = await s.get(Player, tr.player_id)
            if p:
                p.team_id = tr.to_team_id
                p.salary_per_month = tr.salary_usd

                # Трансферный сбор
                if tr.transfer_fee_usd > 0:
                    buyer_team = await s.get(Team, tr.to_team_id)
                    seller_team = await s.get(Team, tr.from_team_id)
                    if buyer_team:
                        buyer_team.budget_current -= tr.transfer_fee_usd
                    if seller_team:
                        seller_team.budget_current += tr.transfer_fee_usd

                    from database.models import GameState
                    gs_res = await s.execute(select(GameState))
                    gs = gs_res.scalar_one_or_none()
                    season = gs.current_season if gs else 1

                    for team_id, t_type in [
                        (tr.to_team_id, "expense"), (tr.from_team_id, "income")
                    ]:
                        s.add(Finance(
                            team_id=team_id, type=t_type, category="transfer",
                            amount_usd=tr.transfer_fee_usd,
                            description=f"Трансфер {p.nickname}",
                            season=season
                        ))

        await s.commit()

    if decision == "accepted":
        await msg.answer(f"✅ Трансфер #{transfer_id} принят! Игрок переведён в новую команду.")
    else:
        await msg.answer(f"❌ Трансфер #{transfer_id} отклонён.")
