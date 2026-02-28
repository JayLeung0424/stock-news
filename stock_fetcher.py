"""
Stock Fetcher - Fetch top 200 hot stocks from Futu (富途).

Uses the Futu OpenD API (futu-api) to retrieve the current
hottest stocks across HK, US, and CN markets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from futu import (
    Market,
    OpenQuoteContext,
    RET_OK,
    SortField,
    SimpleFilter,
)
from loguru import logger

import config


@dataclass
class StockInfo:
    """Represents a single stock entry."""
    code: str            # e.g. "HK.00700"
    name: str            # e.g. "腾讯控股"
    market: str          # e.g. "HK"
    last_price: float = 0.0
    change_rate: float = 0.0   # percent
    turnover: float = 0.0      # 成交額
    volume: float = 0.0        # 成交量


def _connect(host: str = None, port: int = None) -> OpenQuoteContext:
    """Create and return a Futu OpenQuoteContext."""
    host = host or config.FUTU_HOST
    port = port or config.FUTU_PORT
    ctx = OpenQuoteContext(host=host, port=port)
    return ctx


def fetch_hot_stocks(
    market: Market = Market.HK,
    count: int = None,
) -> List[StockInfo]:
    """
    Fetch top hot stocks from Futu for a given market.

    Uses the stock filter / plate data to retrieve popularity-ranked stocks.

    Parameters
    ----------
    market : Market
        Futu market enum (Market.HK, Market.US, Market.SH, Market.SZ).
    count : int
        Number of stocks to return (default from config).

    Returns
    -------
    list[StockInfo]
        List of hot stocks sorted by popularity / turnover.
    """
    count = count or config.HOT_STOCK_COUNT
    ctx = None
    stocks: List[StockInfo] = []

    try:
        ctx = _connect()
        logger.info(f"Fetching top {count} hot stocks for market {market} ...")

        # Use get_stock_filter to get high-turnover stocks (proxy for "hot")
        simple_filter = SimpleFilter()
        simple_filter.filter_min = 0
        simple_filter.stock_field = SimpleFilter.StockField.TURNOVER_RATE
        simple_filter.is_no_filter = False
        simple_filter.sort = SortField.TURNOVER_RATE
        simple_filter.is_ascending = False

        ret, ls = ctx.get_stock_filter(
            market=market,
            filter_list=[simple_filter],
            begin=0,
            num=count,
        )

        if ret != RET_OK:
            logger.error(f"Failed to fetch stock filter: {ls}")
            return stocks

        for _, row in ls.iterrows():
            stocks.append(
                StockInfo(
                    code=row.get("stock_code", ""),
                    name=row.get("stock_name", ""),
                    market=str(market),
                    last_price=float(row.get("cur_price", 0)),
                    change_rate=float(row.get("change_rate", 0)),
                    turnover=float(row.get("turnover", 0)),
                    volume=float(row.get("volume", 0)),
                )
            )

        logger.info(f"Fetched {len(stocks)} hot stocks from {market}")

    except Exception as e:
        logger.error(f"Error fetching hot stocks: {e}")
    finally:
        if ctx is not None:
            ctx.close()

    return stocks


def fetch_all_market_hot_stocks() -> List[StockInfo]:
    """
    Fetch top 200 hot stocks across multiple Futu markets.

    Combines results from HK, US, SH, SZ and deduplicates,
    returning up to HOT_STOCK_COUNT stocks ranked by turnover rate.
    """
    target = config.HOT_STOCK_COUNT
    markets = [Market.HK, Market.US, Market.SH, Market.SZ]
    all_stocks: List[StockInfo] = []
    per_market = max(target // len(markets), 50)

    for mkt in markets:
        try:
            batch = fetch_hot_stocks(market=mkt, count=per_market)
            all_stocks.extend(batch)
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Skipping market {mkt}: {e}")

    # Deduplicate by code
    seen = set()
    unique: List[StockInfo] = []
    for s in all_stocks:
        if s.code not in seen:
            seen.add(s.code)
            unique.append(s)

    # Sort by turnover descending and take top N
    unique.sort(key=lambda s: s.turnover, reverse=True)
    result = unique[:target]
    logger.info(f"Total unique hot stocks collected: {len(result)}")
    return result


if __name__ == "__main__":
    # Quick test
    from loguru import logger
    logger.add("debug.log", level="DEBUG")
    stocks = fetch_hot_stocks(market=Market.HK, count=10)
    for s in stocks:
        print(f"{s.code:>12}  {s.name:<20}  price={s.last_price:>10.2f}  chg={s.change_rate:>+6.2f}%")
