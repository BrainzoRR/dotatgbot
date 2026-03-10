"""
handlers/gm/training.py — Тренировочная система GM
Команды: /train, /train report
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.session import async_session
from database.models import Player, Team, User, Finance
from database.crud.players import get_team_players
from database.crud.teams import get_team_by_owner
import random
import logging
from datetime import datetime

log = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════
# Константы тренировочной системы
# ═══════════════════════════════════════

TRAINING_TYPES = {
    "MECHANICS": {
        "emoji": "🎮", "desc": "Механика и нажатие кнопок",
        "stats": ["mechanics", "hero_pool_width"],
        "roles_bonus": [1, 2],   # Carry/Mid получают бонус
        "cost": 3000,
    },
    "LANING": {
        "emoji": "🌾", "desc": "Лайнинг и фарм",
        "stats": ["laning"],
        "roles_bonus": [1, 2, 3],
        "cost": 2500,
    },
    "TEAMFIGHT": {
        "emoji": "⚔️", "desc": "Командные файты и позиционирование",
        "stats": ["teamfight", "communication"],
        "roles_bonus": [3, 4, 5],
        "cost": 2500,
    },
    "DRAFT": {
        "emoji": "📋", "desc": "Понимание драфта (вся команда)",
        "stats": ["draft_iq"],
        "roles_bonus": [],  # все равно
        "cost": 2000,
    },
    "MENTAL": {
        "emoji": "🧠", "desc": "Ментальная устойчивость",
        "stats": ["mental", "consistency"],
        "roles_bonus": [],
        "cost": 2000,
    },
    "REST": {
        "emoji": "😴", "desc": "Отдых и восстановление",
        "stats": [],
        "special": "fatigue_reduce",
        "cost": 500,
    },
    "SCRIM": {
        "emoji": "🤝", "desc": "Скримы — комплексный опыт",
        "stats": ["mechanics", "game_sense", "communication", "teamfight"],
        "roles_bonus": [],
        "cost": 4000,
    },
    "BOOTCAMP": {
        "emoji": "🏕", "desc": "Буткемп — максимальная отдача",
        "stats": ["mechanics", "laning", "game_sense", "teamfight",
                  "draft_iq", "communication", "mental"],
        "special": "bootcamp",
        "roles_bonus": [],
        "cost": 10000,
    },
}

INTENSITIES = {
    "LOW":    {"mult": 0.6, "fatigue": 5,  "label": "🟢 Низкая"},
    "MEDIUM": {"mult": 1.0, "fatigue": 12, "label": "🟡 Средняя"},
    "HIGH":   {"mult": 1.5, "fatigue": 20, "label": "🔴 Высокая"},
}

MAX_STAT = 100.0


# ═══════════════════════════════════════
# FSM
# ═══════════════════════════════════════

class TrainFSM(StatesGroup):
    choose_type      = State()
    choose_intensity = State()
    confirm          = State()


# ═══════════════════════════════════════
# Helpers
# ═══════════════════════════════════════

async def _get_gm_team(session, telegram_id: int):
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    u = res.scalar_one_or_none()
    if not u or u.role != "gm":
        return None, None
    team = await get_team_by_owner(session, u.id)
    return u, team


def _calc_stat_gain(player: Player, stat: str, intensity_mult: float,
                    has_role_bonus: bool) -> float:
    """Вычисляет прирост стата за тренировку."""
    current = getattr(player, stat, 0)
    if isinstance(current, int):
        current = float(current)

    # Чем выше стат, тем сложнее его развивать
    ceiling_factor = max(0.1, (MAX_STAT - current) / MAX_STAT)
    potential_factor = player.potential / 100.0
    base_gain = 1.5 * intensity_mult * ceiling_factor * potential_factor

    if has_role_bonus:
        base_gain *= 1.3

    # Небольшой рандом
    base_gain *= random.uniform(0.7, 1.3)
    return round(min(base_gain, 3.0), 2)  # Макс +3 за тренировку


def _apply_training(player: Player, train_type: dict,
                    intensity: dict) -> dict:
    """Применяет эффект тренировки к игроку, возвращает изменения."""
    changes = {}
    t_key = next(k for k, v in TRAINING_TYPES.items() if v is train_type)
    role_bonus_roles = train_type.get("roles_bonus", [])
    has_role_bonus = player.primary_role in role_bonus_roles

    special = train_type.get("special", None)

    if special == "fatigue_reduce":
        # REST
        old_physical = player.physical
        player.physical = min(100, player.physical + 15)
        player.form = min(100, player.form + 5)
        changes["physical"] = round(player.physical - old_physical, 1)
        changes["form"] = 5.0
        return changes

    # Обычные статы
    for stat in train_type.get("stats", []):
        if stat == "hero_pool_width":
            gain = random.choice([0, 0, 1])  # редко +1
            if gain:
                player.hero_pool_width = min(10, player.hero_pool_width + 1)
                changes["hero_pool_width"] = gain
            continue

        gain = _calc_stat_gain(player, stat, intensity["mult"], has_role_bonus)
        old = getattr(player, stat, 0)
        new_val = min(MAX_STAT, old + gain)
        setattr(player, stat, new_val)
        changes[stat] = round(new_val - old, 2)

    if special == "bootcamp":
        # Форма тоже растёт
        player.form = min(100, player.form + random.uniform(3, 8))
        changes["form"] = 5.0

    # Усталость (откат от physical)
    fatigue_hit = intensity["fatigue"]
    if t_key == "HIGH" or intensity["mult"] >= 1.5:
        fatigue_hit += 5
    player.physical = max(0, player.physical - fatigue_hit * 0.3)

    return changes


# ═══════════════════════════════════════
# Команды
# ═══════════════════════════════════════

@router.message(Command("train"))
async def cmd_train(msg: Message, state: FSMContext):
    args = msg.text.split(maxsplit=1)
    sub = args[1].strip().upper() if len(args) > 1 else ""

    if sub == "REPORT":
        return await _cmd_train_report(msg)

    # Проверить команду
    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")
        await state.update_data(team_id=team.id, team_name=team.name,
                                team_budget=team.budget_current)

    await state.set_state(TrainFSM.choose_type)

    kb_rows = []
    row = []
    for i, (name, info) in enumerate(TRAINING_TYPES.items()):
        row.append(InlineKeyboardButton(
            text=f"{info['emoji']} {name}",
            callback_data=f"train_type:{name}"
        ))
        if len(row) == 2 or i == len(TRAINING_TYPES) - 1:
            kb_rows.append(row)
            row = []

    await msg.answer(
        "🏋️ <b>Тренировка команды</b>\n\n"
        "Выбери тип тренировки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )


@router.callback_query(TrainFSM.choose_type, F.data.startswith("train_type:"))
async def fsm_train_type(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    t_name = cb.data.split(":")[1]
    if t_name not in TRAINING_TYPES:
        return await cb.answer("❌ Неизвестный тип")

    info = TRAINING_TYPES[t_name]
    await state.update_data(train_type=t_name)
    await state.set_state(TrainFSM.choose_intensity)

    data = await state.get_data()
    await cb.message.edit_text(
        f"{info['emoji']} <b>{t_name}</b> — {info['desc']}\n"
        f"💵 Стоимость от: ${info['cost']:,}\n"
        f"Бюджет команды: ${data['team_budget']:,.0f}\n\n"
        f"Выбери интенсивность:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🟢 Низкая",  callback_data="train_int:LOW"),
            InlineKeyboardButton(text="🟡 Средняя", callback_data="train_int:MEDIUM"),
            InlineKeyboardButton(text="🔴 Высокая", callback_data="train_int:HIGH"),
        ]])
    )


@router.callback_query(TrainFSM.choose_intensity, F.data.startswith("train_int:"))
async def fsm_train_intensity(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    intensity_key = cb.data.split(":")[1]
    intensity = INTENSITIES[intensity_key]
    data = await state.get_data()
    train_info = TRAINING_TYPES[data["train_type"]]

    cost = int(train_info["cost"] * intensity["mult"])
    await state.update_data(intensity=intensity_key, cost=cost)
    await state.set_state(TrainFSM.confirm)

    await cb.message.edit_text(
        f"📋 <b>Подтверждение тренировки</b>\n\n"
        f"Тип: {train_info['emoji']} <b>{data['train_type']}</b>\n"
        f"Интенсивность: {intensity['label']}\n"
        f"Стоимость: <b>${cost:,}</b>\n"
        f"Бюджет: ${data['team_budget']:,.0f}\n\n"
        f"Усталость игроков: <b>-{intensity['fatigue']} физика</b>\n\n"
        f"Провести тренировку?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Начать", callback_data="train_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="train_confirm:no"),
        ]])
    )


@router.callback_query(TrainFSM.confirm, F.data.startswith("train_confirm:"))
async def fsm_train_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    if cb.data.split(":")[1] == "no":
        await state.clear()
        return await cb.message.edit_text("❌ Тренировка отменена.")

    data = await state.get_data()
    await state.clear()

    train_info = TRAINING_TYPES[data["train_type"]]
    intensity  = INTENSITIES[data["intensity"]]
    cost = data["cost"]

    async with async_session() as s:
        team = await s.get(Team, data["team_id"])
        if not team:
            return await cb.message.edit_text("❌ Команда не найдена.")
        if team.budget_current < cost:
            return await cb.message.edit_text(
                f"❌ Недостаточно бюджета.\n"
                f"Нужно: ${cost:,} | Есть: ${team.budget_current:,.0f}"
            )

        players = await get_team_players(s, team.id)
        if not players:
            return await cb.message.edit_text("❌ В команде нет игроков.")

        team.budget_current -= cost

        all_changes = {}
        for p in players:
            changes = _apply_training(p, train_info, intensity)
            all_changes[p.nickname] = changes

        from database.models import GameState, TrainingSession
        gs_res = await s.execute(select(GameState))
        gs = gs_res.scalar_one_or_none()
        season = gs.current_season if gs else 1

        # Сохранить запись тренировки
        ts = TrainingSession(
            team_id=team.id,
            focus=data["train_type"],
            intensity={"LOW": 1, "MEDIUM": 3, "HIGH": 5}[data["intensity"]],
            scheduled_at=datetime.utcnow(),
            result=all_changes,
            fatigue_added=intensity["fatigue"],
            stat_gained=data["train_type"]
        )
        s.add(ts)

        fin = Finance(
            team_id=team.id, type="expense", category="training",
            amount_usd=cost,
            description=f"Тренировка {data['train_type']} ({data['intensity']})",
            season=season
        )
        s.add(fin)
        await s.commit()

    # Формируем отчёт
    lines = [
        f"✅ <b>Тренировка завершена: {train_info['emoji']} {data['train_type']}</b>\n",
        f"Интенсивность: {intensity['label']} | Стоимость: ${cost:,}\n"
    ]

    for nick, changes in all_changes.items():
        if not changes:
            continue
        change_str = " | ".join(
            f"{k}: +{v:.1f}" for k, v in changes.items() if v > 0
        )
        lines.append(f"👤 <b>{nick}</b>: {change_str or 'без изменений'}")

    await cb.message.edit_text("\n".join(lines))


# ─── /train report ──────────────────────────────────────────────────────────

async def _cmd_train_report(msg: Message):
    async with async_session() as s:
        res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
        u = res.scalar_one_or_none()
        if not u or u.role != "gm":
            return await msg.answer("❌ Ты не GM.")
        team = await get_team_by_owner(s, u.id)
        if not team:
            return await msg.answer("❌ У тебя нет команды.")

        from database.models import TrainingSession
        ts_res = await s.execute(
            select(TrainingSession)
            .where(TrainingSession.team_id == team.id)
            .order_by(TrainingSession.scheduled_at.desc())
            .limit(5)
        )
        sessions = ts_res.scalars().all()

    if not sessions:
        return await msg.answer("📋 Тренировок ещё не было.\n\nНачни с /train")

    lines = [f"📊 <b>Последние тренировки {team.name}</b>\n"]
    for ts in sessions:
        info = TRAINING_TYPES.get(ts.focus, {})
        emoji = info.get("emoji", "🏋️")
        date_str = ts.scheduled_at.strftime("%d.%m %H:%M") if ts.scheduled_at else "?"
        int_label = {1: "Low", 3: "Med", 5: "High"}.get(ts.intensity, "?")
        lines.append(f"{emoji} <b>{ts.focus}</b> [{int_label}] — {date_str}")

    await msg.answer("\n".join(lines))
