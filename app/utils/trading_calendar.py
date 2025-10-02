from datetime import date
from ..fiin_client import get_client


def is_trading_day(today: date) -> bool:
    """Heuristic: query recent VNINDEX bars; if last bar's date == today -> trading day.
    Avoids maintaining a holiday list. If API unavailable, default to True to avoid accidental skips.
    """
    try:
        c = get_client()
        df = c.Fetch_Trading_Data(realtime=False, tickers=["VNINDEX"], by="1d", period=3).get_data()
        if df.empty:
            return True
        last_ts = str(df["timestamp"].max())[:10]
        return last_ts == str(today)
    except Exception:
        return True
