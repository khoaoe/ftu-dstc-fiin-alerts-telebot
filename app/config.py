from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Settings:
    fiin_user: str = os.getenv("FIIN_USER", "")
    fiin_pass: str = os.getenv("FIIN_PASS", "")
    bot_token: str = os.getenv("BOT_TOKEN", "")
    chat_id: str   = os.getenv("CHAT_ID", "")
    thread_id: int = int(os.getenv("THREAD_ID", "0") or "0")
    tickers: list  = tuple([s.strip().upper() for s in os.getenv("TICKERS","VNINDEX,VCB,FPT").split(",")])
    tz: str        = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

CFG = Settings()
