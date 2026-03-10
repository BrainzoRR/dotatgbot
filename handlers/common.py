from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
import logging

from database.session import async_session
from database.models import User, Team, Organizer

log = logging.getLogger(__name__)
router = Router()

ROLE_NAMES = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Soft Sup", 5: "Hard Sup"}

# ══════════════════════════════════════════════
# FSM
# ══════════════════════════════════════════════
class RegStates(StatesGroup):
    choose_role = State()

class GMStates(StatesGroup):
    choose_team   = State()
    create_name   = State()
    create_tag    = State()
    create_region = State()

class TOStates(StatesGroup):
    create_name = State()
    create_tag  = State()

# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════
def kb(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])

def main_menu_kb(role: str):
    if role == "gm":
        return kb(
            [("📋 Ростер", "menu_roster"),      ("🛒 Рынок", "menu_market")],
            [("📅 Расписание", "menu_schedule"), ("💰 Бюджет", "menu_budget")],
            [("🏆 Турниры", "menu_tournaments"), ("📊 DPC", "menu_dpc")],
            [("🌍 Рейтинг", "menu_rankings"),    ("👤 Профиль", "menu_profile")],
        )
    elif role == "to":
        return kb(
            [("🆕 Создать турнир", "menu_to_create"), ("📋 Мои турниры", "menu_to_list")],
            [("💼 Спонсоры", "menu_to_sponsors"),     ("📊 Профиль TO", "menu_to_profile")],
        )
    else:
        return kb(
            [("🌍 Рейтинг команд", "menu_rankings"), ("🏆 Турниры", "menu_tournaments")],
            [("📊 DPC таблица", "menu_dpc"),          ("👤 Профиль", "menu_profile")],
        )

async def get_or_create_user(tg_id: int, username: str) -> User:
    async with async_session() as s:
        res = await s.execute(select(User).where(User.telegram_id == tg_id))
        u = res.scalar_one_or_none()
        if not u:
            u = User(telegram_id=tg_id, username=username, role="spectator")
            s.add(u)
            await s.commit()
            await s.refresh(u)
        return u

async def get_user(tg_id: int) -> User | None:
    async with async_session() as s:
        res = await s.execute(select(User).where(User.telegram_id == tg_id))
        return res.scalar_one_or_none()

async def show_main_menu(msg: Message, u: User):
    role_label = {"gm": "General Manager", "to": "Tournament Organizer",
                  "spectator": "Spectator", "admin": "Admin"}.get(u.role, u.role)
    entity = "—"
    if u.role == "gm" and u.team_id:
        async with async_session() as s:
            t = await s.get(Team, u.team_id)
            if t:
                entity = f"{t.logo_emoji} {t.name}"
    elif u.role == "to" and u.organizer_id:
        async with async_session() as s:
            o = await s.get(Organizer, u.organizer_id)
            if o:
                v = "✅" if o.is_verified else "⏳"
                entity = f"{v} {o.logo_emoji} {o.name} (Rep: {o.reputation:.0f})"

    await msg.answer(
        f"🎮 <b>DOTA 2 FM</b>\n\n"
        f"Роль: <b>{role_label}</b>\n"
        f"Команда/Орга: <b>{entity}</b>\n\n"
        f"Выбери действие:",
        reply_markup=main_menu_kb(u.role)
    )

# ══════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════
@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    u = await get_or_create_user(msg.from_user.id, msg.from_user.username or "")
    if u.role == "spectator":
        await state.set_state(RegStates.choose_role)
        await msg.answer(
            "👋 <b>Добро пожаловать в DOTA 2 FM!</b>\n\n"
            "Симулятор про-сцены Dota 2.\nВыбери свою роль:",
            reply_markup=kb(
                [("🎯 General Manager", "role_gm")],
                [("🏆 Tournament Organizer", "role_to")],
                [("👁 Spectator (наблюдатель)", "role_spectator")],
            )
        )
    else:
        await show_main_menu(msg, u)

# ══════════════════════════════════════════════
# Выбор роли
# ══════════════════════════════════════════════
@router.callback_query(RegStates.choose_role, F.data.startswith("role_"))
async def cb_choose_role(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    role = cb.data.split("_", 1)[1]

    if role == "spectator":
        async with async_session() as s:
            res = await s.execute(select(User).where(User.telegram_id == cb.from_user.id))
            u = res.scalar_one_or_none()
            if u:
                u.role = "spectator"
                await s.commit()
        await state.clear()
        await cb.message.edit_text(
            "👁 <b>Spectator</b>\n\nНапиши /start чтобы открыть меню."
        )
        return

    if role == "gm":
        await state.set_state(GMStates.choose_team)
        async with async_session() as s:
            res = await s.execute(
                select(Team).where(Team.owner_user_id.is_(None)).order_by(Team.world_ranking)
            )
            teams = res.scalars().all()

        if not teams:
            rows = []
        else:
            rows = [
                [(f"{t.logo_emoji} {t.name} [{t.tag}] #{t.world_ranking}", f"pick_team_{t.id}")]
                for t in teams[:12]
            ]
        rows.append([("➕ Создать свою команду", "pick_team_new")])

        await cb.message.edit_text(
            "🎯 <b>General Manager</b>\n\nВыбери команду или создай свою:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t, callback_data=d)]
                for row in rows for t, d in row
            ])
        )
        return

    if role == "to":
        await state.set_state(TOStates.create_name)
        await cb.message.edit_text(
            "🏆 <b>Tournament Organizer</b>\n\n"
            "Введи название своей организации:\n"
            "<i>Например: PGL Esports, ESL Gaming</i>"
        )

# ══════════════════════════════════════════════
# GM — выбор существующей команды
# ══════════════════════════════════════════════
@router.callback_query(GMStates.choose_team, F.data.startswith("pick_team_"))
async def cb_pick_team(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    val = cb.data.replace("pick_team_", "")

    if val == "new":
        await state.set_state(GMStates.create_name)
        return await cb.message.edit_text(
            "➕ <b>Создание команды — Шаг 1/3</b>\n\nВведи название команды:"
        )

    team_id = int(val)
    async with async_session() as s:
        t = await s.get(Team, team_id)
        if not t or t.owner_user_id is not None:
            await cb.message.edit_text("❌ Команда уже занята. Напиши /start.")
            await state.clear()
            return
        res = await s.execute(select(User).where(User.telegram_id == cb.from_user.id))
        u = res.scalar_one_or_none()
        if u:
            u.role = "gm"
            u.team_id = team_id
            t.owner_user_id = u.id
            await s.commit()

        from database.models import Player
        pres = await s.execute(select(Player).where(Player.team_id == team_id).order_by(Player.primary_role))
        players = pres.scalars().all()

    roster_text = "\n".join(
        f"  [{ROLE_NAMES.get(p.primary_role,'?')}] <b>{p.nickname}</b> — {p.nationality} ({p.age} л.)"
        for p in players
    ) or "  <i>Нет игроков</i>"

    await state.clear()
    await cb.message.edit_text(
        f"{t.logo_emoji} <b>Добро пожаловать, GM {t.name}!</b>\n\n"
        f"Регион: {t.region} | Рейтинг: #{t.world_ranking}\n"
        f"Бюджет: <b>${t.budget_current:,.0f}</b>\n"
        f"DPC: <b>{t.dpc_points_current} pts</b>\n\n"
        f"<b>Ростер:</b>\n{roster_text}\n\n"
        f"Напиши /start чтобы открыть главное меню."
    )

# ══════════════════════════════════════════════
# GM — создание своей команды
# ══════════════════════════════════════════════
@router.message(GMStates.create_name)
async def gm_create_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 50:
        return await msg.answer("❌ Название должно быть от 2 до 50 символов.")
    await state.update_data(team_name=name)
    await state.set_state(GMStates.create_tag)
    await msg.answer(
        f"Название: <b>{name}</b>\n\n"
        "<b>Шаг 2/3</b> — Введи тег команды (2-6 букв):\n"
        "<i>Например: TL, OG, EG, VP</i>"
    )

@router.message(GMStates.create_tag)
async def gm_create_tag(msg: Message, state: FSMContext):
    tag = msg.text.strip().upper()
    if len(tag) < 2 or len(tag) > 6:
        return await msg.answer("❌ Тег от 2 до 6 символов.")
    await state.update_data(team_tag=tag)
    await state.set_state(GMStates.create_region)
    await msg.answer(
        f"Тег: <b>{tag}</b>\n\n<b>Шаг 3/3</b> — Выбери регион:",
        reply_markup=kb(
            [("🌍 WEU", "creg_WEU"), ("🌏 EEU", "creg_EEU")],
            [("🌎 NA",  "creg_NA"),  ("🌎 SA",  "creg_SA")],
            [("🌏 CN",  "creg_CN"),  ("🌏 SEA", "creg_SEA")],
        )
    )

@router.callback_query(GMStates.create_region, F.data.startswith("creg_"))
async def gm_create_region(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    region = cb.data.replace("creg_", "")
    data   = await state.get_data()
    name, tag = data["team_name"], data["team_tag"]

    async with async_session() as s:
        existing = (await s.execute(select(Team).where(Team.name == name))).scalar_one_or_none()
        if existing:
            await cb.message.edit_text(f"❌ Команда <b>{name}</b> уже существует. Напиши /start.")
            await state.clear()
            return
        res = await s.execute(select(User).where(User.telegram_id == cb.from_user.id))
        u = res.scalar_one_or_none()
        new_team = Team(
            name=name, tag=tag, region=region,
            prestige=1, fan_base=500, sponsor_level=1,
            budget_current=200000, budget_monthly=200000,
            total_earnings=0, world_ranking=99, region_ranking=20,
            logo_emoji="🎮", color_hex="#888888",
            dpc_points_current=0, dpc_points_all_time=0,
            wins=0, losses=0,
        )
        s.add(new_team)
        await s.flush()
        if u:
            u.role = "gm"
            u.team_id = new_team.id
            new_team.owner_user_id = u.id
        await s.commit()

    await state.clear()
    await cb.message.edit_text(
        f"🎮 <b>Команда создана!</b>\n\n"
        f"Название: <b>{name}</b> [{tag}]\n"
        f"Регион: <b>{region}</b>\n"
        f"Бюджет: <b>$200,000</b>\n\n"
        f"Используй /market чтобы найти игроков.\n"
        f"Напиши /start чтобы открыть главное меню."
    )

# ══════════════════════════════════════════════
# TO — создание организации
# ══════════════════════════════════════════════
@router.message(TOStates.create_name)
async def to_create_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 60:
        return await msg.answer("❌ Название от 2 до 60 символов.")
    await state.update_data(org_name=name)
    await state.set_state(TOStates.create_tag)
    await msg.answer(
        f"Название: <b>{name}</b>\n\n"
        "Введи тег организации (2-6 букв):\n"
        "<i>Например: PGL, ESL, WP, DH</i>"
    )

@router.message(TOStates.create_tag)
async def to_create_tag(msg: Message, state: FSMContext, bot: Bot):
    tag = msg.text.strip().upper()
    if len(tag) < 2 or len(tag) > 6:
        return await msg.answer("❌ Тег от 2 до 6 символов.")
    data = await state.get_data()
    name = data["org_name"]

    async with async_session() as s:
        existing = (await s.execute(select(Organizer).where(Organizer.name == name))).scalar_one_or_none()
        if existing:
            await msg.answer(f"❌ Организация <b>{name}</b> уже существует.")
            await state.clear()
            return
        res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
        u = res.scalar_one_or_none()
        org = Organizer(
            user_id=u.id if u else 0,
            name=name, tag=tag,
            reputation=0, reputation_tier="D",
            is_verified=False, balance_usd=50000,
            founded_season=1, logo_emoji="🏆",
        )
        s.add(org)
        await s.flush()
        if u:
            u.role = "to"
            u.organizer_id = org.id
        await s.commit()
        # Нужно получить org и u после коммита для уведомления
        org_id = org.id

    await state.clear()
    await msg.answer(
        f"🏆 <b>Организация создана!</b>\n\n"
        f"Название: <b>{name}</b> [{tag}]\n"
        f"Репутация: <b>0</b> (Tier D)\n"
        f"Баланс: <b>$50,000</b>\n\n"
        f"⏳ Заявка отправлена на верификацию Admin.\n"
        f"После одобрения сможешь создавать турниры.\n\n"
        f"Напиши /start чтобы открыть главное меню."
    )

    # Уведомить Admin — bot передан как параметр
    from handlers.admin.time_control import notify_admins_new_to
    async with async_session() as s:
        o = await s.get(Organizer, org_id)
        res = await s.execute(select(User).where(User.telegram_id == msg.from_user.id))
        u2 = res.scalar_one_or_none()
    if o and u2:
        await notify_admins_new_to(bot, o, u2)

# ══════════════════════════════════════════════
# Главное меню — кнопки
# ══════════════════════════════════════════════
@router.callback_query(F.data.startswith("menu_"))
async def cb_menu(cb: CallbackQuery):
    await cb.answer()
    action = cb.data.replace("menu_", "")
    u = await get_user(cb.from_user.id)

    if action == "roster":
        if not u or not u.team_id:
            return await cb.message.answer("❌ У тебя нет команды.")
        from database.models import Player
        async with async_session() as s:
            t = await s.get(Team, u.team_id)
            res = await s.execute(select(Player).where(Player.team_id == u.team_id).order_by(Player.primary_role))
            players = res.scalars().all()
        if not players:
            return await cb.message.answer(
                f"{t.logo_emoji} <b>{t.name}</b>\n\nРостер пустой.",
                reply_markup=kb([("🔙 Меню", "back_main")])
            )
        FORM_E = lambda f: "⭐" if f>=86 else "🟢" if f>=71 else "🟡" if f>=51 else "🟠" if f>=31 else "🔴"
        text = f"{t.logo_emoji} <b>Ростер {t.name}</b>\n\n"
        for p in players:
            text += (
                f"<b>[{ROLE_NAMES.get(p.primary_role,'?')}] {p.nickname}</b>\n"
                f"  {FORM_E(p.form)} Форма: {p.form:.0f} | {p.nationality} | {p.age} л.\n"
                f"  ⚙️ Mech:{p.mechanics:.0f} Lane:{p.laning:.0f} "
                f"GS:{p.game_sense:.0f} TF:{p.teamfight:.0f}\n"
                f"  💵 ${p.salary_per_month:,.0f}/мес\n\n"
            )
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "market":
        from database.models import Player
        async with async_session() as s:
            res = await s.execute(select(Player).where(Player.team_id.is_(None)).limit(20))
            agents = res.scalars().all()
        if not agents:
            return await cb.message.answer("🛒 Свободных агентов нет.", reply_markup=kb([("🔙 Меню", "back_main")]))
        text = "🛒 <b>Свободные агенты</b>\n\n"
        for p in agents:
            text += f"[{ROLE_NAMES.get(p.primary_role,'?')}] <b>{p.nickname}</b> — {p.nationality or '??'}, {p.age} л. | ${p.salary_per_month:,.0f}/мес\n"
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "budget":
        if not u or not u.team_id:
            return await cb.message.answer("❌ У тебя нет команды.")
        from database.models import Player
        async with async_session() as s:
            t = await s.get(Team, u.team_id)
            res = await s.execute(select(Player).where(Player.team_id == u.team_id))
            players = res.scalars().all()
        salary = sum(p.salary_per_month for p in players)
        await cb.message.answer(
            f"💰 <b>Финансы {t.name}</b>\n\n"
            f"Текущий бюджет: <b>${t.budget_current:,.0f}</b>\n"
            f"Зарплаты/мес: <b>${salary:,.0f}</b>\n"
            f"Прогноз: <b>${t.budget_current - salary:,.0f}</b>\n"
            f"Всего заработано: <b>${t.total_earnings:,.0f}</b>",
            reply_markup=kb([("🔙 Меню", "back_main")])
        )

    elif action == "dpc":
        async with async_session() as s:
            res = await s.execute(select(Team).order_by(Team.dpc_points_current.desc()).limit(20))
            teams = res.scalars().all()
        text = "📊 <b>DPC Рейтинг</b>\n\n"
        for i, t in enumerate(teams, 1):
            text += f"{i}. {t.logo_emoji} <b>{t.name}</b> [{t.region}] — {t.dpc_points_current} pts\n"
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "rankings":
        async with async_session() as s:
            res = await s.execute(select(Team).order_by(Team.world_ranking).limit(20))
            teams = res.scalars().all()
        text = "🌍 <b>Мировой рейтинг</b>\n\n"
        for t in teams:
            text += f"#{t.world_ranking} {t.logo_emoji} <b>{t.name}</b> [{t.region}] — {t.wins}W/{t.losses}L\n"
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "tournaments":
        from database.models import Tournament
        async with async_session() as s:
            res = await s.execute(
                select(Tournament)
                .where(Tournament.status.in_(["upcoming","approved","group","playoffs"]))
                .limit(10)
            )
            trns = res.scalars().all()
        if not trns:
            return await cb.message.answer("🏆 Активных турниров нет.", reply_markup=kb([("🔙 Меню", "back_main")]))
        text = "🏆 <b>Активные турниры</b>\n\n"
        for tr in trns:
            text += f"[{tr.tier}] <b>{tr.name}</b> | {tr.region} | ${tr.prize_pool_usd:,.0f}\n"
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "to_profile":
        if not u or not u.organizer_id:
            return await cb.message.answer("❌ У тебя нет организации.")
        async with async_session() as s:
            o = await s.get(Organizer, u.organizer_id)
        v = "✅ Верифицирован" if o.is_verified else "⏳ Ожидает верификации"
        await cb.message.answer(
            f"{o.logo_emoji} <b>{o.name}</b> [{o.tag}]\n\n"
            f"Репутация: <b>{o.reputation:.0f}</b> (Tier {o.reputation_tier})\n"
            f"Статус: {v}\n"
            f"Баланс: <b>${o.balance_usd:,.0f}</b>\n"
            f"Турниров: <b>{o.total_tournaments_held}</b>",
            reply_markup=kb([("🔙 Меню", "back_main")])
        )

    elif action == "to_create":
        await cb.message.answer("Используй команду /to tournament create")

    elif action == "to_list":
        await cb.message.answer("Используй команду /to tournament list")

    elif action == "to_sponsors":
        await cb.message.answer("💼 Система спонсоров — в разработке.", reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "schedule":
        await cb.message.answer("📅 Расписание матчей — в разработке.", reply_markup=kb([("🔙 Меню", "back_main")]))

    elif action == "profile":
        if not u:
            return await cb.message.answer("❌ Профиль не найден.")
        role_l = {"gm":"General Manager","to":"Tournament Organizer",
                  "spectator":"Spectator","admin":"Admin"}.get(u.role, u.role)
        text = (
            f"👤 <b>Профиль</b>\n\n"
            f"Telegram: @{cb.from_user.username}\n"
            f"ID: <code>{cb.from_user.id}</code>\n"
            f"Роль: <b>{role_l}</b>\n"
        )
        if u.team_id:
            async with async_session() as s:
                t = await s.get(Team, u.team_id)
                if t:
                    text += f"Команда: <b>{t.logo_emoji} {t.name}</b>\n"
        if u.organizer_id:
            async with async_session() as s:
                o = await s.get(Organizer, u.organizer_id)
                if o:
                    text += f"Организация: <b>{o.logo_emoji} {o.name}</b>\n"
        await cb.message.answer(text, reply_markup=kb([("🔙 Меню", "back_main")]))

@router.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery):
    await cb.answer()
    u = await get_user(cb.from_user.id)
    if u:
        await show_main_menu(cb.message, u)

# ══════════════════════════════════════════════
# /help и /me
# ══════════════════════════════════════════════
@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📚 <b>Команды DOTA 2 FM</b>\n\n"
        "/start — главное меню\n"
        "/me — профиль\n\n"
        "<b>TO:</b>\n"
        "/to tournament create — создать турнир\n"
        "/to tournament list — мои турниры\n"
        "/to profile — профиль TO\n\n"
        "<b>Admin:</b>\n"
        "/admin time status\n"
        "/admin time advance [n]\n"
        "/admin tournament pending\n"
        "/admin to pending\n"
        "/admin patch apply &lt;version&gt;\n"
        "/admin backup now"
    )

@router.message(Command("me"))
async def cmd_me(msg: Message):
    u = await get_user(msg.from_user.id)
    role = u.role if u else "не зарегистрирован"
    await msg.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"Telegram: @{msg.from_user.username}\n"
        f"ID: <code>{msg.from_user.id}</code>\n"
        f"Роль: <b>{role}</b>"
    )
