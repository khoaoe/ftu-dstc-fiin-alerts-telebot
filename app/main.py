import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import CFG
from .jobs.eod_scan import run_eod_scan
from .jobs.intraday_stream import start_intraday_stream, stop_intraday_stream
from .jobs.intraday_day_stream import start_intraday_day_stream, stop_intraday_day_stream


async def main():
    sch = AsyncIOScheduler(timezone=CFG.tz)
    # EOD daily (confirm-on-close)
    sch.add_job(run_eod_scan, CronTrigger(day_of_week="mon-fri", hour=15, minute=5))
    # 15m early flow: open 09:00, stop 15:00
    sch.add_job(lambda: start_intraday_stream(block=False), CronTrigger(day_of_week="mon-fri", hour=9, minute=0))
    sch.add_job(stop_intraday_stream, CronTrigger(day_of_week="mon-fri", hour=15, minute=0))
    # Day-running V12 (1d bar, updating): open 09:00, stop 15:00
    sch.add_job(lambda: start_intraday_day_stream(block=False), CronTrigger(day_of_week="mon-fri", hour=9, minute=0))
    sch.add_job(stop_intraday_day_stream, CronTrigger(day_of_week="mon-fri", hour=15, minute=0))

    sch.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        stop_intraday_stream()
        stop_intraday_day_stream()


if __name__ == "__main__":
    asyncio.run(main())
