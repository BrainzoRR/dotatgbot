from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import Player

async def get_free_agents(s: AsyncSession):
    res = await s.execute(
        select(Player).where(Player.team_id.is_(None))
    )
    return res.scalars().all()

async def get_team_players(s: AsyncSession, team_id: int):
    res = await s.execute(
        select(Player).where(Player.team_id == team_id)
                      .order_by(Player.primary_role)
    )
    return res.scalars().all()

async def get_player_by_nick(s: AsyncSession, nick: str):
    res = await s.execute(
        select(Player).where(Player.nickname.ilike(nick))
    )
    return res.scalar_one_or_none()

def calc_player_rating(p) -> float:
    """Базовый рейтинг игрока для симуляции матча"""
    base = (
        p.mechanics     * 0.20 +
        p.laning        * 0.15 +
        p.game_sense    * 0.20 +
        p.teamfight     * 0.20 +
        p.draft_iq      * 0.10 +
        p.communication * 0.10 +
        p.clutch        * 0.05
    )
    fm = 0.85 + (p.form / 100) * 0.30   # form 0-100 → mult 0.85-1.15
    mm = 0.88 + (p.mental / 100) * 0.17  # mental → mult 0.88-1.05
    return base * fm * mm

ROLE_WEIGHT = {1: 1.3, 2: 1.2, 3: 1.1, 4: 1.0, 5: 0.9}

def calc_team_rating(players: list) -> float:
    if not players:
        return 0
    total = sum(
        calc_player_rating(p) * ROLE_WEIGHT.get(p.primary_role, 1.0)
        for p in players
    )
    return total / len(players)
