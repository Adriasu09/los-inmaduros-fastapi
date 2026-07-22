"""Telegram notifications (D9/D22): env-gating, payload shape, fail-safety.

Same mocking pattern as the Clerk SDK: monkeypatch settings + httpx.post directly,
never hit the real network.
"""

from datetime import datetime

import pytest

from src.common import notifications as n

WHEN = datetime(2026, 7, 25, 17, 0)  # naive UTC -> 19:00 Madrid


@pytest.fixture()
def telegram_configured(monkeypatch):
    """Simulate a configured bot: both env vars present."""
    monkeypatch.setattr(n.settings, "TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setattr(n.settings, "TELEGRAM_CHAT_ID", "12345")


@pytest.fixture()
def recorded_posts(monkeypatch):
    """Replace httpx.post with a fake that records every call and returns 200 OK."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})

        class FakeResponse:
            status_code = 200
            text = ""

        return FakeResponse()

    monkeypatch.setattr(n.httpx, "post", fake_post)
    return calls


def test_without_credentials_httpx_is_never_called(monkeypatch):
    # Force the "unconfigured" state explicitly: the real .env (dev machine, CI)
    # may or may not have real credentials, and this test must not depend on that.
    monkeypatch.setattr(n.settings, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(n.settings, "TELEGRAM_CHAT_ID", None)
    calls = []
    monkeypatch.setattr(n.httpx, "post", lambda *a, **k: calls.append((a, k)))

    n.notify_route_call_created(
        route_call_id="rc-1",
        title="Ruta del Retiro",
        description="<p>Hola</p>",
        image="https://img/cover.jpg",
        date_route=WHEN,
        paces=["ROCA"],
        primary_point_name="Plaza de Callao",
    )

    assert calls == []


def test_created_with_image_sends_photo_with_clean_truncated_caption(
    telegram_configured, recorded_posts
):
    long_html = "<p>" + ("bla <strong>fuerte</strong> " * 200) + "</p>"

    n.notify_route_call_created(
        route_call_id="rc-1",
        title="Ruta del Retiro",
        description=long_html,
        image="https://img/cover.jpg",
        date_route=WHEN,
        paces=["ROCA", "CARACOL"],
        primary_point_name="Plaza de Callao",
    )

    assert len(recorded_posts) == 1
    call = recorded_posts[0]
    assert call["url"].endswith("/sendPhoto")
    payload = call["json"]
    assert payload["chat_id"] == "12345"
    assert payload["photo"] == "https://img/cover.jpg"
    assert payload["parse_mode"] == "HTML"
    caption = payload["caption"]
    assert "Ritmo: ROCA, CARACOL" in caption
    assert "Punto de encuentro: Plaza de Callao" in caption
    # Tiptap HTML cleaned: no <p>/<strong>, but <b> survives (mapped from <strong>)
    assert "<p>" not in caption
    assert "<strong>" not in caption
    assert caption.count("<b>") == caption.count("</b>")
    # Truncated to Telegram's real (UTF-16) limit, link always present
    assert n._tg_len(caption) <= n.CAPTION_LIMIT
    assert caption.rstrip().endswith("/events/rc-1")
    assert call["timeout"] == n.TIMEOUT_SECONDS


def test_created_with_secondary_point_shows_its_own_time(
    telegram_configured, recorded_posts
):
    n.notify_route_call_created(
        route_call_id="rc-1",
        title="Ruta del Retiro",
        description=None,
        image=None,
        date_route=WHEN,
        paces=["ROCA"],
        primary_point_name="Plaza de Callao",
        secondary_point_name="Atocha",
        secondary_point_time=datetime(2026, 7, 25, 17, 30),
    )

    caption = recorded_posts[0]["json"]["text"]
    assert "SEGUNDO Punto de encuentro: Atocha" in caption
    assert "19:30" in caption  # 17:30 UTC -> Madrid summer time


def test_created_without_image_sends_message(telegram_configured, recorded_posts):
    n.notify_route_call_created(
        route_call_id="rc-1",
        title="Ruta corta",
        description=None,
        image=None,
        date_route=WHEN,
        paces=["ROCA"],
        primary_point_name="Plaza de Callao",
    )

    assert len(recorded_posts) == 1
    call = recorded_posts[0]
    assert call["url"].endswith("/sendMessage")
    assert "photo" not in call["json"]
    assert "Ruta corta" in call["json"]["text"]


def test_httpx_failure_does_not_propagate(telegram_configured, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(n.httpx, "post", boom)

    # Must return normally: a Telegram failure can never break the caller.
    n.notify_route_call_created(
        route_call_id="rc-1",
        title="Ruta",
        description=None,
        image=None,
        date_route=WHEN,
        paces=["ROCA"],
        primary_point_name="Plaza de Callao",
    )


def test_cancelled_sends_message_announcing_cancellation(
    telegram_configured, recorded_posts
):
    n.notify_route_call_cancelled(route_call_id="rc-1", title="Ruta", date_route=WHEN)

    assert len(recorded_posts) == 1
    call = recorded_posts[0]
    assert call["url"].endswith("/sendMessage")
    assert "cancelada" in call["json"]["text"].lower()
    assert "Ruta" in call["json"]["text"]


def test_updated_sends_message_announcing_the_edit(telegram_configured, recorded_posts):
    n.notify_route_call_updated(route_call_id="rc-1", title="Ruta", date_route=WHEN)

    assert len(recorded_posts) == 1
    call = recorded_posts[0]
    assert call["url"].endswith("/sendMessage")
    assert "actualizada" in call["json"]["text"].lower()
    assert "Ruta" in call["json"]["text"]


def test_deleted_sends_message_without_link(telegram_configured, recorded_posts):
    """D23: deletion has NO route_call_id/link — the page would 404 afterwards."""
    n.notify_route_call_deleted(title="Ruta", date_route=WHEN)

    assert len(recorded_posts) == 1
    call = recorded_posts[0]
    assert call["url"].endswith("/sendMessage")
    text = call["json"]["text"]
    assert "eliminada" in text.lower()
    assert "Ruta" in text
    assert "http" not in text  # no link at all
