import disnake
from disnake.ext import commands
from disnake import ui
import datetime

import config
import utils
from database import sheet, apply_row_style

class DynamicRegisterModal(ui.Modal):
    def __init__(self, current_nick="", current_steam="", has_account=False):
        self.has_account = has_account
        
        components = [
            ui.TextInput(
                label="Позывной (без звания и ID)", 
                placeholder="Lucky", 
                custom_id="callsign", 
                value=str(current_nick)
            ),
            ui.TextInput(
                label="SteamID", 
                placeholder="STEAM_0:...", 
                custom_id="steam_id", 
                value=str(current_steam)
            ),
            ui.TextInput(
                label="Специализация (Довписать)", 
                placeholder="MED, ENG, PIL...", 
                custom_id="spec", 
                required=False
            )
        ]
        
        super().__init__(title="Таблица CG", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        callsign_val = inter.text_values["callsign"]
        steam_val = inter.text_values["steam_id"]
        spec_val = inter.text_values.get("spec", "")

        display_name = inter.author.display_name
        rp_id = utils.extract_rp_id(display_name)
        if rp_id == "0000": rp_id = "НЕТ_ID"
        
        name_parts = display_name.split("|")
        if len(name_parts) >= 2: 
            detected_rank = name_parts[1].strip().upper()
        else: 
            detected_rank = display_name.split(" ")[0].upper()
        
        valid_ranks = [r[1] for r in config.RANKS]
        if detected_rank not in valid_ranks: 
            detected_rank = "PVT"
            
        officer_channel = inter.guild.get_channel(config.LOG_CHANNEL_ID)
        
        embed = disnake.Embed(title="📝 Запрос на обновление/регистрацию состава", color=disnake.Color.blue())
        embed.add_field(name="Боец (Discord ID)", value=f"{inter.author.mention} (`{inter.author.id}`)", inline=False)
        embed.add_field(name="Игровой IDN", value=rp_id, inline=True)
        embed.add_field(name="Позывной", value=callsign_val, inline=True)
        embed.add_field(name="Звание", value=detected_rank, inline=True)
        embed.add_field(name="SteamID", value=steam_val, inline=True)
        embed.add_field(name="Доп. Специализация", value=spec_val or "Нет", inline=True)
        embed.add_field(name="Тип", value="Обновление" if self.has_account else "Новый боец", inline=False)

        # Передаем inter.author (самого новичка) в кнопку ApproveRegView
        view = ApproveRegView(
            user=inter.author, rp_id=rp_id, rank=detected_rank, 
            callsign=callsign_val, steam=steam_val, 
            spec=spec_val, is_update=self.has_account
        )
        await officer_channel.send(embed=embed, view=view)
        await inter.response.send_message("✅ Анкета отправлена штабу на проверку!", ephemeral=True)

class ApproveRegView(ui.View):
    def __init__(self, user, rp_id, rank, callsign, steam, spec, is_update):
        super().__init__(timeout=None)
        self.user = user # Объект новичка в Дискорде
        self.rp_id = rp_id
        self.rank = rank
        self.callsign = callsign
        self.steam = steam
        self.spec = spec
        self.is_update = is_update

    @ui.button(label="Одобрить", style=disnake.ButtonStyle.green)
    async def approve(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_officer(inter.author): 
            return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.response.defer()
        
        today_str = datetime.date.today().strftime('%d.%m.%Y')
        
        # 1. Запись данных в Гугл Таблицу
        if sheet:
            if self.is_update:
                cell = sheet.find(str(self.rp_id), in_column=2)
                if cell:
                    sheet.update_cell(cell.row, 3, self.rank)
                    sheet.update_cell(cell.row, 4, self.callsign)
                    sheet.update_cell(cell.row, 9, self.steam)
                    sheet.update_cell(cell.row, 10, str(self.user.id))
                    
                    if self.rank in config.BASE_COMP_RANKS:
                        sheet.update_cell(cell.row, 6, today_str) 

                    if self.spec:
                        old_spec = sheet.cell(cell.row, 8).value
                        new_spec = f"{old_spec}, {self.spec.upper()}" if old_spec else self.spec.upper()
                        sheet.update_cell(cell.row, 8, new_spec)
                    
                    apply_row_style(cell.row, self.rank)
            else:
                warn_str = "0/2 0/3"
                new_row = [self.rp_id, self.rank, self.callsign, today_str, today_str, "", self.spec.upper() or "", self.steam, str(self.user.id), warn_str, ""]
                sheet.append_row(new_row, table_range="B6")
                
                total_rows = len(sheet.get_all_values())
                apply_row_style(total_rows, self.rank)

        # 2. ЖЕЛЕЗОБЕТОННАЯ СМЕНА НИКА И ВЫДАЧА ПЕРВЫХ 2 РОЛЕЙ
        if inter.guild and self.user:
            try:
                # Передаем объект self.user напрямую. Функция в utils сама выдаст первые 2 роли и сменит ник!
                await utils.update_member_nickname(inter.guild, self.rp_id, self.rank, member=self.user)
            except Exception as e: 
                print(f"Ошибка смены ника/ролей при регистрации новичка: {e}")

        await inter.message.edit(content=f"✅ Одобрено ({inter.author.display_name})", view=None)

    @ui.button(label="Отклонить", style=disnake.ButtonStyle.red)
    async def deny(self, btn: ui.Button, inter: disnake.MessageInteraction):
        if not utils.is_officer(inter.author): 
            return await inter.response.send_message("❌ Нет прав.", ephemeral=True)
        await inter.message.edit(content=f"❌ Отклонено ({inter.author.display_name})", view=None)

class RegistrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_gate(self, ctx):
        view = ui.View(timeout=None)
        btn = ui.Button(label="Зарегистрироваться / Обновить данные", style=disnake.ButtonStyle.primary)
        
        async def callback(inter: disnake.MessageInteraction):
            rp_id = utils.extract_rp_id(inter.author.display_name)
            curr_nick, curr_steam, has_account = "", "", False
            
            if sheet and rp_id != "0000":
                try:
                    cell = sheet.find(str(rp_id), in_column=2)
                    if cell:
                        row_data = sheet.row_values(cell.row)
                        curr_nick = row_data[3] if len(row_data) > 3 else ""
                        curr_steam = row_data[8] if len(row_data) > 8 else ""
                        has_account = True
                except: 
                    pass
                
            await inter.response.send_modal(DynamicRegisterModal(curr_nick, curr_steam, has_account))

        btn.callback = callback
        view.add_item(btn)
        await ctx.send("⚔️ **БАЗА ДАННЫХ CORUSCANT GUARD**\nПройдите регистрацию персонажа.", view=view)

def setup(bot):
    bot.add_cog(RegistrationCog(bot))