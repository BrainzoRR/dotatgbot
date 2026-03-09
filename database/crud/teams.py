from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_team(s: AsyncSession, team_id: int):
    res = await s.execute(select(Team).where(Team.id == team_id))
    return res.scalar_one_or_none()

async def get_team_by_owner(s: AsyncSession, user_id: int):
    res = await s.execute(
        select(Team).where(Team.owner_user_id == user_id)
    )
    return res.scalar_one_or_none()

async def get_rankings(s: AsyncSession, region: str = None, limit: int = 20):
    q = select(Team).order_by(Team.dpc_points_current.desc()).limit(limit)
    if region:
        q = q.where(Team.region == region)
    res = await s.execute(q)
    return res.scalars().all()
