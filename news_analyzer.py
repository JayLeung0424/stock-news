"""
News Analyzer - Score and rank news articles by importance.

Uses keyword-based heuristics to estimate:
  1. Importance score (how significant the news is)
  2. Sentiment / price impact (bullish, bearish, or neutral)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from loguru import logger


# ---------------------------------------------------------------------------
# Keyword dictionaries with weights
# ---------------------------------------------------------------------------

# High-importance keywords (major market-moving events)
_HIGH_IMPORTANCE = {
    # Earnings & financials
    "earnings": 8, "revenue": 7, "profit": 7, "loss": 7, "quarterly": 6,
    "annual report": 7, "guidance": 7, "forecast": 6, "outlook": 6,
    "beat expectations": 9, "miss expectations": 9, "beat estimates": 9,
    "missed estimates": 9, "eps": 6, "income": 5,
    # Major corporate events
    "merger": 9, "acquisition": 9, "acquire": 9, "buyout": 9, "takeover": 9,
    "ipo": 8, "spinoff": 8, "spin-off": 8, "bankruptcy": 10, "bankrupt": 10,
    "restructuring": 7, "layoff": 7, "layoffs": 7, "job cuts": 7,
    "dividend": 6, "stock split": 8, "buyback": 6, "share repurchase": 6,
    # Regulatory & legal
    "sec": 6, "fda approval": 9, "fda": 7, "lawsuit": 7, "settlement": 7,
    "investigation": 7, "fraud": 8, "regulatory": 6, "antitrust": 7,
    "sanctions": 7, "ban": 6, "recall": 7,
    # Leadership
    "ceo": 7, "cfo": 6, "resign": 7, "fired": 7, "appointed": 6,
    "steps down": 7, "new leadership": 6,
    # Market impact
    "crash": 9, "surge": 8, "plunge": 8, "soar": 8, "rally": 7,
    "all-time high": 8, "record high": 8, "52-week low": 7, "52-week high": 7,
    "halt": 8, "halted": 8, "delisted": 9, "downgrade": 7, "upgrade": 7,
    # Macro
    "fed": 6, "interest rate": 7, "inflation": 6, "tariff": 7, "trade war": 7,
    "recession": 8, "stimulus": 7,
}

# Medium-importance keywords
_MEDIUM_IMPORTANCE = {
    "analyst": 4, "rating": 4, "target price": 5, "price target": 5,
    "partnership": 5, "contract": 5, "deal": 5, "agreement": 4,
    "launch": 4, "product": 3, "innovation": 3, "patent": 4,
    "expansion": 4, "market share": 5, "growth": 4, "decline": 4,
    "warning": 5, "risk": 4, "concern": 3, "uncertainty": 3,
    "insider": 5, "insider trading": 7, "insider buying": 6, "insider selling": 6,
    "supply chain": 4, "shortage": 5, "disruption": 5,
}

# Bullish (positive) keywords
_BULLISH_KEYWORDS = {
    "beat": 3, "beats": 3, "surpass": 3, "exceed": 3, "exceeded": 3,
    "surge": 3, "soar": 3, "rally": 3, "gain": 2, "gains": 2,
    "rise": 2, "rising": 2, "jump": 3, "jumps": 3, "up": 1,
    "growth": 2, "strong": 2, "record": 2, "momentum": 2,
    "upgrade": 3, "outperform": 3, "buy": 2, "bullish": 3,
    "positive": 2, "optimistic": 2, "boost": 2, "recovery": 2,
    "approval": 3, "approved": 3, "breakthrough": 3, "innovation": 2,
    "expansion": 2, "profit": 2, "dividend": 2, "buyback": 2,
    "all-time high": 3, "record high": 3, "beat expectations": 4,
    "beat estimates": 4, "above consensus": 3,
}

# Bearish (negative) keywords
_BEARISH_KEYWORDS = {
    "miss": 3, "missed": 3, "below": 2, "decline": 2, "declining": 2,
    "fall": 2, "falls": 2, "drop": 2, "drops": 2, "plunge": 3,
    "crash": 3, "sink": 2, "loss": 2, "losses": 2, "down": 1,
    "weak": 2, "weakness": 2, "slump": 3, "tumble": 3,
    "downgrade": 3, "underperform": 3, "sell": 2, "bearish": 3,
    "negative": 2, "concern": 2, "warning": 2, "risk": 1,
    "lawsuit": 2, "fraud": 3, "investigation": 2, "recall": 2,
    "bankruptcy": 4, "bankrupt": 4, "default": 3,
    "layoff": 2, "layoffs": 2, "job cuts": 2, "restructuring": 1,
    "miss expectations": 4, "missed estimates": 4, "below consensus": 3,
    "halt": 2, "halted": 2, "delisted": 3, "ban": 2,
    "recession": 2, "inflation": 1, "tariff": 1,
}


@dataclass
class AnalyzedArticle:
    """A news article with importance score and sentiment analysis."""
    stock_code: str
    stock_name: str
    title: str
    link: str
    source: str
    published: str
    summary: str
    importance_score: int       # 0-100
    sentiment: str              # "bullish", "bearish", "neutral"
    sentiment_score: int        # positive = bullish, negative = bearish
    impact_summary: str         # brief impact description


def _score_text(text: str, keyword_dict: dict) -> int:
    """Score text against a keyword dictionary. Returns total score."""
    text_lower = text.lower()
    total = 0
    for keyword, weight in keyword_dict.items():
        # Use word boundary matching for short keywords
        if len(keyword) <= 3:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                total += weight
        else:
            if keyword in text_lower:
                total += weight
    return total


def analyze_article(article) -> AnalyzedArticle:
    """
    Analyze a single news article for importance and sentiment.

    Parameters
    ----------
    article : NewsArticle
        The article to analyze.

    Returns
    -------
    AnalyzedArticle
        The article with scores and analysis.
    """
    text = f"{article.title} {article.summary}"

    # --- Importance scoring ---
    high_score = _score_text(text, _HIGH_IMPORTANCE)
    med_score = _score_text(text, _MEDIUM_IMPORTANCE)
    raw_importance = high_score * 2 + med_score

    # Normalize to 0-100
    importance = min(100, raw_importance)

    # Boost for known high-quality sources
    quality_sources = {"reuters", "bloomberg", "cnbc", "wsj", "wall street journal",
                       "financial times", "barron", "marketwatch", "yahoo finance",
                       "seeking alpha", "the motley fool", "investor's business daily"}
    if article.source and article.source.lower() in quality_sources:
        importance = min(100, importance + 10)

    # --- Sentiment scoring ---
    bull_score = _score_text(text, _BULLISH_KEYWORDS)
    bear_score = _score_text(text, _BEARISH_KEYWORDS)
    sentiment_score = bull_score - bear_score

    if sentiment_score >= 3:
        sentiment = "bullish"
    elif sentiment_score <= -3:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    # --- Generate impact summary ---
    impact_summary = _generate_impact_summary(
        article.stock_code, article.stock_name,
        sentiment, sentiment_score, importance
    )

    return AnalyzedArticle(
        stock_code=article.stock_code,
        stock_name=article.stock_name,
        title=article.title,
        link=article.link,
        source=article.source,
        published=article.published or "",
        summary=article.summary,
        importance_score=importance,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        impact_summary=impact_summary,
    )


def _generate_impact_summary(
    code: str, name: str, sentiment: str, score: int, importance: int
) -> str:
    """Generate a brief human-readable impact summary in Chinese."""
    strength = abs(score)

    if sentiment == "bullish":
        if strength >= 8:
            direction = "股價有強烈上漲潛力"
        elif strength >= 5:
            direction = "可能對股價產生正面影響"
        else:
            direction = "輕微正面信號"
    elif sentiment == "bearish":
        if strength >= 8:
            direction = "股價有顯著下跌風險"
        elif strength >= 5:
            direction = "可能對股價產生負面影響"
        else:
            direction = "輕微負面信號"
    else:
        direction = "中性 / 方向不明"

    if importance >= 70:
        urgency = "高度影響"
    elif importance >= 40:
        urgency = "中度影響"
    else:
        urgency = "低度影響"

    return f"{urgency} — {direction}"


def analyze_and_rank(
    articles: list,
    top_n: int = 10,
) -> List[AnalyzedArticle]:
    """
    Analyze all articles and return the top N most important ones.

    Parameters
    ----------
    articles : list[NewsArticle]
        Raw news articles.
    top_n : int
        Number of top articles to return.

    Returns
    -------
    list[AnalyzedArticle]
        Top N articles sorted by importance (descending).
    """
    if not articles:
        return []

    analyzed = []
    for a in articles:
        try:
            analyzed.append(analyze_article(a))
        except Exception as e:
            logger.warning(f"Failed to analyze article '{a.title[:50]}': {e}")

    # Sort by importance descending, then by absolute sentiment score
    analyzed.sort(key=lambda x: (x.importance_score, abs(x.sentiment_score)), reverse=True)

    top = analyzed[:top_n]
    logger.info(
        f"Analyzed {len(analyzed)} articles, selected top {len(top)} "
        f"(score range: {top[-1].importance_score}–{top[0].importance_score})"
        if top else f"Analyzed {len(analyzed)} articles, no results"
    )
    return top
