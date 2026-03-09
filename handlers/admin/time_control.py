from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import settings

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Нет прав.")

    parts = msg.text.split()
    if len(parts) < 3:
        return await msg.answer(
            "📟 *Admin панель*\n\n"
            "Команды времени:\n"
            "`/admin time status` — состояние игры\n"
            "`/admin time advance [n]` — продвинуть на n недель\n"
            "`/admin time pause` — пауза\n"
            "`/admin time resume` — продолжить\n"
            "`/admin time set week <n>` — установить неделю\n\n"
            "Турниры:\n"
            "`/admin tournament pending` — ждут одобрения\n"
            "`/admin tournament approve <id>` — одобрить\n"
            "`/admin tournament reject <id> --reason <текст>`\n\n"
            "Игроки:\n"
            "`/admin player list` — все игроки\n"
            "`/admin player spawn_free_agents <n>`\n\n"
            "Патчи:\n"
            "`/admin patch apply <version>`\n\n"
            "Бэкап:\n"
            "`/admin backup now` — создать бэкап",
            parse_mode="Markdown"
        )

    section = parts[1].lower()
    action  = parts[2].lower() if len(parts) > 2 else ""

    if section == "time":
        await _handle_time(msg, action, parts)
    elif section == "tournament":
        await _handle_tournament(msg, action, parts)
    elif section == "patch":
        await _handle_patch(msg, action, parts)
    elif section == "backup":
        await _handle_backup(msg, action, parts)
    else:
        await msg.answer(f"❓ Неизвестный раздел: {section}")

async def _handle_time(msg: Message, action: str, parts: list):
    # TODO: реальные DB-вызовы через session
    if action == "status":
        await msg.answer(
            "📊 *Состояние игры*\n\n"
            "Сезон: `1` | Неделя: `1`\n"
            "Фаза: `offseason`\n"
            "Пауза: `нет`\n"
            "Патч: `7.37`\n\n"
            "_(Подключи реальную БД)_",
            parse_mode="HTML"
        )
    elif action == "advance":
        n = int(parts[3]) if len(parts) > 3 else 1
        # TODO: gs = await advance_week(session, n); await run_weekly_tick(...)
        await msg.answer(
            f"⏭ *Продвинуто на {n} нед.*\n\n"
            "_(Подключи реальный weekly_tick)_",
            parse_mode="HTML"
        )
    elif action == "pause":
        await msg.answer("⏸ Игра поставлена на паузу.")
    elif action == "resume":
        await msg.answer("▶️ Игра продолжена.")
    elif action == "set" and len(parts) >= 5 and parts[3] == "week":
        week = int(parts[4])
        await msg.answer(f"📅 Неделя установлена: `{week}`", parse_mode="Markdown")

async def _handle_tournament(msg: Message, action: str, parts: list):
    if action == "pending":
        # TODO: запрос в БД Tournament.status == "pending_approval"
        await msg.answer(
            "📋 *Ожидают одобрения:*\n\n"
            "_(Нет данных — подключи БД)_",
            parse_mode="HTML"
        )
    elif action == "approve" and len(parts) > 3:
        tid = parts[3].lstrip("#")
        comment = ""
        if "--comment" in parts:
            idx = parts.index("--comment")
            comment = " ".join(parts[idx+1:])
        # TODO: Tournament.status = "approved" в БД + уведомить TO
        await msg.answer(
            f"✅ Турнир #{tid} одобрен.\n"
            + (f"💬 Комментарий: {comment}" if comment else ""),
            parse_mode="HTML"
        )
    elif action == "reject" and len(parts) > 3:
        tid = parts[3].lstrip("#")
        reason = ""
        if "--reason" in parts:
            idx = parts.index("--reason")
            reason = " ".join(parts[idx+1:])
        await msg.answer(
            f"❌ Турнир #{tid} отклонён.\n"
            + (f"📝 Причина: {reason}" if reason else ""),
            parse_mode="HTML"
        )

async def _handle_patch(msg: Message, action: str, parts: list):
    if action == "apply" and len(parts) > 3:
        version = parts[3]
        # TODO:
        # 1. Читаем data/patch_templates/{version}.json
        # 2. Обновляем Hero.current_meta_tier в БД
        # 3. Применяем global_changes к engine config
        # 4. Сохраняем в Patch
        # 5. Уведомляем всех GM
        await msg.answer(
            f"🔧 *Патч {version} применён!*\n\n"
            "Изменения мета-тиров героев обновлены.\n"
            "Уведомления отправлены GM.\n"
            "_(Добавь реальное чтение JSON-файла)_",
            parse_mode="HTML"
        )
    elif action == "list":
        await msg.answer("📜 История патчей: _(подключи БД)_")

async def _handle_backup(msg: Message, action: str, parts: list):
    if action == "now":
        note = " ".join(parts[3:]) if len(parts) > 3 else "manual"
        # TODO: subprocess.run(["pg_dump", DATABASE_URL, "-f", filename])
        import datetime
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
        filename = f"backup_{ts}.sql"
        await msg.answer(
            f"💾 *Бэкап создан:* `{filename}`\n"
            f"Заметка: {note}\n\n"
            "_(Добавь реальный pg_dump вызов)_",
            parse_mode="HTML"
        )
