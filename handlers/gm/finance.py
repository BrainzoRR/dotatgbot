"""
handlers/gm/finance.py — Финансовая панель GM
Команды: /budget, /finances, /salary
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func
from database.session import async_session
from database.models import Player, Team, User, Finance, GameState
from database.crud.players import get_team_players
from database.crud.teams import get_team_by_owner
import logging

log = logging.getLogger(__name__)
router = Router()


async def _get_gm_team(session, telegram_id: int):
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    u = res.scalar_one_or_none()
    if not u or u.role != "gm":
        return None, None
    team = await get_team_by_owner(session, u.id)
    return u, team


# ─── /budget ────────────────────────────────────────────────────────────────

@router.message(Command("budget"))
async def cmd_budget(msg: Message):
    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")

        players = await get_team_players(s, team.id)
        monthly_salaries = sum(p.salary_per_month for p in players)

        # Спонсорский доход (примерный расчёт)
        sponsor_monthly = int(
            team.prestige * 5000 +
            team.fan_base * 0.1 +
            team.sponsor_level * 8000
        )

        # Ожидаемый бюджет через 4 недели
        forecast = team.budget_current + (sponsor_monthly - monthly_salaries) * 4

        # Последние 3 расхода/дохода для обзора
        fin_res = await s.execute(
            select(Finance).where(Finance.team_id == team.id)
            .order_by(Finance.created_at.desc()).limit(5)
        )
        recent = fin_res.scalars().all()

    # Оценка финансового здоровья
    months_runway = (team.budget_current / monthly_salaries) if monthly_salaries else 999
    health = "🔴 Критично" if months_runway < 2 else \
             "🟠 Осторожно" if months_runway < 4 else \
             "🟡 Норма" if months_runway < 8 else "🟢 Отлично"

    text = (
        f"💰 <b>Финансы {team.logo_emoji} {team.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Текущий бюджет: <b>${team.budget_current:,.0f}</b>\n"
        f"📥 Доход/мес:  <b>+${sponsor_monthly:,.0f}</b> (спонсоры)\n"
        f"📤 Расход/мес: <b>-${monthly_salaries:,.0f}</b> (зарплаты)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💹 Баланс/мес: <b>{'+' if sponsor_monthly >= monthly_salaries else ''}"
        f"${sponsor_monthly - monthly_salaries:,.0f}</b>\n"
        f"🔮 Прогноз (4 нед.): <b>${forecast:,.0f}</b>\n"
        f"⏳ Запас (мес.): <b>{months_runway:.1f}</b>  {health}\n"
    )

    if recent:
        text += "\n📋 <b>Последние операции:</b>\n"
        for f in recent:
            sign = "+" if f.type == "income" else "-"
            emoji = "💰" if f.type == "income" else "💸"
            text += f"{emoji} {sign}${f.amount_usd:,.0f} — {f.description}\n"

    text += (
        "\n/salary — зарплатная ведомость\n"
        "/finances — полная история"
    )
    await msg.answer(text)


# ─── /salary ────────────────────────────────────────────────────────────────

@router.message(Command("salary"))
async def cmd_salary(msg: Message):
    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")

        gs_res = await s.execute(select(GameState))
        gs = gs_res.scalar_one_or_none()
        season = gs.current_season if gs else 1

        players = await get_team_players(s, team.id)

    if not players:
        return await msg.answer("📋 В команде нет игроков.\n\nИди на /market!")

    ROLE_NAMES = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "S.Sup", 5: "H.Sup"}
    total = sum(p.salary_per_month for p in players)

    lines = [
        f"💼 <b>Зарплатная ведомость {team.name}</b>\n"
        f"Текущий сезон: {season}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for p in sorted(players, key=lambda x: x.primary_role):
        role = ROLE_NAMES.get(p.primary_role, "?")
        end = p.contract_end_season or "?"
        lines.append(
            f"[{role}] <b>{p.nickname}</b>\n"
            f"  💵 ${p.salary_per_month:,.0f}/мес  |  до сезона {end}"
        )

    lines.append(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Итого: <b>${total:,.0f}/мес</b> "
        f"(~${total * 4:,.0f}/сезон)"
    )

    # Предупреждение о кончающихся контрактах
    ending_soon = [p for p in players
                   if p.contract_end_season and p.contract_end_season <= season + 1]
    if ending_soon:
        lines.append("\n⚠️ <b>Истекающие контракты:</b>")
        for p in ending_soon:
            lines.append(f"  • {p.nickname} — сезон {p.contract_end_season}")
        lines.append("\n💡 Продли через /transfer offer или потеряешь игроков!")

    await msg.answer("\n".join(lines))


# ─── /finances ──────────────────────────────────────────────────────────────

@router.message(Command("finances"))
async def cmd_finances(msg: Message):
    args = msg.text.split()[1:]
    page = 1
    if args and args[0].isdigit():
        page = max(1, int(args[0]))
    per_page = 15

    async with async_session() as s:
        u, team = await _get_gm_team(s, msg.from_user.id)
        if not team:
            return await msg.answer("❌ Ты не GM или у тебя нет команды.")

        offset = (page - 1) * per_page
        fin_res = await s.execute(
            select(Finance).where(Finance.team_id == team.id)
            .order_by(Finance.created_at.desc())
            .limit(per_page).offset(offset)
        )
        records = fin_res.scalars().all()

        # Суммарные доходы/расходы за сезон
        total_income = (await s.execute(
            select(func.sum(Finance.amount_usd)).where(
                Finance.team_id == team.id, Finance.type == "income"
            )
        )).scalar() or 0

        total_expense = (await s.execute(
            select(func.sum(Finance.amount_usd)).where(
                Finance.team_id == team.id, Finance.type == "expense"
            )
        )).scalar() or 0

    if not records:
        return await msg.answer(
            f"📊 <b>Финансовая история {team.name}</b>\n\nЗаписей нет."
        )

    CAT_EMOJI = {
        "salary": "👤", "prize": "🏆", "sponsor": "💰",
        "transfer": "🔄", "fine": "⚠️", "training": "🏋️",
    }

    text = (
        f"📊 <b>Финансы {team.name}</b> (стр. {page})\n"
        f"Доходы: +${total_income:,.0f}  Расходы: -${total_expense:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    for f in records:
        em = CAT_EMOJI.get(f.category, "📝")
        sign = "+" if f.type == "income" else "-"
        date_str = f.created_at.strftime("%d.%m") if f.created_at else ""
        text += f"{em} {sign}${f.amount_usd:,.0f}  {f.description}  [{date_str}]\n"

    if len(records) == per_page:
        text += f"\n📄 /finances {page + 1} — следующая страница"

    await msg.answer(text)


# ─── /dpc ───────────────────────────────────────────────────────────────────

@router.message(Command("dpc"))
async def cmd_dpc(msg: Message):
    async with async_session() as s:
        res = await s.execute(
            select(Team).order_by(Team.dpc_points_current.desc()).limit(20)
        )
        teams = res.scalars().all()

        u, my_team = await _get_gm_team(s, msg.from_user.id)

    if not teams:
        return await msg.answer("📊 DPC таблица пуста.")

    lines = ["🏆 <b>DPC Ranking</b>\n"]
    for i, t in enumerate(teams, 1):
        marker = " ◀" if my_team and t.id == my_team.id else ""
        lines.append(
            f"{i:2}. {t.logo_emoji} <b>{t.name}</b> [{t.region}] "
            f"— {t.dpc_points_current} pts{marker}"
        )

    if my_team and my_team not in teams:
        lines.append(f"\n...  {my_team.logo_emoji} <b>{my_team.name}</b> "
                     f"— {my_team.dpc_points_current} pts")

    await msg.answer("\n".join(lines))
