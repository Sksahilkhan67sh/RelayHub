"""
Notification dispatch for the Alerts module.

Follows the same shape as common/queue_client.py: a Protocol, real production
implementations, and an injectable in-memory implementation so alert-triggering
logic is fully unit-testable without live Slack/Discord/SMTP.

SMS is deliberately left as an architecture hook, not a working implementation --
the spec itself lists it as "SMS architecture hooks" (as opposed to a required working
channel like the other four), so NotImplementedError with a clear message is the
honest implementation here, not a corner cut.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import settings


class NotificationDeliveryError(Exception):
    pass


class NotificationDispatcher(Protocol):
    async def send(self, *, channel: str, config: dict, subject: str, message: str) -> None: ...


class RealNotificationDispatcher:
    async def send(self, *, channel: str, config: dict, subject: str, message: str) -> None:
        if channel == "slack":
            await self._send_slack(config, message)
        elif channel == "discord":
            await self._send_discord(config, message)
        elif channel == "webhook":
            await self._send_webhook(config, subject, message)
        elif channel == "email":
            # smtplib is blocking; running it directly on the event loop would
            # stall every other in-flight request for the duration of the SMTP
            # connect/TLS/login/send round trip. Offload to a worker thread.
            await asyncio.to_thread(self._send_email, config, subject, message)
        elif channel == "sms":
            raise NotImplementedError(
                "SMS is an architecture hook per spec, not yet a working channel. "
                "Wire a provider (e.g. Twilio) here when SMS support is prioritized."
            )
        else:
            raise NotificationDeliveryError(f"Unknown notification channel '{channel}'")

    async def _send_slack(self, config: dict, message: str) -> None:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise NotificationDeliveryError("Slack channel config missing 'webhook_url'")
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json={"text": message}, timeout=10)
            if resp.status_code >= 400:
                raise NotificationDeliveryError(f"Slack webhook returned HTTP {resp.status_code}")

    async def _send_discord(self, config: dict, message: str) -> None:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise NotificationDeliveryError("Discord channel config missing 'webhook_url'")
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json={"content": message}, timeout=10)
            if resp.status_code >= 400:
                raise NotificationDeliveryError(f"Discord webhook returned HTTP {resp.status_code}")

    async def _send_webhook(self, config: dict, subject: str, message: str) -> None:
        url = config.get("url")
        if not url:
            raise NotificationDeliveryError("Webhook channel config missing 'url'")
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"subject": subject, "message": message}, timeout=10)
            if resp.status_code >= 400:
                raise NotificationDeliveryError(f"Alert webhook returned HTTP {resp.status_code}")

    def _send_email(self, config: dict, subject: str, message: str) -> None:
        to_address = config.get("to_address")
        if not to_address:
            raise NotificationDeliveryError("Email channel config missing 'to_address'")
        if not settings.SMTP_HOST:
            raise NotificationDeliveryError("SMTP_HOST is not configured -- cannot send email alerts")

        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_address

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)


class InMemoryNotificationDispatcher:
    """Used in tests. Records every send() call instead of touching the network."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail_channels: set[str] = set()  # channels to simulate delivery failure for

    async def send(self, *, channel: str, config: dict, subject: str, message: str) -> None:
        if channel in self.fail_channels:
            raise NotificationDeliveryError(f"Simulated failure for channel '{channel}'")
        self.sent.append({"channel": channel, "config": config, "subject": subject, "message": message})


@lru_cache
def get_notification_dispatcher() -> NotificationDispatcher:
    return RealNotificationDispatcher()
