"""
News Searcher - Search latest news for given stocks.

Uses Google News RSS feed (free, no API key required) to fetch
recent news articles for each stock symbol / name.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from loguru import logger

import config


@dataclass
class NewsArticle:
    """Represents a single news article."""
    stock_code: str
    stock_name: str
    title: str
    link: str
    source: str
    published: Optional[str] = None   # human-readable datetime
    published_dt: Optional[datetime] = None
    summary: str = ""


# ---------------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------------

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _build_google_news_url(query: str, lang: str = None) -> str:
    """Build a Google News RSS search URL."""
    lang = lang or config.NEWS_LANG
    # Map lang to Google hl/gl parameters
    hl_map = {
        "zh-HK": ("zh-HK", "HK"),
        "zh-TW": ("zh-TW", "TW"),
        "zh-CN": ("zh-CN", "CN"),
        "en": ("en", "US"),
    }
    hl, gl = hl_map.get(lang, ("zh-HK", "HK"))

    params = {
        "q": query,
        "hl": hl,
        "gl": gl,
        "ceid": f"{gl}:{hl}",
    }
    return f"{_GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"


def search_news_for_stock(
    stock_code: str,
    stock_name: str,
    max_results: int = None,
) -> List[NewsArticle]:
    """
    Search news for a single stock using Google News RSS.

    Parameters
    ----------
    stock_code : str
        Stock code, e.g. "HK.00700".
    stock_name : str
        Stock name, e.g. "腾讯控股".
    max_results : int
        Max number of articles to return.

    Returns
    -------
    list[NewsArticle]
    """
    max_results = max_results or config.MAX_NEWS_PER_STOCK
    articles: List[NewsArticle] = []

    # Build search query: combine name + code for better results
    # Strip market prefix from code for cleaner search
    clean_code = stock_code.split(".")[-1] if "." in stock_code else stock_code
    query = f"{stock_name} {clean_code} stock"

    url = _build_google_news_url(query)
    logger.debug(f"Fetching news for {stock_code} ({stock_name}): {url}")

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Feed parse error for {stock_code}: {feed.bozo_exception}")
            return articles

        for entry in feed.entries[:max_results]:
            pub_dt = None
            pub_str = entry.get("published", "")
            if pub_str:
                try:
                    # feedparser provides time struct
                    ts = entry.get("published_parsed")
                    if ts:
                        pub_dt = datetime(*ts[:6])
                except Exception:
                    pass

            # Extract source from title (Google News format: "Title - Source")
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1] if len(parts) > 1 else ""

            summary = ""
            raw_summary = entry.get("summary", "")
            if raw_summary:
                # Strip HTML tags from summary
                summary = BeautifulSoup(raw_summary, "html.parser").get_text(strip=True)

            articles.append(
                NewsArticle(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    title=title.strip(),
                    link=entry.get("link", ""),
                    source=source.strip(),
                    published=pub_str,
                    published_dt=pub_dt,
                    summary=summary[:500],  # cap summary length
                )
            )

        logger.debug(f"Found {len(articles)} articles for {stock_code}")

    except Exception as e:
        logger.error(f"Error searching news for {stock_code}: {e}")

    return articles


def search_news_batch(
    stocks: list,
    max_per_stock: int = None,
    delay: float = 1.0,
) -> List[NewsArticle]:
    """
    Search news for a batch of stocks.

    Parameters
    ----------
    stocks : list[StockInfo]
        List of stocks to search news for.
    max_per_stock : int
        Max articles per stock.
    delay : float
        Delay in seconds between requests to avoid rate limiting.

    Returns
    -------
    list[NewsArticle]
        All collected news articles.
    """
    all_articles: List[NewsArticle] = []
    total = len(stocks)

    for i, stock in enumerate(stocks, 1):
        logger.info(f"[{i}/{total}] Searching news for {stock.code} ({stock.name}) ...")
        try:
            articles = search_news_for_stock(
                stock_code=stock.code,
                stock_name=stock.name,
                max_results=max_per_stock,
            )
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"Error processing {stock.code}: {e}")

        # Rate limiting
        if i < total:
            time.sleep(delay)

    logger.info(f"Total news articles collected: {len(all_articles)}")
    return all_articles


if __name__ == "__main__":
    # Quick test
    articles = search_news_for_stock("HK.00700", "腾讯控股", max_results=3)
    for a in articles:
        print(f"[{a.source}] {a.title}")
        print(f"  {a.link}")
        print(f"  {a.published}")
        print()
