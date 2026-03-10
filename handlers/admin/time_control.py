from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.session import async_session
from database.models import Tournament, Organizer, User
from config import settings
import logging

log = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids

def get_phase_for_week(week: int) -> str:
    if week <= 3:  return "offseason"
    if week <= 5:  return "preseason"
    if week <= 10: return "regional_s1"
    if week == 11: return "midseason_break"
    if week <= 16: return "regional_s2"
    if week <= 20: return "major_circuit"
    if week <= 23: return "ti_qualifier"
    if week <= 26: return "the_international"
    return "season_wrap"

# ══════════════════════════════════════════════
# /admin
# ══════════════════════════════════════════════
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Нет прав.")
    parts = msg.text.split()
    if len(parts) < 3:
        return await msg.answer(
            "📟 <b>Admin панель</b>\n\n"
            "<b>Время:</b>\n"
            "/admin time status\n"
            "/admin time advance [n]\n"
            "/admin time pause / resume\n"
            "/admin time set week &lt;n&gt;\n\n"
            "<b>Турниры:</b>\n"
            "/admin tournament pending\n"
            "/admin tournament approve &lt;id&gt;\n"
            "/admin tournament reject &lt;id&gt;\n\n"
            "<b>TO:</b>\n"
            "/admin to pending\n"
            "/admin to list\n"
            "/admin to verify &lt;id&gt;\n\n"
            "<b>Игроки:</b>\n"
            "/admin player list\n\n"
            "<b>Патч:</b>\n"
            "/admin patch apply &lt;version&gt;\n"
            "/admin patch list\n\n"
            "<b>Бэкап:</b>\n"
            "/admin backup now"
        )
    section = parts[1].lower()
    action  = parts[2].lower() if len(parts) > 2 else ""
    if section == "time":
        await _handle_time(msg, action, parts)
    elif section == "tournament":
        await _handle_tournament_cmd(msg, action, parts)
    elif section == "to":
        await _handle_to(msg, action, parts)
    elif section == "player":
        await _handle_player(msg, action, parts)
    elif section == "patch":
        await _handle_patch(msg, action, parts)
    elif section == "backup":
        await _handle_backup(msg, action, parts)
    else:
        await msg.answer(f"❓ Неизвестный раздел: {section}")

# ══════════════════════════════════════════════
# TIME
# ══════════════════════════════════════════════
async def _handle_time(msg: Message, action: str, parts: list):
    from database.models import GameState
    async with async_session() as s:
        gs = (await s.execute(select(GameState))).scalar_one_or_none()

    if action == "status":
        if not gs:
            return await msg.answer("❌ GameState не найден в БД.")
        paused = "⏸ Да" if gs.is_paused else "▶️ Нет"
        await msg.answer(
            f"📊 <b>Состояние игры</b>\n\n"
            f"Сезон: <b>{gs.current_season}</b> | Неделя: <b>{gs.current_week}/28</b>\n"
            f"Фаза: <b>{gs.current_phase}</b>\n"
            f"Пауза: {paused}\n"
            f"Патч: <b>{gs.patch_version}</b>"
        )
    elif action == "advance":
        n = int(parts[3]) if len(parts) > 3 else 1
        async with async_session() as s:
            gs2 = (await s.execute(select(GameState))).scalar_one_or_none()
            if gs2:
                gs2.current_week = min(28, gs2.current_week + n)
                gs2.current_phase = get_phase_for_week(gs2.current_week)
                await s.commit()
                await msg.answer(f"⏭ Продвинуто на <b>{n}</b> нед. Текущая: <b>{gs2.current_week}</b> ({gs2.current_phase})")
    elif action == "pause":
        async with async_session() as s:
            gs2 = (await s.execute(select(GameState))).scalar_one_or_none()
            if gs2:
                gs2.is_paused = True
                await s.commit()
        await msg.answer("⏸ Игра поставлена на паузу.")
    elif action == "resume":
        async with async_session() as s:
            gs2 = (await s.execute(select(GameState))).scalar_one_or_none()
            if gs2:
                gs2.is_paused = False
                await s.commit()
        await msg.answer("▶️ Игра продолжена.")
    elif action == "set" and len(parts) >= 5 and parts[3] == "week":
        week = max(1, min(28, int(parts[4])))
        async with async_session() as s:
            gs2 = (await s.execute(select(GameState))).scalar_one_or_none()
            if gs2:
                gs2.current_week = week
                gs2.current_phase = get_phase_for_week(week)
                await s.commit()
        await msg.answer(f"📅 Неделя установлена: <b>{week}</b> ({get_phase_for_week(week)})")
    else:
        await msg.answer("❓ Неизвестная time-команда.")

# ══════════════════════════════════════════════
# TOURNAMENT (текстовые команды)
# ══════════════════════════════════════════════
async def _handle_tournament_cmd(msg: Message, action: str, parts: list):
    if action == "pending":
        async with async_session() as s:
            res = await s.execute(select(Tournament).where(Tournament.status == "pending_approval"))
            trns = res.scalars().all()
        if not trns:
            return await msg.answer("✅ Нет турниров на одобрении.")
        for trn in trns:
            async with async_session() as s:
                org = await s.get(Organizer, trn.organizer_id) if trn.organizer_id else None
            org_info = f"{org.name} (Tier {org.reputation_tier}, Rep: {org.reputation:.0f})" if org else "Системный"
            await msg.answer(
                f"📋 <b>Турнир #{trn.id}</b>\n\n"
                f"TO: {org_info}\n"
                f"Название: <b>{trn.name}</b>\n"
                f"Тир: <b>{trn.tier}</b> | Регион: <b>{trn.region}</b>\n"
                f"Формат: <b>{trn.format}</b> | Команд: <b>{trn.team_count}</b>\n"
                f"Тип: <b>{trn.event_type.upper()}</b>\n"
                f"Призовые: <b>${trn.prize_pool_usd:,.0f}</b>\n"
                f"Старт: неделя <b>{trn.start_week}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"adm_trn_approve:{trn.id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_trn_reject:{trn.id}"),
                ]])
            )
    elif action == "approve" and len(parts) > 3:
        trn_id = int(parts[3].lstrip("#"))
        # Для текстовой команды бот не нужен для редактирования, но нужен для уведомлений
        # Используем send вместо edit
        await msg.answer(f"✅ Обработка турнира #{trn_id}...")
        await _do_approve_tournament(trn_id, notify_bot=None)
        await msg.answer(f"✅ Турнир #{trn_id} одобрен.")
    elif action == "reject" and len(parts) > 3:
        trn_id = int(parts[3].lstrip("#"))
        reason = " ".join(parts[4:]).replace("--reason","").strip() or "Без причины"
        await _do_reject_tournament(trn_id, reason, notify_bot=None)
        await msg.answer(f"❌ Турнир #{trn_id} отклонён. Причина: {reason}")
    else:
        await msg.answer("Использование:\n/admin tournament pending\n/admin tournament approve &lt;id&gt;\n/admin tournament reject &lt;id&gt;")

# ══════════════════════════════════════════════
# КНОПКИ турниров — bot: Bot инжектируется aiogram
# ══════════════════════════════════════════════
@router.callback_query(F.data.startswith("adm_trn_approve:"))
async def cb_approve_tournament(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Нет прав.", show_alert=True)
    await cb.answer()
    trn_id = int(cb.data.split(":")[1])
    result = await _do_approve_tournament(trn_id, notify_bot=bot)
    if result["ok"]:
        await cb.message.edit_text(
            f"✅ <b>Турнир #{trn_id} одобрен!</b>\n<b>{result['name']}</b>"
        )
    else:
        await cb.message.edit_text(f"❌ Ошибка: {result['error']}")

@router.callback_query(F.data.startswith("adm_trn_reject:"))
async def cb_reject_tournament(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Нет прав.", show_alert=True)
    await cb.answer()
    trn_id = int(cb.data.split(":")[1])
    result = await _do_reject_tournament(trn_id, "Отклонено Admin", notify_bot=bot)
    if result["ok"]:
        await cb.message.edit_text(
            f"❌ <b>Турнир #{trn_id} отклонён</b>\n<b>{result['name']}</b>"
        )
    else:
        await cb.message.edit_text(f"❌ Ошибка: {result['error']}")

async def _do_approve_tournament(trn_id: int, notify_bot: Bot | None) -> dict:
    async with async_session() as s:
        trn = await s.get(Tournament, trn_id)
        if not trn:
            return {"ok": False, "error": f"Турнир #{trn_id} не найден"}
        if trn.status != "pending_approval":
            return {"ok": False, "error": f"Статус уже: {trn.status}"}
        trn.status = "approved"
        trn_name = trn.name
        organizer_id = trn.organizer_id
        await s.commit()

    if notify_bot and organizer_id:
        async with async_session() as s:
            owner_res = await s.execute(select(User).where(User.organizer_id == organizer_id))
            owner = owner_res.scalar_one_or_none()
        if owner:
            try:
                await notify_bot.send_message(
                    owner.telegram_id,
                    f"✅ <b>Твой турнир одобрен!</b>\n\n<b>{trn_name}</b>\n\nУдачи с организацией!"
                )
            except Exception as e:
                log.warning(f"Не удалось уведомить TO: {e}")

    return {"ok": True, "name": trn_name}

async def _do_reject_tournament(trn_id: int, reason: str, notify_bot: Bot | None) -> dict:
    async with async_session() as s:
        trn = await s.get(Tournament, trn_id)
        if not trn:
            return {"ok": False, "error": f"Турнир #{trn_id} не найден"}
        trn.status = "rejected"
        trn.admin_comment = reason
        trn_name = trn.name
        organizer_id = trn.organizer_id
        await s.commit()

    if notify_bot and organizer_id:
        async with async_session() as s:
            owner_res = await s.execute(select(User).where(User.organizer_id == organizer_id))
            owner = owner_res.scalar_one_or_none()
        if owner:
            try:
                await notify_bot.send_message(
                    owner.telegram_id,
                    f"❌ <b>Твой турнир отклонён</b>\n\n<b>{trn_name}</b>\n"
                    f"Причина: {reason}\n\nМожешь создать новый с учётом замечаний."
                )
            except Exception as e:
                log.warning(f"Не удалось уведомить TO: {e}")

    return {"ok": True, "name": trn_name}

# ══════════════════════════════════════════════
# TO верификация
# ══════════════════════════════════════════════
async def _handle_to(msg: Message, action: str, parts: list):
    if action == "pending":
        async with async_session() as s:
            res = await s.execute(select(Organizer).where(Organizer.is_verified == False))
            orgs = res.scalars().all()
        if not orgs:
            return await msg.answer("✅ Нет организаторов ожидающих верификации.")
        for o in orgs:
            async with async_session() as s:
                ur = await s.execute(select(User).where(User.organizer_id == o.id))
                u = ur.scalar_one_or_none()
            tg = f"@{u.username}" if u and u.username else f"ID:{u.telegram_id}" if u else "?"
            await msg.answer(
                f"🏆 <b>Организатор #{o.id}</b>\n\n"
                f"Название: <b>{o.name}</b> [{o.tag}]\n"
                f"Владелец: {tg}\n"
                f"Репутация: {o.reputation:.0f} (Tier {o.reputation_tier})",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Верифицировать", callback_data=f"adm_to_verify:{o.id}"),
                    InlineKeyboardButton(text="❌ Отклонить",      callback_data=f"adm_to_reject:{o.id}"),
                ]])
            )
    elif action == "list":
        async with async_session() as s:
            res = await s.execute(select(Organizer).limit(20))
            orgs = res.scalars().all()
        if not orgs:
            return await msg.answer("Организаторов нет.")
        text = "🏆 <b>Все организаторы:</b>\n\n"
        for o in orgs:
            v = "✅" if o.is_verified else "⏳"
            text += f"{v} #{o.id} <b>{o.name}</b> [{o.tag}] — Tier {o.reputation_tier}, Rep: {o.reputation:.0f}\n"
        await msg.answer(text)
    elif action == "verify" and len(parts) > 3:
        org_id = int(parts[3])
        result = await _do_verify_organizer(org_id, notify_bot=None)
        await msg.answer(f"✅ {result.get('msg', 'Готово')}" if result["ok"] else f"❌ {result['error']}")
    else:
        await msg.answer("Использование:\n/admin to pending\n/admin to list\n/admin to verify &lt;id&gt;")

@router.callback_query(F.data.startswith("adm_to_verify:"))
async def cb_verify_to(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Нет прав.", show_alert=True)
    await cb.answer()
    org_id = int(cb.data.split(":")[1])
    result = await _do_verify_organizer(org_id, notify_bot=bot)
    if result["ok"]:
        await cb.message.edit_text(f"✅ Организатор <b>{result['name']}</b> верифицирован!")
    else:
        await cb.message.edit_text(f"❌ Ошибка: {result['error']}")

@router.callback_query(F.data.startswith("adm_to_reject:"))
async def cb_reject_to(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Нет прав.", show_alert=True)
    await cb.answer()
    org_id = int(cb.data.split(":")[1])
    async with async_session() as s:
        o = await s.get(Organizer, org_id)
        if not o:
            return await cb.message.edit_text("❌ Организатор не найден.")
        org_name = o.name
        owner_res = await s.execute(select(User).where(User.organizer_id == org_id))
        owner = owner_res.scalar_one_or_none()
        await s.commit()

    await cb.message.edit_text(f"❌ Организатор <b>{org_name}</b> отклонён.")
    if owner:
        try:
            await bot.send_message(
                owner.telegram_id,
                f"❌ <b>Твоя организация {org_name} не прошла верификацию.</b>\n\n"
                f"Обратись к Admin за подробностями."
            )
        except Exception as e:
            log.warning(f"Не удалось уведомить TO: {e}")

async def _do_verify_organizer(org_id: int, notify_bot: Bot | None) -> dict:
    async with async_session() as s:
        o = await s.get(Organizer, org_id)
        if not o:
            return {"ok": False, "error": f"Организатор #{org_id} не найден"}
        o.is_verified = True
        org_name = o.name
        owner_res = await s.execute(select(User).where(User.organizer_id == org_id))
        owner = owner_res.scalar_one_or_none()
        await s.commit()

    if notify_bot and owner:
        try:
            await notify_bot.send_message(
                owner.telegram_id,
                f"🎉 <b>Твоя организация {org_name} верифицирована!</b>\n\n"
                f"Теперь ты можешь создавать турниры Tier D и C.\n"
                f"Используй /to tournament create"
            )
        except Exception as e:
            log.warning(f"Не удалось уведомить TO: {e}")

    return {"ok": True, "name": org_name, "msg": f"Организатор {org_name} верифицирован!"}

# ══════════════════════════════════════════════
# Уведомление Admin о новом TO (вызывается из common.py)
# ══════════════════════════════════════════════
async def notify_admins_new_to(bot: Bot, org: Organizer, owner: User):
    tg = f"@{owner.username}" if owner.username else f"ID:{owner.telegram_id}"
    text = (
        f"🆕 <b>Новый Tournament Organizer!</b>\n\n"
        f"Название: <b>{org.name}</b> [{org.tag}]\n"
        f"Владелец: {tg}\n"
        f"Telegram ID: <code>{owner.telegram_id}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Верифицировать", callback_data=f"adm_to_verify:{org.id}"),
        InlineKeyboardButton(text="❌ Отклонить",      callback_data=f"adm_to_reject:{org.id}"),
    ]])
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:
            log.warning(f"Не удалось уведомить Admin {admin_id}: {e}")

# ══════════════════════════════════════════════
# PLAYER
# ══════════════════════════════════════════════
async def _handle_player(msg: Message, action: str, parts: list):
    from database.models import Player
    if action == "list":
        async with async_session() as s:
            res = await s.execute(select(Player).order_by(Player.team_id, Player.primary_role).limit(30))
            players = res.scalars().all()
        ROLE = {1:"Carry",2:"Mid",3:"Off",4:"Sup4",5:"Sup5"}
        text = "👥 <b>Игроки (первые 30):</b>\n\n"
        for p in players:
            tag = "FREE" if not p.team_id else f"t{p.team_id}"
            text += f"[{ROLE.get(p.primary_role,'?')}] <b>{p.nickname}</b> [{tag}] — {p.nationality or '??'}\n"
        await msg.answer(text)
    else:
        await msg.answer("Использование: /admin player list")

# ══════════════════════════════════════════════
# PATCH
# ══════════════════════════════════════════════
async def _handle_patch(msg: Message, action: str, parts: list):
    from database.models import Hero, GameState, Patch
    if action == "apply" and len(parts) > 3:
        version = parts[3]
        import json, pathlib
        patch_file = pathlib.Path(f"data/patch_templates/{version.replace('.','_')}.json")
        if not patch_file.exists():
            return await msg.answer(f"❌ Файл <code>{patch_file}</code> не найден.")
        data = json.loads(patch_file.read_text())
        changes = data.get("hero_tier_changes", {})
        async with async_session() as s:
            for hero_name, change in changes.items():
                new_tier = change.split("→")[1] if "→" in change else change
                res = await s.execute(select(Hero).where(Hero.name == hero_name))
                hero = res.scalar_one_or_none()
                if hero:
                    hero.current_meta_tier = new_tier
            s.add(Patch(version=version, changes=data, description=data.get("description","")))
            gs = (await s.execute(select(GameState))).scalar_one_or_none()
            if gs:
                gs.patch_version = version
            await s.commit()
        await msg.answer(f"🔧 <b>Патч {version} применён!</b>\nИзменено героев: <b>{len(changes)}</b>")
    elif action == "list":
        from database.models import Patch
        async with async_session() as s:
            res = await s.execute(select(Patch).order_by(Patch.id.desc()).limit(10))
            patches = res.scalars().all()
        if not patches:
            return await msg.answer("Патчей нет.")
        text = "📜 <b>История патчей:</b>\n\n"
        for p in patches:
            text += f"<b>{p.version}</b> — {p.applied_at.strftime('%d.%m.%Y')}\n{p.description}\n\n"
        await msg.answer(text)
    else:
        await msg.answer("Использование: /admin patch apply &lt;version&gt; | list")

# ══════════════════════════════════════════════
# BACKUP
# ══════════════════════════════════════════════
async def _handle_backup(msg: Message, action: str, parts: list):
    if action == "now":
        note = " ".join(parts[3:]) if len(parts) > 3 else "manual"
        import datetime, subprocess, pathlib
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
        filename = f"backup_{ts}.sql"
        pathlib.Path("backups").mkdir(exist_ok=True)
        try:
            db_url = settings.database_url.replace("+asyncpg", "")
            result = subprocess.run(
                ["pg_dump", db_url, "-f", f"backups/{filename}"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                await msg.answer(f"💾 <b>Бэкап создан:</b> <code>{filename}</code>\nЗаметка: {note}")
            else:
                await msg.answer(f"⚠️ pg_dump ошибка:\n<code>{result.stderr[:300]}</code>")
        except Exception as e:
            await msg.answer(f"❌ Ошибка бэкапа: {e}")
    else:
        await msg.answer("Использование: /admin backup now [заметка]")
