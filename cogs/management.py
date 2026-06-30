import disnake
from disnake.ext import commands
from disnake import ui
import datetime
import aiosqlite

import config
import utils
from database import sheet, apply_row_style, sync_google_warns, archive_soldier
from cogs.reports import PromotionView

class AdminManageView(ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @ui.button(label="Баллы (+/-)", style=disnake.ButtonStyle.secondary, custom_id="adm_pts", row=0)
    async def pts(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_deputy(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Правка баллов", custom_id="m_pts", components=[ui.TextInput(label="ID Бойца", custom_id="mid"), ui.TextInput(label="Сумма (+10 или -5)", custom_id="act")]))
        
    @ui.button(label="Звание (Force)", style=disnake.ButtonStyle.secondary, custom_id="adm_rnk", row=0)
    async def rnk(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_deputy(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Смена звания", custom_id="m_rank", components=[ui.TextInput(label="ID Бойца", custom_id="mid"), ui.TextInput(label="Код звания (напр: SGT)", custom_id="rnk")]))

    @ui.button(label="Выговор", style=disnake.ButtonStyle.danger, custom_id="adm_warn", row=1)
    async def warn(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_officer(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Выдача выговора", custom_id="m_warn", components=[ui.TextInput(label="ID Бойца", custom_id="mid"), ui.TextInput(label="Тип (устный / строгий)", custom_id="wtype"), ui.TextInput(label="Причина", custom_id="reason", style=disnake.TextInputStyle.paragraph)]))

    @ui.button(label="Отработка", style=disnake.ButtonStyle.danger, custom_id="adm_unwarn", row=1)
    async def unwarn(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_officer(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Отработка выговора", custom_id="m_unwarn", components=[ui.TextInput(label="ID Бойца", custom_id="mid")]))

    @ui.button(label="Дата вступления", style=disnake.ButtonStyle.primary, custom_id="adm_reset", row=2)
    async def reset(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_deputy(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Изменить дату вступления", custom_id="m_reset", components=[ui.TextInput(label="ID Бойца", custom_id="mid"), ui.TextInput(label="Дата (ГГГГ-ММ-ДД)", custom_id="new_date", placeholder="Например: 2026-06-26")]))

    @ui.button(label="❌ Отчислить", style=disnake.ButtonStyle.danger, custom_id="adm_dismiss", row=2)
    async def dismiss(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_deputy(inter.author): return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.send_modal(ui.Modal(title="Архивация бойца", custom_id="m_dismiss", components=[
            ui.TextInput(label="ID Бойца (IDN)", custom_id="mid"), 
            ui.TextInput(label="Причина увольнения", custom_id="reason", placeholder="ПСЖ / Нарушение устава")
        ]))

class ManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def manage(self, ctx):
        await ctx.send(embed=disnake.Embed(title="🕹️ ПАНЕЛЬ УПРАВЛЕНИЯ", color=disnake.Color.blue()), view=AdminManageView())

    # --- ДЕТЕКТОР ВЫХОДА С СЕРВЕРА (АВТО-АРХИВАЦИЯ ЛИВНУВШИХ) ---
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        rp_id = utils.extract_rp_id(member.display_name)
        if rp_id != "0000":
            # 1. Удаляем из SQLite (army_base.db)
            async with aiosqlite.connect(config.DB_PATH) as db:
                await db.execute("DELETE FROM soldiers WHERE user_id = ?", (rp_id,))
                await db.commit()
            
            # 2. Вырезаем с главного листа и переносим в Архив Гугла
            archive_soldier(rp_id, "Дезертир (Ливнул с сервера)")
            
            # 3. Отправляем лог штабу
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"🏃‍♂️ **Дезертирство!** Боец **{member.display_name}** покинул сервер. Строка перенесена в Архив.")

    @commands.Cog.listener("on_modal_submit")
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        cid = inter.custom_id
        if cid not in ["m_pts", "m_rank", "m_warn", "m_unwarn", "m_reset", "m_dismiss"]: return
        
        await inter.response.defer(ephemeral=True)
        rp_id = inter.text_values.get('mid', '').strip()
        today_str = datetime.date.today().isoformat()
        act, val, reason, new_date, is_error = "", 0, "", "", False
        v_w, s_w = 0, 0
        
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("INSERT OR IGNORE INTO soldiers (user_id, join_date) VALUES (?, ?)", (rp_id, today_str))
            
            if cid == "m_pts":
                act = inter.text_values.get('act', '')
                val = int(act.replace("+","").replace("-","")) if act else 0
                if "-" in act: await db.execute("UPDATE soldiers SET points = MAX(0, points - ?) WHERE user_id = ?", (val, rp_id))
                else: await db.execute("UPDATE soldiers SET points = points + ? WHERE user_id = ?", (val, rp_id))
                
            elif cid == "m_rank":
                rnk = inter.text_values.get('rnk', '').upper()
                reset_sql = ", ".join([f"{col} = 0" for col in config.METRIC_COLUMNS])
                async with db.execute("SELECT rank FROM soldiers WHERE user_id = ?", (rp_id,)) as c: 
                    row = await c.fetchone()
                    old_r = dict(row).get("rank", "PVT") if row else "PVT"
                if rnk in ["SGT", "JLT", "MAJ"]: await db.execute(f"UPDATE soldiers SET rank = ?, points = 0, join_date = ?, {reset_sql} WHERE user_id = ?", (rnk, today_str, rp_id))
                else: await db.execute(f"UPDATE soldiers SET rank = ?, points = 0, {reset_sql} WHERE user_id = ?", (rnk, rp_id))
                
            elif cid == "m_warn":
                wtype = inter.text_values.get('wtype', '').lower()
                reason = inter.text_values.get('reason', 'Не указана')
                if "устн" in wtype:
                    await db.execute("UPDATE soldiers SET verbal_warn = verbal_warn + 1 WHERE user_id = ?", (rp_id,))
                    async with db.execute("SELECT verbal_warn FROM soldiers WHERE user_id = ?", (rp_id,)) as c:
                        row = await c.fetchone()
                        if row and dict(row)['verbal_warn'] >= 2:
                            await db.execute("UPDATE soldiers SET verbal_warn = 0, strict_warn = strict_warn + 1 WHERE user_id = ?", (rp_id,))
                            wtype = "Устный (Конвертирован в Строгий)"
                else: await db.execute("UPDATE soldiers SET strict_warn = MIN(3, strict_warn + 1) WHERE user_id = ?", (rp_id,))
                
            elif cid == "m_unwarn":
                reset_sql = ", ".join([f"{col} = 0" for col in config.METRIC_COLUMNS])
                await db.execute(f"UPDATE soldiers SET points = points - 50, strict_warn = MAX(0, strict_warn - 1), {reset_sql} WHERE user_id = ?", (rp_id,))
                
            elif cid == "m_reset":
                new_date = inter.text_values.get('new_date', '').strip()
                try:
                    datetime.date.fromisoformat(new_date)
                    await db.execute("UPDATE soldiers SET join_date = ? WHERE user_id = ?", (new_date, rp_id))
                except ValueError:
                    is_error = True

            elif cid == "m_dismiss":
                reason = inter.text_values.get('reason', 'Не указана')
                await db.execute("DELETE FROM soldiers WHERE user_id = ?", (rp_id,))

            await db.commit()
            async with db.execute("SELECT * FROM soldiers WHERE user_id = ?", (rp_id,)) as cur:
                row = await cur.fetchone()
                new_stats = dict(row) if row else {}
                v_w, s_w = new_stats.get('verbal_warn', 0), new_stats.get('strict_warn', 0)
        
        if is_error: return await inter.edit_original_response(content="❌ Ошибка! Дата введена в неверном формате (ГГГГ-ММ-ДД).")

        # --- СИНХРОНИЗАЦИЯ С ГУГЛОМ И ОТПРАВКА СООБЩЕНИЙ ---
        if cid in ["m_warn", "m_unwarn"]:
            await sync_google_warns(rp_id, v_w, s_w)

        if cid == "m_dismiss":
            # Переносим в архив Гугла (на отдельный лист)
            archive_soldier(rp_id, reason)
            
            # Снимаем роли в Дискорде
            try:
                member = disnake.utils.get(inter.guild.members, display_name=rp_id)
                if member: await member.edit(roles=[], nick=member.name)
            except: pass
            return await inter.edit_original_response(content=f"🚨 Боец IDN: **{rp_id}** отчислен и переведен на лист Архива.")
        
        if cid == "m_pts":
            tp, r = new_stats.get("points", 0), new_stats.get("rank", "PVT")
            tgt, nxt = utils.get_target_points(r)
            if inter.message: await utils.sync_dossier(self.bot, rp_id, f"ID: {rp_id}", "АДМИН-ПРАВКА", int(act) if "-" not in act else -val, new_stats, inter.message.jump_url, officer=inter.author.display_name)
            if "-" not in act and r != "MAJ" and utils.check_promotion_criteria(r, new_stats, tgt): await utils.send_promo_request(self.bot, rp_id, r, nxt, tp, f"ID: {rp_id}", PromotionView)
            await inter.edit_original_response(content=f"✅ Готово. Текущие баллы: {tp}")
            
        elif cid == "m_rank":
            # --- ОБНОВЛЕНИЕ ГУГЛ ТАБЛИЦЫ ПРИ FORCE ПОВЫШЕНИИ ---
            if sheet:
                try:
                    cell = sheet.find(str(rp_id), in_column=2)
                    if cell:
                        today_ru = datetime.date.today().strftime('%d.%m.%Y')
                        sheet.update_cell(cell.row, 3, rnk) # Меняем звание в таблице
                        if rnk in config.BASE_COMP_RANKS:
                            sheet.update_cell(cell.row, 6, today_ru) # Обновляем дату состава
                        apply_row_style(cell.row, rnk) # Перекрашиваем и сортируем
                except Exception as e:
                    print(f"Ошибка Гугла при Force-смене звания: {e}")
            # ---------------------------------------------------

            # ЖЕЛЕЗОБЕТОННЫЙ ПОИСК ИГРОКА ПО DISCORD ID ИЗ БАЗЫ ДАННЫХ
            if inter.guild:
                member = None
                # Пробуем достать Discord ID из нашей обновленной строки в SQLite
                discord_id_str = new_stats.get('user_id_discord') or new_stats.get('user_id') 
                
                # Если в базе лежит нормальный Discord ID (длинное число), ищем по нему
                if discord_id_str and discord_id_str.isdigit() and len(discord_id_str) > 10:
                    member = inter.guild.get_member(int(discord_id_str))
                
                # Если по ID не нашли, ищем по старинке (по совпадению IDN в нике)
                if not member:
                    for m in inter.guild.members:
                        if f"[{rp_id}]" in m.display_name or m.display_name.startswith(str(rp_id)):
                            member = m
                            break
                
                # Если нашли игрока — меняем ник и выдаем ВСЕ новые роли
                if member:
                    try:
                        # Вызываем функцию из utils.py, она сменит ник и выдаст базовые роли + роли за CPL/SGM/CPT
                        await utils.update_member_nickname(inter.guild, rp_id, rnk)
                    except Exception as e:
                        print(f"Ошибка при вызове update_member_nickname: {e}")
                else:
                    print(f"⚠️ Предупреждение: Бот не нашел на сервере человека с IDN {rp_id}, роли и ник не изменены.")

            if inter.message: 
                await utils.sync_dossier(self.bot, rp_id, f"ID: {rp_id}", "СМЕНА ЗВАНИЯ", 0, new_stats, inter.message.jump_url, officer=inter.author.display_name)
            
            pl = self.bot.get_channel(config.PROMO_LOG_CHANNEL_ID)
            if isinstance(pl, disnake.TextChannel): 
                await pl.send(f"⚠️ **ПРИКАЗ:** Боец **ID: {rp_id}** назначен на звание **{rnk}**! (Утвердил: {inter.author.display_name})")
                
            await inter.edit_original_response(content=f"✅ **ID: {rp_id}** переведен в {rnk}. Таблица, никнейм и роли обновлены!")
            
        elif cid == "m_warn":
            warn_chan = self.bot.get_channel(config.WARNINGS_LOG_CHANNEL_ID)
            if isinstance(warn_chan, disnake.TextChannel):
                e = disnake.Embed(title="🚨 ВЫДАЧА ВЫГОВОРА", color=disnake.Color.red())
                e.add_field(name="Боец (ID)", value=f"`{rp_id}`", inline=True)
                e.add_field(name="Офицер", value=inter.author.display_name, inline=True)
                e.add_field(name="Тип", value=wtype.upper(), inline=True)
                e.add_field(name="Причина", value=f"```{reason}```", inline=False)
                await warn_chan.send(embed=e)
                
            await utils.sync_dossier(self.bot, rp_id, f"ID: {rp_id}", "ВЫДАЧА ВЫГОВОРА", 0, new_stats, "[https://discord.com](https://discord.com)", officer=inter.author.display_name)
            await inter.edit_original_response(content=f"✅ Выговор выдан бойцу **ID: {rp_id}** и отправлен в лог-канал.")
            
        elif cid == "m_unwarn":
            await utils.sync_dossier(self.bot, rp_id, f"ID: {rp_id}", "ОТРАБОТКА ВЫГОВОРА (-50 баллов)", -50, new_stats, "[https://discord.com](https://discord.com)", officer=inter.author.display_name)
            await inter.edit_original_response(content=f"✅ Боец **ID: {rp_id}** отработал выговор.")
            
        elif cid == "m_reset":
            await inter.edit_original_response(content=f"✅ Дата вступления для **ID: {rp_id}** изменена на `{new_date}`.")

def setup(bot):
    bot.add_cog(ManagementCog(bot))