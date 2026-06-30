import disnake
from disnake.ext import commands
from disnake import ui
import datetime
import aiosqlite

import config
import utils
from database import sheet, apply_row_style

PROCESSING_MESSAGES = set()

class PromotionView(ui.View):
    def __init__(self, rp_id: str, author_info: str, new_rank: str):
        super().__init__(timeout=None)
        self.rp_id = rp_id
        self.author_info = author_info
        self.new_rank = new_rank

    @ui.button(label="Утвердить", style=disnake.ButtonStyle.green, custom_id="conf_v9")
    async def approve(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not isinstance(inter.author, disnake.Member) or not utils.is_deputy(inter.author): 
            return await inter.response.send_message("❌ У вас нет прав для утверждения повышений.", ephemeral=True)
        
        await inter.response.edit_message(content="⏳ Приказ обрабатывается...", view=None)
        
        reset_sql = ", ".join([f"{col} = 0" for col in config.METRIC_COLUMNS])
        today_str = datetime.date.today().isoformat()
        
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if self.new_rank in ["SGT", "JLT", "MAJ"]: 
                await db.execute(f"UPDATE soldiers SET rank = ?, points = 0, join_date = ?, {reset_sql} WHERE user_id = ?", (self.new_rank, today_str, self.rp_id))
            else: 
                await db.execute(f"UPDATE soldiers SET rank = ?, points = 0, {reset_sql} WHERE user_id = ?", (self.new_rank, self.rp_id))
            await db.commit()
            
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (self.rp_id,)) as cur:
                row = await cur.fetchone()
                new_stats = dict(row) if row else {}
        
        if sheet:
            try:
                cell = sheet.find(str(self.rp_id), in_column=2)
                if cell:
                    today_ru = datetime.date.today().strftime('%d.%m.%Y')
                    sheet.update_cell(cell.row, 3, self.new_rank)
                    if self.new_rank in config.BASE_COMP_RANKS:
                        sheet.update_cell(cell.row, 6, today_ru)
                    apply_row_style(cell.row, self.new_rank)
            except Exception as e:
                print(f"Ошибка Гугла при повышении: {e}")

        if inter.guild: 
            target_member = inter.message.mentions[0] if inter.message.mentions else inter.author
            if isinstance(target_member, disnake.Member):
                await utils.update_member_nickname(inter.guild, self.rp_id, self.new_rank, member=target_member)
            
        await utils.sync_dossier(inter.bot, self.rp_id, self.author_info, "ПОВЫШЕНИЕ (Критерии обнулены)", 0, new_stats, inter.message.jump_url, officer=inter.author.display_name)
        
        pl = inter.bot.get_channel(config.PROMO_LOG_CHANNEL_ID)
        if isinstance(pl, disnake.TextChannel): 
            await pl.send(f"🎊 **ПРИКАЗ:** {self.author_info} повышен до **{self.new_rank}**! (Утвердил: {inter.author.display_name})")
            
        if inter.message and inter.message.embeds: 
            e = disnake.Embed(title="✅ Повышение утверждено", color=disnake.Color.green())
            e.set_footer(text=f"Утвердил: {inter.author.display_name}")
            await inter.edit_original_response(content="", embed=e, view=None)


class ManualPointsModal(ui.Modal):
    def __init__(self, view, inter_orig, override_cat=None):
        self.view = view
        self.inter_orig = inter_orig
        self.override_cat = override_cat
        super().__init__(title="Назначение баллов", components=[
            ui.TextInput(label="Баллы Автору", placeholder="5", custom_id="pts_a"),
            ui.TextInput(label="Баллы Участникам", placeholder="2", custom_id="pts_m", required=False)
        ])

    async def callback(self, inter: disnake.ModalInteraction):
        msg_id = self.inter_orig.message.id if self.inter_orig.message else None
        if msg_id and msg_id in PROCESSING_MESSAGES: 
            return await inter.response.send_message("⏳ Рапорт обрабатывается...", ephemeral=True)
            
        if msg_id: PROCESSING_MESSAGES.add(msg_id)
        try:
            await inter.response.defer(ephemeral=True)
            await self.inter_orig.edit_original_response(content="⏳ Выдача баллов...", view=None)
            pts_a = int(inter.text_values.get("pts_a", "0") or 0)
            pts_m = int(inter.text_values.get("pts_m", "0") or 0)
            await self.view.process(self.inter_orig, "approved", manual_pts=(pts_a, pts_m), override_category=self.override_cat)
            await inter.edit_original_response(content=f"✅ Начислено (Категория: {self.override_cat or 'Другое'})")
        finally:
            if msg_id: PROCESSING_MESSAGES.discard(msg_id)


class OtherCategoryRouteView(ui.View):
    def __init__(self, officer_view, inter_orig):
        super().__init__(timeout=300)
        self.officer_view = officer_view
        self.inter_orig = inter_orig
        
        options = [disnake.SelectOption(label=c, value=c) for c in config.MAIN_MENU_OPTIONS if c != "Нарушение (СКТ/Задержание)"]
        options.append(disnake.SelectOption(label="СКТ / Задержание", value="Задержание"))
        
        self.add_item(ui.Select(options=options, placeholder="Куда распределить?", custom_id="route_sel"))

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.data.custom_id == "route_sel": 
            await inter.response.send_modal(ManualPointsModal(self.officer_view, self.inter_orig, str(inter.values[0]) if inter.values else "Другое"))
        return False


class OfficerButtons(ui.View):
    def __init__(self): 
        super().__init__(timeout=None)

    @ui.button(label="Одобрить", style=disnake.ButtonStyle.green, custom_id="app_v9")
    async def approve(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not isinstance(inter.author, disnake.Member) or not utils.is_officer(inter.author): 
            return await inter.response.send_message("❌ У вас нет прав.", ephemeral=True)
            
        if inter.message.embeds and inter.message.embeds[0].title and "Другое" in inter.message.embeds[0].title: 
            await inter.response.send_message("Выберите категорию:", view=OtherCategoryRouteView(self, inter), ephemeral=True)
        else:
            msg_id = inter.message.id
            if msg_id in PROCESSING_MESSAGES: 
                return await inter.response.send_message("⏳ Обрабатывается...", ephemeral=True)
            PROCESSING_MESSAGES.add(msg_id)
            try:
                await inter.response.edit_message(content="⏳ Обработка рапорта...", view=None)
                await self.process(inter, "approved")
            finally: 
                PROCESSING_MESSAGES.discard(msg_id)

    @ui.button(label="Отклонить", style=disnake.ButtonStyle.red, custom_id="deny_v9")
    async def deny(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not isinstance(inter.author, disnake.Member) or not utils.is_officer(inter.author): 
            return await inter.response.send_message("❌ У вас нет прав.", ephemeral=True)
            
        msg_id = inter.message.id
        if msg_id in PROCESSING_MESSAGES: 
            return await inter.response.send_message("⏳ Обрабатывается...", ephemeral=True)
        PROCESSING_MESSAGES.add(msg_id)
        try:
            await inter.response.edit_message(content="⏳ Отклонение рапорта...", view=None)
            await self.process(inter, "denied")
        finally: 
            PROCESSING_MESSAGES.discard(msg_id)

    async def process(self, inter: disnake.MessageInteraction, status: str, manual_pts=None, override_category=None):
        if not inter.message or not inter.message.embeds: return
        embed = inter.message.embeds[0]
        
        full_r_type = override_category if override_category else str(embed.title).replace("📥 РАПОРТ: ", "")
        base_r_type = full_r_type.split(" (")[0]
        subcat = full_r_type.split("(")[1].replace(")", "").strip().lower() if "(" in full_r_type else ""
        
        if base_r_type == "Тренировка" and not manual_pts:
            if "специальная" in subcat: rew_a, rew_m = 6, 4
            elif "методичк" in subcat: rew_a, rew_m = 8, 5
            else: rew_a, rew_m = 4, 3
        else: 
            rew_a, rew_m = manual_pts if manual_pts else config.PRICES_COMPLEX.get(base_r_type, (1, 0))
            
        if status != "approved": 
            rew_a = rew_m = 0
        
        auth_f = utils.get_field_val(embed, "Подал", "")
        author_rp_id = utils.extract_rp_id(auth_f)
        participants_list = [p.strip() for p in utils.get_field_val(embed, "Участники", "").split('\n') if p.strip()]
        is_cmd = utils.get_field_val(embed, "Командир", "").lower()

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
            auth_col = "flights_commanded" if ("да" in is_cmd or "+" in is_cmd) else "combat_or_def_done"
        elif base_r_type == "Тренировка":
            part_col = "trainings_passed"
            if "специальная" in subcat: auth_col = "spec_trainings_conducted"
            elif "методичк" in subcat: auth_col = "method_trainings_conducted"
            else: auth_col = "trainings_conducted"
        elif base_r_type == "Боевой вылет":
            part_col = "combat_or_def_done"
            auth_col = "flights_commanded" if ("да" in is_cmd or "+" in is_cmd) else "combat_or_def_done"

        results, today_str = {}, datetime.date.today().isoformat()
        
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id, join_date) VALUES (?, ?)", (author_rp_id, today_str))
            
            if status == "approved": 
                await db.execute("UPDATE soldiers SET points = points + ? WHERE user_id = ?", (rew_a, author_rp_id))
                if auth_col: 
                    await db.execute(f"UPDATE soldiers SET {auth_col} = {auth_col} + 1 WHERE user_id = ?", (author_rp_id,))
                    
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (author_rp_id,)) as c: 
                row = await c.fetchone()
                results[author_rp_id] = {"stats": dict(row) if row else {}, "reward": rew_a, "info": auth_f}

            for part_info in participants_list:
                p_id = utils.extract_rp_id(part_info)
                if p_id == author_rp_id or not p_id.isdigit(): continue 
                
                await db.execute("INSERT OR IGNORE INTO soldiers (user_id, join_date) VALUES (?, ?)", (p_id, today_str))
                
                if status == "approved": 
                    await db.execute("UPDATE soldiers SET points = points + ? WHERE user_id = ?", (rew_m, p_id))
                    if part_col: 
                        await db.execute(f"UPDATE soldiers SET {part_col} = {part_col} + 1 WHERE user_id = ?", (p_id,))
                        
                async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (p_id,)) as c: 
                    row = await c.fetchone()
                    results[p_id] = {"stats": dict(row) if row else {}, "reward": rew_m, "info": part_info}
            await db.commit()

        jump_url = inter.message.jump_url
        target_cid = config.CHANNELS_MAP.get(base_r_type) or config.CHANNELS_MAP.get("Другое")
        
        if target_cid:
            chan = inter.bot.get_channel(target_cid)
            if isinstance(chan, disnake.TextChannel):
                log_msg = await chan.send(embed=embed)
                await log_msg.add_reaction("✅" if status=="approved" else "❌")
                jump_url = log_msg.jump_url

        # Логируем нарушителей в отдельный форум (без занесения в нашу БД)
        if base_r_type in ["СКТ", "Задержание", "Предупреждение"] and status == "approved": 
            await utils.sync_offender(inter.bot, embed, jump_url, status, inter.author.display_name)

        for p_id, data in results.items():
            await utils.sync_dossier(inter.bot, p_id, data["info"], full_r_type, data["reward"], data["stats"], jump_url, status, inter.author.display_name)
            rank_s = data["stats"].get('rank', 'PVT')
            
            if status == "approved" and rank_s != "MAJ":
                tgt_pts = utils.get_target_points(rank_s)[0]
                if utils.check_promotion_criteria(rank_s, data["stats"], tgt_pts):
                    await utils.send_promo_request(inter.bot, p_id, rank_s, utils.get_target_points(rank_s)[1], data["stats"].get('points', 0), data["info"], PromotionView)

        e_verdict = disnake.Embed(title=f"Вердикт: {status.upper()}", color=disnake.Color.green() if status=="approved" else disnake.Color.red())
        e_verdict.set_footer(text=f"Проверил офицер: {inter.author.display_name}")
        await inter.edit_original_response(content="", embed=e_verdict, view=None)


class ReportModal(ui.Modal):
    def __init__(self, r_type: str, author_name: str, selected_users=None, extra_fields=None):
        self.r_type = r_type
        self.author_name = author_name
        self.selected_users = selected_users or []
        self.extra_fields = extra_fields or {}
        
        base_type = r_type.split(" (")[0]
        components = []
        
        if base_type == "План/Методичка": 
            components = [
                ui.TextInput(label="Тема", custom_id="topic", max_length=100), 
                ui.TextInput(label="Ссылка на Google Doc", custom_id="evidence", style=disnake.TextInputStyle.paragraph)
            ]
        elif base_type in ["СКТ", "Предупреждение", "Задержание"]:
            components = [
                ui.TextInput(label="Нарушитель (IDN | RANK | NICK)", custom_id="offender_info", max_length=100, placeholder="Строго в формате: 1122 | SGT | Kuz"), 
                ui.TextInput(label="Формирование", custom_id="unit", max_length=50)
            ]
            if base_type == "СКТ": 
                components.append(ui.TextInput(label="Вид наказания", custom_id="punishment", max_length=100))
            elif base_type == "Задержание": 
                components.append(ui.TextInput(label="Сколько сроков?", custom_id="punishment", max_length=100))
            components += [
                ui.TextInput(label="Причина", custom_id="reason", style=disnake.TextInputStyle.paragraph), 
                ui.TextInput(label="Доказательства", custom_id="evidence", style=disnake.TextInputStyle.paragraph)
            ]
        elif base_type == "Пост/Патруль": 
            components = [
                ui.TextInput(label="Маршрут/пост", custom_id="route", max_length=100), 
                ui.TextInput(label="Время (мин)", custom_id="time", max_length=50), 
                ui.TextInput(label="Инциденты", custom_id="incidents", style=disnake.TextInputStyle.paragraph, required=False), 
                ui.TextInput(label="Доказательства", custom_id="evidence", style=disnake.TextInputStyle.paragraph)
            ]
        elif base_type == "Тренировка":
            components = [ui.TextInput(label="Описание", custom_id="desc", style=disnake.TextInputStyle.paragraph)]
            if self.extra_fields.get("⚙️ Тип тренировки") == "По методичке": 
                components.append(ui.TextInput(label="Ссылка на методичку", custom_id="method_link"))
            components.append(ui.TextInput(label="Доказательства", custom_id="evidence", style=disnake.TextInputStyle.paragraph))
        else: 
            components = [
                ui.TextInput(label="Описание", custom_id="desc", style=disnake.TextInputStyle.paragraph), 
                ui.TextInput(label="Доказательства", custom_id="evidence", style=disnake.TextInputStyle.paragraph)
            ]
            
        super().__init__(title="Рапорт", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        e = disnake.Embed(title=f"📥 РАПОРТ: {self.r_type}", color=disnake.Color.red(), timestamp=datetime.datetime.now())
        e.add_field(name="👤 Подал", value=f"```\n{self.author_name}\n```", inline=False)
        tv = inter.text_values
        
        if 'offender_info' in tv: e.add_field(name="🚨 Нарушитель", value=f"```\n{tv['offender_info']}\n```", inline=False)
        if 'unit' in tv: e.add_field(name="🔰 Формирование", value=f"```\n{tv['unit']}\n```", inline=True)
        for k, v in self.extra_fields.items(): e.add_field(name=k, value=f"```\n{v}\n```", inline=True)
        if 'punishment' in tv: e.add_field(name="⏳ Наказание/Сроки", value=f"```\n{tv['punishment']}\n```", inline=True)
        if 'reason' in tv: e.add_field(name="📋 Причина", value=f"```\n{tv['reason']}\n```", inline=False)
        
        if self.selected_users:
            p_text = "\n".join([u.display_name for u in self.selected_users])
            e.add_field(name="👥 Участники", value=f"```\n{p_text}\n```", inline=False)
            
        if 'topic' in tv: e.add_field(name="📚 Тема", value=f"```\n{tv['topic']}\n```", inline=False)
        if 'route' in tv: e.add_field(name="📍 Маршрут/Пост", value=f"```\n{tv['route']}\n```", inline=True)
        if 'time' in tv: e.add_field(name="⏱️ Время (мин)", value=f"```\n{tv['time']}\n```", inline=True)
        if 'method_link' in tv: e.add_field(name="📖 Ссылка на методичку", value=tv['method_link'], inline=False)
        if 'desc' in tv: e.add_field(name="📝 Детали", value=f"```\n{tv['desc']}\n```", inline=False)
        if 'incidents' in tv and tv['incidents']: e.add_field(name="⚠️ Инциденты", value=f"```\n{tv['incidents']}\n```", inline=False)
        if 'evidence' in tv: e.add_field(name="📸 Доказательства", value=tv['evidence'], inline=False)
        
        msg_channel = inter.bot.get_channel(config.LOG_CHANNEL_ID)
        if isinstance(msg_channel, disnake.TextChannel):
            msg = await msg_channel.send(embed=e, view=OfficerButtons())
            await msg.create_thread(name=f"Разбор: {self.r_type.split(' (')[0]}")
            
        await inter.response.send_message("✅ Рапорт отправлен на проверку!", ephemeral=True)


class ParticipantSelectView(ui.View):
    def __init__(self, r_type: str, author_name: str, extra_fields=None):
        super().__init__(timeout=300)
        self.r_type = r_type
        self.author_name = author_name
        self.extra_fields = extra_fields or {}
        self.selected_users = []
        
        if "Аттестация" not in r_type and "Обучение" not in r_type:
            btn = ui.Button(label="Пропустить (Я один)", style=disnake.ButtonStyle.grey)
            btn.callback = self.skip_callback # type: ignore
            self.add_item(btn)

    @ui.user_select(placeholder="Выберите участников", min_values=1, max_values=25)
    async def select_users(self, select: ui.UserSelect, inter: disnake.MessageInteraction):
        self.selected_users = select.values
        await inter.response.defer()

    @ui.button(label="Далее (с участниками)", style=disnake.ButtonStyle.green)
    async def next_step(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not self.selected_users: 
            return await inter.response.send_message("Вы не выбрали участников!", ephemeral=True)
        await inter.response.send_modal(ReportModal(self.r_type, self.author_name, self.selected_users, self.extra_fields))

    async def skip_callback(self, inter: disnake.MessageInteraction): 
        await inter.response.send_modal(ReportModal(self.r_type, self.author_name, [], self.extra_fields))


class MainView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [disnake.SelectOption(label=k, value=k) for k in config.MAIN_MENU_OPTIONS]
        self.add_item(ui.Select(options=options, placeholder="Выберите тип рапорта", custom_id="sel_v9", row=0))

    @ui.button(label="🪪 Моя статистика", style=disnake.ButtonStyle.blurple, custom_id="btn_my_profile", row=1)
    async def my_profile(self, btn: ui.Button, inter: disnake.MessageInteraction):
        rp_id = utils.extract_rp_id(inter.author.display_name)
        if rp_id == "0000": 
            return await inter.response.send_message("❌ Не удалось определить ваш ID по никнейму. Ник должен начинаться с IDN (например: 1234 | PVT | Nick).", ephemeral=True)
            
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur:
                row = await cur.fetchone()
                
        if not row: 
            return await inter.response.send_message("📭 В базе данных нет информации о вас.", ephemeral=True)
            
        stats = dict(row)
        rank = stats.get('rank', 'PVT')
        target_points, nxt = utils.get_target_points(rank)
        warn_text = f"🟨 Устные: `{stats.get('verbal_warn',0)}/2` | 🟥 Строгие: `{stats.get('strict_warn',0)}/3`" + (" (Заморожен)" if stats.get('strict_warn', 0) > 0 else "")
        
        desc = f"**Боец:** {inter.author.mention}\n**ID:** `{rp_id}` | **Звание:** `{rank}`\n**Выговоры:** {warn_text}\n**Баллы:** `{stats.get('points',0)}`\n**Прогресс:** {utils.get_progress_bar(stats.get('points',0), target_points)} ({target_points - stats.get('points',0)} до {nxt})\n\n**📋 Требования:**\n{utils.get_criteria_text(rank, stats)}"
        await inter.response.send_message(embed=disnake.Embed(title="🪪 Военный билет", description=desc, color=disnake.Color.blue()).set_thumbnail(url=inter.author.display_avatar.url), ephemeral=True)

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.data.custom_id == "sel_v9":
            r_type = str(inter.values[0]) if inter.values else ""
            
            class ArrView(ui.View):
                @ui.button(label="СКТ", style=disnake.ButtonStyle.danger)
                async def b1(self, b, i): await i.response.send_modal(ReportModal("СКТ", inter.author.display_name, extra_fields={"⚖️ Тип": "СКТ"}))
                @ui.button(label="Задержание", style=disnake.ButtonStyle.primary)
                async def b2(self, b, i): await i.response.send_modal(ReportModal("Задержание", inter.author.display_name, extra_fields={"⚖️ Тип": "Задержание"}))
                @ui.button(label="Предупреждение", style=disnake.ButtonStyle.secondary)
                async def b3(self, b, i): await i.response.send_modal(ReportModal("Предупреждение", inter.author.display_name, extra_fields={"⚖️ Тип": "Предупреждение"}))
                
            class CmdView(ui.View):
                @ui.button(label="Я командовал (Да)", style=disnake.ButtonStyle.green)
                async def b1(self, b, i): await i.response.send_message("Участники:", view=ParticipantSelectView(r_type, inter.author.display_name, {"🎖️ Командир": "Да"}), ephemeral=True)
                @ui.button(label="Только участвовал", style=disnake.ButtonStyle.grey)
                async def b2(self, b, i): await i.response.send_message("Участники:", view=ParticipantSelectView(r_type, inter.author.display_name, {"🎖️ Командир": "Нет"}), ephemeral=True)
                
            class TrView(ui.View):
                @ui.button(label="Обычная", style=disnake.ButtonStyle.primary)
                async def b1(self, b, i): await i.response.send_message(f"Вы оформляете: **Тренировка (Обычная)**", view=ParticipantSelectView("Тренировка (Обычная)", inter.author.display_name, {"⚙️ Тип тренировки": "Обычная"}), ephemeral=True)
                @ui.button(label="Специальная", style=disnake.ButtonStyle.primary)
                async def b2(self, b, i): await i.response.send_message(f"Вы оформляете: **Тренировка (Специальная)**", view=ParticipantSelectView("Тренировка (Специальная)", inter.author.display_name, {"⚙️ Тип тренировки": "Специальная"}), ephemeral=True)
                @ui.button(label="По методичке", style=disnake.ButtonStyle.primary)
                async def b3(self, b, i): await i.response.send_message(f"Вы оформляете: **Тренировка (По методичке)**", view=ParticipantSelectView("Тренировка (По методичке)", inter.author.display_name, {"⚙️ Тип тренировки": "По методичке"}), ephemeral=True)
                
            class SubView(ui.View):
                @ui.button(label="Рядовой", style=disnake.ButtonStyle.primary)
                async def b1(self, b, i): await i.response.send_message(f"Вы оформляете: **{r_type} (Рядовой состав)**", view=ParticipantSelectView(f"{r_type} (Рядовой состав)", inter.author.display_name), ephemeral=True)
                @ui.button(label="Сержантский", style=disnake.ButtonStyle.primary)
                async def b2(self, b, i): await i.response.send_message(f"Вы оформляете: **{r_type} (Сержантский состав)**", view=ParticipantSelectView(f"{r_type} (Сержантский состав)", inter.author.display_name), ephemeral=True)
                @ui.button(label="Мл. Офицерский", style=disnake.ButtonStyle.primary)
                async def b3(self, b, i): await i.response.send_message(f"Вы оформляете: **{r_type} (Мл. офицерский состав)**", view=ParticipantSelectView(f"{r_type} (Мл. офицерский состав)", inter.author.display_name), ephemeral=True)
                @ui.button(label="Ст. Офицерский", style=disnake.ButtonStyle.primary)
                async def b4(self, b, i): await i.response.send_message(f"Вы оформляете: **{r_type} (Ст. офицерский состав)**", view=ParticipantSelectView(f"{r_type} (Ст. офицерский состав)", inter.author.display_name), ephemeral=True)

            if r_type == "Нарушение (СКТ/Задержание)": 
                await inter.response.send_message("Укажите тип:", view=ArrView(), ephemeral=True)
            elif r_type == "План/Методичка": 
                await inter.response.send_modal(ReportModal("План/Методичка", inter.author.display_name))
            elif r_type in ["Боевой вылет", "Защита объекта"]: 
                await inter.response.send_message("Ваша роль:", view=CmdView(), ephemeral=True)
            elif r_type == "Тренировка": 
                await inter.response.send_message("Тип тренировки:", view=TrView(), ephemeral=True)
            elif r_type in ["Аттестация", "Обучение"]: 
                await inter.response.send_message("Состав:", view=SubView(), ephemeral=True)
            else: 
                await inter.response.send_message("Участники:", view=ParticipantSelectView(r_type, inter.author.display_name), ephemeral=True)
            return False
        return True


class ReportsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx): 
        await ctx.send(embed=disnake.Embed(title="🏛️ ТЕРМИНАЛ CG", color=disnake.Color.red()), view=MainView())


def setup(bot):
    bot.add_cog(ReportsCog(bot))