import random
import math
from datetime import datetime

def simulate_game(r_rating: float, d_rating: float,
                  r_consistency: float = 70, d_consistency: float = 70) -> dict:

    total = r_rating + d_rating
    if total == 0:
        total = 1
    base_prob = r_rating / total

    # Дисперсия через consistency
    avg_cons = (r_consistency + d_consistency) / 200
    noise = random.gauss(0, (1 - avg_cons) * 0.15)
    final_prob = max(0.05, min(0.95, base_prob + noise))

    radiant_wins = random.random() < final_prob
    diff = abs(r_rating - d_rating)

    if diff > 1200:
        dur = random.randint(22, 35)
    elif diff > 600:
        dur = random.randint(30, 48)
    else:
        dur = random.randint(38, 68)

    return {
        "winner": "radiant" if radiant_wins else "dire",
        "duration": dur,
        "radiant_win_prob": round(final_prob, 3),
        "radiant_wins": radiant_wins,
    }

def simulate_series(r_players: list, d_players: list,
                    series_format: str = "BO3") -> dict:

    from database.crud.players import calc_team_rating

    r_rt = calc_team_rating(r_players) if r_players else 60
    d_rt = calc_team_rating(d_players) if d_players else 60

    r_cons = (sum(p.consistency for p in r_players) / len(r_players)) if r_players else 60
    d_cons = (sum(p.consistency for p in d_players) / len(d_players)) if d_players else 60

    max_games = {"BO1": 1, "BO3": 3, "BO5": 5}.get(series_format, 3)
    needed = math.ceil(max_games / 2) if max_games > 1 else 1

    r_score = d_score = 0
    games = []

    while r_score < needed and d_score < needed:
        g = simulate_game(r_rt, d_rt, r_cons, d_cons)
        if g["radiant_wins"]:
            r_score += 1
        else:
            d_score += 1
        games.append(g)

    return {
        "radiant_score": r_score,
        "dire_score": d_score,
        "winner": "radiant" if r_score >= needed else "dire",
        "total_duration": sum(g["duration"] for g in games),
        "games": games,
        "radiant_rating": round(r_rt, 1),
        "dire_rating": round(d_rt, 1),
    }

def generate_player_stats(p, won: bool, dur: int, is_core: bool) -> dict:
    """Генерирует статистику игрока для одной игры."""
    base = (p.mechanics + p.teamfight) / 200
    role = p.primary_role

    if role == 1:
        kills   = max(0, int(random.normalvariate(base*8 + won*3, 2)))
        deaths  = max(0, int(random.normalvariate((1-base)*4 + (1-won)*2, 1.5)))
        assists = max(0, int(random.normalvariate(base*4, 2)))
        gpm     = max(200, int(random.normalvariate(480 + p.laning*3, 70)))
    elif role == 2:
        kills   = max(0, int(random.normalvariate(base*7 + won*3, 2)))
        deaths  = max(0, int(random.normalvariate((1-base)*4 + (1-won)*2, 1.5)))
        assists = max(0, int(random.normalvariate(base*6, 2)))
        gpm     = max(200, int(random.normalvariate(440 + p.laning*2.5, 65)))
    elif role == 3:
        kills   = max(0, int(random.normalvariate(base*5 + won*2, 2)))
        deaths  = max(0, int(random.normalvariate((1-base)*5 + (1-won)*2, 2)))
        assists = max(0, int(random.normalvariate(base*8, 3)))
        gpm     = max(150, int(random.normalvariate(370 + p.laning*2, 55)))
    elif role == 4:
        kills   = max(0, int(random.normalvariate(base*4, 1.5)))
        deaths  = max(0, int(random.normalvariate(3 + (1-won)*2, 1.5)))
        assists = max(0, int(random.normalvariate(base*12, 3)))
        gpm     = max(100, int(random.normalvariate(310 + p.laning*1.5, 50)))
    else:  # pos5
        kills   = max(0, int(random.normalvariate(2, 1)))
        deaths  = max(0, int(random.normalvariate(3 + (1-won)*2, 1.5)))
        assists = max(0, int(random.normalvariate(base*14, 3)))
        gpm     = max(80, int(random.normalvariate(270 + p.laning*1.2, 45)))

    lh = max(0, int(random.normalvariate(dur * (5 + p.laning/25), 30)))
    nw = gpm * dur

    perf = int(min(100, max(10,
        40 + (kills * 4) - (deaths * 5) + (assists * 2) +
        (gpm / 15) + (won * 15) + random.randint(-5, 5)
    )))

    return {
        "kills": kills, "deaths": deaths, "assists": assists,
        "gpm": gpm, "net_worth": nw, "last_hits": lh,
        "performance_score": perf,
    }
