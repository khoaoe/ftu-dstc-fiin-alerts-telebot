import time
import threading
from datetime import date
from FiinQuantX import BarDataUpdate
from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import compute_features_v12, apply_v12_on_last_day
from ..utils.trading_calendar import is_trading_day
from ..state import load_state, save_state

_event_day = None
_state = load_state()
_last_ts_day = _state.get("last_ts_day", None)


def _on_bar_1d(data: BarDataUpdate):
    global _last_ts_day
    df = data.to_dataFrame().sort_values(["ticker", "timestamp"])  # includes historical + running day
    feat = compute_features_v12(df)
    if "timestamp" not in feat.columns or feat.empty:
        return
    last_ts = feat["timestamp"].max()
    if _last_ts_day == last_ts:
        return

    picks = apply_v12_on_last_day(feat)  # apply on running day bar
    if picks:
        TelegramNotifier.send("<b>[Day-Running V12]</b> " + ", ".join(picks), parse_mode="HTML")
    _last_ts_day = last_ts
    _state["last_ts_day"] = _last_ts_day
    save_state(_state)


def start_intraday_day_stream(block: bool = False):
    if not is_trading_day(date.today()):
        return
    client = get_client()

    def _runner():
        global _event_day
        backoff = 1
        while True:
            try:
                _event_day = client.Fetch_Trading_Data(
                    realtime=True,
                    tickers=list(CFG.tickers),
                    fields=['open','high','low','close','volume','bu','sd','fb','fs','fn'],
                    adjusted=True,
                    by='1d',
                    callback=_on_bar_1d,
                    wait_for_full_timeFrame=False  # running day bar updates
                )
                _event_day.get_data()
                while not _event_day._stop:
                    time.sleep(1)
                backoff = 1
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

    if block:
        _runner()
    else:
        threading.Thread(target=_runner, daemon=True).start()


def stop_intraday_day_stream():
    try:
        _event_day.stop()
    except Exception:
        pass
