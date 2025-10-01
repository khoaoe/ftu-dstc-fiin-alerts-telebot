import time
import requests
from .config import CFG

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None, thread_id: int | None = None):
        self.token = token or CFG.bot_token
        self.chat_id = chat_id or CFG.chat_id
        self.thread_id = thread_id if thread_id is not None else (CFG.thread_id or None)

    def send(self, text: str, parse_mode: str = "HTML", retries: int = 3, backoff: float = 1.0):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
        if self.thread_id:
            payload["message_thread_id"] = self.thread_id  # send into specific Topic
        last_err = None
        for i in range(retries):
            try:
                r = requests.post(url, data=payload, timeout=10)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                time.sleep(backoff * (2**i))
        raise last_err
