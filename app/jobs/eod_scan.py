from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import compute_picks_from_daily_df

def run_eod_scan():
    client = get_client()
    data = client.Fetch_Trading_Data(
        realtime=False,
        tickers=list(CFG.tickers),
        fields=['open','high','low','close','volume','bu','sd','fb','fs','fn'],
        adjusted=True,
        by='1d',
        period=260
    ).get_data()

    last_ts = data["timestamp"].max()
    df_last = data[data["timestamp"] == last_ts].copy()

    picks = compute_picks_from_daily_df(df_last)
    tg = TelegramNotifier()
    tg.send("<b>[EOD] V12 picks</b>: " + ", ".join(picks) if picks else "<b>[EOD]</b> Không có mã đạt filter hôm nay.")
