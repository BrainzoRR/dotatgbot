from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import GameState

WEEK_PHASES = {
    range(1, 4):   "offseason",
    range(4, 6):   "preseason",
    range(6, 11):  "regional_s1",
    range(11, 12): "midseason_break",
    range(12, 17): "regional_s2",
    range(17, 21): "major_circuit",
    range(21, 24): "ti_qualifier",
    range(24, 27): "the_international",
    range(27, 29): "season_wrap",
}

def get_phase_for_week(week: int) -> str:
    for r, phase in WEEK_PHASES.items():
        if week in r:
            return phase
    return "offseason"

async def get_game_state(s: AsyncSession):
    res = await s.execute(select(GameState))
    gs = res.scalar_one_or_none()
    if not gs:
        gs = GameState(id=1)
        s.add(gs)
        await s.flush()
    return gs

async def advance_week(s: AsyncSession, n: int = 1):
    gs = await get_game_state(s)
    gs.current_week = min(28, gs.current_week + n)
    gs.current_phase = get_phase_for_week(gs.current_week)
    gs.last_tick_at = datetime.utcnow()
    return gs
