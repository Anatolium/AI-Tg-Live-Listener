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

        # Получаем данные из .env
        api_id = os.getenv("TG_API_ID")
        api_hash = os.getenv("TG_API_HASH")
        session_name = os.getenv("TG_SESSION_NAME", "tg_listener")

        if not api_id or not api_hash:
            raise ValueError("❌ Ошибка: TG_API_ID или TG_API_HASH не найдены в .env!")

        # Telethon требует API_ID как целое число
        self.client = TelegramClient(session_name, int(api_id), api_hash)
        self.is_running = False

    async def start(self):
        # При первом запуске здесь в консоли PyCharm появится запрос кода
        await self.client.start()
        print(f"✅ Telethon клиент запущен (сессия: {os.getenv('TG_SESSION_NAME')})")

        @self.client.on(events.NewMessage())
        async def handler(event):
            active_channel = await self.db.get_active_channel()
            if not active_channel:
                return

            chat = await event.get_chat()
            # # Проверка соответствия канала (по username или chat_id)
            # if hasattr(chat, 'username') and chat.username == active_channel.username:
            #     from tg_listener.db import Message as MsgModel
            #
            #     async with self.db.session_factory() as session:
            #         new_msg = MsgModel(
            #             msg_id=event.id,
            #             chat_id=active_channel.id,
            #             sender=str(event.sender_id),
            #             text=event.text or "[Медиа]",
            #             date=event.date  # Используем дату сообщения из Telegram
            #         )
            #         session.add(new_msg)
            #         await session.commit()
            #     print(f"📥 Новое сообщение сохранено из @{chat.username}")

            # Логика сравнения: проверяем username или ID
            is_target = False
            if hasattr(chat, 'username') and chat.username == active_channel.username:
                if chat.username.lower() == active_channel.username.lower():
                    is_target = True

            if is_target:
                # Сохраняем в БД (как в вашем коде ранее)
                await self.db.save_message(
                    channel_id=active_channel.id,
                    msg_id=event.id,
                    sender_id=str(event.sender_id),
                    text=event.text or ""
                )
                print(f"✅ Сообщение из {active_channel.username} сохранено!")

        await self.client.run_until_disconnected()

    async def restart(self):
        print("🔄 Перезапуск логики мониторинга (смена активного канала)...")
        # В данной реализации фильтрация происходит внутри handler через БД
