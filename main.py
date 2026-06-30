import disnake
from disnake.ext import commands
import config
import database

# Импортируем Вьюшки для их вечной работы (чтобы кнопки не ломались после рестарта)
from cogs.reports import MainView, OfficerButtons
from cogs.management import AdminManageView

intents = disnake.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # Создаем таблицы в базе если их нет
    await database.init_db()
    
    # Регистрируем кнопки
    bot.add_view(MainView())
    bot.add_view(OfficerButtons())
    bot.add_view(AdminManageView())
    
    print(f"Система активна: {bot.user}")

# Загрузка модулей
bot.load_extension("cogs.registration")
bot.load_extension("cogs.reports")
bot.load_extension("cogs.management")

if __name__ == "__main__":
    bot.run(config.TOKEN)