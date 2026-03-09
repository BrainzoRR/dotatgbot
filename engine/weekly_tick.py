import random
from datetime import datetime

async def run_weekly_tick(session, bot):

    gs = await get_game_state(session)
    if gs.is_paused:
        return "⏸ Игра на паузе"

    results = []

    # 1 — Форма игроков
    players = (await session.execute(select(Player))).scalars().all()
    for p in players:
        noise = random.uniform(-8, 10)
        mental_f = (p.mental - 50) * 0.05
        new_form = p.form * 0.7 + noise * 0.1 + mental_f * 0.05
        p.form = max(1, min(100, new_form + random.uniform(-5, 5)))
    results.append(f"✅ Форма {len(players)} игроков обновлена")

    # 2 — Симуляция запланированных матчей этой недели
    pending_matches = (await session.execute(
        select(Match).where(
            Match.simulated_at.is_(None),
            Match.scheduled_at.isnot(None),
        )
    )).scalars().all()

    for m in pending_matches[:20]:  # лимит 20 матчей за тик
        await _simulate_match(session, m)
    results.append(f"⚔️ Сыграно матчей: {min(len(pending_matches), 20)}")

    # 3 — Зарплаты
    teams = (await session.execute(select(Team).where(
        Team.owner_user_id.isnot(None)
    ))).scalars().all()
    for t in teams:
        tplayers = await get_team_players(session, t.id)
        salaries = sum(p.salary_per_month for p in tplayers)
        t.budget_current -= salaries
        f = Finance(
            team_id=t.id, type="expense", category="salary",
            amount_usd=salaries,
            description=f"Зарплаты нед. {gs.current_week}",
            season=gs.current_season,
        )
        session.add(f)
    results.append(f"💰 Зарплаты выплачены для {len(teams)} команд")

    # 4 — Случайные события
    events_fired = await _fire_random_events(session, gs, bot)
    results.append(f"⚡ Событий: {events_fired}")

    gs.last_tick_at = datetime.utcnow()
    return "\n".join(results)

async def _simulate_match(session, match):
    r_players = await get_team_players(session, match.team_radiant_id)
    d_players = await get_team_players(session, match.team_dire_id)

    # Определить формат по стадии
    fmt = "BO3"
    if "grand" in (match.stage or "").lower():
        fmt = "BO5"
    elif match.round == 1:
        fmt = "BO3"

    series = simulate_series(r_players, d_players, fmt)
    match.winner_id = (match.team_radiant_id if series["winner"] == "radiant"
                       else match.team_dire_id)
    match.score_radiant = series["radiant_score"]
    match.score_dire = series["dire_score"]
    match.duration_minutes = series["total_duration"]
    match.simulated_at = datetime.utcnow()

    # Статы игроков
    for i, g in enumerate(series["games"], 1):
        won_r = g["radiant_wins"]
        all_ps = [(p, True, won_r) for p in r_players] + \
                 [(p, False, not won_r) for p in d_players]
        for p, is_r, won in all_ps:
            stats = generate_player_stats(p, won, g["duration"],
                                          p.primary_role <= 3)
            mps = MatchPlayerStat(
                match_id=match.id, player_id=p.id,
                team_id=p.team_id or 0, game_number=i,
                **{k: v for k, v in stats.items()
                   if k != "performance_score"},
                performance_score=stats["performance_score"]
            )
            session.add(mps)

    # Обновить W/L команд
    winner_team = await get_team(session, match.winner_id)
    loser_id = (match.team_dire_id if match.winner_id == match.team_radiant_id
                else match.team_radiant_id)
    loser_team = await get_team(session, loser_id)
    if winner_team: winner_team.wins += 1
    if loser_team:  loser_team.losses += 1

RANDOM_EVENTS = [
    {"type": "injury",       "prob": 0.02, "msg": "🤕 {nick} получил травму — пропустит {n} матча"},
    {"type": "conflict",     "prob": 0.03, "msg": "💢 Конфликт в команде: mental -15 у {nick}"},
    {"type": "sponsor_up",   "prob": 0.05, "msg": "💰 Спонсор увеличил бюджет на $50,000!"},
    {"type": "viral_clip",   "prob": 0.02, "msg": "🔥 Вирусный клип! fan_base +20, sponsor +1"},
    {"type": "raise_demand", "prob": 0.06, "msg": "💬 {nick} требует повышения зарплаты"},
    {"type": "breakthrough", "prob": 0.04, "msg": "⭐ Прорыв {nick}! potential раскрывается"},
]

async def _fire_random_events(session, gs, bot) -> int:
    """Генерирует случайные события для команд с владельцами."""
    from sqlalchemy import select
    teams = (await session.execute(
        select(Team).where(Team.owner_user_id.isnot(None))
    )).scalars().all()

    count = 0
    for team in teams:
        for ev in RANDOM_EVENTS:
            if random.random() < ev["prob"]:
                tplayers = await get_team_players(session, team.id)
                if not tplayers:
                    continue
                p = random.choice(tplayers)
                msg = ev["msg"].format(
                    nick=p.nickname,
                    n=random.randint(1, 3),
                    team=team.name
                )
                # Применить эффект
                if ev["type"] == "injury":
                    p.physical = max(0, p.physical - 20)
                elif ev["type"] == "conflict":
                    p.mental = max(0, p.mental - 15)
                elif ev["type"] == "sponsor_up":
                    team.budget_current += 50000
                elif ev["type"] == "viral_clip":
                    team.fan_base += 20
                    team.sponsor_level = min(10, team.sponsor_level + 1)
                elif ev["type"] == "breakthrough":
                    p.potential = min(100, p.potential + 5)

                # Уведомить GM
                owner = (await session.execute(
                    select(User).where(User.id == team.owner_user_id)
                )).scalar_one_or_none()
                if owner and bot:
                    try:
                        await bot.send_message(
                            owner.telegram_id,
                            f"⚡ *Событие в {team.name}*\n{msg}",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                count += 1
    return count
