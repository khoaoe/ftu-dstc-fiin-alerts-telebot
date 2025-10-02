import time
import threading
from datetime import date
from FiinQuantX import BarDataUpdate
from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import early_signal_from_15m_bar
from ..utils.trading_calendar import is_trading_day
from ..state import load_state, save_state

_event = None
_tg = TelegramNotifier()
_state = load_state()
_last_alert = _state.get("last_alert_15m", {})  # ticker -> last_bar_ts


def _on_bar_15m(data: BarDataUpdate):
    df = data.to_dataFrame().sort_values(["ticker", "timestamp"])
    for tk, g in df.groupby("ticker"):
        if len(g) < 2:
            continue
        prev = g.iloc[-2]  # closed 15' candle
        if _last_alert.get(tk) == prev["timestamp"]:
            continue
        if early_signal_from_15m_bar(prev):
            try:
                px = float(prev.get("close", 0.0))
                op = float(prev.get("open", 0.0))
                chg = (px / op - 1) * 100 if op else 0.0
                vol = int(prev.get("volume", 0))
                _tg.send(f"<b>[15’ Early]</b> {tk} | {px:.2f} ({chg:+.2f}%) | vol {vol:,} @ {prev['timestamp']}")
            finally:
                _last_alert[tk] = prev["timestamp"]
                _state["last_alert_15m"] = _last_alert
                save_state(_state)


def start_intraday_stream(block: bool = False):
    if not is_trading_day(date.today()):
        return
    client = get_client()

    def _runner():
        global _event
        backoff = 1
        while True:
            try:
                _event = client.Fetch_Trading_Data(
                    realtime=True,
                    tickers=list(CFG.tickers),
                    fields=['open','high','low','close','volume','bu','sd','fb','fs','fn'],
                    adjusted=True,
                    by='15m',
                    callback=_on_bar_15m,
                    wait_for_full_timeFrame=True
                )
                _event.get_data()
                while not _event._stop:
                    time.sleep(1)
                backoff = 1  # reset after a clean stop
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

    if block:
        _runner()
    else:
        threading.Thread(target=_runner, daemon=True).start()


def stop_intraday_stream():
    try:
        _event.stop()
    except Exception:
        pass
