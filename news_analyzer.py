"""
News Analyzer - Use GitHub Models (GPT-4o-mini) to analyze and rank news.

Sends collected news articles to GPT-4o-mini via the GitHub Models API
to get professional-grade analysis including:
  1. Importance score (0-100)
  2. Sentiment (bullish / bearish / neutral)
  3. Chinese summary of the news
  4. Chinese impact analysis on stock price
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI
from loguru import logger

import config


# ---------------------------------------------------------------------------
# GitHub Models client
# ---------------------------------------------------------------------------

_GITHUB_MODELS_URL = "https://models.inference.ai.azure.com"

def _get_client() -> OpenAI:
    """Create an OpenAI client targeting GitHub Models."""
    return OpenAI(
        base_url=_GITHUB_MODELS_URL,
        api_key=config.GITHUB_TOKEN,
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AnalyzedArticle:
    """A news article with LLM-powered analysis."""
    stock_code: str
    stock_name: str
    title: str
    link: str
    source: str
    published: str
    summary: str                # Original summary
    importance_score: int       # 0-100
    sentiment: str              # "bullish", "bearish", "neutral"
    sentiment_score: int        # -10 to +10
    impact_summary: str         # Chinese impact description
    news_summary_zh: str        # Chinese news summary


# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一位專業的股市新聞分析師。你的任務是分析新聞對股票價格的影響。

對於每則新聞，你需要回傳以下 JSON 格式：
{
  "importance": <0-100整數，代表這則新聞對股價的重要程度>,
  "sentiment": "<bullish|bearish|neutral>",
  "sentiment_score": <-10到+10的整數，正數代表看漲，負數代表看跌>,
  "summary_zh": "<用中文一句話概述新聞內容，最多50字>",
  "impact_zh": "<用中文分析這則新聞對股價可能的影響，最多80字>"
}

評分標準：
- importance 90-100：重大事件（財報大幅超預期/不及預期、併購、破產、CEO更換、FDA審批結果）
- importance 70-89：較重要（分析師大幅調整評級、重要合作、重大訴訟、大規模裁員）
- importance 50-69：中等重要（產品發布、一般業績更新、行業趨勢）
- importance 30-49：一般（普通評論、市場概述）
- importance 0-29：低重要性（花邊新聞、重複報導、與股價無關）

sentiment_score 判斷：
- +7 到 +10：強烈利多（財報大幅超預期、重大利好合約等）
- +3 到 +6：利多（業績良好、分析師看好等）
- -2 到 +2：中性（不確定方向、影響有限）
- -6 到 -3：利空（業績下滑、負面消息等）
- -10 到 -7：強烈利空（重大虧損、欺詐醜聞、破產等）

請務必只回傳合法 JSON，不要加任何多餘文字。"""


def _analyze_batch_with_llm(articles_data: list[dict]) -> list[dict]:
    """
    Send a batch of articles to GPT-4o-mini for analysis.

    Parameters
    ----------
    articles_data : list[dict]
        List of {"index": int, "stock": str, "title": str, "summary": str}.

    Returns
    -------
    list[dict]
        List of LLM analysis results.
    """
    if not articles_data:
        return []

    # Build the user prompt with all articles
    lines = ["請分析以下新聞，回傳一個 JSON 陣列，每個元素對應一則新聞：\n"]
    for item in articles_data:
        lines.append(
            f"[{item['index']}] 股票: {item['stock']}\n"
            f"    標題: {item['title']}\n"
            f"    摘要: {item['summary'][:200]}\n"
        )
    user_prompt = "\n".join(lines)
    user_prompt += "\n請回傳 JSON 陣列，格式為 [{...}, {...}, ...]，按照上面的順序。"

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        results = json.loads(raw)
        if isinstance(results, dict):
            results = [results]
        return results

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}\nRaw: {raw[:500]}")
        return []
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        return []


def analyze_and_rank(
    articles: list,
    top_n: int = 10,
    batch_size: int = 15,
) -> List[AnalyzedArticle]:
    """
    Analyze all articles using GPT-4o-mini and return the top N.

    Sends articles in batches to the LLM, then ranks by importance.

    Parameters
    ----------
    articles : list[NewsArticle]
        Raw news articles from the news searcher.
    top_n : int
        Number of top articles to return.
    batch_size : int
        Articles per LLM request (to stay within token limits).

    Returns
    -------
    list[AnalyzedArticle]
        Top N articles sorted by importance (descending).
    """
    if not articles:
        return []

    if not config.GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not configured — cannot use LLM analysis")
        return []

    # Prepare article data for LLM
    all_data = []
    for i, a in enumerate(articles):
        all_data.append({
            "index": i,
            "stock": f"{a.stock_code} ({a.stock_name})",
            "title": a.title,
            "summary": a.summary or a.title,
        })

    # Send in batches
    all_results: list[Optional[dict]] = [None] * len(articles)
    total_batches = (len(all_data) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, len(all_data))
        batch = all_data[start:end]

        logger.info(f"LLM 分析批次 {batch_num + 1}/{total_batches} ({len(batch)} 則新聞) ...")

        results = _analyze_batch_with_llm(batch)

        # Map results back
        for j, result in enumerate(results):
            idx = start + j
            if idx < len(all_results):
                all_results[idx] = result

        # Rate limiting between batches
        if batch_num < total_batches - 1:
            time.sleep(2)

    # Build AnalyzedArticle list
    analyzed: List[AnalyzedArticle] = []
    for i, article in enumerate(articles):
        result = all_results[i]
        if result is None:
            # Fallback for failed analysis
            result = {
                "importance": 20,
                "sentiment": "neutral",
                "sentiment_score": 0,
                "summary_zh": article.title,
                "impact_zh": "分析失敗，無法判斷影響",
            }

        try:
            sentiment = result.get("sentiment", "neutral")
            if sentiment not in ("bullish", "bearish", "neutral"):
                sentiment = "neutral"

            analyzed.append(AnalyzedArticle(
                stock_code=article.stock_code,
                stock_name=article.stock_name,
                title=article.title,
                link=article.link,
                source=article.source or "",
                published=article.published or "",
                summary=article.summary or "",
                importance_score=max(0, min(100, int(result.get("importance", 20)))),
                sentiment=sentiment,
                sentiment_score=max(-10, min(10, int(result.get("sentiment_score", 0)))),
                impact_summary=str(result.get("impact_zh", "無法判斷")),
                news_summary_zh=str(result.get("summary_zh", article.title)),
            ))
        except Exception as e:
            logger.warning(f"Failed to parse LLM result for '{article.title[:40]}': {e}")

    # Sort by importance descending, then by absolute sentiment score
    analyzed.sort(key=lambda x: (x.importance_score, abs(x.sentiment_score)), reverse=True)

    top = analyzed[:top_n]
    if top:
        logger.info(
            f"LLM 分析完成：共 {len(analyzed)} 則，選出 Top {len(top)} "
            f"（分數範圍：{top[-1].importance_score}–{top[0].importance_score}）"
        )
    else:
        logger.info(f"LLM 分析完成：共 {len(analyzed)} 則，無結果")

    return top
