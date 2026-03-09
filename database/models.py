from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    role = Column(String(12), default="spectator")  # gm/to/admin/spectator
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    organizer_id = Column(Integer, ForeignKey("organizers.id"), nullable=True)
    balance_usd = Column(Float, default=0.0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False)
    last_active = Column(DateTime, default=datetime.utcnow)
    timezone = Column(String(32), default="UTC")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    tag = Column(String(10), nullable=False)
    region = Column(String(8), nullable=False)  # WEU/EEU/NA/SA/CN/SEA
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    prestige = Column(Integer, default=3)        # 1-10
    fan_base = Column(Integer, default=5000)
    sponsor_level = Column(Integer, default=1)
    budget_current = Column(Float, default=500000)
    budget_monthly = Column(Float, default=500000)
    total_earnings = Column(Float, default=0)
    founded_season = Column(Integer, default=1)
    logo_emoji = Column(String(8), default="🎮")
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    color_hex = Column(String(7), default="#4488ff")
    dpc_points_current = Column(Integer, default=0)
    dpc_points_all_time = Column(Integer, default=0)
    world_ranking = Column(Integer, default=50)
    region_ranking = Column(Integer, default=10)

    players = relationship("Player", back_populates="team",
                           foreign_keys="Player.team_id")

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    real_name = Column(String(64), nullable=True)
    nickname = Column(String(32), nullable=False, index=True)
    nationality = Column(String(3), nullable=True)
    age = Column(Integer, default=22)
    primary_role = Column(Integer, nullable=False)   # 1-5
    secondary_role = Column(Integer, nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    contract_end_season = Column(Integer, nullable=True)
    salary_per_month = Column(Float, default=5000)
    # ── Характеристики (1-100)
    mechanics     = Column(Float, default=60)
    laning        = Column(Float, default=60)
    game_sense    = Column(Float, default=60)
    teamfight     = Column(Float, default=60)
    draft_iq      = Column(Float, default=60)
    communication = Column(Float, default=60)
    clutch        = Column(Float, default=60)
    consistency   = Column(Float, default=60)
    mental        = Column(Float, default=70)
    physical      = Column(Float, default=80)
    form          = Column(Float, default=70)
    potential     = Column(Float, default=70)   # скрыт от GM
    # ── Производные
    hero_pool_width   = Column(Integer, default=5)
    meta_adaptability = Column(Float, default=60)
    leadership        = Column(Float, default=50)
    hero_ratings      = Column(JSON, default=dict)

    team = relationship("Team", back_populates="players",
                        foreign_keys=[team_id])
    contracts = relationship("Contract", back_populates="player")

class Organizer(Base):
    __tablename__ = "organizers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(64), unique=True, nullable=False)
    tag = Column(String(10), nullable=False)
    reputation = Column(Float, default=0)
    reputation_tier = Column(String(1), default="D")  # D/C/B/A/S
    total_tournaments_held = Column(Integer, default=0)
    successful_tournaments = Column(Integer, default=0)
    total_prize_distributed_usd = Column(Float, default=0)
    max_tier_achieved = Column(String(1), default="D")
    lan_events_held = Column(Integer, default=0)
    sponsor_contracts = Column(JSON, default=list)
    founded_season = Column(Integer, default=1)
    logo_emoji = Column(String(8), default="🏆")
    description = Column(Text, default="")
    is_verified = Column(Boolean, default=False)
    balance_usd = Column(Float, default=100000)
    ban_until = Column(DateTime, nullable=True)

    tournaments = relationship("Tournament", back_populates="organizer")

class Tournament(Base):
    __tablename__ = "tournaments"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    organizer_id = Column(Integer, ForeignKey("organizers.id"), nullable=True)
    is_system = Column(Boolean, default=False)
    tier = Column(String(2), default="C")
    region = Column(String(8), default="global")
    format = Column(String(16), default="DE")
    team_count = Column(Integer, default=8)
    group_count = Column(Integer, nullable=True)
    advance_count = Column(Integer, nullable=True)
    playoff_format = Column(String(4), default="DE")
    selection_mode = Column(String(8), default="invite")
    participating_teams = Column(JSON, default=list)
    qualifier_slots = Column(Integer, default=0)
    direct_invite_slots = Column(Integer, default=8)
    event_type = Column(String(8), default="online")
    venue_city = Column(String(64), nullable=True)
    venue_cost_usd = Column(Float, default=0)
    broadcast_budget_usd = Column(Float, default=5000)
    production_quality = Column(Integer, default=2)
    prize_pool_usd = Column(Float, default=10000)
    sponsor_contributions = Column(JSON, default=dict)
    entry_fee_usd = Column(Float, default=0)
    organizer_cut_pct = Column(Float, default=10)
    awards_dpc_points = Column(Boolean, default=False)
    dpc_points_distribution = Column(JSON, default=dict)
    status = Column(String(24), default="draft")
    admin_comment = Column(Text, nullable=True)
    season = Column(Integer, default=1)
    start_week = Column(Integer, nullable=True)
    end_week = Column(Integer, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    results = Column(JSON, default=dict)

    organizer = relationship("Organizer", back_populates="tournaments")
    matches = relationship("Match", back_populates="tournament")

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    stage = Column(String(32), default="group")
    round = Column(Integer, default=1)
    team_radiant_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_dire_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    simulated_at = Column(DateTime, nullable=True)
    winner_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    score_radiant = Column(Integer, default=0)
    score_dire = Column(Integer, default=0)
    duration_minutes = Column(Integer, nullable=True)
    radiant_draft = Column(JSON, default=list)
    dire_draft = Column(JSON, default=list)
    mvp_player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    detailed_stats = Column(JSON, default=dict)
    narrative = Column(Text, nullable=True)
    viewers_peak = Column(Integer, default=0)

    tournament = relationship("Tournament", back_populates="matches")
    player_stats = relationship("MatchPlayerStat", back_populates="match")

class MatchPlayerStat(Base):
    __tablename__ = "match_player_stats"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    game_number = Column(Integer, default=1)
    hero = Column(String(32), nullable=True)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    net_worth = Column(Integer, default=0)
    gpm = Column(Integer, default=300)
    xpm = Column(Integer, default=300)
    last_hits = Column(Integer, default=0)
    denies = Column(Integer, default=0)
    hero_damage = Column(Integer, default=0)
    tower_damage = Column(Integer, default=0)
    healing = Column(Integer, default=0)
    performance_score = Column(Integer, default=50)

    match = relationship("Match", back_populates="player_stats")

class Hero(Base):
    __tablename__ = "heroes"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    primary_attribute = Column(String(4))  # STR/AGI/INT/UNI
    roles = Column(JSON, default=list)
    current_meta_tier = Column(String(1), default="B")
    pick_rate = Column(Float, default=5.0)
    ban_rate = Column(Float, default=2.0)
    synergies = Column(JSON, default=list)
    counters = Column(JSON, default=list)

class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    salary_per_month = Column(Float, nullable=False)
    duration_seasons = Column(Integer, default=1)
    start_season = Column(Integer, nullable=False)
    end_season = Column(Integer, nullable=False)
    buyout_clause = Column(Float, nullable=True)
    status = Column(String(16), default="active")

    player = relationship("Player", back_populates="contracts")

class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    from_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    to_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    transfer_fee_usd = Column(Float, default=0)
    salary_usd = Column(Float, default=0)
    offer_expires_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="pending")
    initiated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season = Column(Integer, default=1)

class Finance(Base):
    __tablename__ = "finances"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    organizer_id = Column(Integer, ForeignKey("organizers.id"), nullable=True)
    type = Column(String(8), nullable=False)   # income/expense
    category = Column(String(16), nullable=False)
    amount_usd = Column(Float, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    season = Column(Integer, default=1)

class GameState(Base):
    __tablename__ = "game_state"
    id = Column(Integer, primary_key=True, default=1)
    current_season = Column(Integer, default=1)
    current_week = Column(Integer, default=1)
    current_phase = Column(String(16), default="offseason")
    is_paused = Column(Boolean, default=False)
    last_tick_at = Column(DateTime, nullable=True)
    next_tick_at = Column(DateTime, nullable=True)
    patch_version = Column(String(8), default="7.37")

class Patch(Base):
    __tablename__ = "patches"
    id = Column(Integer, primary_key=True)
    version = Column(String(8), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    changes = Column(JSON, default=dict)
    description = Column(Text, default="")

class Backup(Base):
    __tablename__ = "backups"
    id = Column(Integer, primary_key=True)
    filename = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    size_bytes = Column(Integer, default=0)
    note = Column(Text, default="")

class TournamentApplication(Base):
    __tablename__ = "tournament_applications"
    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    slot_type = Column(String(16), default="qualifier")
    status = Column(String(16), default="pending")
