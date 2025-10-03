import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
from .config import CFG
from .jobs.eod_scan import run_eod_scan
try:
    from .jobs.intraday_stream import start_intraday_stream, stop_intraday_stream
    from .jobs.intraday_day_stream import start_intraday_day_stream, stop_intraday_day_stream
except Exception:
    start_intraday_stream = stop_intraday_stream = lambda *a, **k: None
    start_intraday_day_stream = stop_intraday_day_stream = lambda *a, **k: None
from .notifier import TelegramNotifier
from .fiin_client import get_client

async def main():
    sch = AsyncIOScheduler(timezone=ZoneInfo(CFG.tz))
    # Boot sanity check & ping
    try:
        _ = get_client()
        TelegramNotifier.send(
            f"✅ Bot started (tz={CFG.tz}) • EOD {CFG.eod_hour:02d}:{CFG.eod_minute:02d} • 15’ {CFG.open_hour:02d}:00→{CFG.close_hour:02d}:00",
            parse_mode="HTML"
        )
    except Exception as e:
        try:
            TelegramNotifier.send(f"⚠️ Bot started nhưng lỗi đăng nhập FiinQuantX: {e}", parse_mode="HTML")
        except Exception:
            pass
        
    # EOD daily (confirm-on-close)
    sch.add_job(
        run_eod_scan,
        CronTrigger(day_of_week="mon-fri", hour=CFG.eod_hour, minute=CFG.eod_minute)
    )
    # Intraday streams (disabled by default)
    if getattr(CFG, "use_intraday", False):
        # 15m early flow: open at OPEN_HOUR, stop at CLOSE_HOUR
        sch.add_job(
            lambda: start_intraday_stream(block=False),
            CronTrigger(day_of_week="mon-fri", hour=CFG.open_hour, minute=0)
        )
        sch.add_job(
            stop_intraday_stream,
            CronTrigger(day_of_week="mon-fri", hour=CFG.close_hour, minute=0)
        )
        # Day-running V12 (1d bar, updating): same open/close window
        sch.add_job(
            lambda: start_intraday_day_stream(block=False),
            CronTrigger(day_of_week="mon-fri", hour=CFG.open_hour, minute=0)
        )
        sch.add_job(
            stop_intraday_day_stream,
            CronTrigger(day_of_week="mon-fri", hour=CFG.close_hour, minute=0)
        )

    sch.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        if getattr(CFG, "use_intraday", False):
            stop_intraday_stream()
            stop_intraday_day_stream()


if __name__ == "__main__":
    asyncio.run(main())
