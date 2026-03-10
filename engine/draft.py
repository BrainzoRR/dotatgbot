"""
engine/draft.py — Авто-драфт на основе hero_ratings + meta_tier

Стратегии: AGGRESSIVE / LATE / TEAMFIGHT / POCKET / COUNTER / BALANCED
"""

import random
from typing import Optional

# Вес метатиров
META_TIER_WEIGHT = {"S": 1.30, "A": 1.15, "B": 1.00, "C": 0.85, "D": 0.70}

# Какие стратегии предпочитают каких героев (по ролям/атрибутам)
STRATEGY_WEIGHTS = {
    "AGGRESSIVE": {
        "preferred_tiers":    ["S", "A"],
        "role_focus":         [3, 4],       # Offlane, Soft Sup
        "attribute_bonus":    {"STR": 1.2},
        "description":        "Ранняя агрессия и давление",
    },
    "LATE": {
        "preferred_tiers":    ["A", "B"],
        "role_focus":         [1],           # Carry
        "attribute_bonus":    {"AGI": 1.2},
        "description":        "Поздняя игра и carry",
    },
    "TEAMFIGHT": {
        "preferred_tiers":    ["S", "A"],
        "role_focus":         [3, 4, 5],
        "attribute_bonus":    {"STR": 1.1, "INT": 1.1},
        "description":        "Mass AoE teamfight",
    },
    "POCKET": {
        "preferred_tiers":    ["S", "A", "B"],
        "role_focus":         [1, 2],
        "attribute_bonus":    {},
        "description":        "Comfort picks игроков",
    },
    "COUNTER": {
        "preferred_tiers":    ["S", "A", "B"],
        "role_focus":         [],
        "attribute_bonus":    {},
        "description":        "Контр-пики сопернику",
    },
    "BALANCED": {
        "preferred_tiers":    ["S", "A", "B"],
        "role_focus":         [],
        "attribute_bonus":    {},
        "description":        "Сбалансированный подход",
    },
}


def draft_team(
    players: list,
    heroes: list,
    strategy: str = "BALANCED",
    banned_heroes: Optional[list] = None,
    enemy_draft: Optional[list] = None,
) -> list:
    """
    Авто-драфт команды.

    Args:
        players: список объектов Player (pos1–5)
        heroes: список объектов Hero из БД
        strategy: строка из STRATEGY_WEIGHTS
        banned_heroes: список имён забаненных героев
        enemy_draft: список имён героев противника (для COUNTER)

    Returns:
        list из 5 строк — имена задрафтованных героев (по ролям)
    """
    banned = set(banned_heroes or [])
    available = [h for h in heroes if h.name not in banned]

    strat = STRATEGY_WEIGHTS.get(strategy.upper(), STRATEGY_WEIGHTS["BALANCED"])
    attr_bonus = strat["attribute_bonus"]

    # Строим словарь hero_name → score по всем игрокам
    draft = []
    used_heroes = set()

    # Сортируем игроков по роли 1→5
    sorted_players = sorted(players, key=lambda p: p.primary_role)

    for p in sorted_players:
        role = p.primary_role
        hero_ratings = p.hero_ratings or {}

        # Считаем score для каждого доступного героя
        candidates = []
        for h in available:
            if h.name in used_heroes:
                continue

            # Базовый скор из рейтинга игрока на герое
            player_rate = hero_ratings.get(h.name, 50)

            # Мета-бонус
            meta_mult = META_TIER_WEIGHT.get(h.current_meta_tier, 1.0)

            # Стратегический бонус
            strat_mult = 1.0
            role_roles = []  # роли героя
            if hasattr(h, "roles") and h.roles:
                hero_roles_str = h.roles
                if isinstance(hero_roles_str, list):
                    role_text = " ".join(hero_roles_str).lower()
                else:
                    role_text = str(hero_roles_str).lower()
                if "carry"   in role_text and role == 1: strat_mult *= 1.2
                if "mid"     in role_text and role == 2: strat_mult *= 1.2
                if "offlane" in role_text and role == 3: strat_mult *= 1.2
                if "support" in role_text and role in [4, 5]: strat_mult *= 1.2

            # Бонус атрибута
            attr = getattr(h, "primary_attribute", "")
            strat_mult *= attr_bonus.get(attr, 1.0)

            # POCKET: максимизируем рейтинг игрока
            if strategy.upper() == "POCKET":
                score = player_rate * meta_mult
            # COUNTER: штрафуем героев без counters к enemy_draft
            elif strategy.upper() == "COUNTER" and enemy_draft:
                counters = getattr(h, "counters", []) or []
                counter_bonus = sum(1 for e in enemy_draft if e in counters) * 0.15
                score = player_rate * meta_mult * (1 + counter_bonus)
            else:
                score = player_rate * meta_mult * strat_mult

            # Добавляем шум
            score *= random.uniform(0.9, 1.1)

            candidates.append((h.name, score))

        if not candidates:
            draft.append("Unknown")
            continue

        # Топ-3, выбираем взвешенно
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:5]
        weights = [c[1] for c in top]
        total_w = sum(weights) or 1
        probs = [w / total_w for w in weights]

        chosen = random.choices([c[0] for c in top], weights=probs, k=1)[0]
        draft.append(chosen)
        used_heroes.add(chosen)

    return draft


def build_ban_phase(
    heroes: list,
    enemy_players: list,
    strategy: str = "BALANCED",
    num_bans: int = 3,
) -> list:
    """
    Авто-баны: банит сильных метапиков и comfort picks противника.

    Returns:
        list из `num_bans` имён героев
    """
    # Сначала баним S-тир героев
    s_tier = [h for h in heroes if h.current_meta_tier == "S"]
    s_tier.sort(key=lambda h: -(h.ban_rate or 0))

    # Comfort picks противника
    enemy_favorites = []
    for p in enemy_players:
        ratings = p.hero_ratings or {}
        top_heroes = sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:2]
        for h_name, _ in top_heroes:
            enemy_favorites.append(h_name)

    bans = []
    seen = set()

    # Сначала банить фаворитов противника если они S/A тир
    for h in heroes:
        if h.name in enemy_favorites and h.current_meta_tier in ["S", "A"]:
            if h.name not in seen:
                bans.append(h.name)
                seen.add(h.name)
            if len(bans) >= num_bans:
                break

    # Добивать топ-S тиром
    for h in s_tier:
        if len(bans) >= num_bans:
            break
        if h.name not in seen:
            bans.append(h.name)
            seen.add(h.name)

    return bans[:num_bans]


def format_draft_text(
    radiant_picks: list,
    dire_picks: list,
    radiant_bans: list,
    dire_bans: list,
    r_name: str,
    d_name: str,
) -> str:
    """Форматирует текст драфта для нарратива матча."""
    r_picks_str = ", ".join(radiant_picks) if radiant_picks else "—"
    d_picks_str = ", ".join(dire_picks) if dire_picks else "—"
    r_bans_str  = ", ".join(radiant_bans) if radiant_bans else "—"
    d_bans_str  = ", ".join(dire_bans) if dire_bans else "—"

    return (
        f"━━━━ DRAFT ━━━━\n"
        f"🟢 <b>{r_name}</b>: {r_picks_str}\n"
        f"🔵 <b>{d_name}</b>: {d_picks_str}\n"
        f"🚫 Баны: {r_name}: {r_bans_str}\n"
        f"🚫 Баны: {d_name}: {d_bans_str}\n"
    )


def calc_draft_synergy_bonus(draft: list, heroes: list) -> float:
    """
    Считает синергетический бонус от подобранных героев (1.0–1.15).
    """
    hero_map = {h.name: h for h in heroes}
    synergy_count = 0

    for i, h_name in enumerate(draft):
        h = hero_map.get(h_name)
        if not h or not h.synergies:
            continue
        for other in draft[i+1:]:
            if other in (h.synergies or []):
                synergy_count += 1

    # Каждая синергия даёт +2%
    return min(1.15, 1.0 + synergy_count * 0.02)
