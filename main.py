import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import settings
from database.models import Base
from database.session import engine, async_session

from handlers.common import router as common_router
from handlers.gm.roster import router as gm_roster_router
from handlers.to.tournament_create import router as to_create_router
from handlers.admin.time_control import router as admin_router
from engine.formats.round_robin import rr_router
from handlers.gm.transfer import router as gm_transfer_router
from handlers.gm.training import router as gm_training_router
from handlers.gm.finance  import router as gm_finance_router
from handlers.gm.match    import router as gm_match_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# SEED DATA — всё прямо здесь, без отдельного модуля
# ══════════════════════════════════════════════════
TEAMS_SEED = [
    {"name":"Team Falcons","tag":"FLCN","region":"WEU","prestige":9,"fan_base":85000,"sponsor_level":9,"budget_current":4500000,"total_earnings":9500000,"world_ranking":1,"region_ranking":1,"logo_emoji":"🦅","color_hex":"#00A3E0","dpc_points_current":500,"dpc_points_all_time":1850,"wins":221,"losses":121},
    {"name":"Team Spirit","tag":"TSP","region":"EEU","prestige":9,"fan_base":90000,"sponsor_level":8,"budget_current":4000000,"total_earnings":12000000,"world_ranking":2,"region_ranking":1,"logo_emoji":"👻","color_hex":"#1A73E8","dpc_points_current":440,"dpc_points_all_time":2100,"wins":310,"losses":160},
    {"name":"Xtreme Gaming","tag":"XG","region":"CN","prestige":8,"fan_base":70000,"sponsor_level":8,"budget_current":3500000,"total_earnings":7800000,"world_ranking":3,"region_ranking":1,"logo_emoji":"⚡","color_hex":"#FF4500","dpc_points_current":400,"dpc_points_all_time":1400,"wins":185,"losses":95},
    {"name":"Team Liquid","tag":"TL","region":"WEU","prestige":9,"fan_base":95000,"sponsor_level":9,"budget_current":4200000,"total_earnings":14000000,"world_ranking":4,"region_ranking":2,"logo_emoji":"💧","color_hex":"#009AC7","dpc_points_current":380,"dpc_points_all_time":2400,"wins":290,"losses":145},
    {"name":"PARIVISION","tag":"PVS","region":"EEU","prestige":7,"fan_base":45000,"sponsor_level":6,"budget_current":2000000,"total_earnings":3200000,"world_ranking":5,"region_ranking":2,"logo_emoji":"👁","color_hex":"#8B00FF","dpc_points_current":350,"dpc_points_all_time":800,"wins":165,"losses":80},
    {"name":"BetBoom Team","tag":"BB","region":"EEU","prestige":7,"fan_base":40000,"sponsor_level":6,"budget_current":1800000,"total_earnings":2900000,"world_ranking":6,"region_ranking":3,"logo_emoji":"💣","color_hex":"#FF6B00","dpc_points_current":300,"dpc_points_all_time":750,"wins":155,"losses":90},
    {"name":"Tundra Esports","tag":"TND","region":"WEU","prestige":8,"fan_base":55000,"sponsor_level":7,"budget_current":2800000,"total_earnings":8500000,"world_ranking":7,"region_ranking":3,"logo_emoji":"🌨","color_hex":"#4169E1","dpc_points_current":290,"dpc_points_all_time":1600,"wins":200,"losses":110},
    {"name":"Gaimin Gladiators","tag":"GG","region":"WEU","prestige":7,"fan_base":50000,"sponsor_level":6,"budget_current":2200000,"total_earnings":5500000,"world_ranking":8,"region_ranking":4,"logo_emoji":"🏛","color_hex":"#FFD700","dpc_points_current":260,"dpc_points_all_time":1200,"wins":190,"losses":100},
    {"name":"Natus Vincere","tag":"NAVI","region":"WEU","prestige":8,"fan_base":110000,"sponsor_level":8,"budget_current":3000000,"total_earnings":6000000,"world_ranking":9,"region_ranking":5,"logo_emoji":"⚔️","color_hex":"#F5A623","dpc_points_current":240,"dpc_points_all_time":1100,"wins":175,"losses":95},
    {"name":"Aurora Gaming","tag":"AUR","region":"EEU","prestige":6,"fan_base":30000,"sponsor_level":5,"budget_current":1500000,"total_earnings":2100000,"world_ranking":10,"region_ranking":4,"logo_emoji":"🌅","color_hex":"#FF69B4","dpc_points_current":220,"dpc_points_all_time":600,"wins":140,"losses":80},
    {"name":"OG","tag":"OG","region":"SEA","prestige":8,"fan_base":100000,"sponsor_level":7,"budget_current":2500000,"total_earnings":11000000,"world_ranking":12,"region_ranking":1,"logo_emoji":"🪙","color_hex":"#C0392B","dpc_points_current":180,"dpc_points_all_time":2800,"wins":260,"losses":140},
    {"name":"HEROIC","tag":"HRC","region":"SA","prestige":5,"fan_base":25000,"sponsor_level":5,"budget_current":1200000,"total_earnings":1500000,"world_ranking":13,"region_ranking":1,"logo_emoji":"⚡","color_hex":"#E74C3C","dpc_points_current":160,"dpc_points_all_time":400,"wins":110,"losses":65},
    {"name":"Virtus.pro","tag":"VP","region":"EEU","prestige":7,"fan_base":70000,"sponsor_level":6,"budget_current":2000000,"total_earnings":7000000,"world_ranking":14,"region_ranking":5,"logo_emoji":"🐻","color_hex":"#E67E22","dpc_points_current":150,"dpc_points_all_time":1800,"wins":220,"losses":130},
    {"name":"BOOM Esports","tag":"BOOM","region":"SEA","prestige":5,"fan_base":28000,"sponsor_level":4,"budget_current":900000,"total_earnings":1200000,"world_ranking":15,"region_ranking":2,"logo_emoji":"💥","color_hex":"#2ECC71","dpc_points_current":130,"dpc_points_all_time":350,"wins":95,"losses":65},
    {"name":"paiN Gaming","tag":"paiN","region":"SA","prestige":5,"fan_base":32000,"sponsor_level":5,"budget_current":1100000,"total_earnings":1600000,"world_ranking":16,"region_ranking":2,"logo_emoji":"🌶","color_hex":"#E74C3C","dpc_points_current":120,"dpc_points_all_time":600,"wins":130,"losses":80},
    {"name":"GamerLegion","tag":"GL","region":"NA","prestige":5,"fan_base":20000,"sponsor_level":4,"budget_current":800000,"total_earnings":900000,"world_ranking":17,"region_ranking":1,"logo_emoji":"🛡","color_hex":"#9B59B6","dpc_points_current":100,"dpc_points_all_time":280,"wins":75,"losses":55},
    {"name":"Fnatic","tag":"FNC","region":"SEA","prestige":6,"fan_base":60000,"sponsor_level":6,"budget_current":1300000,"total_earnings":3500000,"world_ranking":20,"region_ranking":3,"logo_emoji":"🦊","color_hex":"#F4810A","dpc_points_current":80,"dpc_points_all_time":900,"wins":180,"losses":120},
]

PLAYERS_SEED = [
    # Team Falcons
    {"nickname":"skiter","real_name":"Oliver Lepko","nationality":"SVK","age":24,"primary_role":1,"team":"Team Falcons","salary_per_month":25000,"mechanics":89,"laning":86,"game_sense":87,"teamfight":88,"draft_iq":80,"communication":75,"clutch":88,"consistency":85,"mental":88,"physical":85,"form":82,"potential":89,"hero_pool_width":8,"meta_adaptability":82,"leadership":55,"hero_ratings":{"Anti-Mage":85,"Phantom Lancer":88,"Medusa":90}},
    {"nickname":"Malr1ne","real_name":"Stanislav Potorak","nationality":"UKR","age":22,"primary_role":2,"team":"Team Falcons","salary_per_month":30000,"mechanics":94,"laning":91,"game_sense":92,"teamfight":90,"draft_iq":88,"communication":80,"clutch":93,"consistency":82,"mental":85,"physical":88,"form":90,"potential":96,"hero_pool_width":9,"meta_adaptability":90,"leadership":60,"hero_ratings":{"Invoker":96,"Lina":92,"Storm Spirit":91}},
    {"nickname":"AMMAR_THE_F","real_name":"Ammar Al-Assaf","nationality":"SAU","age":21,"primary_role":3,"team":"Team Falcons","salary_per_month":22000,"mechanics":88,"laning":85,"game_sense":90,"teamfight":92,"draft_iq":87,"communication":82,"clutch":89,"consistency":80,"mental":83,"physical":87,"form":85,"potential":92,"hero_pool_width":8,"meta_adaptability":87,"leadership":70,"hero_ratings":{"Magnus":93,"Void Spirit":89,"Mars":88}},
    {"nickname":"Cr1t-","real_name":"Andreas Nielsen","nationality":"DNK","age":30,"primary_role":4,"team":"Team Falcons","salary_per_month":20000,"mechanics":82,"laning":84,"game_sense":93,"teamfight":87,"draft_iq":92,"communication":95,"clutch":85,"consistency":88,"mental":90,"physical":78,"form":83,"potential":83,"hero_pool_width":7,"meta_adaptability":80,"leadership":88,"hero_ratings":{"Earth Spirit":91,"Rubick":87,"Clockwerk":85}},
    {"nickname":"Sneyking","real_name":"Jingjun Wu","nationality":"USA","age":29,"primary_role":5,"team":"Team Falcons","salary_per_month":18000,"mechanics":80,"laning":82,"game_sense":90,"teamfight":88,"draft_iq":88,"communication":88,"clutch":83,"consistency":86,"mental":88,"physical":80,"form":79,"potential":81,"hero_pool_width":7,"meta_adaptability":82,"leadership":80,"hero_ratings":{"Dazzle":88,"Ancient Apparition":87,"Witch Doctor":85}},
    # Team Spirit
    {"nickname":"Yatoro","real_name":"Illya Mulyarchuk","nationality":"UKR","age":22,"primary_role":1,"team":"Team Spirit","salary_per_month":35000,"mechanics":96,"laning":93,"game_sense":91,"teamfight":93,"draft_iq":82,"communication":72,"clutch":95,"consistency":88,"mental":87,"physical":88,"form":88,"potential":97,"hero_pool_width":9,"meta_adaptability":85,"leadership":50,"hero_ratings":{"Terrorblade":95,"Anti-Mage":94,"Medusa":92}},
    {"nickname":"Larl","real_name":"Denis Sigitov","nationality":"RUS","age":22,"primary_role":2,"team":"Team Spirit","salary_per_month":25000,"mechanics":88,"laning":87,"game_sense":89,"teamfight":87,"draft_iq":87,"communication":80,"clutch":88,"consistency":83,"mental":84,"physical":85,"form":82,"potential":90,"hero_pool_width":8,"meta_adaptability":85,"leadership":58,"hero_ratings":{"Invoker":90,"Storm Spirit":89,"Lina":87}},
    {"nickname":"Collapse","real_name":"Magomed Khalilov","nationality":"RUS","age":23,"primary_role":3,"team":"Team Spirit","salary_per_month":28000,"mechanics":91,"laning":87,"game_sense":92,"teamfight":95,"draft_iq":90,"communication":83,"clutch":93,"consistency":85,"mental":88,"physical":86,"form":87,"potential":93,"hero_pool_width":8,"meta_adaptability":88,"leadership":72,"hero_ratings":{"Magnus":97,"Tidehunter":92,"Primal Beast":91}},
    {"nickname":"rue","real_name":"Alexsander Filin","nationality":"RUS","age":20,"primary_role":4,"team":"Team Spirit","salary_per_month":12000,"mechanics":80,"laning":82,"game_sense":88,"teamfight":87,"draft_iq":85,"communication":83,"clutch":83,"consistency":78,"mental":82,"physical":85,"form":75,"potential":88,"hero_pool_width":6,"meta_adaptability":83,"leadership":50,"hero_ratings":{"Spirit Breaker":86,"Tusk":84,"Earth Spirit":80}},
    {"nickname":"Miposhka","real_name":"Yaroslav Naidenov","nationality":"RUS","age":27,"primary_role":5,"team":"Team Spirit","salary_per_month":20000,"mechanics":79,"laning":81,"game_sense":93,"teamfight":88,"draft_iq":92,"communication":96,"clutch":84,"consistency":90,"mental":92,"physical":80,"form":84,"potential":80,"hero_pool_width":7,"meta_adaptability":80,"leadership":95,"hero_ratings":{"Warlock":90,"Dazzle":88,"Witch Doctor":87}},
    # Team Liquid
    {"nickname":"miCKe","real_name":"Michael Vu","nationality":"SWE","age":24,"primary_role":1,"team":"Team Liquid","salary_per_month":28000,"mechanics":91,"laning":90,"game_sense":89,"teamfight":89,"draft_iq":83,"communication":78,"clutch":90,"consistency":88,"mental":87,"physical":86,"form":85,"potential":91,"hero_pool_width":8,"meta_adaptability":84,"leadership":52,"hero_ratings":{"Anti-Mage":93,"Medusa":91,"Spectre":87}},
    {"nickname":"Nisha","real_name":"Michal Jankowski","nationality":"POL","age":24,"primary_role":2,"team":"Team Liquid","salary_per_month":28000,"mechanics":93,"laning":90,"game_sense":91,"teamfight":90,"draft_iq":87,"communication":80,"clutch":91,"consistency":86,"mental":85,"physical":87,"form":84,"potential":92,"hero_pool_width":9,"meta_adaptability":88,"leadership":58,"hero_ratings":{"Lina":93,"Invoker":91,"Storm Spirit":90}},
    {"nickname":"SabeRLighT-","real_name":"Jonas Volek","nationality":"CZE","age":22,"primary_role":3,"team":"Team Liquid","salary_per_month":15000,"mechanics":83,"laning":82,"game_sense":87,"teamfight":88,"draft_iq":83,"communication":80,"clutch":82,"consistency":80,"mental":81,"physical":85,"form":76,"potential":88,"hero_pool_width":6,"meta_adaptability":82,"leadership":50,"hero_ratings":{"Beastmaster":86,"Bristleback":84,"Dark Seer":83}},
    {"nickname":"Boxi","real_name":"Samuel Svahn","nationality":"SWE","age":25,"primary_role":4,"team":"Team Liquid","salary_per_month":17000,"mechanics":83,"laning":85,"game_sense":90,"teamfight":87,"draft_iq":85,"communication":88,"clutch":84,"consistency":85,"mental":87,"physical":83,"form":80,"potential":84,"hero_pool_width":7,"meta_adaptability":80,"leadership":80,"hero_ratings":{"Tusk":88,"Earth Spirit":86,"Clockwerk":85}},
    {"nickname":"Insania","real_name":"Aydin Sarkohi","nationality":"SWE","age":32,"primary_role":5,"team":"Team Liquid","salary_per_month":18000,"mechanics":78,"laning":80,"game_sense":92,"teamfight":87,"draft_iq":93,"communication":95,"clutch":82,"consistency":88,"mental":91,"physical":72,"form":78,"potential":79,"hero_pool_width":7,"meta_adaptability":78,"leadership":93,"hero_ratings":{"Witch Doctor":90,"Warlock":89,"Dazzle":88}},
    # Xtreme Gaming
    {"nickname":"Ame","real_name":"Wang Chunyu","nationality":"CHN","age":26,"primary_role":1,"team":"Xtreme Gaming","salary_per_month":30000,"mechanics":94,"laning":91,"game_sense":90,"teamfight":91,"draft_iq":86,"communication":75,"clutch":93,"consistency":87,"mental":86,"physical":84,"form":85,"potential":92,"hero_pool_width":9,"meta_adaptability":87,"leadership":52,"hero_ratings":{"Anti-Mage":95,"Spectre":93,"Morphling":90}},
    {"nickname":"NothingToSay","real_name":"Cheng Jin Xiang","nationality":"CHN","age":27,"primary_role":2,"team":"Xtreme Gaming","salary_per_month":25000,"mechanics":89,"laning":87,"game_sense":90,"teamfight":88,"draft_iq":87,"communication":78,"clutch":87,"consistency":83,"mental":82,"physical":83,"form":80,"potential":88,"hero_pool_width":8,"meta_adaptability":85,"leadership":55,"hero_ratings":{"Puck":91,"Storm Spirit":89,"Invoker":87}},
    {"nickname":"Xxs","real_name":"Zhang Zhiping","nationality":"CHN","age":26,"primary_role":3,"team":"Xtreme Gaming","salary_per_month":18000,"mechanics":84,"laning":83,"game_sense":89,"teamfight":90,"draft_iq":85,"communication":80,"clutch":84,"consistency":82,"mental":82,"physical":84,"form":78,"potential":84,"hero_pool_width":7,"meta_adaptability":82,"leadership":62,"hero_ratings":{"Axe":88,"Dark Seer":87,"Tidehunter":84}},
    {"nickname":"fy","real_name":"Xu Linsen","nationality":"CHN","age":29,"primary_role":4,"team":"Xtreme Gaming","salary_per_month":20000,"mechanics":84,"laning":86,"game_sense":91,"teamfight":89,"draft_iq":88,"communication":85,"clutch":86,"consistency":87,"mental":87,"physical":80,"form":82,"potential":83,"hero_pool_width":7,"meta_adaptability":82,"leadership":80,"hero_ratings":{"Rubick":91,"Earth Spirit":89,"Nyx Assassin":87}},
    {"nickname":"xNova","real_name":"Yuen Wai Ho","nationality":"PHL","age":28,"primary_role":5,"team":"Xtreme Gaming","salary_per_month":15000,"mechanics":79,"laning":80,"game_sense":90,"teamfight":87,"draft_iq":88,"communication":88,"clutch":82,"consistency":85,"mental":86,"physical":80,"form":79,"potential":80,"hero_pool_width":7,"meta_adaptability":82,"leadership":82,"hero_ratings":{"Jakiro":88,"Grimstroke":86,"Oracle":84}},
    # BetBoom
    {"nickname":"Pure","real_name":"Ivan Moskalenko","nationality":"BLR","age":21,"primary_role":1,"team":"BetBoom Team","salary_per_month":22000,"mechanics":90,"laning":89,"game_sense":87,"teamfight":88,"draft_iq":82,"communication":74,"clutch":89,"consistency":83,"mental":82,"physical":88,"form":84,"potential":91,"hero_pool_width":8,"meta_adaptability":83,"leadership":48,"hero_ratings":{"Morphling":91,"Anti-Mage":90,"Spectre":88}},
    {"nickname":"gpk~","real_name":"Danil Skutin","nationality":"RUS","age":20,"primary_role":2,"team":"BetBoom Team","salary_per_month":20000,"mechanics":89,"laning":88,"game_sense":89,"teamfight":87,"draft_iq":86,"communication":79,"clutch":89,"consistency":82,"mental":83,"physical":88,"form":86,"potential":92,"hero_pool_width":8,"meta_adaptability":86,"leadership":52,"hero_ratings":{"Lina":91,"Storm Spirit":90,"Shadow Fiend":89}},
    {"nickname":"MieRo","real_name":"Matvei Vasiunin","nationality":"RUS","age":22,"primary_role":3,"team":"BetBoom Team","salary_per_month":11000,"mechanics":81,"laning":80,"game_sense":85,"teamfight":86,"draft_iq":82,"communication":79,"clutch":81,"consistency":79,"mental":79,"physical":83,"form":73,"potential":83,"hero_pool_width":6,"meta_adaptability":77,"leadership":55,"hero_ratings":{"Mars":85,"Axe":84,"Primal Beast":83}},
    {"nickname":"Save-","real_name":"Vitalie Melnic","nationality":"MDA","age":22,"primary_role":4,"team":"BetBoom Team","salary_per_month":10000,"mechanics":80,"laning":82,"game_sense":87,"teamfight":86,"draft_iq":85,"communication":84,"clutch":82,"consistency":82,"mental":81,"physical":85,"form":76,"potential":83,"hero_pool_width":6,"meta_adaptability":79,"leadership":62,"hero_ratings":{"Spirit Breaker":87,"Tusk":85,"Bounty Hunter":83}},
    {"nickname":"Kataomi","real_name":"Vladislav Semenov","nationality":"RUS","age":21,"primary_role":5,"team":"BetBoom Team","salary_per_month":9000,"mechanics":76,"laning":78,"game_sense":86,"teamfight":84,"draft_iq":84,"communication":85,"clutch":79,"consistency":78,"mental":79,"physical":83,"form":71,"potential":81,"hero_pool_width":6,"meta_adaptability":77,"leadership":65,"hero_ratings":{"Jakiro":87,"Crystal Maiden":85,"Dazzle":83}},
    # Tundra
    {"nickname":"Crystallis","real_name":"Remko Arets","nationality":"NLD","age":24,"primary_role":1,"team":"Tundra Esports","salary_per_month":20000,"mechanics":87,"laning":86,"game_sense":85,"teamfight":86,"draft_iq":81,"communication":76,"clutch":86,"consistency":84,"mental":82,"physical":84,"form":80,"potential":86,"hero_pool_width":7,"meta_adaptability":80,"leadership":48,"hero_ratings":{"Phantom Lancer":88,"Anti-Mage":87,"Medusa":85}},
    {"nickname":"33","real_name":"Neta Shapira","nationality":"ISR","age":26,"primary_role":2,"team":"Tundra Esports","salary_per_month":25000,"mechanics":90,"laning":88,"game_sense":93,"teamfight":89,"draft_iq":91,"communication":83,"clutch":89,"consistency":87,"mental":87,"physical":83,"form":84,"potential":89,"hero_pool_width":8,"meta_adaptability":86,"leadership":68,"hero_ratings":{"Puck":91,"Void Spirit":89,"Lina":88}},
    {"nickname":"Whitemon","real_name":"Erin Aldeguer","nationality":"PHL","age":23,"primary_role":4,"team":"Tundra Esports","salary_per_month":13000,"mechanics":81,"laning":83,"game_sense":88,"teamfight":86,"draft_iq":86,"communication":85,"clutch":82,"consistency":83,"mental":83,"physical":84,"form":78,"potential":84,"hero_pool_width":6,"meta_adaptability":81,"leadership":65,"hero_ratings":{"Tusk":87,"Spirit Breaker":85,"Nyx Assassin":84}},
    {"nickname":"Saksa","real_name":"Martin Sazdov","nationality":"DNK","age":29,"primary_role":5,"team":"Tundra Esports","salary_per_month":16000,"mechanics":80,"laning":82,"game_sense":89,"teamfight":87,"draft_iq":88,"communication":88,"clutch":82,"consistency":84,"mental":86,"physical":78,"form":79,"potential":80,"hero_pool_width":7,"meta_adaptability":80,"leadership":80,"hero_ratings":{"Ancient Apparition":89,"Grimstroke":87,"Warlock":84}},
    # PARIVISION
    {"nickname":"Satanic","real_name":"Alan Gallyamov","nationality":"RUS","age":18,"primary_role":1,"team":"PARIVISION","salary_per_month":20000,"mechanics":92,"laning":90,"game_sense":88,"teamfight":90,"draft_iq":84,"communication":76,"clutch":91,"consistency":80,"mental":83,"physical":90,"form":88,"potential":97,"hero_pool_width":7,"meta_adaptability":85,"leadership":45,"hero_ratings":{"Anti-Mage":93,"Terrorblade":91,"Phantom Lancer":89}},
    {"nickname":"No[o]ne-","real_name":"Vladimir Minenko","nationality":"UKR","age":28,"primary_role":2,"team":"PARIVISION","salary_per_month":18000,"mechanics":88,"laning":86,"game_sense":90,"teamfight":87,"draft_iq":90,"communication":83,"clutch":87,"consistency":83,"mental":84,"physical":80,"form":80,"potential":85,"hero_pool_width":8,"meta_adaptability":82,"leadership":68,"hero_ratings":{"Invoker":93,"Storm Spirit":90,"Tinker":89}},
    {"nickname":"Miposhka","real_name":"Yaroslav Naidenov","nationality":"RUS","age":27,"primary_role":5,"team":"PARIVISION","salary_per_month":18000,"mechanics":79,"laning":81,"game_sense":90,"teamfight":87,"draft_iq":90,"communication":93,"clutch":82,"consistency":88,"mental":90,"physical":80,"form":80,"potential":79,"hero_pool_width":7,"meta_adaptability":79,"leadership":90,"hero_ratings":{"Warlock":89,"Dazzle":87,"Shadow Shaman":85}},
    # Свободные агенты — добавь в PLAYERS_SEED
    {"nickname":"FreeCarry1","real_name":"Test Player","nationality":"RUS","age":22,"primary_role":1,"salary_per_month":8000,"mechanics":72,"laning":70,"game_sense":68,"teamfight":70,"draft_iq":65,"communication":65,"clutch":70,"consistency":68,"mental":72,"physical":80,"form":65,"potential":80,"hero_pool_width":5,"meta_adaptability":70,"leadership":45,"hero_ratings":{"Anti-Mage":75,"Spectre":72}},
    {"nickname":"FreeMid1","real_name":"Test Mid","nationality":"UKR","age":21,"primary_role":2,"salary_per_month":7000,"mechanics":70,"laning":72,"game_sense":70,"teamfight":68,"draft_iq":70,"communication":68,"clutch":69,"consistency":67,"mental":70,"physical":80,"form":68,"potential":82,"hero_pool_width":5,"meta_adaptability":72,"leadership":48,"hero_ratings":{"Storm Spirit":78,"Lina":74}},
    {"nickname":"FreeOff1","real_name":"Test Off","nationality":"BLR","age":23,"primary_role":3,"salary_per_month":6000,"mechanics":68,"laning":67,"game_sense":70,"teamfight":72,"draft_iq":66,"communication":70,"clutch":67,"consistency":69,"mental":71,"physical":80,"form":66,"potential":75,"hero_pool_width":5,"meta_adaptability":68,"leadership":55,"hero_ratings":{"Axe":76,"Mars":74}},
    {"nickname":"FreeSup4","real_name":"Test Sup4","nationality":"RUS","age":20,"primary_role":4,"salary_per_month":5000,"mechanics":65,"laning":67,"game_sense":68,"teamfight":66,"draft_iq":67,"communication":72,"clutch":64,"consistency":66,"mental":70,"physical":80,"form":64,"potential":78,"hero_pool_width":5,"meta_adaptability":67,"leadership":60,"hero_ratings":{"Tusk":74,"Earth Spirit":72}},
    {"nickname":"FreeSup5","real_name":"Test Sup5","nationality":"RUS","age":21,"primary_role":5,"salary_per_month":4500,"mechanics":63,"laning":64,"game_sense":67,"teamfight":65,"draft_iq":66,"communication":74,"clutch":62,"consistency":65,"mental":69,"physical":80,"form":63,"potential":76,"hero_pool_width":5,"meta_adaptability":65,"leadership":65,"hero_ratings":{"Witch Doctor":74,"Dazzle":72}},
]

HEROES_SEED = [
    # S
    ("Anti-Mage","AGI",["Carry"],"S"),("Dawnbreaker","STR",["Offlane","Support"],"S"),
    ("Lina","INT",["Mid","Support"],"S"),("Doom","STR",["Offlane"],"S"),
    ("Primal Beast","STR",["Offlane"],"S"),("Rubick","INT",["Support"],"S"),
    ("Magnus","STR",["Offlane","Mid"],"S"),("Sand King","STR",["Offlane","Support"],"S"),
    ("Abaddon","STR",["Support","Carry"],"S"),("Phantom Lancer","AGI",["Carry"],"S"),
    # A
    ("Invoker","UNI",["Mid"],"A"),("Puck","INT",["Mid","Offlane"],"A"),
    ("Storm Spirit","INT",["Mid"],"A"),("Medusa","AGI",["Carry"],"A"),
    ("Mars","STR",["Offlane"],"A"),("Earth Spirit","STR",["Support"],"A"),
    ("Tidehunter","STR",["Offlane"],"A"),("Pangolier","AGI",["Offlane"],"A"),
    ("Io","UNI",["Support"],"A"),("Windranger","INT",["Support","Mid"],"A"),
    ("Clockwerk","STR",["Support","Offlane"],"A"),("Wraith King","STR",["Carry"],"A"),
    ("Dragon Knight","STR",["Mid"],"A"),("Witch Doctor","INT",["Support"],"A"),
    ("Warlock","INT",["Support"],"A"),("Terrorblade","AGI",["Carry"],"A"),
    ("Shadow Fiend","AGI",["Mid"],"A"),("Tinker","INT",["Mid"],"A"),
    ("Ancient Apparition","INT",["Support"],"A"),("Snapfire","STR",["Support"],"A"),
    ("Visage","INT",["Support"],"A"),("Bane","INT",["Support"],"A"),
    ("Underlord","STR",["Offlane"],"A"),("Gyrocopter","AGI",["Carry"],"A"),
    # B
    ("Axe","STR",["Offlane"],"B"),("Bristleback","STR",["Offlane"],"B"),
    ("Spectre","AGI",["Carry"],"B"),("Void Spirit","UNI",["Mid"],"B"),
    ("Ember Spirit","AGI",["Mid"],"B"),("Morphling","AGI",["Carry"],"B"),
    ("Dark Seer","INT",["Offlane"],"B"),("Leshrac","INT",["Mid"],"B"),
    ("Nyx Assassin","AGI",["Support"],"B"),("Shadow Shaman","INT",["Support"],"B"),
    ("Tusk","STR",["Support"],"B"),("Spirit Breaker","STR",["Support"],"B"),
    ("Bounty Hunter","AGI",["Support"],"B"),("Dazzle","AGI",["Support"],"B"),
    ("Crystal Maiden","INT",["Support"],"B"),("Grimstroke","INT",["Support"],"B"),
    ("Jakiro","INT",["Support"],"B"),("Ogre Magi","STR",["Support"],"B"),
    ("Beastmaster","STR",["Offlane"],"B"),("Timbersaw","STR",["Offlane"],"B"),
    ("Weaver","AGI",["Carry"],"B"),("Drow Ranger","AGI",["Carry"],"B"),
    ("Queen of Pain","INT",["Mid"],"B"),("Slardar","STR",["Offlane"],"B"),
    ("Pudge","STR",["Support"],"B"),("Faceless Void","AGI",["Carry"],"B"),
    ("Templar Assassin","AGI",["Mid"],"B"),("Lion","INT",["Support"],"B"),
    ("Enigma","INT",["Offlane"],"B"),("Winter Wyvern","INT",["Support"],"B"),
    ("Razor","AGI",["Carry"],"B"),("Centaur Warrunner","STR",["Offlane"],"B"),
    ("Keeper of the Light","INT",["Support"],"B"),
    # C
    ("Lifestealer","STR",["Carry"],"C"),("Kunkka","STR",["Mid"],"C"),
    ("Juggernaut","AGI",["Carry"],"C"),("Luna","AGI",["Carry"],"C"),
    ("Necrophos","INT",["Mid"],"C"),("Death Prophet","INT",["Mid"],"C"),
    ("Viper","AGI",["Mid"],"C"),("Zeus","INT",["Mid"],"C"),
    ("Clinkz","AGI",["Carry"],"C"),("Disruptor","INT",["Support"],"C"),
    ("Earthshaker","STR",["Support"],"C"),("Naga Siren","AGI",["Carry"],"C"),
    ("Chen","INT",["Support"],"C"),("Oracle","INT",["Support"],"C"),
    ("Brewmaster","STR",["Offlane"],"C"),("Meepo","AGI",["Carry"],"C"),
    ("Lone Druid","STR",["Carry"],"C"),("Silencer","INT",["Support"],"C"),
    ("Batrider","INT",["Offlane"],"C"),("Outworld Destroyer","INT",["Mid"],"C"),
    ("Pugna","INT",["Support"],"C"),("Undying","STR",["Support"],"C"),
    ("Omniknight","STR",["Support"],"C"),("Venomancer","AGI",["Support"],"C"),
    ("Phoenix","STR",["Support"],"C"),("Bloodseeker","AGI",["Carry"],"C"),
    ("Broodmother","AGI",["Carry"],"C"),("Muerta","INT",["Carry"],"C"),
    # D
    ("Techies","UNI",["Support"],"D"),("Arc Warden","AGI",["Carry"],"D"),
    ("Nature's Prophet","INT",["Offlane"],"D"),("Sniper","AGI",["Carry"],"D"),
    ("Huskar","STR",["Carry"],"D"),("Ursa","AGI",["Carry"],"D"),
    ("Night Stalker","STR",["Offlane"],"D"),("Slark","AGI",["Carry"],"D"),
    ("Riki","AGI",["Carry"],"D"),("Treant Protector","STR",["Support"],"D"),
    ("Alchemist","STR",["Carry"],"D"),("Lycan","STR",["Carry"],"D"),
    ("Chaos Knight","STR",["Carry"],"D"),("Elder Titan","STR",["Support"],"D"),
    ("Skywrath Mage","INT",["Support"],"D"),("Marci","UNI",["Support"],"D"),
    ("Hoodwink","AGI",["Support"],"D"),("Monkey King","AGI",["Carry"],"D"),
    ("Vengeful Spirit","AGI",["Support"],"D"),("Shadow Demon","INT",["Support"],"D"),
    ("Lich","INT",["Support"],"D"),
]

async def seed_database(session):
    from sqlalchemy import select
    from database.models import Team, Player, Hero, GameState

    existing = (await session.execute(select(Team).limit(1))).scalar_one_or_none()
    if existing:
        log.info("🔁 БД уже засеяна, пропускаем.")
        return

    log.info("🌱 Засевка БД начата...")

    gs = GameState(id=1, current_season=1, current_week=1,
                   current_phase="offseason", patch_version="7.38")
    session.add(gs)

    for td in TEAMS_SEED:
        t = Team(
            name=td["name"], tag=td["tag"], region=td["region"],
            prestige=td["prestige"], fan_base=td["fan_base"],
            sponsor_level=td["sponsor_level"],
            budget_current=td["budget_current"],
            budget_monthly=td["budget_current"],
            total_earnings=td["total_earnings"],
            world_ranking=td["world_ranking"],
            region_ranking=td["region_ranking"],
            logo_emoji=td["logo_emoji"], color_hex=td["color_hex"],
            dpc_points_current=td["dpc_points_current"],
            dpc_points_all_time=td["dpc_points_all_time"],
            wins=td["wins"], losses=td["losses"],
        )
        session.add(t)
    await session.flush()

    teams_db = (await session.execute(select(Team))).scalars().all()
    team_map = {t.name: t.id for t in teams_db}

    for pd in PLAYERS_SEED:
        tid = team_map.get(pd.get("team"))
        p = Player(
            real_name=pd.get("real_name"), nickname=pd["nickname"],
            nationality=pd.get("nationality"), age=pd.get("age", 22),
            primary_role=pd["primary_role"],
            team_id=tid,
            contract_end_season=2,
            salary_per_month=pd.get("salary_per_month", 8000),
            mechanics=pd["mechanics"], laning=pd["laning"],
            game_sense=pd["game_sense"], teamfight=pd["teamfight"],
            draft_iq=pd["draft_iq"], communication=pd["communication"],
            clutch=pd["clutch"], consistency=pd["consistency"],
            mental=pd["mental"], physical=pd["physical"],
            form=pd.get("form", 70), potential=pd["potential"],
            hero_pool_width=pd.get("hero_pool_width", 6),
            meta_adaptability=pd.get("meta_adaptability", 70),
            leadership=pd.get("leadership", 50),
            hero_ratings=pd.get("hero_ratings", {}),
        )
        session.add(p)

    seen = set()
    for name, attr, roles, tier in HEROES_SEED:
        if name in seen:
            continue
        seen.add(name)
        session.add(Hero(name=name, primary_attribute=attr,
                         roles=roles, current_meta_tier=tier,
                         pick_rate=10.0, ban_rate=5.0))

    await session.commit()
    log.info(f"✅ Засеяно: {len(TEAMS_SEED)} команд, "
             f"{len(PLAYERS_SEED)} игроков, {len(seen)} героев")


async def main():
    storage = MemoryStorage()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=storage)

    dp.include_router(common_router)
    dp.include_router(gm_roster_router)
    dp.include_router(to_create_router)
    dp.include_router(admin_router)
    dp.include_router(rr_router)
    dp.include_router(gm_transfer_router)
    dp.include_router(gm_training_router)
    dp.include_router(gm_finance_router)
    dp.include_router(gm_match_router)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("✅ Таблицы БД созданы/проверены")

    async with async_session() as s:
        await seed_database(s)

    log.info("🎮 DOTA 2 FM запущен!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
