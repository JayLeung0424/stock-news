"""
Stock News Scheduler - Main Entry Point

Usage:
    python main.py              # Start the scheduler (runs every hour)
    python main.py --once       # Run once and exit
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger

import config


def setup_logging():
    """Configure loguru logging."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
    )
    logger.add(
        "logs/stock_news_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        compression="gz",
        encoding="utf-8",
    )


def run_once():
    """Run a single fetch cycle and exit."""
    import storage
    from scheduler import news_fetch_job

    storage.init_db()
    news_fetch_job()
    logger.info("Single run completed. Exiting.")


def run_scheduler():
    """Start the recurring scheduler."""
    from scheduler import start_scheduler
    start_scheduler()


def main():
    parser = argparse.ArgumentParser(
        description="Stock News Scheduler - Fetch news for S&P 500 stocks",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single fetch cycle and exit (no scheduling).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help=f"Override scheduler interval in minutes (default: {config.SCHEDULER_INTERVAL_MINUTES}).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help=f"Override database path (default: {config.DB_PATH}).",
    )

    args = parser.parse_args()

    # Apply overrides
    if args.interval:
        config.SCHEDULER_INTERVAL_MINUTES = args.interval
    if args.db:
        config.DB_PATH = args.db

    setup_logging()

    logger.info("Stock News Scheduler starting ...")
    logger.info("  Stock universe: S&P 500")
    logger.info(f"  Interval:     {config.SCHEDULER_INTERVAL_MINUTES} min")
    logger.info(f"  News/stock:   {config.MAX_NEWS_PER_STOCK}")
    logger.info(f"  Language:     {config.NEWS_LANG}")
    logger.info(f"  Database:     {config.DB_PATH}")

    if args.once:
        run_once()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
