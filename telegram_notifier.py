"""
Telegram Notifier - Send stock news summaries to Telegram.

Uses the Telegram Bot API to send formatted news messages
to a specified chat.
"""

from __future__ import annotations

from typing import List

import requests
from loguru import logger

import config

_API_BASE = "https://api.telegram.org/bot{token}"


def _send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a single message to the configured Telegram chat.

    Parameters
    ----------
    text : str
        Message text (supports HTML formatting).
    parse_mode : str
        Telegram parse mode ("HTML" or "MarkdownV2").

    Returns
    -------
    bool
        True if the message was sent successfully.
    """
    url = f"{_API_BASE.format(token=config.TELEGRAM_BOT_TOKEN)}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            logger.error(f"Telegram API error: {data}")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_news_to_telegram(articles: list, total_found: int = 0, new_count: int = 0) -> int:
    """
    Format and send analyzed top news articles to Telegram.

    Parameters
    ----------
    articles : list[AnalyzedArticle]
        Top analyzed news articles (already ranked by importance).
    total_found : int
        Total articles found before filtering.
    new_count : int
        Number of newly inserted articles.

    Returns
    -------
    int
        Number of messages successfully sent.
    """
    if not articles:
        _send_message("📭 <b>S&amp;P 500 新聞速報</b>\n\n本次未找到重要新聞。")
        return 1

    # Sentiment emoji mapping
    sentiment_emoji = {
        "bullish": "🟢 看漲",
        "bearish": "🔴 看跌",
        "neutral": "⚪ 中性",
    }

    # Build message
    messages: List[str] = []
    header = f"📰 <b>S&amp;P 500 — 最重要 {len(articles)} 則新聞</b>\n"
    header += f"🔍 共掃描 {total_found} 則新聞"
    if new_count > 0:
        header += f"（{new_count} 則新增）"
    header += "\n"

    current_msg = header

    for i, a in enumerate(articles, 1):
        sentiment = sentiment_emoji.get(a.sentiment, "⚪ 中性")
        title = _escape_html(a.title)
        source = f" — {_escape_html(a.source)}" if a.source else ""
        stock_label = f"{a.stock_code} ({_escape_html(a.stock_name)})"
        # Use LLM-generated Chinese summary
        news_zh = _escape_html(getattr(a, 'news_summary_zh', '') or a.summary[:150])
        impact = _escape_html(a.impact_summary)

        block = f"\n<b>{'─' * 25}</b>\n"
        block += f"<b>#{i}</b>  💹 <b>{stock_label}</b>\n"
        block += f"📊 重要性: <b>{a.importance_score}/100</b>  |  {sentiment}\n"
        block += f'📰 <a href="{a.link}">{title}</a>{source}\n'
        if news_zh:
            block += f"📝 {news_zh}\n"
        block += f"💡 {impact}\n"

        if len(current_msg) + len(block) > 3800:
            messages.append(current_msg)
            current_msg = f"📰 <b>S&amp;P 500 重要新聞（續）</b>\n"

        current_msg += block

    if current_msg.strip():
        messages.append(current_msg)

    # Send all messages
    sent = 0
    for i, msg in enumerate(messages):
        logger.debug(f"Sending Telegram message {i + 1}/{len(messages)} ({len(msg)} chars)")
        if _send_message(msg):
            sent += 1

    logger.info(f"Telegram: sent {sent}/{len(messages)} messages")
    return sent


def send_error_to_telegram(error_msg: str) -> bool:
    """Send an error notification to Telegram."""
    text = f"⚠️ <b>股票新聞錯誤</b>\n\n{_escape_html(error_msg)}"
    return _send_message(text)


if __name__ == "__main__":
    # Quick test
    ok = _send_message("✅ <b>Stock News Bot</b> is connected!")
    print(f"Test message sent: {ok}")
