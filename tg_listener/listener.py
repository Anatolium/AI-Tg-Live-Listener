import os
from telethon import TelegramClient, events
from pathlib import Path
from dotenv import load_dotenv

# Находим путь к папке, где лежит этот файл (tg_listener)
current_file_path = Path(__file__).resolve()

# Переходим на уровень выше (в корень проекта)
project_root = current_file_path.parent.parent

# Указываем точный путь к .env
env_path = project_root / '.env'

load_dotenv(dotenv_path=env_path)


class TelegramListener:
    def __init__(self, db_manager):
        self.db = db_manager
        self.monitored_usernames = set()
        self.is_running = False

        # Получаем данные из .env
        api_id = os.getenv("TG_API_ID")
        api_hash = os.getenv("TG_API_HASH")
        session_name = os.getenv("TG_SESSION_NAME", "tg_listener")

        if not api_id or not api_hash:
            raise ValueError("❌ Ошибка: TG_API_ID или TG_API_HASH не найдены в .env!")

        self.client = TelegramClient(session_name, int(api_id), api_hash)

    async def update_monitored_channels(self):
        """Обновляем список отслеживаемых каналов из БД."""
        channels = await self.db.get_monitored_channels()
        self.monitored_usernames = {ch.username.lower() for ch in channels}
        print(f"🔄 Отслеживаемые каналы обновлены: {self.monitored_usernames}")

    async def start(self):
        await self.client.start()
        print(f"✅ Telethon клиент запущен (сессия: {os.getenv('TG_SESSION_NAME')})")

        # Загружаем каналы при старте
        await self.update_monitored_channels()

        @self.client.on(events.NewMessage())
        async def handler(event):
            try:
                chat = await event.get_chat()
                if not hasattr(chat, 'username') or not chat.username:
                    return

                if chat.username.lower() in self.monitored_usernames:
                    # Найти канал в БД по юзернейму
                    async with self.db.session_factory() as session:
                        from tg_listener.db import Channel
                        from sqlalchemy import select
                        result = await session.execute(
                            select(Channel).where(Channel.username == chat.username)
                        )
                        channel = result.scalar_one_or_none()
                        if not channel:
                            return

                        # ✅ Проверяем, начинается ли текст с "Пожалуйста, подождите"
                        text = event.text or ""
                        if text.startswith("Пожалуйста, подождите"):
                            # print(f"⚠️ Сообщение из {chat.username} проигнорировано: начинается с 'Пожалуйста, подождите'")
                            return

                        await self.db.save_message(
                            channel_id=channel.id,
                            msg_id=event.id,
                            sender_id=str(event.sender_id),
                            text=text
                        )
                        print(f"✅ Сообщение из {chat.username} сохранено!")
            except Exception as e:
                print(f"⚠️ Ошибка в обработчике: {e}")

        await self.client.run_until_disconnected()
