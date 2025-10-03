# tests/ping_notifier.py
from app.notifier import TelegramNotifier

if __name__ == "__main__":
    TelegramNotifier.send("✅ Ping: Hello fen", parse_mode="HTML")
