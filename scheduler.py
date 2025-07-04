from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем планировщик с UTC временем
scheduler = AsyncIOScheduler(timezone=pytz.UTC)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен")