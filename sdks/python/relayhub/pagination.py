"""
RelayHub's list endpoints return a plain JSON array (no envelope, no cursor) and
take `limit`/`offset` query params. `paginate` wraps any "fetch a page" callable
into a generator so callers can walk an entire result set without manually
tracking offsets:

    for job in paginate(lambda limit, offset: client.dlq.list(limit=limit, offset=offset)):
        ...
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TypeVar

T = TypeVar("T")


def paginate(fetch_page: Callable[[int, int], list[T]], page_size: int = 50) -> Iterator[T]:
    offset = 0
    while True:
        page = fetch_page(page_size, offset)
        yield from page
        if len(page) < page_size:
            return
        offset += page_size


def collect_all(fetch_page: Callable[[int, int], list[T]], page_size: int = 50) -> list[T]:
    """Collects every page into a single list. Convenient for small result sets; prefer `paginate` for large ones."""
    return list(paginate(fetch_page, page_size))
