import asyncio
from django.core.management.base import BaseCommand
from bot_zudrason.bot.bot_logic import BotHandler

class Command(BaseCommand):
    help = 'Запускает Telegram бота Zudrason'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Запуск бота...'))
        
        try:
            bot_handler = BotHandler()
            asyncio.run(bot_handler.start_polling())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))