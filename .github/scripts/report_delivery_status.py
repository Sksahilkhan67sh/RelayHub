#!/usr/bin/env python3
"""Prints a status breakdown for delivery jobs. Reads a JSONL file where each
line is the JSON array returned by GET /v1/deliveries/by-event/{id} for one
published event (there's no "list all deliveries" endpoint, only per-event
lookup -- see .github/workflows/live-delivery-test.yml).

Kept as a real script file rather than embedded inline in the workflow YAML,
since a multi-line Python block inside a YAML block scalar is fragile
(indentation rules collide between the two languages)."""
import json
import sys


def main() -> None:
    path = sys.argv[1]
    jobs: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, list):
                jobs.extend(parsed)
            else:
                print(f"  (unexpected response, not a list): {parsed}")

    if not jobs:
        print("No delivery jobs found for any published event.")
        return

    by_status: dict[str, int] = {}
    for job in jobs:
        status = job.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    print(f"Total delivery jobs: {len(jobs)}")
    print("Status breakdown:", by_status)
    for job in jobs:
        print(f"  {job.get('id')}: status={job.get('status')} attempt={job.get('attempt_number')}/{job.get('max_attempts')}")


if __name__ == "__main__":
    main()
