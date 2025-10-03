import time
import requests
from .config import CFG
import os, time, requests, json

class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None, thread_id: int | None = None):
        self.token = token or CFG.bot_token
        self.chat_id = chat_id or CFG.chat_id
        self.thread_id = thread_id if thread_id is not None else (CFG.thread_id or None)

    def _send(self, text: str, parse_mode: str = "HTML", retries: int = 3, backoff: float = 1.0):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
        if self.thread_id:
            payload["message_thread_id"] = self.thread_id  # send into specific topic

        last_err = None
        for attempt in range(retries):
            try:
                r = requests.post(url, data=payload, timeout=10)
                if r.status_code == 429:
                    retry_after = 1
                    try:
                        retry_after = int(r.json().get("parameters", {}).get("retry_after", retry_after))
                    except Exception:
                        retry_after = int(r.headers.get("Retry-After", retry_after))
                    time.sleep(max(1, retry_after))
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last_err = exc
                time.sleep(backoff * (2 ** attempt))
        raise last_err

    def send_message(self, text: str, parse_mode: str = "HTML", retries: int = 3, backoff: float = 1.0):
        return self._send(text=text, parse_mode=parse_mode, retries=retries, backoff=backoff)

    @classmethod
    def send(cls, text: str, parse_mode: str = "HTML"):
        """
        Gui tin nhan toi TELEGRAM CHAT_ID.
        - Tu doc BOT_TOKEN, CHAT_ID, THREAD_ID tu env/config.
        - Neu THREAD_ID ton tai -> them message_thread_id vao payload de gui vao topic.
        - Ho tro parse_mode='HTML'.
        - Co backoff 429 dua tren Retry-After (neu da code roi thi giu nguyen).
        """
        return cls()._send(text=text, parse_mode=parse_mode)
