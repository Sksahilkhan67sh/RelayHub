from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import AlertEventOut, AlertRuleOut, TestAlertResponse


class NotificationsResource:
    """
    "Notifications" maps to RelayHub's alert rules: Slack, Discord, webhook, or
    email notifications fired when an endpoint's failure rate crosses a threshold.
    There is no separate /notifications API in the backend -- this resource is
    kept under that name because that's the developer-facing concept it serves,
    while every method below hits the real /v1/alerts/* routes.
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create_rule(
        self,
        *,
        condition_type: str,
        channel: str,
        channel_config: dict[str, Any],
        severity: str = "warning",
        threshold_config: dict[str, Any] | None = None,
        throttle_window_minutes: int | None = None,
        is_enabled: bool = True,
        options: RequestOptions | None = None,
    ) -> AlertRuleOut:
        """POST /v1/alerts/rules"""
        body = {
            "condition_type": condition_type,
            "severity": severity,
            "channel": channel,
            "channel_config": channel_config,
            "threshold_config": threshold_config or {},
            "throttle_window_minutes": throttle_window_minutes,
            "is_enabled": is_enabled,
        }
        return self._transport.request("POST", "/v1/alerts/rules", body, options)

    def list_rules(self, options: RequestOptions | None = None) -> list[AlertRuleOut]:
        """GET /v1/alerts/rules"""
        return self._transport.request("GET", "/v1/alerts/rules", None, options)

    def update_rule(self, rule_id: str, *, options: RequestOptions | None = None, **fields: Any) -> AlertRuleOut:
        """PATCH /v1/alerts/rules/{id}"""
        return self._transport.request("PATCH", f"/v1/alerts/rules/{rule_id}", fields, options)

    def delete_rule(self, rule_id: str, options: RequestOptions | None = None) -> None:
        """DELETE /v1/alerts/rules/{id} -- 204 No Content on success."""
        return self._transport.request("DELETE", f"/v1/alerts/rules/{rule_id}", None, options)

    def test_rule(self, rule_id: str, options: RequestOptions | None = None) -> TestAlertResponse:
        """POST /v1/alerts/rules/{id}/test -- fires a test notification through the rule's configured channel."""
        return self._transport.request("POST", f"/v1/alerts/rules/{rule_id}/test", None, options)

    def history(
        self, *, condition_type: str | None = None, limit: int = 50, offset: int = 0, options: RequestOptions | None = None
    ) -> list[AlertEventOut]:
        """GET /v1/alerts/history"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "condition_type": condition_type, "limit": limit, "offset": offset}
        return self._transport.request("GET", "/v1/alerts/history", None, opts)
