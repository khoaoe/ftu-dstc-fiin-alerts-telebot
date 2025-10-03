# app/jobs/eod_scan.py
from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import compute_picks_from_history

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

    # DÙNG CHUẨN V12: tính feature trên toàn lịch sử, rồi áp filter last-day
    picks = compute_picks_from_history(data)

    # Optional exclude list (e.g., VNINDEX, VN30) from config
    if getattr(CFG, "exclude_tickers", None):
        picks = [p for p in picks if p.upper() not in CFG.exclude_tickers]

    tg = TelegramNotifier()
    tg.send("<b>[EOD] V12 picks</b>: " + ", ".join(picks) if picks else "<b>[EOD]</b> Không có mã đạt filter hôm nay.")
