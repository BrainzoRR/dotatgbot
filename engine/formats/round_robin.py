"""
engine/formats/round_robin.py — Round Robin формат (BO2)

Используется для Regional Leagues:
- Все против всех (BO2)
- 3 очка за 2:0, 1 очко за 1:1 каждому, 0 за 0:2
- Тайbreaker: head-to-head
"""

import random
from itertools import combinations
from sqlalchemy import select
from database.session import async_session
from database.models import Team, Match, Tournament
from database.crud.players import get_team_players
from engine.simulation import simulate_series
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════
# Генерация расписания
# ═══════════════════════════════════════

async def generate_rr_schedule(
    session,
    tournament_id: int,
    team_ids: list[int],
    start_week: int,
) -> list[Match]:
    """
    Создаёт матчи Round Robin в БД.
    Каждая пара играет BO2.
    Returns: список созданных Match объектов
    """
    pairs = list(combinations(team_ids, 2))
    random.shuffle(pairs)

    matches = []
    for i, (t1, t2) in enumerate(pairs):
        week_offset = i // 3  # 3 матча за неделю
        m = Match(
            tournament_id=tournament_id,
            stage="group",
            round=i + 1,
            team_radiant_id=t1,
            team_dire_id=t2,
            scheduled_at=None,  # симулируется при advance_week
        )
        session.add(m)
        matches.append(m)

    await session.flush()
    log.info(f"RR: создано {len(matches)} матчей для турнира {tournament_id}")
    return matches


# ═══════════════════════════════════════
# Симуляция всех матчей (admin / tick)
# ═══════════════════════════════════════

async def simulate_all_rr_matches(session, tournament_id: int) -> dict:
    """
    Симулирует все не-сыгранные RR матчи.
    BO2 = 2 независимых игры, возможен ничейный исход 1:1.
    """
    res = await session.execute(
        select(Match).where(
            Match.tournament_id == tournament_id,
            Match.simulated_at.is_(None),
        )
    )
    matches = res.scalars().all()

    results = {}  # team_id → {"wins": 0, "draws": 0, "losses": 0, "pts": 0, ...}

    for m in matches:
        r_players = await get_team_players(session, m.team_radiant_id)
        d_players = await get_team_players(session, m.team_dire_id)

        # Симулируем 2 игры отдельно для BO2
        g1 = _simulate_bo2_game(r_players, d_players)
        g2 = _simulate_bo2_game(r_players, d_players)

        r_score = (1 if g1["winner"] == "radiant" else 0) + \
                  (1 if g2["winner"] == "radiant" else 0)
        d_score = 2 - r_score

        m.score_radiant = r_score
        m.score_dire = d_score
        m.winner_id = None  # В BO2 ничья возможна
        if r_score > d_score:
            m.winner_id = m.team_radiant_id
        elif d_score > r_score:
            m.winner_id = m.team_dire_id
        m.simulated_at = datetime.utcnow()
        m.duration_minutes = g1["duration"] + g2["duration"]

        # Обновляем таблицу
        _update_rr_table(results, m.team_radiant_id, r_score, d_score)
        _update_rr_table(results, m.team_dire_id, d_score, r_score)

    return results


def _simulate_bo2_game(r_players, d_players) -> dict:
    """Симулирует одну игру BO2 (упрощённая версия из simulation.py)."""
    from engine.simulation import simulate_game
    from database.crud.players import calc_team_rating

    r_rt = calc_team_rating(r_players) if r_players else 60
    d_rt = calc_team_rating(d_players) if d_players else 60
    r_cons = (sum(p.consistency for p in r_players) / len(r_players)) if r_players else 60
    d_cons = (sum(p.consistency for p in d_players) / len(d_players)) if d_players else 60

    return simulate_game(r_rt, d_rt, r_cons, d_cons)


def _update_rr_table(table: dict, team_id: int, my_score: int, opp_score: int):
    if team_id not in table:
        table[team_id] = {
            "wins": 0, "draws": 0, "losses": 0,
            "pts": 0, "maps_won": 0, "maps_lost": 0
        }
    t = table[team_id]
    t["maps_won"] += my_score
    t["maps_lost"] += opp_score
    if my_score == 2:
        t["wins"] += 1
        t["pts"] += 3
    elif my_score == 1:
        t["draws"] += 1
        t["pts"] += 1
    else:
        t["losses"] += 1


# ═══════════════════════════════════════
# Построение таблицы
# ═══════════════════════════════════════

async def get_rr_standings(session, tournament_id: int) -> list[dict]:
    """
    Возвращает таблицу standings: список {team_id, pts, wins, draws, losses, ...}
    Отсортированный по pts DESC, затем по разнице карт.
    """
    res = await session.execute(
        select(Match).where(
            Match.tournament_id == tournament_id,
            Match.simulated_at.isnot(None),
        )
    )
    matches = res.scalars().all()

    table = {}
    for m in matches:
        for team_id, my, opp in [
            (m.team_radiant_id, m.score_radiant, m.score_dire),
            (m.team_dire_id, m.score_dire, m.score_radiant)
        ]:
            if team_id not in table:
                table[team_id] = {
                    "team_id": team_id,
                    "wins": 0, "draws": 0, "losses": 0,
                    "pts": 0, "maps_won": 0, "maps_lost": 0,
                    "played": 0
                }
            t = table[team_id]
            t["played"] += 1
            t["maps_won"] += my
            t["maps_lost"] += opp
            if my > opp:
                t["wins"] += 1
                t["pts"] += 3
            elif my == opp:
                t["draws"] += 1
                t["pts"] += 1
            else:
                t["losses"] += 1

    standings = sorted(
        table.values(),
        key=lambda x: (x["pts"], x["maps_won"] - x["maps_lost"]),
        reverse=True
    )
    return standings


# ═══════════════════════════════════════
# Форматирование для Telegram
# ═══════════════════════════════════════

async def format_rr_standings(session, tournament_id: int) -> str:
    """Форматирует таблицу RR для вывода в Telegram."""
    standings = await get_rr_standings(session, tournament_id)
    if not standings:
        return "Матчи ещё не сыграны."

    # Загружаем имена команд
    team_ids = [s["team_id"] for s in standings]
    res = await session.execute(select(Team).where(Team.id.in_(team_ids)))
    teams = {t.id: t for t in res.scalars().all()}

    # Загрузим имя турнира
    trn = await session.get(Tournament, tournament_id)
    trn_name = trn.name if trn else f"Турнир #{tournament_id}"

    lines = [
        f"📊 <b>{trn_name}</b> — Round Robin\n"
        f"{'#':2} {'Команда':<22} {'И':>2} {'О':>3} {'В':>2} {'Н':>2} {'П':>2}  {'Карты'}"
    ]
    lines.append("─" * 48)

    for i, s in enumerate(standings, 1):
        t = teams.get(s["team_id"])
        name = (t.logo_emoji + " " + t.name)[:22] if t else f"#{s['team_id']}"
        map_str = f"{s['maps_won']}:{s['maps_lost']}"
        lines.append(
            f"{i:2}. {name:<22} {s['played']:>2} {s['pts']:>3} "
            f"{s['wins']:>2} {s['draws']:>2} {s['losses']:>2}  {map_str}"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════
# /standings команда
# ═══════════════════════════════════════

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

rr_router = Router()


@rr_router.message(Command("standings"))
async def cmd_standings(msg: Message):
    args = msg.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await msg.answer(
            "Использование: /standings <tournament_id>\n\n"
            "/tournaments — список активных турниров"
        )
    tid = int(args[1])

    async with async_session() as s:
        trn = await s.get(Tournament, tid)
        if not trn:
            return await msg.answer(f"❌ Турнир #{tid} не найден.")
        if trn.format not in ("RR", "round_robin"):
            return await msg.answer("ℹ️ Этот турнир не Round Robin формата.")
        text = await format_rr_standings(s, tid)

    await msg.answer(f"<pre>{text}</pre>")
