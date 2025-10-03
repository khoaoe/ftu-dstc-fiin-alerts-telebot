from datetime import date
from ..fiin_client import get_client
import pandas as pd
from datetime import date


def is_trading_day(today: date) -> bool:
    """Simple VN trading calendar: Mon–Fri."""
    return today.weekday() < 5