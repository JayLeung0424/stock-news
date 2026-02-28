"""
Stock Fetcher - Provides S&P 500 stock list.

Returns the S&P 500 component stocks as StockInfo objects
for downstream news fetching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from loguru import logger

from sp500_stocks import SP500_STOCKS


@dataclass
class StockInfo:
    """Represents a single stock entry."""
    code: str            # e.g. "AAPL"
    name: str            # e.g. "Apple Inc."
    market: str = "US"   # All S&P 500 stocks are US market


def get_sp500_stocks() -> List[StockInfo]:
    """
    Return the full S&P 500 stock list as StockInfo objects.

    Returns
    -------
    list[StockInfo]
        All S&P 500 component stocks.
    """
    stocks = [
        StockInfo(code=ticker, name=name, market="US")
        for ticker, name in SP500_STOCKS
    ]
    logger.info(f"Loaded {len(stocks)} S&P 500 stocks")
    return stocks


if __name__ == "__main__":
    # Quick test
    stocks = get_sp500_stocks()
    for s in stocks[:20]:
        print(f"{s.code:>8}  {s.name}")
