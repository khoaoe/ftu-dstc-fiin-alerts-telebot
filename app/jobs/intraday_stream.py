import time
import threading
from FiinQuantX import BarDataUpdate
from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import early_signal_from_15m_bar

_event = None
_last_alert = {}  # ticker -> last_bar_ts
_tg = TelegramNotifier()


def _on_bar_15m(data: BarDataUpdate):
    df = data.to_dataFrame().sort_values(["ticker", "timestamp"])
    for tk, g in df.groupby("ticker"):
        if len(g) < 2:
            continue
        prev = g.iloc[-2]  # only handle the closed 15' candle
        if _last_alert.get(tk) == prev["timestamp"]:
            continue
        if early_signal_from_15m_bar(prev):
            _tg.send(f"<b>[15’ Early]</b> {tk} — BU/SD lệch dương, vol tích cực @ {prev['timestamp']}")
            _last_alert[tk] = prev["timestamp"]


def start_intraday_stream(block: bool = False):
    """Start 15' stream during trading window. If block=False, run in a daemon thread."""
    client = get_client()

    def _runner():
        global _event
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
        try:
            while not _event._stop:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_intraday_stream()

    if block:
        _runner()
    else:
        threading.Thread(target=_runner, daemon=True).start()


def stop_intraday_stream():
    try:
        _event.stop()
    except Exception:
        pass
