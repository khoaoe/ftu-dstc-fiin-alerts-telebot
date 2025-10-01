import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import CFG
from .jobs.eod_scan import run_eod_scan
from .jobs.intraday_stream import start_intraday_stream, stop_intraday_stream


async def main():
    sch = AsyncIOScheduler(timezone=CFG.tz)
    sch.add_job(run_eod_scan, CronTrigger(day_of_week="mon-fri", hour=15, minute=1))
    sch.add_job(lambda: start_intraday_stream(block=False), CronTrigger(day_of_week="mon-fri", hour=9, minute=0))
    sch.add_job(stop_intraday_stream, CronTrigger(day_of_week="mon-fri", hour=15, minute=0))
    sch.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        stop_intraday_stream()


if __name__ == "__main__":
    asyncio.run(main())
