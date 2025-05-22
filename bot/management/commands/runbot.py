import asyncio
from django.core.management.base import BaseCommand
from zudrasonbot.bot.bot_logic import BotHandler


class Command(BaseCommand):
    help = 'Запускает Telegram бота Zudrason'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Запуск Telegram-бота...'))

        try:
            bot_handler = BotHandler()
            asyncio.run(bot_handler.start_polling())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Бот остановлен вручную (Ctrl+C).'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Ошибка при запуске бота: {e}'))
