import disnake
import config
import datetime
import re

def extract_rp_id(nickname: str) -> str:
    """Извлекает 4-значный ID строго из начала никнейма формата: 1234 | RANK | NICK"""
    match_start = re.search(r'^(\d{4})', nickname.strip())
    if match_start:
        return match_start.group(1)
    
    match_fallback = re.search(r'(\d{4})\s*\|', nickname)
    if match_fallback:
        return match_fallback.group(1)
        
    return "0000"

def is_officer(member: disnake.Member) -> bool:
    if member.guild_permissions.administrator: return True
    return any(role.id in config.OFFICER_ROLE_IDS for role in member.roles)

def is_deputy(member: disnake.Member) -> bool:
    if member.guild_permissions.administrator: return True
    return any(role.id in config.DEPUTY_ROLE_IDS for role in member.roles)

def get_field_val(embed: disnake.Embed, field_name: str, default: str = "") -> str:
    for field in embed.fields:
        if field.name and field_name in field.name:
            if field.value: return field.value.replace("```", "").strip()
    return default

def get_target_points(rank: str) -> tuple:
    for i, (_, r_code) in enumerate(config.RANKS):
        if r_code == rank and i - 1 >= 0:
            next_rank = config.RANKS[i-1][1]
            req_pts = config.PROMOTION_REQUIREMENTS.get(next_rank, 9999)
            return req_pts, next_rank
    return 9999, "MAX"

def get_progress_bar(current: int, target: int) -> str:
    if target <= 0: return "██████████"
    percentage = min(current / target, 1.0)
    filled = int(percentage * 10)
    return "█" * filled + "░" * (10 - filled)

def get_criteria_text(rank: str, stats: dict) -> str:
    _, nxt = get_target_points(rank)
    if nxt == "MAX": return "Вы достигли максимального звания."
    
    req_stats = config.RANK_CRITERIA.get(nxt, {})
    lines = []
    for metric, req_val in req_stats.items():
        curr_val = stats.get(metric, 0)
        status = "✅" if curr_val >= req_val else "❌"
        ru_name = config.METRICS_NAMES.get(metric, metric)
        lines.append(f"{ru_name}: `{curr_val}/{req_val}` {status}")
    return "\n".join(lines) if lines else "Спец. критериев нет, только баллы."

def check_promotion_criteria(rank: str, stats: dict, target_points: int) -> bool:
    if stats.get('points', 0) < target_points: return False
    if stats.get('strict_warn', 0) > 0: return False
        
    _, nxt = get_target_points(rank)
    req_stats = config.RANK_CRITERIA.get(nxt, {})
    for metric, req_val in req_stats.items():
        if stats.get(metric, 0) < req_val: return False
    return True

async def send_promo_request(bot, rp_id: str, current_rank: str, next_rank: str, current_points: int, author_info: str, view_class):
    chan = bot.get_channel(config.PROMO_REQ_CHANNEL_ID)
    if isinstance(chan, disnake.TextChannel):
        e = disnake.Embed(title="🚀 ДОСТУПНО ПОВЫШЕНИЕ!", color=disnake.Color.gold())
        e.add_field(name="Боец", value=author_info, inline=True)
        e.add_field(name="IDN", value=f"`{rp_id}`", inline=True)
        e.add_field(name="Маршрут", value=f"`{current_rank}` ➔ **`{next_rank}`**", inline=False)
        e.add_field(name="Набрано баллов", value=f"`{current_points}`", inline=True)
        await chan.send(embed=e, view=view_class(rp_id, author_info, next_rank))

async def sync_dossier(bot, rp_id: str, author_info: str, reason: str, pts_change: int, new_stats: dict, jump_url: str, status: str = "approved", officer: str = "Система"):
    """Создает личное дело как стартовое сообщение и добавляет записи в ряд"""
    forum = bot.get_channel(config.FORUM_ARCHIVE_ID)
    if not forum or not hasattr(forum, 'threads'): return
    
    thread = None
    clean_id = str(rp_id).strip()
    search_pattern = f"{clean_id} | "
    
    async for t in forum.archived_threads(limit=100):
        if t.name.strip().startswith(search_pattern):
            thread = t
            break
    if not thread:
        for t in forum.threads:
            if t.name.strip().startswith(search_pattern):
                thread = t
                break
                
    rank = new_stats.get('rank', 'PVT')
    pts = new_stats.get('points', 0)
    target_pts, nxt = get_target_points(rank)
    warn_text = f"🟨 Устные: `{new_stats.get('verbal_warn',0)}/2` | 🟥 Строгие: `{new_stats.get('strict_warn',0)}/3`"
    
    if target_pts <= 0: target_pts = 1
    progress_val = int(min(pts / target_pts, 1.0) * 100)
    progress = f"[{get_progress_bar(pts, target_pts)}] {progress_val}% ({max(0, target_pts - pts)} до {nxt})"
    
    clean_name = author_info.split("|")[-1].strip() if "|" in author_info else author_info.strip()
    target_thread_name = f"{clean_id} | {rank} | {clean_name}"
    
    # ------------------ 1. ГЛАВНОЕ ДОСЬЕ (Для шапки ветки) ------------------
    emb_dossier = disnake.Embed(title="🗃️ ЛИЧНОЕ ДЕЛО", color=0x2b2d31)
    emb_dossier.add_field(name=f"Боец: {clean_id} | {rank} | {clean_name}", value=f"**Звание:** `{rank}`\n**Баллы:** `{pts}`\n**Дисциплина:** {warn_text}\n**Прогресс:** {progress}", inline=False)
    emb_dossier.add_field(name=f"📋 Выполнение нормы на {nxt}:", value=get_criteria_text(rank, new_stats), inline=False)
    # -------------------------------------------------------------------------

    # ------------------ 2. КАРТОЧКА ЗАПИСИ (В ряд, как история) --------------
    status_str = "✅ ОДОБРЕНО" if status == "approved" else "❌ ОТКЛОНЕНО"
    emb_color = disnake.Color.green() if status == "approved" else disnake.Color.red()
    if "ПОВЫШЕНИЕ" in reason: emb_color = disnake.Color.blue()
    
    emb_record = disnake.Embed(title=f"Запись: {reason.split('(')[0].strip()}", color=emb_color)
    emb_record.add_field(name="Статус", value=status_str, inline=True)
    emb_record.add_field(name="Проверяющий", value=officer, inline=True)
    
    sign = "+" if pts_change > 0 else ""
    pts_str = f" ({sign}{pts_change} баллов)" if pts_change != 0 else ""
    emb_record.add_field(name="Действие", value=f"{reason}{pts_str}", inline=False)
    emb_record.add_field(name="Первоисточник", value=f"[Перейти к рапорту]({jump_url})", inline=False)
    # -------------------------------------------------------------------------
    
    if not thread:
        try:
            # Создаем ветку со стартовым сообщением ДОСЬЕ
            created = await forum.create_thread(name=target_thread_name, embed=emb_dossier)
            actual_thread = created.thread if hasattr(created, 'thread') else created
            # Отправляем историю вторым сообщением
            await actual_thread.send(embed=emb_record)
        except Exception as e:
            print(f"Ошибка создания ветки на форуме для {clean_id}: {e}")
    else:
        try:
            if thread.archived: await thread.edit(archived=False)
            if not thread.name.startswith(f"{clean_id} | {rank}"):
                await thread.edit(name=target_thread_name)
                
            # Обновляем СТАРТОВОЕ сообщение ветки новой статистикой
            try:
                starter_msg = await thread.fetch_message(thread.id)
                await starter_msg.edit(embed=emb_dossier)
            except Exception as e:
                print(f"Не удалось обновить стартовое сообщение: {e}")
                
            # Отправляем ЗАПИСЬ в ряд новым сообщением
            await thread.send(embed=emb_record)
        except Exception as e:
            print(f"Ошибка обновления ветки на форуме для {clean_id}: {e}")

async def sync_offender(bot, embed: disnake.Embed, jump_url: str, status: str, officer: str):
    forum = bot.get_channel(config.OFFENDERS_ARCHIVE_ID)
    if not forum or not hasattr(forum, 'threads'): return
    
    off_f = get_field_val(embed, "Нарушитель", "Неизвестно")
    off_id = extract_rp_id(off_f)
    if off_id == "0000": off_id = "НЕИЗВЕСТЕН"
    
    thread = None
    search_pattern = f"{off_id} | "
    for t in forum.threads:
        if t.name.strip().startswith(search_pattern):
            thread = t
            break
            
    emb = disnake.Embed(title=f"Фиксация проступка ({status.upper()})", color=disnake.Color.red())
    emb.add_field(name="Оформил офицер", value=officer, inline=True)
    emb.add_field(name="Нарушитель", value=off_f, inline=True)
    emb.add_field(name="Детали", value=get_field_val(embed, "Причина", "Нет описания"), inline=False)
    emb.add_field(name="Наказание", value=get_field_val(embed, "Наказание/Сроки", "Предупреждение"), inline=True)
    emb.add_field(name="Доказательства", value=get_field_val(embed, "Доказательства", "Отсутствуют"), inline=False)
    emb.add_field(name="Первоисточник", value=f"[Ссылка на рапорт]({jump_url})", inline=False)
    
    if not thread:
        try:
            await forum.create_thread(name=f"{off_id} | Нарушения боевой единицы", embed=emb)
        except Exception as e:
            print(f"Ошибка форума нарушителей: {e}")
    else:
        try:
            if thread.archived: await thread.edit(archived=False)
            await thread.send(embed=emb)
        except Exception as e:
            print(f"Ошибка обновления дела нарушителя: {e}")

async def update_member_nickname(guild: disnake.Guild, rp_id: str, rank_code: str, member: disnake.Member = None):
    if not member:
        member = disnake.utils.get(guild.members, name=rp_id)
        if not member:
            for m in guild.members:
                if m.display_name.strip().startswith(str(rp_id)):
                    member = m
                    break

    if member:
        try:
            roles_to_add = []
            role1 = guild.get_role(config.AUTO_ROLE_1_ID)
            role2 = guild.get_role(config.AUTO_ROLE_2_ID)
            
            if role1 and role1 not in member.roles: roles_to_add.append(role1)
            if role2 and role2 not in member.roles: roles_to_add.append(role2)
                
            if rank_code == "CPL":
                cpl_role = guild.get_role(config.ROLE_CPL_ID)
                if cpl_role and cpl_role not in member.roles: roles_to_add.append(cpl_role)
            elif rank_code == "SGM":
                sgm_role = guild.get_role(config.ROLE_SGM_ID)
                if sgm_role and sgm_role not in member.roles: roles_to_add.append(sgm_role)
            elif rank_code == "CPT":
                cpt_role = guild.get_role(config.ROLE_CPT_ID)
                if cpt_role and cpt_role not in member.roles: roles_to_add.append(cpt_role)

            if roles_to_add:
                await member.add_roles(*roles_to_add)
        except Exception as role_error:
            print(f"⚠️ Ошибка при выдаче ролей: {role_error}")

        try:
            current_name = member.display_name
            if "|" in current_name:
                current_name = current_name.split("|")[-1].strip()
            
            current_name = current_name.replace(str(rp_id), "").strip()
            if not current_name or current_name == str(rp_id):
                current_name = member.name
                
            new_nick = f"{rp_id} | {rank_code} | {current_name}"
            
            if len(new_nick) > 32:
                new_nick = new_nick[:32]
                
            await member.edit(nick=new_nick)
        except Exception as nick_error:
            print(f"⚠️ Ошибка изменения ника: {nick_error}")