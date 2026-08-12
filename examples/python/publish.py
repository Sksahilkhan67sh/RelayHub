"""
Event publishing example (Python SDK).
Run: RELAYHUB_API_KEY=... python publish.py

Requires the SDK to be installed first: pip install -e ../../sdks/python
"""

import os
import sys

from relayhub import RelayHubClient, RequestOptions

api_key = os.environ.get("RELAYHUB_API_KEY")
if not api_key:
    print("Set RELAYHUB_API_KEY (an API key with the events:write scope)", file=sys.stderr)
    sys.exit(1)

with RelayHubClient(api_key=api_key, base_url=os.environ.get("RELAYHUB_BASE_URL", "https://api.relayhub.dev/v1")) as client:
    event = client.events.publish(
        event="payment.success",
        environment="test",
        payload={"order_id": "ord_123", "amount": 4200},
        options=RequestOptions(idempotency_key="ord_123-payment-success"),
    )

    print(f"Published {event['event']} -- event {event['id']}")
    print(f"{len(event['delivery_jobs'])} delivery job(s) queued:")
    for job in event["delivery_jobs"]:
        print(f"  - {job['id']} -> endpoint {job['endpoint_id']} ({job['status']})")
