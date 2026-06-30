import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ Токен не найден! Убедитесь, что файл .env существует и содержит DISCORD_TOKEN.")

DB_PATH = "data/army_base.db"

# Права и каналы
LOG_CHANNEL_ID = 1340029496853794869
PROMO_LOG_CHANNEL_ID = 1340029496249684058
WARNINGS_LOG_CHANNEL_ID = 1340029495721070640
DEPUTY_ROLE_IDS = [1340029495708618813]
OFFICER_ROLE_IDS = [1340029495708618812]
FORUM_ARCHIVE_ID = 1520151286023061577
OFFENDERS_ARCHIVE_ID = 1520151514986053754 

CHANNELS_MAP = {
    "СКТ": 1340029496249684051, "Предупреждение": 1340029496249684051, "Задержание": 1340029496249684051,
    "Пост/Патруль": 1340029496249684052, "Тренировка": 1340029496249684054, "Боевой вылет": 1340029496249684055,              
    "Защита объекта": 1520153327139029054, "Аттестация": 1520153512204439572, "Обучение": 1340029496249684053,        
    "План/Методичка": 1520153704903348315, "Другое": 1520153888840355961
}

PRICES_COMPLEX = {
    "СКТ": (2, 0), "Предупреждение": (1, 0), "Задержание": (2, 0),
    "Пост/Патруль": (1, 1), "Тренировка": (4, 3), "Обучение": (5, 3), 
    "Боевой вылет": (10, 5), "Защита объекта": (7, 4), 
    "Аттестация": (10, 5), "План/Методичка": (15, 0), "Другое": (0, 0)
}

MAIN_MENU_OPTIONS = [
    "Нарушение (СКТ/Задержание)", "Пост/Патруль", "Тренировка", 
    "Боевой вылет", "Защита объекта", "Аттестация", "Обучение", "План/Методичка", "Другое"
]
# ==========================================
# ТРЕБОВАНИЯ БАЛЛОВ ДЛЯ ПОВЫШЕНИЯ
# ==========================================
PROMOTION_REQUIREMENTS = {
    "PFC": 20,
    "SPC": 30,
    "CPL": 40,
    "SGT": 50,
    "SSG": 60,
    "MSG": 70,
    "SGM": 80,
    "JLT": 100,
    "LT": 120,
    "SLT": 130,
    "CPT": 150,
    "MAJ": 200,
    "LTC": 250,
    "CO": 300,
    "COL": 400,
    "SCO": 500
}

RANKS = [
    (500, "SCO"), (400, "COL"), (300, "CO"), (250, "LTC"), (200, "MAJ"),
    (150, "CPT"), (130, "SLT"), (120, "LT"), (100, "JLT"),
    (80, "SGM"), (70, "MSG"), (60, "SSG"), (50, "SGT"),
    (40, "CPL"), (30, "SPC"), (20, "PFC"), (0, "PVT")
]

BASE_COMP_RANKS = ["PVT", "SGT", "JLT", "MAJ", "MC"]

# Цвета для Google Таблиц
# Цвета для Google Таблиц
COLORS = {
    "PVT": "#daf7d7", "PFC": "#daf7d7", "SPC": "#daf7d7", "CPL": "#daf7d7",
    
    # Сержанты теперь цвета light green 3 из палитры Google
    "SGT": "#9eff7a", "SSG": "#9eff7a", "MSG": "#9eff7a", "SGM": "#9eff7a",
    
    "JLT": "#8ac0fa", "LT": "#8ac0fa", "SLT": "#8ac0fa", "CPT": "#8ac0fa",
    "MAJ": "#FF9F9F", "LTC": "#FF9F9F", "CO": "#FF9F9F", "COL": "#FF9F9F", "SCO": "#FF9F9F",
    "MC": "#fffa9e", "GEN": "#fffa9e", "SGEN": "#fffa9e", "HGEN": "#fffa9e",
    "ARCHIVE": "#4D4D4D"
}

RANK_CRITERIA = {
    "PVT": {"edu_ryad_passed": 1},
    "PFC": {"patrols_done": 2, "trainings_passed": 1},      
    "SPC": {"patrols_done": 4, "trainings_passed": 3},      
    "CPL": {"att_ryad_passed": 1, "trainings_conducted": 3}, 
    "SGT": {"edu_serg_passed": 1, "method_materials_written": 1, "spec_trainings_conducted": 2, "days_served": 7},
    "SSG": {"combat_or_def_done": 1, "spec_trainings_conducted": 4},
    "MSG": {"spec_trainings_conducted": 7, "combat_or_def_done": 2},
    "SGM": {"att_serg_passed": 1, "attestations_conducted": 2, "combat_or_def_done": 2},
    "JLT": {"edu_jro_passed": 1, "days_served": 20},
    "LT":  {"combat_or_def_done": 3},
    "SLT": {"flights_commanded": 2},
    "CPT": {"att_jro_passed": 1, "edu_conducted": 1},
    "MAJ": {"edu_sro_passed": 1, "method_materials_written": 1, "days_served": 35},
    "LTC": {"flights_commanded": 10},
    "CO":  {"flights_commanded": 15, "method_trainings_conducted": 3},
    "COL": {"flights_commanded": 20, "method_materials_written": 1},
    "SCO": {"method_trainings_conducted": 3, "att_sro_passed": 1}
}

METRICS_NAMES = {
    "edu_ryad_passed": "Обучение (Ряд. состав)", "edu_serg_passed": "Обучение (Сержант. состав)",
    "edu_jro_passed": "Обучение (Мл. офиц. состав)", "edu_sro_passed": "Обучение (Ст. офиц. состав)",
    "att_ryad_passed": "Аттестация (Ряд. состав)", "att_serg_passed": "Аттестация (Сержант. состав)",
    "att_jro_passed": "Аттестация (Мл. офиц. состав)", "att_sro_passed": "Аттестация (Ст. офиц. состав)",
    "patrols_done": "Посты/Патрули", "trainings_passed": "Пройдено тренировок",
    "trainings_conducted": "Проведено тренировок", "method_materials_written": "Написано планов/методичек",
    "spec_trainings_conducted": "Спец. тренировок проведено", "combat_or_def_done": "Вылеты / Защита ОВО",
    "attestations_conducted": "Проведено аттестаций", "flights_commanded": "Командование операциями",
    "edu_conducted": "Проведено лекций/обучений", "method_trainings_conducted": "Учений по методичке проведено",
    "days_served": "Дней выслуги в текущем составе"
}

METRIC_COLUMNS = [
    "patrols_done", "trainings_passed", "trainings_conducted", "spec_trainings_conducted", 
    "attestations_conducted", "edu_conducted", "combat_or_def_done", "flights_commanded", 
    "method_materials_written", "method_trainings_conducted", "edu_ryad_passed", "edu_serg_passed", 
    "edu_jro_passed", "edu_sro_passed", "att_ryad_passed", "att_serg_passed", "att_jro_passed", "att_sro_passed"
]
AUTO_ROLE_1_ID = 1340029495708618805 
AUTO_ROLE_2_ID = 1340029495708618806  
# ID ролей за особые звания
ROLE_CPL_ID = 1340029495318417482  # ID роли для CPL
ROLE_SGM_ID = 1340029495318417483  # ID роли для CGM
ROLE_CPT_ID = 1340029495318417484  # ID роли для CPT