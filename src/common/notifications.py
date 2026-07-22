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

# Hardcoded (not locale.setlocale): locale availability differs between the dev
# machine and Render, and process-wide locale state is a hazard not worth it here.
_WEEKDAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_MONTHS_ES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]


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


def _to_madrid(value: datetime) -> datetime:
    """Naive-UTC (or aware) datetime -> aware datetime in Madrid local time."""
    aware = value.replace(tzinfo=_UTC) if value.tzinfo is None else value
    return aware.astimezone(_MADRID)


def _format_when(date_route: datetime) -> str:
    """'dd/mm/YYYY HH:MM' in Madrid local time (cancel/update/delete announcements)."""
    return _to_madrid(date_route).strftime("%d/%m/%Y %H:%M")


def _format_date_es(value: datetime) -> str:
    """'Jueves, 23 de jul de 2026' in Madrid local time."""
    madrid = _to_madrid(value)
    weekday = _WEEKDAYS_ES[madrid.weekday()]
    month = _MONTHS_ES[madrid.month - 1]
    return f"{weekday}, {madrid.day} de {month} de {madrid.year}"


def _format_time_es(value: datetime) -> str:
    """'20:00' in Madrid local time."""
    return _to_madrid(value).strftime("%H:%M")


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
    title: str,
    date_route: datetime,
    paces: list[str],
    primary_point_name: str,
    secondary_point_name: str | None,
    secondary_point_time: datetime | None,
    description: str | None,
    link: str,
) -> str:
    """Assemble the caption, capped at 1024 (UTF-16) with the link ALWAYS last.

    Only the "Comentarios" block (the description) is trimmed on overflow — every
    other block (header, schedule, meeting points, link) is fixed-size and never cut.
    """
    header = f'<b>¡Rut4! "{_escape(title)}"</b>'
    info_block = "\n".join(
        [
            f"• Fecha: {_format_date_es(date_route)}",
            f"• Hora: {_format_time_es(date_route)} h",
            f"• Ritmo: {', '.join(paces)}",
            f"• Punto de encuentro: {_escape(primary_point_name)}",
        ]
    )

    secondary_block = None
    if secondary_point_name:
        secondary_lines = [f"• SEGUNDO Punto de encuentro: {_escape(secondary_point_name)}"]
        if secondary_point_time is not None:
            secondary_lines.append(f"• Hora: {_format_time_es(secondary_point_time)} h")
        secondary_block = "\n".join(secondary_lines)

    body = _clean_caption_html(description) if description else ""

    def assemble(desc: str) -> str:
        blocks = [header, info_block]
        if secondary_block:
            blocks.append(secondary_block)
        if desc:
            blocks.append(f"• Comentarios: {desc}")
        blocks.append(f"Puedes ver más detalles y apuntarte en: {link}")
        return "\n\n".join(blocks)

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
    paces: list[str],
    primary_point_name: str,
    secondary_point_name: str | None = None,
    secondary_point_time: datetime | None = None,
) -> None:
    """Announce a new route call: sendPhoto with the cover, or sendMessage if none."""
    caption = _build_caption(
        title,
        date_route,
        paces,
        primary_point_name,
        secondary_point_name,
        secondary_point_time,
        description,
        _detail_url(route_call_id),
    )
    if image:
        _post("sendPhoto", {"photo": image, "caption": caption, "parse_mode": "HTML"})
    else:
        _post("sendMessage", {"text": caption, "parse_mode": "HTML"})


def _announce(heading: str, *, title: str, date_route: datetime, link: str | None) -> None:
    """Shared shape for the cancel/update/delete announcements: heading + title +
    date, with the detail link ONLY when the route call still exists to link to."""
    text = (
        f"<b>{heading}</b>\n\n"
        f"<b>{_escape(title)}</b>\n"
        f"📅 {_format_when(date_route)}"
    )
    if link:
        text += f"\n\n{link}"
    _post("sendMessage", {"text": text, "parse_mode": "HTML"})


def notify_route_call_cancelled(
    *, route_call_id: str, title: str, date_route: datetime
) -> None:
    """Announce a cancellation so people who only saw it on Telegram find out (D6)."""
    _announce(
        "❌ Rut4 cancelada",
        title=title,
        date_route=date_route,
        link=_detail_url(route_call_id),
    )


def notify_route_call_updated(
    *, route_call_id: str, title: str, date_route: datetime
) -> None:
    """Announce an edit so people who saw it on Telegram know to check the details."""
    _announce(
        "✏️ Rut4 actualizada",
        title=title,
        date_route=date_route,
        link=_detail_url(route_call_id),
    )


def notify_route_call_deleted(*, title: str, date_route: datetime) -> None:
    """Announce a deletion (D23): no link, the route call no longer resolves —
    people who saw it on Telegram but never confirmed attendance should still
    know not to show up."""
    _announce("🗑️ Rut4 eliminada", title=title, date_route=date_route, link=None)
