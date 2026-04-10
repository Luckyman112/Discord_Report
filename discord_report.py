import disnake
from disnake.ext import commands
from disnake import ui
import datetime
import re
import aiosqlite

# ==========================================
# НАСТРОЙКИ (ВСТАВЬ СВОИ ID)
# ==========================================
TOKEN = "" 
LOG_CHANNEL_ID = 1491612522749497354      # Канал проверки (Штаб)
FORUM_ARCHIVE_ID = 1491631113670758570    # Канал-Форум (Личные дела)

# Каналы для полных логов (дубликаты со скринами)
CHANNELS_MAP = {
    "СКТ/Расстрел": 1492267166001533101,   
    "Патрулирование": 123456789, 
    "Тренировка": 1491627496385548419,     
    "Боевой вылет": 123456789,   
    "Защита объекта": 123456789   
}

# Расценки: (Баллы проводящему / Баллы участнику)
PRICES_COMPLEX = {
    "СКТ/Расстрел": (2, 0), 
    "Патрулирование": (1, 1), 
    "Тренировка": (5, 3), 
    "Обучение": (5, 3), 
    "Боевой вылет": (10, 5), 
    "Защита объекта": (7, 4)
}

# Пороги званий
RANKS = [
    (100, "MAJ"), (90, "HCP"), (80, "CPT"), (60, "GLT"), (50, "HLT"),
    (40, "LT"), (30, "CWO"), (25, "WO2"), (20, "WO1"), (14, "GSG"),
    (12, "MSG"), (10, "SGT"), (5, "CPL"), (3, "PFC"), (0, "PVT")
]

intents = disnake.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# СИСТЕМНЫЕ ФУНКЦИИ
# ==========================================

async def init_db():
    async with aiosqlite.connect("army_base.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS soldiers (
                user_id TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0,
                rank TEXT DEFAULT 'PVT'
            )
        """)
        await db.commit()

def get_progress_bar(current, total):
    if total <= 0: return "`[MAX]`"
    percentage = min(current / total, 1.0)
    length = 10
    filled = int(length * percentage)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` {int(percentage * 100)}%"

# ==========================================
# ЛОГИКА ФОРУМА И ПОВЫШЕНИЙ
# ==========================================

async def sync_dossier(m_id, author_info, r_type, reward, total_p, rank, jump_url, status="approved"):
    forum = await bot.fetch_channel(FORUM_ARCHIVE_ID)
    thread = next((t for t in forum.threads if f"ID: {m_id}" in t.name), None)
    
    nxt = "MAX"; p_to = 0; target_points = 0
    for i in range(len(RANKS)-1):
        if RANKS[i+1][1] == rank:
            nxt, target_points = RANKS[i][1], RANKS[i][0]
            p_to = target_points - total_p
            break
    
    bar = get_progress_bar(total_p, target_points)
    prog_text = f"До {nxt}: {p_to} б.\n{bar}" if p_to > 0 else "⚡ **Готов к повышению!**"
    desc = f"**Боец:** {author_info}\n**Звание:** `{rank}`\n**Баллы:** `{total_p}`\n**Прогресс:**\n{prog_text}"

    if not thread:
        thread_data = await forum.create_thread(name=f"ID: {m_id} | {author_info}", 
                                                embed=disnake.Embed(title=f"🗃️ ЛИЧНОЕ ДЕЛО", description=desc, color=disnake.Color.blue()))
        thread = thread_data.thread
    else:
        async for msg in thread.history(oldest_first=True, limit=1):
            if msg.embeds:
                e = msg.embeds[0]; e.description = desc
                await msg.edit(embed=e)

    log_color = disnake.Color.green() if status == "approved" else disnake.Color.red()
    log_label = "✅ Одобрено" if status == "approved" else "❌ Отклонено"
    
    log_embed = disnake.Embed(
        title=f"📑 {r_type}", 
        description=f"Статус: **{log_label}**\nНачислено: `+{reward}` б.\n🔗 [ПОЛНЫЙ ОТЧЕТ]({jump_url})", 
        color=log_color
    )
    await thread.send(embed=log_embed)
    return p_to <= 0, nxt

class PromotionView(ui.View):
    def __init__(self, m_id, author_info, new_rank):
        super().__init__(timeout=None)
        self.m_id, self.author_info, self.new_rank = m_id, author_info, new_rank

    @ui.button(label="Утвердить повышение", style=disnake.ButtonStyle.green, custom_id="btn_promo_confirm")
    async def approve(self, button: ui.Button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator: return
        async with aiosqlite.connect("army_base.db") as db:
            # СБРОС БАЛЛОВ ПРИ ПОВЫШЕНИИ
            await db.execute("UPDATE soldiers SET rank = ?, points = 0 WHERE user_id = ?", (self.new_rank, self.m_id))
            await db.commit()
        await sync_dossier(self.m_id, self.author_info, "ПОВЫШЕНИЕ", 0, 0, self.new_rank, inter.message.jump_url)
        await inter.response.edit_message(content=f"🎊 **{self.author_info}** повышен до **{self.new_rank}**. Баллы сброшены.", embed=None, view=None)

# ==========================================
# ОБРАБОТКА РАПОРТОВ
# ==========================================

class OfficerButtons(ui.View):
    def __init__(self): super().__init__(timeout=None)

    async def process(self, inter, status):
        embed = inter.message.embeds[0]
        r_type = embed.title.replace("📥 РАПОРТ: ", "")
        rew_author, rew_member = PRICES_COMPLEX.get(r_type, (1, 0))
        if status != "approved": rew_author = rew_member = 0
        
        # Данные автора и участников
        auth_f = next((f.value for f in embed.fields if "Подал" in f.name), "")
        author_id = re.search(r'\d{4,}', auth_f).group() if re.search(r'\d{4,}', auth_f) else str(inter.author.id)
        
        # Парсинг участников
        members_text = ""
        for field in embed.fields:
            if "Детали" in field.name or "Состав" in field.name: members_text = field.value
        member_ids = [m for m in re.findall(r'\d{4,}', members_text) if m != author_id]

        # Дублирование и Реакции
        jump_url = "https://discord.com"
        target_cid = CHANNELS_MAP.get(r_type)
        if target_cid:
            target_chan = bot.get_channel(target_cid)
            if target_chan:
                log_msg = await target_chan.send(embed=embed)
                await log_msg.add_reaction("✅" if status == "approved" else "❌")
                jump_url = log_msg.jump_url

        async with aiosqlite.connect("army_base.db") as db:
            # Автор
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (author_id,))
            if status == "approved":
                await db.execute("UPDATE soldiers SET points = points + ? WHERE user_id = ?", (rew_author, author_id))
            async with db.execute("SELECT points, rank FROM soldiers WHERE user_id = ?", (author_id,)) as cur:
                total_p, current_r = await cur.fetchone()
            
            # Участники (массовое начисление)
            if status == "approved" and rew_member > 0:
                for mid in member_ids:
                    await db.execute("INSERT OR IGNORE INTO soldiers (user_id) VALUES (?)", (mid,))
                    await db.execute("UPDATE soldiers SET points = points + ? WHERE user_id = ?", (rew_member, mid))
            await db.commit()

        # Форум (только для автора)
        is_ready, nxt_r = await sync_dossier(author_id, auth_f.replace("```",""), r_type, rew_author, total_p, current_r, jump_url, status)

        if is_ready and current_r != "MAJ" and status == "approved":
            p_embed = disnake.Embed(title="📈 ЗАПРОС ПОВЫШЕНИЯ", color=disnake.Color.gold(),
                                     description=f"Боец: {auth_f}\nЗвание: {current_r} -> **{nxt_r}**\nБаллы: **{total_p}**")
            await bot.get_channel(LOG_CHANNEL_ID).send(embed=p_embed, view=PromotionView(author_id, auth_f.replace("```",""), nxt_r))

        res_color = disnake.Color.green() if status == "approved" else disnake.Color.red()
        await inter.response.edit_message(embed=disnake.Embed(title=f"Вердикт: {status.upper()}", 
            description=f"Начислено: Автору +{rew_author}, Участникам ({len(member_ids)} чел.) +{rew_member}", color=res_color), view=None)

    @ui.button(label="Одобрить", style=disnake.ButtonStyle.green, custom_id="btn_app_final")
    async def approve(self, button: ui.Button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator: return
        await self.process(inter, "approved")

    @ui.button(label="Отклонить", style=disnake.ButtonStyle.red, custom_id="btn_deny_final")
    async def deny(self, button: ui.Button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator: return
        await self.process(inter, "denied")

# ==========================================
# ИНТЕРФЕЙС ПОДАЧИ
# ==========================================

class BaseModal(ui.Modal):
    def __init__(self, title, r_type, fields):
        self.r_type = r_type
        comps = [ui.TextInput(label=f[0], placeholder=f[1], custom_id=f[2], 
                 style=disnake.TextInputStyle.short if f[3]==1 else disnake.TextInputStyle.paragraph) for f in fields]
        super().__init__(title=title, components=comps)

    async def callback(self, inter: disnake.ModalInteraction):
        embed = disnake.Embed(title=f"📥 РАПОРТ: {self.r_type}", color=disnake.Color.red(), timestamp=datetime.datetime.now())
        for k, v in inter.text_values.items():
            if k == "image": continue
            embed.add_field(name="👤 Подал" if k == "author" else "📝 Детали / Состав", value=f"```\n{v}\n```", inline=False)
        if inter.text_values.get("image"): embed.set_image(url=inter.text_values["image"])
        
        msg = await bot.get_channel(LOG_CHANNEL_ID).send(embed=embed, view=OfficerButtons())
        await msg.create_thread(name=f"Разбор: {self.r_type}")
        await inter.response.send_message("✅ Отправлено в штаб!", ephemeral=True)

class ReportSelect(ui.Select):
    def __init__(self):
        opts = [disnake.SelectOption(label=k, value=k) for k in PRICES_COMPLEX.keys()]
        super().__init__(placeholder="Выберите категорию", options=opts, custom_id="sel_v_fin")

    async def callback(self, inter: disnake.MessageInteraction):
        v = self.values[0]
        f = [["ID и Ник", "Lucky | 2955", "author", 1], ["Состав и Описание", "ID участников через запятую и детали...", "desc", 2], ["Скриншот", "Ссылка", "image", 1]]
        await inter.response.send_modal(BaseModal(v, v, f))

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send(embed=disnake.Embed(title="🏛️ ТЕРМИНАЛ КОРУСАНТСКОЙ ГВАРДИИ", color=disnake.Color.red()), 
                   view=ui.View(timeout=None).add_item(ReportSelect()))

@bot.event
async def on_ready():
    await init_db()
    bot.add_view(OfficerButtons())
    print(f"Система активна: {bot.user}")

bot.run(TOKEN)