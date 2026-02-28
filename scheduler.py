"""
Scheduler - APScheduler-based hourly news fetching.

Orchestrates the full pipeline:
  1. Load S&P 500 stock list
  2. Search news for each stock
  3. Analyze & rank by importance (top 10)
  4. Store results in SQLite
  5. Send top news to Telegram
  6. Repeat every hour
"""

from __future__ import annotations

import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

import config
import storage
from news_searcher import search_news_batch
from news_analyzer import analyze_and_rank
from stock_fetcher import get_sp500_stocks
from telegram_notifier import send_news_to_telegram, send_error_to_telegram


def news_fetch_job():
    """
    Main scheduled job: fetch hot stocks → search news → store results.
    """
    job_start = datetime.now()
    logger.info("=" * 60)
    logger.info(f"[JOB START] News fetch cycle at {job_start.isoformat()}")
    logger.info("=" * 60)

    log_id = storage.log_fetch_start()

    try:
        # Step 1: Load S&P 500 stocks
        logger.info("Step 1/3: Loading S&P 500 stock list ...")
        stocks = get_sp500_stocks()

        if not stocks:
            logger.warning("No stocks fetched. Skipping news search.")
            storage.log_fetch_end(log_id, 0, 0, status="no_stocks")
            return

        logger.info(f"Fetched {len(stocks)} hot stocks.")

        # Step 2: Search news for each stock
        logger.info("Step 2/3: Searching news for stocks ...")
        articles = search_news_batch(
            stocks=stocks,
            max_per_stock=config.MAX_NEWS_PER_STOCK,
            delay=1.0,  # 1 second between requests to avoid rate limiting
        )

        logger.info(f"Found {len(articles)} news articles total.")

        # Step 3: Analyze & rank articles
        logger.info("Step 3/5: Analyzing and ranking articles ...")
        top_articles = analyze_and_rank(articles, top_n=10)
        logger.info(f"Selected top {len(top_articles)} important articles.")

        # Step 4: Store results
        logger.info("Step 4/5: Saving to database ...")
        new_count = storage.save_articles(articles)
        total_in_db = storage.get_article_count()

        # Step 5: Send top news to Telegram
        logger.info("Step 5/5: Sending top news to Telegram ...")
        try:
            tg_sent = send_news_to_telegram(top_articles, total_found=len(articles), new_count=new_count)
            logger.info(f"Telegram messages sent: {tg_sent}")
        except Exception as tg_err:
            logger.error(f"Telegram notification failed: {tg_err}")

        storage.log_fetch_end(log_id, len(stocks), len(articles), status="success")

        elapsed = (datetime.now() - job_start).total_seconds()
        logger.info(f"[JOB DONE] Cycle completed in {elapsed:.1f}s")
        logger.info(f"  Stocks processed: {len(stocks)}")
        logger.info(f"  Articles found:   {len(articles)}")
        logger.info(f"  New articles:     {new_count}")
        logger.info(f"  Total in DB:      {total_in_db}")

    except Exception as e:
        logger.exception(f"[JOB ERROR] {e}")
        storage.log_fetch_end(log_id, 0, 0, status=f"error: {e}")
        try:
            send_error_to_telegram(str(e))
        except Exception:
            pass  # Don't fail the job if TG notification fails


def start_scheduler():
    """
    Start the APScheduler with an interval trigger.
    Runs the news fetch job immediately, then every SCHEDULER_INTERVAL_MINUTES.
    """
    interval = config.SCHEDULER_INTERVAL_MINUTES

    logger.info("=" * 60)
    logger.info("  Stock News Scheduler")
    logger.info(f"  Interval: every {interval} minutes")
    logger.info("  Stock universe: S&P 500")
    logger.info(f"  Max news per stock: {config.MAX_NEWS_PER_STOCK}")
    logger.info(f"  News language: {config.NEWS_LANG}")
    logger.info(f"  Database: {config.DB_PATH}")
    logger.info("=" * 60)

    # Initialize database
    storage.init_db()

    # Create scheduler
    scheduler = BlockingScheduler()

    # Add the job with interval trigger
    scheduler.add_job(
        news_fetch_job,
        trigger=IntervalTrigger(minutes=interval),
        id="news_fetch_job",
        name="Fetch stock news",
        next_run_time=datetime.now(),  # Run immediately on start
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,  # 5 min grace
    )

    # Handle graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler ...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
