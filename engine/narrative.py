import random

EARLY_TEMPLATES = [
    "{winner} доминирует на линиях с первых минут",
    "Равная ранняя игра — оба тима борются за каждый ресурс",
    "{winner} агрессивно отыгрывает ранние вращения",
    "Спокойная ранняя игра — обе команды фармят",
    "{winner} устраивает ранний гангбэнг по всей карте",
]

MID_TEMPLATES = [
    "Ключевой файт на {min}-й минуте решает исход мидгейма",
    "Серия тимфайтов — {winner} конвертирует преимущество в объекты",
    "Равная борьба в мидгейме, счёт убийств почти одинаковый",
    "Splitpush-стратегия {winner} рвёт карту на части",
]

END_TEMPLATES = [
    "{winner} врывается в хайграунд и заканчивает игру",
    "Решающий файт под Рошаном на {min}-й минуте",
    "{loser} ищет GG-пуш, но {winner} держит оборону и контратакует",
    "Спорная игра завершается неожиданным решением на {min}-й минуте",
]

def build_game_narrative(game_result: dict, r_name: str, d_name: str,
                         game_num: int) -> str:
    winner = r_name if game_result["radiant_wins"] else d_name
    loser  = d_name if game_result["radiant_wins"] else r_name
    dur    = game_result["duration"]
    mid_t  = dur // 2

    early = random.choice(EARLY_TEMPLATES).format(winner=winner, loser=loser)
    mid   = random.choice(MID_TEMPLATES).format(winner=winner, loser=loser,
                                                 min=mid_t)
    end_t = random.choice(END_TEMPLATES).format(winner=winner, loser=loser,
                                                  min=dur - random.randint(2,5))

    return (
        f"🎮 *Игра {game_num}* — {dur} мин\n"
        f"💥 Начало: {early}\n"
        f"⚔️ Мидгейм: {mid}\n"
        f"🏆 Финал: {end_t}\n"
        f"**Победа {winner}**"
    )

def build_series_narrative(series: dict, r_name: str, d_name: str,
                           tournament: str, stage: str) -> str:
    winner = r_name if series["winner"] == "radiant" else d_name
    loser  = d_name if series["winner"] == "radiant" else r_name
    rs, ds = series["radiant_score"], series["dire_score"]

    header = (
        f"🏟 *{tournament}* | {stage}\n"
        f"🟢 {r_name} vs {d_name} 🔵\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    games_text = ""
    for i, g in enumerate(series["games"], 1):
        games_text += build_game_narrative(g, r_name, d_name, i) + "\n\n"

    footer = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *{winner}* побеждает {rs}–{ds}\n"
        f"📊 Рейтинги: {r_name} {series['radiant_rating']:.0f} vs "
        f"{d_name} {series['dire_rating']:.0f}"
    )
    return header + games_text + footer
