"""
Stock News Scheduler - Configuration Module

Loads settings from .env file or environment variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if it exists
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


# --- Scheduler ---
SCHEDULER_INTERVAL_MINUTES: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))

# --- Storage ---
DB_PATH: str = os.getenv("DB_PATH", "stock_news.db")

# --- News Search ---
MAX_NEWS_PER_STOCK: int = int(os.getenv("MAX_NEWS_PER_STOCK", "5"))
NEWS_LANG: str = os.getenv("NEWS_LANG", "zh-TW")

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8758046809:AAGhCwitXf7q5QN291zZe3nLEZ1tDyHRw5U")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "1055293440")
