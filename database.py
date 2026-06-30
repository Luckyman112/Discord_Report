import os
import aiosqlite
import gspread
from gspread_formatting import *
import config
import traceback # Добавили для отслеживания точной ошибки

# --- Подключение Google Sheets ---
try:
    print("⏳ Подключение к Google API...")
    client = gspread.service_account(filename="credentials.json")
    
    # Открываем саму таблицу
    spreadsheet = client.open("Таблица CG")
    
    # В новых версиях gspread .sheet1 удален, используем get_worksheet(0) (0 - это первый лист)
    sheet = spreadsheet.get_worksheet(0)
    # Подключаем лист Архива
    try:
        archive_sheet = spreadsheet.worksheet("Архив")
    except:
        print("⚠️ Лист 'Архив' не найден! Создай его в Гугл Таблице.")
        archive_sheet = None

    print("✅ Успешное подключение к Google Таблицам!")
except Exception as e:
    print(f"⚠️ ПРОИЗОШЛА ОШИБКА ПРИ ПОДКЛЮЧЕНИИ:")
    traceback.print_exc() # Выведет точную строчку и причину ошибки
    sheet = None

def apply_row_style(row_idx, rank="PVT"):
    """Красит ячейки, ставит внутренние СВЕТЛО-СЕРЫЕ рамки и внешние двойные боковые"""
    if not sheet: return
    
    # Высчитываем цвет для B, C, D
    hex_color = config.COLORS.get(rank, "#FFFFFF").lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))
    
    # Настройки стилей и цветов
    light_gray = Color(0.81, 0.81, 0.81)
    
    # Линии
    med_border = Border('SOLID_MEDIUM', light_gray) # Внутренняя (толщина 2, светло-серая)
    dbl_border = Border('DOUBLE', light_gray)           # Внешняя боковая (двойная, черная)
    
    text_fmt = TextFormat(fontFamily='Montserrat', fontSize=10, bold=True)
    bg_colored = Color(*rgb)
    bg_plain = Color(1, 1, 1)

    # 1. Столбец B (С цветом, СЛЕВА ДВОЙНАЯ РАМКА)
    fmt_B = CellFormat(
        backgroundColor=bg_colored, textFormat=text_fmt,
        verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
        borders=Borders(top=med_border, bottom=med_border, left=dbl_border, right=med_border)
    )
    
    # 2. Столбцы C и D (С цветом, ВЕЗДЕ ОБЫЧНАЯ РАМКА)
    fmt_CD = CellFormat(
        backgroundColor=bg_colored, textFormat=text_fmt,
        verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
        borders=Borders(top=med_border, bottom=med_border, left=med_border, right=med_border)
    )
    
    # 3. Столбцы E-K (Белые, ВЕЗДЕ ОБЫЧНАЯ РАМКА)
    fmt_EK = CellFormat(
        backgroundColor=bg_plain, textFormat=text_fmt,
        verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
        borders=Borders(top=med_border, bottom=med_border, left=med_border, right=med_border)
    )
    
    # 4. Столбец L (Белый, СПРАВА ДВОЙНАЯ РАМКА)
    fmt_L = CellFormat(
        backgroundColor=bg_plain, textFormat=text_fmt,
        verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
        borders=Borders(top=med_border, bottom=med_border, left=med_border, right=dbl_border)
    )

    # Применяем все 4 формата по своим местам
    format_cell_range(sheet, f"B{row_idx}", fmt_B)
    format_cell_range(sheet, f"C{row_idx}:D{row_idx}", fmt_CD)
    format_cell_range(sheet, f"E{row_idx}:K{row_idx}", fmt_EK)
    format_cell_range(sheet, f"L{row_idx}", fmt_L)

    # --- ЛОГИКА АВТО-СОРТИРОВКИ ---
    weight = 0
    if rank == "ARCHIVE" or rank == "УВОЛЕН":
        weight = -100
    else:
        for w, r in config.RANKS:
            if r == rank:
                weight = w
                break
                
    sheet.update_cell(row_idx, 13, weight)
    try:
        sheet.sort((13, 'des'), range='B6:M1000')
    except Exception as e:
        print(f"Ошибка при авто-сортировке таблицы: {e}")

async def sync_google_warns(rp_id: str, v_warn: int, s_warn: int):
    """Синхронизирует выговоры с гуглом (0/2 0/3)"""
    if not sheet: return
    try:
        cell = sheet.find(str(rp_id), in_column=2) # Ищем IDN в столбце B(2)
        if cell:
            warn_str = f"{v_warn}/2 {s_warn}/3"
            sheet.update_cell(cell.row, 11, warn_str) # Столбец K(11)
    except Exception as e:
        print(f"Ошибка синхронизации выговоров в Гугл: {e}")

# --- Подключение SQLite ---
async def init_db():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS soldiers (user_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, rank TEXT DEFAULT 'PVT', join_date TEXT, verbal_warn INTEGER DEFAULT 0, strict_warn INTEGER DEFAULT 0)")
        for col in config.METRIC_COLUMNS:
            try: await db.execute(f"ALTER TABLE soldiers ADD COLUMN {col} INTEGER DEFAULT 0")
            except aiosqlite.OperationalError: pass
        await db.commit()

import datetime

def archive_soldier(rp_id: str, reason: str):
    """Вырезает бойца из основной таблицы и переносит в Архив"""
    if not sheet or not archive_sheet: return False
    try:
        cell = sheet.find(str(rp_id), in_column=2)
        if cell:
            row_vals = sheet.row_values(cell.row)
            # Добиваем пустые ячейки, если строка обрезалась
            while len(row_vals) < 13: row_vals.append("")
            
            today_ru = datetime.date.today().strftime('%d.%m.%Y')
            row_vals[1] = "АРХИВ" # Столбец B
            row_vals[2] = "УВОЛЕН" # Столбец C
            row_vals[11] = f"Отчислен {today_ru}. Причина: {reason}" # Столбец L
            
            # Добавляем в архив и удаляем с главного листа
            archive_sheet.append_row(row_vals)
            sheet.delete_rows(cell.row)
            return True
    except Exception as e:
        print(f"Ошибка архивации в Гугл: {e}")
    return False