import disnake
from disnake.ext import commands
from disnake import ui
import datetime
import re
import aiosqlite

# ==========================================
# НАСТРОЙКИ
# ==========================================
TOKEN = "ТВОЙ_ТОКЕН_ЗДЕСЬ" # Не забудь вставить токен
LOG_CHANNEL_ID = 1491612522749497354
PROMO_LOG_CHANNEL_ID = 1492418984539062312
FORUM_ARCHIVE_ID = 1491631113670758570
OFFENDERS_ARCHIVE_ID = 1518770081889255614 # ID ФОРУМА НАРУШИТЕЛЕЙ

CHANNELS_MAP = {
    "СКТ": 1492267166001533101,
    "Предупреждение": 1492267166001533101,
    "Задержание": 1492267166001533101,
    "Пост/Патруль": 1492422973057925200, 
    "Тренировка": 1491627496385548419,     
    "Боевой вылет": 1492432803567243304,             
    "Защита объекта": 1492432775171674223,
    "Аттестация": 1518742580974583849,     
    "Обучение": 1518742580974583849,       
    "План/Методичка": 1518742887309770832, 
    "Другое": 1492422875347681290
}

PRICES_COMPLEX = {
    "СКТ": (2, 0), "Предупреждение": (1, 0), "Задержание": (2, 0),
    "Пост/Патруль": (1, 1), "Тренировка": (4, 3), "Обучение": (5, 3), 
    "Боевой вылет": (10, 5), "Защита объекта": (7, 4), 
    "Аттестация": (10, 5), "План/Методичка": (15, 0),
    "Другое": (0, 0)
}

MAIN_MENU_OPTIONS = [
    "Нарушение (СКТ/Задержание)", "Пост/Патруль", "Тренировка", 
    "Боевой вылет", "Защита объекта", "Аттестация", 
    "Обучение", "План/Методичка", "Другое"
]

RANKS = [
    (500, "SCO"), (400, "COL"), (300, "CO"), (250, "LTC"), (200, "MAJ"),
    (150, "CPT"), (130, "SLT"), (120, "LT"), (100, "JLT"),
    (80, "SGM"), (70, "MSG"), (60, "SSG"), (50, "SGT"),
    (40, "CPL"), (30, "SPC"), (20, "PFC"), (0, "PVT")
]

RANK_CRITERIA = {
    "PVT": {"edu_ryad_passed": 1},
    "PFC": {"patrols_done": 2, "trainings_passed": 1},
    "SPC": {"patrols_done": 4, "trainings_passed": 3},
    "CPL": {"att_ryad_passed": 1, "trainings_conducted": 3},
    "SGT": {"edu_serg_passed": 1, "method_materials_written": 1, 
            "spec_trainings_conducted": 2},
    "SSG": {"combat_or_def_done": 1, "spec_trainings_conducted": 4},
    "MSG": {"spec_trainings_conducted": 7, "combat_or_def_done": 2},
    "SGM": {"att_serg_passed": 1, "attestations_conducted": 2, 
            "combat_or_def_done": 2},
    "JLT": {"edu_jro_passed": 1},
    "LT":  {"combat_or_def_done": 3},
    "SLT": {"flights_commanded": 2},
    "CPT": {"att_jro_passed": 1, "edu_conducted": 1},
    "MAJ": {"edu_sro_passed": 1, "method_materials_written": 1},
    "LTC": {"flights_commanded": 10},
    "CO":  {"flights_commanded": 15, "method_trainings_conducted": 3},
    "COL": {"flights_commanded": 20, "method_materials_written": 1},
    "SCO": {"method_trainings_conducted": 3, "att_sro_passed": 1}
}

METRICS_NAMES = {
    "edu_ryad_passed": "Обучение (Ряд. состав)", 
    "edu_serg_passed": "Обучение (Сержант. состав)",
    "edu_jro_passed": "Обучение (Мл. офиц. состав)", 
    "edu_sro_passed": "Обучение (Ст. офиц. состав)",
    "att_ryad_passed": "Аттестация (Ряд. состав)", 
    "att_serg_passed": "Аттестация (Сержант. состав)",
    "att_jro_passed": "Аттестация (Мл. офиц. состав)", 
    "att_sro_passed": "Аттестация (Ст. офиц. состав)",
    "patrols_done": "Посты/Патрули", 
    "trainings_passed": "Пройдено тренировок",
    "trainings_conducted": "Проведено тренировок", 
    "method_materials_written": "Написано планов/методичек",
    "spec_trainings_conducted": "Спец. тренировок проведено", 
    "combat_or_def_done": "Вылеты / Защита ОВО",
    "attestations_conducted": "Проведено аттестаций", 
    "flights_commanded": "Командование операциями",
    "edu_conducted": "Проведено лекций/обучений", 
    "method_trainings_conducted": "Учений по методичке проведено"
}

intents = disnake.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# УТИЛИТЫ И БАЗА ДАННЫХ
# ==========================================

def get_field_val(embed, name_sub, default=""):
    """Безопасное извлечение текста из Embed (защита от длинных строк)"""
    for f in embed.fields:
        if name_sub in f.name:
            return f.value.replace("```", "").strip()
    return default

def extract_rp_id(text):
    parts = text.split('|')
    if len(parts) > 0:
        potential_id = parts[0].strip()
        if potential_id.isdigit(): 
            return potential_id
    match = re.search(r'\b\d{2,5}\b', text)
    return match.group(0) if match else "0000"

async def init_db():
    async with aiosqlite.connect("army_base.db") as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS soldiers "
            "(user_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, "
            "rank TEXT DEFAULT 'PVT')"
        )
        columns = [
            "patrols_done", "trainings_passed", "trainings_conducted", 
            "spec_trainings_conducted", "attestations_conducted", 
            "edu_conducted", "combat_or_def_done", "flights_commanded", 
            "method_materials_written", "method_trainings_conducted",
            "edu_ryad_passed", "edu_serg_passed", "edu_jro_passed", 
            "edu_sro_passed", "att_ryad_passed", "att_serg_passed", 
            "att_jro_passed", "att_sro_passed"
        ]
        for col in columns:
            try: 
                await db.execute(
                    f"ALTER TABLE soldiers ADD COLUMN {col} INTEGER DEFAULT 0"
                )
            except aiosqlite.OperationalError: 
                pass
        await db.commit()

def get_progress_bar(current, total):
    if total <= 0: 
        return "`[MAX]`"
    percentage = min(current / (total or 1), 1.0)
    filled = int(10 * percentage)
    bar = "█" * filled + "░" * (10 - filled)
    return f"`[{bar}]` {int(percentage * 100)}%"

def get_target_points(rank):
    for i in range(len(RANKS)-1):
        if RANKS[i+1][1] == rank: 
            return RANKS[i][0], RANKS[i][1]
    return 0, "MAX"

def get_criteria_text(rank, stats):
    if rank not in RANK_CRITERIA or not RANK_CRITERIA[rank]: 
        return "*Для этого звания нет системных доп. критериев*"
    lines = []
    for key, target in RANK_CRITERIA[rank].items():
        current = stats.get(key, 0)
        status = '✅' if current >= target else '❌'
        lines.append(f"{METRICS_NAMES[key]}: `{current}/{target}` {status}")
    return "\n".join(lines)

def check_promotion_criteria(rank, stats, target_pts):
    if stats['points'] < target_pts: 
        return False
    if rank not in RANK_CRITERIA: 
        return True
    for key, target in RANK_CRITERIA[rank].items():
        if stats.get(key, 0) < target: 
            return False
    return True

async def update_member_nickname(guild, rp_id, new_rank):
    try:
        for member in guild.members:
            if member.display_name.startswith(str(rp_id)):
                parts = member.display_name.split("|")
                if len(parts) >= 3:
                    new_nick = f"{parts[0].strip()} | {new_rank} | {parts[2].strip()}"
                    await member.edit(nick=new_nick)
                return
    except Exception: 
        pass

async def sync_dossier(rp_id, author_info, r_type, reward, stats, 
                       jump_url, status="approved", officer="Система"):
    try:
        rank = stats['rank']
        total_p = stats['points']
        forum = bot.get_channel(FORUM_ARCHIVE_ID)
        if not forum:
            forum = await bot.fetch_channel(FORUM_ARCHIVE_ID)
            
        thread = next((t for t in forum.threads if f"ID: {rp_id}" in t.name), None)
        
        nick_part = author_info.split('|')[-1].strip()
        new_thread_name = f"ID: {rp_id} | {rank} | {nick_part}"
        if thread and thread.name != new_thread_name: 
            await thread.edit(name=new_thread_name)

        target_points, nxt = get_target_points(rank)
        p_to = target_points - total_p
        
        desc_lines = [
            f"**Боец:** {author_info}",
            f"**Звание:** `{rank}`",
            f"**Баллы:** `{total_p}`",
            f"**Прогресс:** {get_progress_bar(total_p, target_points)} ({p_to} до {nxt})\n",
            f"**📋 Выполнение нормы на {nxt}:**",
            get_criteria_text(rank, stats)
        ]
        desc = "\n".join(desc_lines)
        embed = disnake.Embed(
            title="🗃️ ЛИЧНОЕ ДЕЛО", 
            description=desc, 
            color=disnake.Color.blue()
        )
        
        if not thread:
            thread_data = await forum.create_thread(name=new_thread_name, embed=embed)
            thread = thread_data.thread
        else:
            async for msg in thread.history(oldest_first=True, limit=1):
                if msg.embeds: 
                    await msg.edit(embed=embed)

        log_lines = [
            f"Статус: **{status.upper()}**",
            f"Баллы: `+{reward}`",
            f"Проверил: **{officer}**",
            f"🔗 [ОТЧЕТ]({jump_url})"
        ]
        log_embed = disnake.Embed(
            title=f"📑 {r_type}", 
            description="\n".join(log_lines), 
            color=disnake.Color.green() if status=="approved" else disnake.Color.red()
        )
        await thread.send(embed=log_embed)
    except Exception as e: 
        print(f"Ошибка форума для {rp_id}: {e}")

async def sync_offender(embed_data, jump_url, status, officer):
    try:
        forum = bot.get_channel(OFFENDERS_ARCHIVE_ID)
        if not forum:
            forum = await bot.fetch_channel(OFFENDERS_ARCHIVE_ID)
        
        offender_raw = get_field_val(embed_data, "Нарушитель", "Неизвестно")
        offender_id = extract_rp_id(offender_raw)
        
        thread = next((t for t in forum.threads if f"ID: {offender_id}" in t.name), None)

        if not thread:
            nick = offender_raw.split('|')[-1].strip() if '|' in offender_raw else offender_raw
            embed = disnake.Embed(
                title="🚨 ДЕЛО НАРУШИТЕЛЯ", 
                description=f"**Личное дело нарушителя:** {offender_raw}", 
                color=disnake.Color.dark_red()
            )
            thread_data = await forum.create_thread(
                name=f"ID: {offender_id} | {nick}", 
                embed=embed
            )
            thread = thread_data.thread

        unit = get_field_val(embed_data, "Формирование")
        arr_type = get_field_val(embed_data, "Тип")
        punish = get_field_val(embed_data, "Наказание")
        reason = get_field_val(embed_data, "Причина")
        evidence = get_field_val(embed_data, "Доказательства")

        log_embed = disnake.Embed(
            title=f"⚖️ {arr_type.upper()}", 
            color=disnake.Color.orange()
        )
        
        author_val = embed_data.fields[0].value
        log_embed.add_field(name="Оформил", value=author_val, inline=False)
        
        if unit: 
            log_embed.add_field(name="Формирование", value=f"`{unit}`", inline=True)
        if punish: 
            log_embed.add_field(name="Наказание/Сроки", value=f"`{punish}`", inline=True)
        if reason: 
            log_embed.add_field(name="Причина", value=f"```{reason}```", inline=False)
        if evidence: 
            log_embed.add_field(name="Доказательства", value=evidence, inline=False)
            
        res_lines = [
            f"Статус: **{status.upper()}**",
            f"Утвердил: **{officer}**",
            f"🔗 [СВЯЗАННЫЙ РАПОРТ]({jump_url})"
        ]
        log_embed.add_field(name="Итог", value="\n".join(res_lines), inline=False)

        await thread.send(embed=log_embed)
    except Exception as e: 
        print(f"Ошибка форума нарушителей: {e}")

async def send_promo_request(rp_id, old, new, pts, info=""):
    desc_lines = [
        f"Боец: {info or rp_id}",
        f"{old} -> **{new}**",
        f"Баллы: **{pts}**",
        "*Все обязательные критерии выполнены.*"
    ]
    e = disnake.Embed(
        title="📈 ЗАПРОС ПОВЫШЕНИЯ", 
        description="\n".join(desc_lines), 
        color=disnake.Color.gold()
    )
    chan = bot.get_channel(LOG_CHANNEL_ID)
    if chan:
        await chan.send(embed=e, view=PromotionView(rp_id, info or str(rp_id), new))

# ==========================================
# ВЬЮ И МОДАЛКИ ДЛЯ РАПОРТОВ
# ==========================================

class PromotionView(ui.View):
    def __init__(self, rp_id, author_info, new_rank):
        super().__init__(timeout=None)
        self.rp_id = rp_id
        self.author_info = author_info
        self.new_rank = new_rank

    @ui.button(label="Утвердить", style=disnake.ButtonStyle.green, custom_id="conf_v9")
    async def approve(self, btn, inter):
        if not inter.author.guild_permissions.administrator: 
            return
        await inter.response.defer()
        
        async with aiosqlite.connect("army_base.db") as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE soldiers SET rank = ?, points = 0 WHERE user_id = ?", 
                (self.new_rank, self.rp_id)
            )
            await db.commit()
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (self.rp_id,)) as cur:
                new_stats = dict(await cur.fetchone())
        
        await update_member_nickname(inter.guild, self.rp_id, self.new_rank)
        await sync_dossier(
            self.rp_id, self.author_info, "ПОВЫШЕНИЕ", 0, new_stats, 
            inter.message.jump_url, officer=inter.author.display_name
        )
        
        pl = bot.get_channel(PROMO_LOG_CHANNEL_ID)
        if pl: 
            msg = f"🎊 **ПРИКАЗ:** {self.author_info} повышен до **{self.new_rank}**!"
            msg += f" (Утвердил: {inter.author.display_name})"
            await pl.send(msg)
            
        await inter.edit_original_response(
            content="✅ Повышение утверждено", 
            embed=inter.message.embeds[0], 
            view=None
        )

class ManualPointsModal(ui.Modal):
    def __init__(self, view, inter_orig, override_cat=None):
        self.view = view
        self.inter_orig = inter_orig
        self.override_cat = override_cat
        super().__init__(title="Назначение баллов", components=[
            ui.TextInput(label="Баллы Автору", placeholder="5", custom_id="pts_a"),
            ui.TextInput(label="Баллы Участникам", placeholder="2", custom_id="pts_m", required=False)
        ])
    async def callback(self, inter):
        await inter.response.defer(ephemeral=True)
        pts_a = int(inter.text_values.get("pts_a", 0) or 0)
        pts_m = int(inter.text_values.get("pts_m", 0) or 0)
        
        await self.view.process(
            self.inter_orig, "approved", 
            manual_pts=(pts_a, pts_m), 
            override_category=self.override_cat
        )
        
        cat_name = self.override_cat or 'Другое'
        await inter.edit_original_response(
            content=f"✅ Начислено: +{pts_a}/+{pts_m} (Категория: {cat_name})"
        )

class OtherCategoryRouteView(ui.View):
    def __init__(self, officer_view, inter_orig):
        super().__init__(timeout=300)
        self.officer_view = officer_view
        self.inter_orig = inter_orig
        
        options = []
        for c in MAIN_MENU_OPTIONS:
            if c != "Нарушение (СКТ/Задержание)":
                options.append(disnake.SelectOption(label=c, value=c))
                
        options.append(disnake.SelectOption(label="СКТ / Задержание", value="Задержание"))
        
        self.add_item(
            ui.Select(
                options=options, 
                placeholder="В какой раздел отнести этот рапорт?", 
                custom_id="route_sel"
            )
        )

    async def interaction_check(self, inter):
        if inter.data.custom_id == "route_sel":
            target = inter.values[0]
            await inter.response.send_modal(
                ManualPointsModal(self.officer_view, self.inter_orig, target)
            )
        return False

class OfficerButtons(ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @ui.button(label="Одобрить", style=disnake.ButtonStyle.green, custom_id="app_v9")
    async def approve(self, btn, inter):
        if not inter.author.guild_permissions.administrator: 
            return
        
        if "Другое" in inter.message.embeds[0].title: 
            await inter.response.send_message(
                "Этот рапорт из категории **Другое**. Выберите, куда его распределить:", 
                view=OtherCategoryRouteView(self, inter), 
                ephemeral=True
            )
        else:
            await inter.response.defer()
            await self.process(inter, "approved")

    @ui.button(label="Отклонить", style=disnake.ButtonStyle.red, custom_id="deny_v9")
    async def deny(self, btn, inter):
        if not inter.author.guild_permissions.administrator: 
            return
        await inter.response.defer()
        await self.process(inter, "denied")

    async def process(self, inter, status, manual_pts=None, override_category=None):
        embed = inter.message.embeds[0]
        
        if override_category:
            base_r_type = override_category
            full_r_type = override_category
        else:
            full_r_type = embed.title.replace("📥 РАПОРТ: ", "")
            base_r_type = full_r_type.split(" (")[0]
        
        subcat = ""
        if "(" in full_r_type:
            subcat = full_r_type.split("(")[1].replace(")", "").strip().lower()
        
        if base_r_type == "Тренировка" and not manual_pts:
            if "специальная" in subcat: 
                rew_a, rew_m = 6, 4
            elif "методичк" in subcat: 
                rew_a, rew_m = 8, 5
            else: 
                rew_a, rew_m = 4, 3
        else:
            default_pts = PRICES_COMPLEX.get(base_r_type, (1, 0))
            rew_a, rew_m = manual_pts if manual_pts else default_pts
            
        if status != "approved": 
            rew_a = rew_m = 0
        
        auth_f = get_field_val(embed, "Подал", "")
        author_rp_id = extract_rp_id(auth_f)
        
        participants_str = get_field_val(embed, "Участники", "")
        participants_list = [p.strip() for p in participants_str.split('\n') if p.strip()]
        
        is_cmd = get_field_val(embed, "Командир", "").lower()

        auth_col, part_col = None, None
        
        if base_r_type == "Пост/Патруль": 
            auth_col = part_col = "patrols_done"
            
        elif base_r_type == "Аттестация": 
            auth_col = "attestations_conducted"
            if "рядов" in subcat: part_col = "att_ryad_passed"
            elif "сержант" in subcat: part_col = "att_serg_passed"
            elif "мл." in subcat: part_col = "att_jro_passed"
            elif "ст." in subcat: part_col = "att_sro_passed"
            else: part_col = "att_ryad_passed"
            
        elif base_r_type == "Обучение": 
            auth_col = "edu_conducted"
            if "рядов" in subcat: part_col = "edu_ryad_passed"
            elif "сержант" in subcat: part_col = "edu_serg_passed"
            elif "мл." in subcat: part_col = "edu_jro_passed"
            elif "ст." in subcat: part_col = "edu_sro_passed"
            else: part_col = "edu_ryad_passed"
            
        elif base_r_type == "План/Методичка": 
            auth_col = "method_materials_written"
            
        elif base_r_type == "Защита объекта": 
            part_col = "combat_or_def_done"
            if "да" in is_cmd or "+" in is_cmd: 
                auth_col = "flights_commanded"
            else: 
                auth_col = "combat_or_def_done"
                
        elif base_r_type == "Тренировка":
            part_col = "trainings_passed"
            if "специальная" in subcat: 
                auth_col = "spec_trainings_conducted"
            elif "методичк" in subcat: 
                auth_col = "method_trainings_conducted"
            else: 
                auth_col = "trainings_conducted"
                
        elif base_r_type == "Боевой вылет":
            part_col = "combat_or_def_done"
            if "да" in is_cmd or "+" in is_cmd: 
                auth_col = "flights_commanded"
            else: 
                auth_col = "combat_or_def_done"

        results = {}

        async with aiosqlite.connect("army_base.db") as db:
            db.row_factory = aiosqlite.Row
            
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (author_rp_id,))
            if status == "approved": 
                await db.execute(
                    "UPDATE soldiers SET points = points + ? WHERE user_id = ?", 
                    (rew_a, author_rp_id)
                )
                if auth_col: 
                    await db.execute(
                        f"UPDATE soldiers SET {auth_col} = {auth_col} + 1 WHERE user_id = ?", 
                        (author_rp_id,)
                    )
            
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (author_rp_id,)) as c: 
                results[author_rp_id] = {
                    "stats": dict(await c.fetchone()), 
                    "reward": rew_a, 
                    "info": auth_f
                }

            for part_info in participants_list:
                p_id = extract_rp_id(part_info)
                if p_id == author_rp_id: 
                    continue 
                
                await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (p_id,))
                if status == "approved": 
                    await db.execute(
                        "UPDATE soldiers SET points = points + ? WHERE user_id = ?", 
                        (rew_m, p_id)
                    )
                    if part_col: 
                        await db.execute(
                            f"UPDATE soldiers SET {part_col} = {part_col} + 1 WHERE user_id = ?", 
                            (p_id,)
                        )
                
                async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (p_id,)) as c: 
                    results[p_id] = {
                        "stats": dict(await c.fetchone()), 
                        "reward": rew_m, 
                        "info": part_info
                    }
            await db.commit()

        jump_url = inter.message.jump_url
        target_cid = CHANNELS_MAP.get(base_r_type) or CHANNELS_MAP.get("Другое")
        
        if target_cid:
            chan = bot.get_channel(target_cid)
            if chan:
                log_msg = await chan.send(embed=embed)
                await log_msg.add_reaction("✅" if status=="approved" else "❌")
                jump_url = log_msg.jump_url

        if base_r_type in ["СКТ", "Задержание", "Предупреждение"] and status == "approved":
            await sync_offender(embed, jump_url, status, inter.author.display_name)

        for p_id, data in results.items():
            stats = data["stats"]
            await sync_dossier(
                p_id, data["info"], full_r_type, data["reward"], stats, 
                jump_url, status, inter.author.display_name
            )
            
            if status == "approved" and stats['rank'] != "MAJ":
                target_pts, nxt_r = get_target_points(stats['rank'])
                if check_promotion_criteria(stats['rank'], stats, target_pts):
                    await send_promo_request(
                        p_id, stats['rank'], nxt_r, 
                        stats['points'], data["info"]
                    )

        e = disnake.Embed(
            title=f"Вердикт: {status.upper()}", 
            color=disnake.Color.green() if status=="approved" else disnake.Color.red()
        )
        e.set_footer(text=f"Офицер: {inter.author.display_name}")
        await inter.edit_original_response(embed=e, view=None)

class ReportModal(ui.Modal):
    def __init__(self, r_type, author_name, selected_users=None, extra_fields=None):
        self.r_type = r_type
        self.author_name = author_name
        self.selected_users = selected_users or []
        self.extra_fields = extra_fields or {}
        base_type = r_type.split(" (")[0]
        
        components = []
        
        if base_type == "План/Методичка":
            components = [
                ui.TextInput(
                    label="Тема методички/плана", 
                    custom_id="topic", 
                    max_length=100
                ),
                ui.TextInput(
                    label="Ссылка на Google Doc (с доступом)", 
                    custom_id="evidence", 
                    style=disnake.TextInputStyle.paragraph
                )
            ]
            
        elif base_type in ["СКТ", "Предупреждение", "Задержание"]:
            components = [
                ui.TextInput(
                    label="Нарушитель (IDN | Позывной)", 
                    custom_id="offender_info", 
                    max_length=100
                ),
                ui.TextInput(
                    label="Формирование (напр. 501st)", 
                    custom_id="unit", 
                    max_length=50
                )
            ]
            if base_type == "СКТ":
                components.append(
                    ui.TextInput(
                        label="Вид наказания и сколько раз было?", 
                        custom_id="punishment", 
                        max_length=100
                    )
                )
            elif base_type == "Задержание":
                components.append(
                    ui.TextInput(
                        label="Сколько сроков?", 
                        custom_id="punishment", 
                        max_length=100
                    )
                )
                
            components.append(
                ui.TextInput(
                    label="Причина", 
                    custom_id="reason", 
                    style=disnake.TextInputStyle.paragraph
                )
            )
            components.append(
                ui.TextInput(
                    label="Доказательства (ссылки)", 
                    custom_id="evidence", 
                    style=disnake.TextInputStyle.paragraph
                )
            )
            
        elif base_type == "Пост/Патруль":
            components = [
                ui.TextInput(
                    label="Маршрут или название поста", 
                    custom_id="route", 
                    max_length=100
                ),
                ui.TextInput(
                    label="Время (в минутах)", 
                    custom_id="time", 
                    max_length=50
                ),
                ui.TextInput(
                    label="Инциденты (описание)", 
                    custom_id="incidents", 
                    style=disnake.TextInputStyle.paragraph, 
                    required=False
                ),
                ui.TextInput(
                    label="Доказательства (ссылки с новой строки)", 
                    custom_id="evidence", 
                    style=disnake.TextInputStyle.paragraph
                )
            ]
            
        elif base_type == "Тренировка":
            components = [
                ui.TextInput(
                    label="Описание", 
                    custom_id="desc", 
                    style=disnake.TextInputStyle.paragraph
                )
            ]
            if self.extra_fields.get("⚙️ Тип тренировки") == "По методичке":
                components.append(
                    ui.TextInput(
                        label="Ссылка на методический материал", 
                        custom_id="method_link"
                    )
                )
            components.append(
                ui.TextInput(
                    label="Доказательства (ссылки)", 
                    custom_id="evidence", 
                    style=disnake.TextInputStyle.paragraph
                )
            )
            
        else:
            components = [
                ui.TextInput(
                    label="Описание", 
                    custom_id="desc", 
                    style=disnake.TextInputStyle.paragraph
                ),
                ui.TextInput(
                    label="Доказательства (ссылки с новой строки)", 
                    custom_id="evidence", 
                    style=disnake.TextInputStyle.paragraph
                )
            ]
            
        super().__init__(title="Рапорт", components=components)

    async def callback(self, inter):
        e = disnake.Embed(
            title=f"📥 РАПОРТ: {self.r_type}", 
            color=disnake.Color.red(), 
            timestamp=datetime.datetime.now()
        )
        e.add_field(
            name="👤 Подал", 
            value=f"```\n{self.author_name}\n```", 
            inline=False
        )
        
        tv = inter.text_values
        
        if 'offender_info' in tv: 
            e.add_field(name="🚨 Нарушитель", value=f"```\n{tv['offender_info']}\n```", inline=False)
        if 'unit' in tv: 
            e.add_field(name="🔰 Формирование", value=f"```\n{tv['unit']}\n```", inline=True)
        
        for k, v in self.extra_fields.items():
            e.add_field(name=k, value=f"```\n{v}\n```", inline=True)
            
        if 'punishment' in tv: 
            e.add_field(name="⏳ Наказание/Сроки", value=f"```\n{tv['punishment']}\n```", inline=True)
        if 'reason' in tv: 
            e.add_field(name="📋 Причина", value=f"```\n{tv['reason']}\n```", inline=False)
        
        if self.selected_users:
            mentions = "\n".join([u.display_name for u in self.selected_users])
            e.add_field(name="👥 Участники", value=f"```\n{mentions}\n```", inline=False)
            
        if 'topic' in tv: 
            e.add_field(name="📚 Тема", value=f"```\n{tv['topic']}\n```", inline=False)
        if 'route' in tv: 
            e.add_field(name="📍 Маршрут/Пост", value=f"```\n{tv['route']}\n```", inline=True)
        if 'time' in tv: 
            e.add_field(name="⏱️ Время (мин)", value=f"```\n{tv['time']}\n```", inline=True)
        if 'method_link' in tv: 
            e.add_field(name="📖 Ссылка на методичку", value=tv['method_link'], inline=False)
        
        if 'desc' in tv: 
            e.add_field(name="📝 Детали / Описание", value=f"```\n{tv['desc']}\n```", inline=False)
        if 'incidents' in tv and tv['incidents']: 
            e.add_field(name="⚠️ Инциденты", value=f"```\n{tv['incidents']}\n```", inline=False)
        if 'evidence' in tv: 
            e.add_field(name="📸 Доказательства", value=tv['evidence'], inline=False)
        
        msg = await bot.get_channel(LOG_CHANNEL_ID).send(embed=e, view=OfficerButtons())
        await msg.create_thread(name=f"Разбор: {self.r_type.split(' (')[0]}")
        await inter.response.send_message("✅ Рапорт отправлен на проверку!", ephemeral=True)

class ParticipantSelectView(ui.View):
    def __init__(self, r_type, author_name, extra_fields=None):
        super().__init__(timeout=300)
        self.r_type = r_type
        self.author_name = author_name
        self.extra_fields = extra_fields or {}
        self.selected_users = []
        
        if "Аттестация" not in r_type and "Обучение" not in r_type:
            btn_skip = ui.Button(
                label="Пропустить (Я один)", 
                style=disnake.ButtonStyle.grey, 
                custom_id="skip_step"
            )
            btn_skip.callback = self.skip_callback
            self.add_item(btn_skip)

    @ui.user_select(
        placeholder="Выберите участников (если есть)", 
        min_values=1, 
        max_values=25, 
        custom_id="user_select"
    )
    async def select_users(self, select: ui.UserSelect, inter: disnake.MessageInteraction):
        self.selected_users = select.values
        await inter.response.defer()

    @ui.button(label="Далее (с выбранными)", style=disnake.ButtonStyle.green, custom_id="next_step")
    async def next_step(self, btn, inter):
        if not self.selected_users: 
            return await inter.response.send_message(
                "Вы не выбрали участников!", 
                ephemeral=True
            )
        await inter.response.send_modal(
            ReportModal(self.r_type, self.author_name, self.selected_users, self.extra_fields)
        )

    async def skip_callback(self, inter: disnake.MessageInteraction):
        await inter.response.send_modal(
            ReportModal(self.r_type, self.author_name, [], self.extra_fields)
        )

# --- МЕНЮ-КНОПКИ ДЛЯ РАЗНЫХ КАТЕГОРИЙ ---

class ArrestTypeView(ui.View):
    def __init__(self, author_name):
        super().__init__(timeout=300)
        self.author_name = author_name

    @ui.button(label="СКТ", style=disnake.ButtonStyle.danger)
    async def btn_skt(self, btn, inter): 
        await inter.response.send_modal(
            ReportModal("СКТ", self.author_name, extra_fields={"⚖️ Тип": "СКТ"})
        )
        
    @ui.button(label="Задержание", style=disnake.ButtonStyle.primary)
    async def btn_arr(self, btn, inter): 
        await inter.response.send_modal(
            ReportModal("Задержание", self.author_name, extra_fields={"⚖️ Тип": "Задержание"})
        )
        
    @ui.button(label="Предупреждение", style=disnake.ButtonStyle.secondary)
    async def btn_warn(self, btn, inter): 
        await inter.response.send_modal(
            ReportModal("Предупреждение", self.author_name, extra_fields={"⚖️ Тип": "Предупреждение"})
        )

class CommanderSelectView(ui.View):
    def __init__(self, r_type, author_name):
        super().__init__(timeout=300)
        self.r_type = r_type
        self.author_name = author_name

    @ui.button(label="Я командовал (Да)", style=disnake.ButtonStyle.green)
    async def btn_yes(self, btn, inter):
        await inter.response.send_message(
            "Выберите участников ниже:", 
            view=ParticipantSelectView(
                self.r_type, 
                self.author_name, 
                {"🎖️ Командир": "Да"}
            ), 
            ephemeral=True
        )

    @ui.button(label="Только участвовал (Нет)", style=disnake.ButtonStyle.grey)
    async def btn_no(self, btn, inter):
        await inter.response.send_message(
            "Выберите участников ниже:", 
            view=ParticipantSelectView(
                self.r_type, 
                self.author_name, 
                {"🎖️ Командир": "Нет"}
            ), 
            ephemeral=True
        )

class TrainingTypeView(ui.View):
    def __init__(self, author_name):
        super().__init__(timeout=300)
        self.author_name = author_name

    @ui.button(label="Обычная", style=disnake.ButtonStyle.primary)
    async def btn_norm(self, btn, inter): 
        await self.next_step(inter, "Обычная")
        
    @ui.button(label="Специальная", style=disnake.ButtonStyle.primary)
    async def btn_spec(self, btn, inter): 
        await self.next_step(inter, "Специальная")
        
    @ui.button(label="По методичке", style=disnake.ButtonStyle.primary)
    async def btn_met(self, btn, inter): 
        await self.next_step(inter, "По методичке")

    async def next_step(self, inter, tr_type):
        full_r_type = f"Тренировка ({tr_type})"
        await inter.response.send_message(
            f"Вы оформляете: **{full_r_type}**\nВыберите участников ниже.", 
            view=ParticipantSelectView(
                full_r_type, 
                self.author_name, 
                {"⚙️ Тип тренировки": tr_type}
            ), 
            ephemeral=True
        )

class SubCategoryView(ui.View):
    def __init__(self, base_type, author_name):
        super().__init__(timeout=300)
        self.base_type = base_type
        self.author_name = author_name

    @ui.button(label="Рядовой", style=disnake.ButtonStyle.primary)
    async def btn_ryad(self, btn, inter): 
        await self.next_step(inter, "Рядовой состав")
        
    @ui.button(label="Сержантский", style=disnake.ButtonStyle.primary)
    async def btn_serg(self, btn, inter): 
        await self.next_step(inter, "Сержантский состав")
        
    @ui.button(label="Мл. Офицерский", style=disnake.ButtonStyle.primary)
    async def btn_jro(self, btn, inter): 
        await self.next_step(inter, "Мл. офицерский состав")
        
    @ui.button(label="Ст. Офицерский", style=disnake.ButtonStyle.primary)
    async def btn_sro(self, btn, inter): 
        await self.next_step(inter, "Ст. офицерский состав")

    async def next_step(self, inter, subcat):
        full_r_type = f"{self.base_type} ({subcat})"
        await inter.response.send_message(
            f"Вы оформляете: **{full_r_type}**\nВыберите участников ниже.", 
            view=ParticipantSelectView(full_r_type, self.author_name), 
            ephemeral=True
        )

class MainView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        opts = [disnake.SelectOption(label=k, value=k) for k in MAIN_MENU_OPTIONS]
        self.add_item(
            ui.Select(
                options=opts, 
                placeholder="Выберите тип рапорта", 
                custom_id="sel_v9"
            )
        )
        
    async def interaction_check(self, inter):
        if inter.data.custom_id == "sel_v9":
            r_type = inter.values[0]
            if r_type == "Нарушение (СКТ/Задержание)":
                await inter.response.send_message(
                    "Укажите тип нарушения:", 
                    view=ArrestTypeView(inter.author.display_name), 
                    ephemeral=True
                )
            elif r_type == "План/Методичка":
                await inter.response.send_modal(
                    ReportModal("План/Методичка", inter.author.display_name)
                )
            elif r_type in ["Боевой вылет", "Защита объекта"]:
                await inter.response.send_message(
                    f"Оформление: **{r_type}**. Выберите вашу роль:", 
                    view=CommanderSelectView(r_type, inter.author.display_name), 
                    ephemeral=True
                )
            elif r_type == "Тренировка":
                await inter.response.send_message(
                    "Укажите тип тренировки:", 
                    view=TrainingTypeView(inter.author.display_name), 
                    ephemeral=True
                )
            elif r_type in ["Аттестация", "Обучение"]:
                await inter.response.send_message(
                    f"Укажите состав для категории **{r_type}**:", 
                    view=SubCategoryView(r_type, inter.author.display_name), 
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    f"Вы оформляете: **{r_type}**\nВыберите участников ниже, либо нажмите 'Пропустить'.", 
                    view=ParticipantSelectView(r_type, inter.author.display_name), 
                    ephemeral=True
                )
        return False

# ==========================================
# ПАНЕЛЬ УПРАВЛЕНИЯ (!manage)
# ==========================================

class AdminManageView(ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        
    @ui.button(label="Баллы (+/-)", style=disnake.ButtonStyle.grey, custom_id="adm_pts_v9")
    async def pts(self, btn, inter):
        if not inter.author.guild_permissions.administrator: 
            return
        await inter.response.send_modal(ui.Modal(title="Правка баллов", custom_id="m_pts_v9", components=[
            ui.TextInput(label="ID Бойца", custom_id="mid"),
            ui.TextInput(label="Сумма (напр: +10 или -5)", custom_id="act")
        ]))
        
    @ui.button(label="Звание (Force)", style=disnake.ButtonStyle.grey, custom_id="adm_rnk_v9")
    async def rnk(self, btn, inter):
        if not inter.author.guild_permissions.administrator: 
            return
        await inter.response.send_modal(ui.Modal(title="Смена звания", custom_id="m_rank_v9", components=[
            ui.TextInput(label="ID Бойца", custom_id="mid"),
            ui.TextInput(label="Код звания (напр: SGT)", custom_id="rnk")
        ]))

@bot.event
async def on_modal_submit(inter):
    if inter.custom_id == "m_pts_v9":
        await inter.response.defer(ephemeral=True)
        rp_id = inter.text_values['mid']
        act = inter.text_values['act']
        val = int(act.replace("+","").replace("-",""))
        
        async with aiosqlite.connect("army_base.db") as db:
            db.row_factory = aiosqlite.Row
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (rp_id,))
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur:
                stats = dict(await cur.fetchone())
                old_p = stats.get("points", 0)
                r = stats.get("rank", "PVT")
                
            if "-" in act: 
                await db.execute(
                    "UPDATE soldiers SET points = MAX(0, points - ?) WHERE user_id = ?", 
                    (val, rp_id)
                )
            else: 
                await db.execute(
                    "UPDATE soldiers SET points = points + ? WHERE user_id = ?", 
                    (val, rp_id)
                )
            
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur: 
                new_stats = dict(await cur.fetchone())
                tp = new_stats["points"]
            await db.commit()
            
        await sync_dossier(
            rp_id, f"ID: {rp_id}", "АДМИН-ПРАВКА", act, 
            new_stats, inter.message.jump_url, officer=inter.author.display_name
        )
        
        tgt, nxt = get_target_points(r)
        
        if "-" not in act and r != "MAJ" and check_promotion_criteria(r, new_stats, tgt):
            await send_promo_request(rp_id, r, nxt, tp, f"ID: {rp_id}")
            
        await inter.edit_original_response(content=f"✅ Готово. Текущие баллы: {tp}")
        
    if inter.custom_id == "m_rank_v9":
        await inter.response.defer(ephemeral=True)
        rp_id = inter.text_values['mid']
        rnk = inter.text_values['rnk'].upper()
        
        async with aiosqlite.connect("army_base.db") as db:
            db.row_factory = aiosqlite.Row
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (rp_id,))
            async with db.execute("SELECT rank FROM soldiers WHERE user_id = ?", (rp_id,)) as c: 
                old_r = (await c.fetchone())["rank"]
            
            await db.execute("UPDATE soldiers SET rank = ?, points = 0 WHERE user_id = ?", (rnk, rp_id))
            await db.commit()
            
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur:
                new_stats = dict(await cur.fetchone())
            
        idx_old = next((i for i, r in enumerate(RANKS) if r[1] == old_r), 99)
        idx_new = next((i for i, r in enumerate(RANKS) if r[1] == rnk), 99)
        is_promo = idx_new < idx_old 
        
        await update_member_nickname(inter.guild, rp_id, rnk)
        await sync_dossier(
            rp_id, f"ID: {rp_id}", "ПОВЫШЕНИЕ" if is_promo else "ПОНИЖЕНИЕ", 
            0, new_stats, inter.message.jump_url, officer=inter.author.display_name
        )
        
        pl = bot.get_channel(PROMO_LOG_CHANNEL_ID)
        if pl:
            if is_promo: 
                msg = f"🎊 **ПРИКАЗ (ПОВЫШЕНИЕ):** Боец **ID: {rp_id}** назначен на звание **{rnk}**! "
                msg += f"(Утвердил: {inter.author.display_name})"
                await pl.send(msg)
            else: 
                msg = f"⚠️ **ПРИКАЗ (ПОНИЖЕНИЕ):** Боец **ID: {rp_id}** разжалован до звания **{rnk}**. "
                msg += f"(Утвердил: {inter.author.display_name})"
                await pl.send(msg)
            
        await inter.edit_original_response(content=f"✅ **ID: {rp_id}** переведен в {rnk}")

# ==========================================
# ЗАПУСК БОТА
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send(embed=disnake.Embed(title="🏛️ ТЕРМИНАЛ CG", color=disnake.Color.red()), view=MainView())

@bot.command()
@commands.has_permissions(administrator=True)
async def manage(ctx):
    await ctx.send(embed=disnake.Embed(title="🕹️ ПАНЕЛЬ УПРАВЛЕНИЯ", color=disnake.Color.blue()), view=AdminManageView())

@bot.command(aliases=["профиль", "статистика", "stats"])
async def profile(ctx, member: disnake.Member = None):
    target = member or ctx.author
    rp_id = extract_rp_id(target.display_name)
    
    if rp_id == "0000":
        return await ctx.send(f"❌ Не удалось определить RP ID у пользователя {target.mention}.")
        
    async with aiosqlite.connect("army_base.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur:
            row = await cur.fetchone()
            
    if not row:
        return await ctx.send(f"📭 В базе данных нет информации о бойце **ID: {rp_id}**.")
        
    stats = dict(row)
    rank, total_p = stats['rank'], stats['points']
    target_points, nxt = get_target_points(rank)
    p_to = target_points - total_p
    
    desc_lines = [
        f"**Боец:** {target.mention}",
        f"**ID:** `{rp_id}` | **Звание:** `{rank}`",
        f"**Баллы:** `{total_p}`",
        f"**Прогресс:** {get_progress_bar(total_p, target_points)} ({p_to} до {nxt})\n",
        f"**📋 Требования для повышения:**\n{get_criteria_text(rank, stats)}"
    ]
    
    embed = disnake.Embed(
        title="🪪 Военный билет", 
        description="\n".join(desc_lines), 
        color=disnake.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx):
    try:
        await ctx.author.send(
            "📦 Резервная копия базы данных:", 
            file=disnake.File("army_base.db")
        )
        await ctx.send("✅ Бэкап базы данных успешно отправлен вам в ЛС!")
    except disnake.Forbidden:
        await ctx.send("❌ У вас закрыты личные сообщения, я не могу отправить файл.")

@bot.event
async def on_ready():
    await init_db()
    bot.add_view(MainView())
    bot.add_view(OfficerButtons())
    bot.add_view(AdminManageView())
    print(f"Система активна: {bot.user}")

bot.run(TOKEN)