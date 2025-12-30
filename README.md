# Структура проекта:

AI-Tg-Live-Listener/
├── .env
├── tg_monitor.db
├── bot/
│   ├── bot.py
│   ├── gigachat.py
│   ├── summary_service.py
│   └── utils.py
└── tg_listener/
    ├── db.py
    ├── listener.py
    ├── main.py
    ├── templates/
    │   ├── base.html
    │   ├── channels.html
    │   ├── messages.html
    │   └── stats.html
    └── static/
        └── style.css
