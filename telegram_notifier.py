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


def send_news_to_telegram(articles: list, new_count: int = 0) -> int:
    """
    Format and send news articles to Telegram.

    Groups articles by stock and sends in batches to avoid
    Telegram's 4096-character message limit.

    Parameters
    ----------
    articles : list[NewsArticle]
        List of news articles to send.
    new_count : int
        Number of newly inserted articles (for the summary header).

    Returns
    -------
    int
        Number of messages successfully sent.
    """
    if not articles:
        _send_message("📭 <b>Stock News Update</b>\n\nNo news articles found this cycle.")
        return 1

    # Group articles by stock
    by_stock: dict[str, list] = {}
    for a in articles:
        key = f"{a.stock_code} ({a.stock_name})"
        by_stock.setdefault(key, []).append(a)

    # Build messages in chunks (respect 4096 char limit)
    messages: List[str] = []
    current_msg = f"📰 <b>S&amp;P 500 News Update</b>\n"
    current_msg += f"🕐 Found <b>{len(articles)}</b> articles for <b>{len(by_stock)}</b> stocks"
    if new_count > 0:
        current_msg += f" (<b>{new_count}</b> new)"
    current_msg += "\n"

    for stock_label, stock_articles in by_stock.items():
        stock_block = f"\n<b>{'─' * 20}</b>\n"
        stock_block += f"💹 <b>{_escape_html(stock_label)}</b>\n"

        for a in stock_articles:
            title = _escape_html(a.title)
            source = f" — {_escape_html(a.source)}" if a.source else ""
            line = f'  • <a href="{a.link}">{title}</a>{source}\n'
            stock_block += line

        # Check if adding this block exceeds limit
        if len(current_msg) + len(stock_block) > 3800:
            messages.append(current_msg)
            current_msg = f"📰 <b>S&amp;P 500 News (cont.)</b>\n"

        current_msg += stock_block

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
    text = f"⚠️ <b>Stock News Error</b>\n\n{_escape_html(error_msg)}"
    return _send_message(text)


if __name__ == "__main__":
    # Quick test
    ok = _send_message("✅ <b>Stock News Bot</b> is connected!")
    print(f"Test message sent: {ok}")
