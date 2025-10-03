from dataclasses import dataclass
from dotenv import load_dotenv
from typing import FrozenSet
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
    exclude_tickers: FrozenSet[str] = frozenset(
        s.strip().upper()
        for s in os.getenv("EXCLUDE_TICKERS", "VNINDEX").split(",")
        if s.strip()
    )
    tz: str        = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
    # Scheduling (configurable):
    eod_hour: int   = int(os.getenv("EOD_HOUR", "15"))
    eod_minute: int = int(os.getenv("EOD_MINUTE", "5"))
    open_hour: int  = int(os.getenv("OPEN_HOUR", "9"))
    close_hour: int = int(os.getenv("CLOSE_HOUR", "15"))

CFG = Settings()
