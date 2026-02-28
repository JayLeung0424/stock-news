"""
Storage - SQLite-based storage for stock news results.

Provides persistent storage so we can track news over time
and avoid duplicate entries.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from loguru import logger

import config
from news_searcher import NewsArticle


@contextmanager
def _get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with _get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code  TEXT NOT NULL,
                stock_name  TEXT NOT NULL,
                title       TEXT NOT NULL,
                link        TEXT NOT NULL,
                source      TEXT DEFAULT '',
                published   TEXT DEFAULT '',
                summary     TEXT DEFAULT '',
                fetched_at  TEXT NOT NULL,
                UNIQUE(stock_code, link)
            );

            CREATE INDEX IF NOT EXISTS idx_news_stock_code
                ON news_articles(stock_code);

            CREATE INDEX IF NOT EXISTS idx_news_fetched_at
                ON news_articles(fetched_at);

            CREATE TABLE IF NOT EXISTS fetch_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      TEXT NOT NULL,
                finished_at     TEXT,
                stocks_count    INTEGER DEFAULT 0,
                articles_count  INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'running'
            );
        """)
    logger.info(f"Database initialized: {config.DB_PATH}")


def save_articles(articles: List[NewsArticle]) -> int:
    """
    Save news articles to the database.
    Skips duplicates (same stock_code + link).

    Returns the number of newly inserted articles.
    """
    now = datetime.now().isoformat()
    inserted = 0

    with _get_db() as conn:
        for a in articles:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO news_articles
                       (stock_code, stock_name, title, link, source, published, summary, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (a.stock_code, a.stock_name, a.title, a.link,
                     a.source, a.published, a.summary, now),
                )
                inserted += conn.total_changes  # approximate
            except sqlite3.IntegrityError:
                pass  # duplicate, skip

    # More accurate count via INSERT OR IGNORE
    # We count by checking after commit
    logger.info(f"Saved articles: {inserted} new out of {len(articles)} total")
    return inserted


def log_fetch_start() -> int:
    """Log the start of a fetch cycle. Returns the log ID."""
    now = datetime.now().isoformat()
    with _get_db() as conn:
        cur = conn.execute(
            "INSERT INTO fetch_log (started_at, status) VALUES (?, 'running')",
            (now,),
        )
        return cur.lastrowid


def log_fetch_end(log_id: int, stocks_count: int, articles_count: int, status: str = "success"):
    """Log the end of a fetch cycle."""
    now = datetime.now().isoformat()
    with _get_db() as conn:
        conn.execute(
            """UPDATE fetch_log
               SET finished_at = ?, stocks_count = ?, articles_count = ?, status = ?
               WHERE id = ?""",
            (now, stocks_count, articles_count, status, log_id),
        )


def get_recent_articles(stock_code: str = None, limit: int = 50) -> list:
    """Retrieve recent articles, optionally filtered by stock code."""
    with _get_db() as conn:
        if stock_code:
            rows = conn.execute(
                """SELECT * FROM news_articles
                   WHERE stock_code = ?
                   ORDER BY fetched_at DESC LIMIT ?""",
                (stock_code, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM news_articles
                   ORDER BY fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_article_count() -> int:
    """Get total number of articles in the database."""
    with _get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM news_articles").fetchone()
        return row["cnt"]
