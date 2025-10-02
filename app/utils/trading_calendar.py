from datetime import date
from ..fiin_client import get_client
import pandas as pd


def is_trading_day(today: date) -> bool:
    """Heuristic: trading day iff last VNINDEX 1D bar date == today.
    On API errors/empty data, return False to avoid false-positive alerts (holidays).
    """
    try:
        c = get_client()
        df = c.Fetch_Trading_Data(realtime=False, tickers=["VNINDEX"], by="1d", period=3).get_data()
        if df is None or len(df) == 0:
            return False
        last_ts = pd.to_datetime(df["timestamp"]).max().date()
        return last_ts == today
    except Exception:
        return False
