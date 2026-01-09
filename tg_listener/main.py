import asyncio
import sys
import os
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash
from hypercorn.asyncio import serve
from hypercorn.config import Config
from dotenv import load_dotenv
from tg_listener.db import Database
from tg_listener.listener import TelegramListener
import pytz

load_dotenv()

# Настройка путей, чтобы main.py видел соседние файлы и корень
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

# Инициализация Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
db = Database()
listener = TelegramListener(db)


@app.route("/")
@app.route("/channels", methods=["GET", "POST"])
async def channels():
    if request.method == "POST":
        # Получаем данные из формы (удаляем @ если пользователь его ввел)
        username = (request.form.get("username") or "").strip().lstrip("@")
        title = (request.form.get("title") or "").strip()

        if username and title:
            await db.add_channel(username=username, title=title)
        return redirect(url_for("channels"))

    # Получаем список всех каналов
    all_channels = await db.get_all_channels()
    return render_template("channels.html", channels=all_channels)


@app.route("/channels/activate/<int:channel_id>")
async def activate_channel(channel_id: int):
    await db.set_active_channel(channel_id)
    # Здесь можно добавить логику уведомления листенера о смене канала
    return redirect(url_for("channels"))


@app.route("/channels/toggle/<int:channel_id>", methods=["POST"])
async def toggle_channel(channel_id: int):
    channel = await db.get_channel_by_id(channel_id)
    if channel:
        await db.set_channel_monitored(channel_id, not channel.is_monitored)
    return redirect(url_for("channels"))


@app.route("/channels/delete/<int:channel_id>", methods=["POST"])
async def delete_channel(channel_id: int):
    deleted = await db.delete_channel(channel_id)
    if deleted:
        flash("Канал успешно удалён.", "success")
    else:
        flash("Канал не найден.", "error")
    return redirect(url_for("channels"))


@app.route("/messages")
async def messages():
    async with db.session_factory() as session:
        from sqlalchemy import select
        from tg_listener.db import Message, Channel

        # Получаем все прослушиваемые каналы
        monitored_channels = await db.get_monitored_channels()
        channel_ids = [ch.id for ch in monitored_channels]

        if not channel_ids:
            return render_template("messages.html", messages=[], total_count=0)

        # Запрос: последние 20 сообщений из прослушиваемых каналов
        stmt = (
            select(Message)
            .where(Message.chat_id.in_(channel_ids))
            .order_by(Message.date.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        total_count = len(messages)  # Можно сделать отдельным запросом, если нужно точное общее количество

    return render_template("messages.html", messages=messages, total_count=total_count)


@app.route("/summary")
async def summary():
    async with db.session_factory() as session:
        from sqlalchemy import select
        from tg_listener.db import Summary, Channel
        import pytz

        stmt = (
            select(Summary, Channel)
            .join(Channel, Summary.channel_id == Channel.id)
            .order_by(Summary.created_at.desc())
            .limit(30)
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Конвертируем время в МСК
        # tz_msk = pytz.timezone('Europe/Moscow')
        converted_rows = []
        for summary, ch in rows:
            if summary.created_at:
                # summary.created_at = summary.created_at.replace(tzinfo=pytz.utc).astimezone(tz_msk)
                summary.created_at = summary.created_at.replace(tzinfo=pytz.utc)
            converted_rows.append((summary, ch))

    return render_template("summary.html", rows=converted_rows)


async def update_channels_periodically(listener, interval=60):
    while True:
        await asyncio.sleep(interval)
        await listener.update_monitored_channels()


async def main():
    # 1. Инициализируем базу данных (создаем таблицы в tg_monitor.db)
    await db.init_db()

    # 2. Запускаем фоновую задачу прослушивания Telegram
    # Используем create_task, чтобы листенер работал параллельно с сайтом
    listener_task = asyncio.create_task(listener.start())
    updater_task = asyncio.create_task(update_channels_periodically(listener, 60))  # <-- каждые 60 сек

    # 3. Конфигурация веб-сервера Hypercorn
    config = Config()
    config.bind = ["127.0.0.1:5000"]

    print("\n" + "=" * 30)
    print("🚀 СЕРВИС ЗАПУЩЕН")
    print("🌐 Панель управления: http://127.0.0.1:5000")
    print("📢 Мониторинг Telegram активен")
    print("=" * 30 + "\n")

    try:
        await serve(app, config)
    finally:
        # При остановке сервера пробуем корректно закрыть задачу листенера
        listener_task.cancel()
        updater_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Приложение остановлено пользователем")
