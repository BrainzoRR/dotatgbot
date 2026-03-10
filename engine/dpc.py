"""
engine/dpc.py — Начисление DPC очков и TI-отбор

Очки начисляются только за awards_dpc_points=True турниры.
"""

from sqlalchemy import select
from database.models import Team, Tournament, Match, Finance, GameState
import logging

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# Таблицы начислений
# ══════════════════════════════════════════════

DPC_TABLE = {
    "S":  {1: 500, 2: 350, 3: 200, 4: 200, 5: 100, 6: 100, 7: 100, 8: 100},
    "S-": {1: 200, 2: 140, 3: 80,  4: 80,  5: 40,  6: 40,  7: 40,  8: 40},
    "A":  {1: 80,  2: 55,  3: 30,  4: 30,  5: 15,  6: 15,  7: 15,  8: 15},
    "B":  {1: 25,  2: 15,  3: 8,   4: 8,   5: 4,   6: 4,   7: 0,   8: 0},
    "C":  {1: 5,   2: 3,   3: 1,   4: 1,   5: 0},
    "D":  {1: 1,   2: 0},
}

LAN_BONUS_MULT = 1.25  # +25% за LAN

PRIZE_DISTRIBUTION = {
    1: 0.35,  # 35% победителю
    2: 0.20,
    3: 0.12,
    4: 0.10,
    5: 0.06,
    6: 0.06,
    7: 0.05,
    8: 0.06,
}


async def award_dpc_and_prizes(
    session,
    tournament_id: int,
    results: dict,    # {place: team_id}
    bot=None,
) -> str:
    """
    Начисляет DPC очки и призовые по итогам турнира.

    Args:
        session:      async DB session
        tournament_id: ID турнира
        results:      словарь {1: team_id, 2: team_id, ...}
        bot:          aiogram Bot для уведомлений (опционально)

    Returns:
        Текстовый отчёт
    """
    trn = await session.get(Tournament, tournament_id)
    if not trn:
        return f"❌ Турнир #{tournament_id} не найден."

    tier = trn.tier
    prize_pool = trn.prize_pool_usd
    is_lan = trn.event_type == "lan"

    gs_res = await session.execute(select(GameState))
    gs = gs_res.scalar_one_or_none()
    season = gs.current_season if gs else 1

    report_lines = [f"🏆 <b>Итоги турнира {trn.name}</b>\n"]
    total_dpc_awarded = 0

    for place, team_id in sorted(results.items()):
        team = await session.get(Team, team_id)
        if not team:
            continue

        # DPC очки
        dpc_pts = 0
        if trn.awards_dpc_points:
            tier_table = DPC_TABLE.get(tier, {})
            dpc_pts = tier_table.get(place, 0)
            if is_lan:
                dpc_pts = int(dpc_pts * LAN_BONUS_MULT)

            team.dpc_points_current += dpc_pts
            team.dpc_points_all_time += dpc_pts
            total_dpc_awarded += dpc_pts

        # Призовые
        prize_pct = PRIZE_DISTRIBUTION.get(place, 0)
        prize_amount = prize_pool * prize_pct
        if prize_amount > 0:
            team.budget_current += prize_amount
            team.total_earnings  += prize_amount

            fin = Finance(
                team_id=team_id,
                type="income",
                category="prize",
                amount_usd=prize_amount,
                description=f"{trn.name} — {place}-е место",
                season=season
            )
            session.add(fin)

        # Обновить W/L если не обновлено
        place_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(place, f"{place}.")
        dpc_str = f" | +{dpc_pts} DPC" if dpc_pts else ""
        prize_str = f" | +${prize_amount:,.0f}" if prize_amount > 0 else ""
        report_lines.append(
            f"{place_emoji} <b>{team.name}</b>{dpc_str}{prize_str}"
        )

        # Уведомить GM команды
        if bot and prize_amount > 0:
            from database.models import User
            res = await session.execute(
                select(User).where(User.id == team.owner_user_id)
            )
            gm = res.scalar_one_or_none()
            if gm:
                try:
                    await bot.send_message(
                        gm.telegram_id,
                        f"🏆 <b>Турнир {trn.name} завершён!</b>\n\n"
                        f"{team.name} занял {place}-е место\n"
                        f"{'DPC: +' + str(dpc_pts) + ' очков' if dpc_pts else ''}\n"
                        f"💰 Призовые: +${prize_amount:,.0f}"
                    )
                except Exception as e:
                    log.warning(f"Не удалось уведомить GM: {e}")

    # Обновить статус и результаты турнира
    trn.status = "finished"
    from datetime import datetime
    trn.finished_at = datetime.utcnow()
    trn.results = {str(k): v for k, v in results.items()}

    # Начислить репутацию TO (если не системный)
    if not trn.is_system and trn.organizer_id:
        rep_gain = await _calc_to_reputation(session, trn, results, is_lan)
        if rep_gain > 0:
            from database.models import Organizer
            org = await session.get(Organizer, trn.organizer_id)
            if org:
                org.reputation += rep_gain
                org.reputation_tier = _rep_to_tier(org.reputation)
                org.total_tournaments_held += 1
                org.successful_tournaments  += 1
                org.total_prize_distributed_usd += prize_pool
                if is_lan:
                    org.lan_events_held += 1
                report_lines.append(f"\n⭐ TO получил +{rep_gain:.0f} репутации")

    report_lines.append(f"\n📊 Всего DPC начислено: {total_dpc_awarded}")
    return "\n".join(report_lines)


async def _calc_to_reputation(session, trn, results, is_lan: bool) -> float:
    """Считает репутацию TO за завершённый турнир."""
    tier_rep = {"D": 5, "C": 12, "B": 25, "A": 60, "S-": 150, "S": 200}
    base = tier_rep.get(trn.tier, 5)
    mult = 1.2 if is_lan else 1.0
    if trn.prize_pool_usd >= 500_000:
        base += 10
    return base * mult


def _rep_to_tier(rep: float) -> str:
    if rep >= 750: return "S"
    if rep >= 500: return "A"
    if rep >= 250: return "B"
    if rep >= 100: return "C"
    return "D"


# ══════════════════════════════════════════════
# TI Отбор — топ-6 по глобальному DPC
# ══════════════════════════════════════════════

async def get_ti_direct_invites(session, count: int = 6) -> list:
    """Возвращает команды с наибольшим DPC для прямого инвайта на TI."""
    res = await session.execute(
        select(Team)
        .where(Team.owner_user_id.isnot(None))  # только реальные команды
        .order_by(Team.dpc_points_current.desc())
        .limit(count)
    )
    return res.scalars().all()


async def get_regional_qualifiers(session, region: str, count: int = 3) -> list:
    """Топ-N команд региона для региональных квалификаторов."""
    res = await session.execute(
        select(Team)
        .where(Team.region == region)
        .order_by(Team.dpc_points_current.desc())
        .limit(count)
    )
    return res.scalars().all()


async def reset_dpc_season(session):
    """Сбрасывает текущие DPC очки в конце сезона."""
    res = await session.execute(select(Team))
    teams = res.scalars().all()
    for t in teams:
        t.dpc_points_current = 0
    log.info(f"DPC сброшен для {len(teams)} команд")


# ══════════════════════════════════════════════
# Admin: системный турнир Regional League
# ══════════════════════════════════════════════

async def create_regional_league(
    session,
    region: str,
    season: int,
    start_week: int,
    prize_pool: float = 50000,
    dpc_points: bool = True,
) -> "Tournament":
    """
    Создаёт системную Regional League для региона.
    Берёт топ-8 команд региона по DPC/ranking.
    """
    from database.models import Tournament

    # Топ-8 команд региона
    res = await session.execute(
        select(Team)
        .where(Team.region == region)
        .order_by(Team.dpc_points_current.desc(), Team.world_ranking.asc())
        .limit(8)
    )
    region_teams = res.scalars().all()

    team_ids = [t.id for t in region_teams]

    trn = Tournament(
        name=f"Regional League {region} S{season}",
        organizer_id=None,
        is_system=True,
        tier="A",
        region=region,
        format="RR",
        team_count=len(team_ids),
        event_type="online",
        prize_pool_usd=prize_pool,
        awards_dpc_points=dpc_points,
        dpc_points_distribution=DPC_TABLE.get("A", {}),
        selection_mode="rated",
        participating_teams=team_ids,
        status="approved",
        season=season,
        start_week=start_week,
        end_week=start_week + 5,
    )
    session.add(trn)
    await session.flush()

    # Создаём расписание RR
    from engine.formats.round_robin import generate_rr_schedule
    await generate_rr_schedule(session, trn.id, team_ids, start_week)

    log.info(f"Создана Regional League {region} с {len(team_ids)} командами")
    return trn
