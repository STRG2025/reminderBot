import asyncio
from aiogram import Bot
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)