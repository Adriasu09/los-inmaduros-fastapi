import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
# Telegram caps photo captions at 1024 characters (messages allow more, but we
# keep a single limit for both paths).
CAPTION_LIMIT = 1024
# Short timeout: a slow Telegram must not hold up the background worker.
TIMEOUT_SECONDS = 3.0

_UTC = ZoneInfo("UTC")
# The community lives in Madrid; dates are stored as naive UTC, so we render the
# local wall-clock time people actually expect.
_MADRID = ZoneInfo("Europe/Madrid")


def _escape(text: str) -> str:
    """Escape plain text for Telegram HTML mode (only these three matter)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tg_len(text: str) -> int:
    """Length the way Telegram counts it: UTF-16 code units (an emoji counts 2)."""
    return len(text.encode("utf-16-le")) // 2


def _clean_caption_html(html: str) -> str:
    """Reduce Tiptap HTML to what Telegram HTML accepts"""

    text = re.sub(r"</p\s*>|<br\s*/?>|</div\s*>|</li\s*>", "\n", html, flags=re.I)
    text = re.sub(r"<(/?)strong\s*>", r"<\1b>", text, flags=re.I)
    text = re.sub(r"<(/?)em\s*>", r"<\1i>", text, flags=re.I)
    # Remove every tag that is not <b>/<i> or </b>/</i>, keeping inner text.
    text = re.sub(r"<(?!/?[bi]\s*>)[^>]*>", "", text, flags=re.I)
    text = re.sub(r"[ \t]+\n", "\n", text)  # trailing spaces the breaks may leave
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse runs of blank lines
    return text.strip()


def _close_dangling_tags(text: str) -> str:
    """Close any <b>/<i> left open (Telegram rejects unbalanced HTML)."""
    result = text
    for tag in ("b", "i"):
        opens = len(re.findall(rf"<{tag}>", result, flags=re.I))
        closes = len(re.findall(rf"</{tag}>", result, flags=re.I))
        result += f"</{tag}>" * max(opens - closes, 0)
    return result


def _format_when(date_route: datetime) -> str:
    """Naive-UTC datetime -> 'dd/mm/YYYY HH:MM' in Madrid local time."""
    aware = date_route.replace(tzinfo=_UTC) if date_route.tzinfo is None else date_route
    return aware.astimezone(_MADRID).strftime("%d/%m/%Y %H:%M")


def _detail_url(route_call_id: str) -> str:
    """Public link to the route-call detail on the frontend."""
    return f"{settings.WEBSITE_URL.rstrip('/')}/events/{route_call_id}"


def _finalize_body(prefix: str) -> str:
    """Tidy a truncated description prefix: avoid cutting inside a tag, re-balance
    any tag left open, and mark the cut with an ellipsis."""
    if "<" in prefix.rsplit(">", 1)[-1]:
        prefix = prefix[: prefix.rfind("<")]
    return _close_dangling_tags(prefix.rstrip()) + "…"


def _build_caption(
    title: str, description: str | None, date_route: datetime, link: str
) -> str:
    """Assemble the caption, capped at 1024 (UTF-16) with the link ALWAYS last"""
    
    header = f"<b>{_escape(title)}</b>"
    when = f"📅 {_format_when(date_route)}"
    body = _clean_caption_html(description) if description else ""

    def assemble(desc: str) -> str:
        parts = [header]
        if desc:
            parts.append(desc)
        parts.extend([when, link])
        return "\n\n".join(parts)

    if _tg_len(assemble(body)) <= CAPTION_LIMIT:
        return assemble(body)

    # Largest prefix length whose finalized caption still fits (binary search).
    lo, hi = 0, len(body)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _tg_len(assemble(_finalize_body(body[:mid]))) <= CAPTION_LIMIT:
            lo = mid
        else:
            hi = mid - 1
    return assemble(_finalize_body(body[:lo]))


def _post(method: str, payload: dict) -> None:
    """Call the Telegram Bot API. No-op without credentials; never raises."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return  # env-gated: disabled until both are configured

    url = f"{TELEGRAM_API}/bot{token}/{method}"
    try:
        response = httpx.post(
            url, json={"chat_id": chat_id, **payload}, timeout=TIMEOUT_SECONDS
        )
        if response.status_code != 200:
            logger.warning(
                "Telegram %s returned %s: %s",
                method,
                response.status_code,
                response.text[:300],
            )
    except Exception:
        # A Telegram failure must never propagate into the request that scheduled it.
        logger.exception("Telegram %s request failed", method)


def notify_route_call_created(
    *,
    route_call_id: str,
    title: str,
    description: str | None,
    image: str | None,
    date_route: datetime,
) -> None:
    """Announce a new route call: sendPhoto with the cover, or sendMessage if none."""
    caption = _build_caption(title, description, date_route, _detail_url(route_call_id))
    if image:
        _post("sendPhoto", {"photo": image, "caption": caption, "parse_mode": "HTML"})
    else:
        _post("sendMessage", {"text": caption, "parse_mode": "HTML"})


def _announce(
    heading: str, *, route_call_id: str, title: str, date_route: datetime
) -> None:
    """Shared shape for the cancel/update announcements: heading + title + date + link."""
    text = (
        f"<b>{heading}</b>\n\n"
        f"<b>{_escape(title)}</b>\n"
        f"📅 {_format_when(date_route)}\n\n"
        f"{_detail_url(route_call_id)}"
    )
    _post("sendMessage", {"text": text, "parse_mode": "HTML"})


def notify_route_call_cancelled(
    *, route_call_id: str, title: str, date_route: datetime
) -> None:
    """Announce a cancellation so people who only saw it on Telegram find out (D6)."""
    _announce(
        "❌ Quedada cancelada",
        route_call_id=route_call_id,
        title=title,
        date_route=date_route,
    )


def notify_route_call_updated(
    *, route_call_id: str, title: str, date_route: datetime
) -> None:
    """Announce an edit so people who saw it on Telegram know to check the details."""
    _announce(
        "✏️ Quedada actualizada",
        route_call_id=route_call_id,
        title=title,
        date_route=date_route,
    )
