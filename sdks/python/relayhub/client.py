from __future__ import annotations

import re
from typing import Any

import httpx

from .http import Transport, TransportConfig
from .resources.analytics import AnalyticsResource
from .resources.api_keys import ApiKeysResource
from .resources.audit import AuditResource
from .resources.auth import AuthResource
from .resources.billing import BillingResource
from .resources.deliveries import DeliveriesResource
from .resources.dlq import DlqResource
from .resources.endpoints import EndpointsResource
from .resources.events import EventsResource
from .resources.insights import InsightsResource
from .resources.notifications import NotificationsResource
from .resources.organizations import OrganizationsResource

DEFAULT_BASE_URL = "https://api.relayhub.dev/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2


class RelayHubClient:
    """
    Official RelayHub API client.

        client = RelayHubClient(api_key="rh_live_...")
        endpoint = client.endpoints.create(name="Prod", url="https://example.com/hook")

    Or build one with the fluent builder:

        client = (
            RelayHubClient.builder()
            .api_key(os.environ["RELAYHUB_API_KEY"])
            .timeout(10.0)
            .max_retries(3)
            .build()
        )
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: dict[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RelayHubClient requires an api_key")

        # base_url may be passed with or without the trailing /v1 -- resource paths
        # below always use the literal "/v1/..." form documented in docs/api.
        normalized_base = re.sub(r"/v1/?$", "", base_url).rstrip("/")

        transport = Transport(
            TransportConfig(
                base_url=normalized_base,
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                default_headers=default_headers or {},
                http_client=http_client,
            )
        )

        self.auth = AuthResource(transport)
        self.api_keys = ApiKeysResource(transport)
        self.organizations = OrganizationsResource(transport)
        self.endpoints = EndpointsResource(transport)
        self.events = EventsResource(transport)
        self.deliveries = DeliveriesResource(transport)
        self.dlq = DlqResource(transport)
        self.analytics = AnalyticsResource(transport)
        self.insights = InsightsResource(transport)
        self.billing = BillingResource(transport)
        self.notifications = NotificationsResource(transport)
        self.audit = AuditResource(transport)
        self._transport = transport

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> RelayHubClient:  # noqa: PYI034 - typing.Self requires Python 3.11+; this SDK supports 3.10+
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @staticmethod
    def builder() -> RelayHubClientBuilder:
        return RelayHubClientBuilder()


class RelayHubClientBuilder:
    def __init__(self) -> None:
        self._kwargs: dict[str, Any] = {}

    def api_key(self, api_key: str) -> RelayHubClientBuilder:
        self._kwargs["api_key"] = api_key
        return self

    def base_url(self, base_url: str) -> RelayHubClientBuilder:
        self._kwargs["base_url"] = base_url
        return self

    def timeout(self, timeout: float) -> RelayHubClientBuilder:
        self._kwargs["timeout"] = timeout
        return self

    def max_retries(self, max_retries: int) -> RelayHubClientBuilder:
        self._kwargs["max_retries"] = max_retries
        return self

    def header(self, name: str, value: str) -> RelayHubClientBuilder:
        headers = dict(self._kwargs.get("default_headers") or {})
        headers[name] = value
        self._kwargs["default_headers"] = headers
        return self

    def http_client(self, client: httpx.Client) -> RelayHubClientBuilder:
        self._kwargs["http_client"] = client
        return self

    def build(self) -> RelayHubClient:
        if "api_key" not in self._kwargs:
            raise ValueError("RelayHubClientBuilder: api_key(...) is required before build()")
        return RelayHubClient(**self._kwargs)
