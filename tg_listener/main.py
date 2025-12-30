import asyncio
import os
import sys
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
from hypercorn.asyncio import serve
from hypercorn.config import Config

from tg_listener.db import Database
from tg_listener.listener import TelegramListener

# Настройка путей, чтобы main.py видел соседние файлы и корень
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

# Инициализация Flask
# Теперь не нужно указывать пути явно, так как папки внутри tg_listener/
app = Flask(__name__)
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

    # Получаем список всех каналов и текущий активный
    all_channels = await db.get_all_channels()
    active = await db.get_active_channel()
    return render_template("channels.html", channels=all_channels, active=active)


@app.route("/channels/activate/<int:channel_id>")
async def activate_channel(channel_id: int):
    await db.set_active_channel(channel_id)
    # Здесь можно добавить логику уведомления листенера о смене канала,
    # если вы решите фильтровать сообщения на лету.
    return redirect(url_for("channels"))


@app.route("/stats")
async def stats():
    stats_data = await db.get_stats()
    return render_template("stats.html", stats=stats_data)


# @app.route("/messages")
# async def messages():
#     # Получаем последние 50 сообщений из базы для отображения
#     async with db.session_factory() as session:
#         from sqlalchemy import select
#         from tg_listener.db import Message, Channel
#
#         # Запрос на получение сообщений вместе с названиями каналов
#         stmt = select(Message, Channel).join(Channel).order_by(Message.date.desc()).limit(50)
#         result = await session.execute(stmt)
#         rows = result.all()  # Получим список кортежей (Message, Channel)
#
#     return render_template("messages.html", rows=rows)


@app.route("/messages")
async def messages():
    async with db.session_factory() as session:
        from sqlalchemy import select
        from tg_listener.db import Summary, Channel

        # Исправлено: используем channel_id вместо chat_id
        stmt = (
            select(Summary, Channel)
            .join(Channel, Summary.channel_id == Channel.id)
            .order_by(Summary.created_at.desc())
            .limit(30)
        )
        result = await session.execute(stmt)
        rows = result.all()

    return render_template("messages.html", rows=rows)


async def main():
    # 1. Инициализируем базу данных (создаем таблицы в tg_monitor.db)
    await db.init_db()

    # 2. Запускаем фоновую задачу прослушивания Telegram
    # Используем create_task, чтобы листенер работал параллельно с сайтом
    listener_task = asyncio.create_task(listener.start())

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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Приложение остановлено пользователем")
