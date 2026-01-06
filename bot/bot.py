import os
import logging
import asyncio
import sys
from pathlib import Path
import urllib3
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot
from sqlalchemy import select
from tg_listener.db import Database, Message, Summary
from summary_service import summarize_messages

# Отключаем предупреждения SSL для GigaChat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Пути и окружение
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
load_dotenv(root_dir / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tg_bot_summary")

bot = AsyncTeleBot(BOT_TOKEN)
db = Database()


@bot.message_handler(commands=["start"])
async def start_command(message):
    await bot.send_message(
        message.chat.id,
        "🤖 **Бот-суммаризатор запущен.**\n\n"
        "Команда: /summary – создать сводку по активному каналу.",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["summary"])
async def summary_command(message):
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        # Получаем **любой** отмеченный как мониторимый канал (например, первый)
        # Или можно сделать выбор канала через аргумент команды, если нужно.
        async with db.session_factory() as session:
            from tg_listener.db import Channel
            from sqlalchemy import select
            result = await session.execute(
                select(Channel).where(Channel.is_monitored == True).limit(1)
            )
            active_channel = result.scalar_one_or_none()

        async with db.session_factory() as session:
            result = await session.execute(
                select(Message)
                .where(Message.chat_id == active_channel.id)
                .where(Message.is_summarized == False)
                .order_by(Message.date.asc())
                .limit(100)
            )
            rows = result.scalars().all()

            if not rows:
                await bot.send_message(message.chat.id, f"✅ Новых сообщений в канале **{active_channel.title}** нет.",
                                       parse_mode="Markdown")
                return

            texts = [m.text for m in rows]
            start_dt = rows[0].date
            end_dt = rows[-1].date

            await bot.send_message(message.chat.id, f"🔄 Анализирую {len(rows)} сообщений...")
            summary_text = await summarize_messages(texts)

            await db.save_summary(
                channel_id=active_channel.id,
                content=summary_text,
                start_dt=start_dt,
                end_dt=end_dt
            )

            response = (
                f"📊 **Сводка: {active_channel.title}**\n"
                f"📅 Период: {start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}\n\n"
                f"{summary_text}"
            )
            await bot.send_message(message.chat.id, response, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Ошибка при создании сводки")
        await bot.send_message(message.chat.id, "⚠️ Произошла ошибка при обработке данных.")


async def run_bot():
    try:
        await db.init_db()
        logger.info("🚀 Telegram бот запущен (polling)...")
        await bot.polling(non_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.critical(f"Бот упал: {e}")
