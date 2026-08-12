from __future__ import annotations

from relayhub import collect_all, paginate


def test_paginate_walks_every_page():
    pages = {0: [1, 2], 2: [3, 4], 4: [5]}

    def fetch_page(limit: int, offset: int) -> list[int]:
        return pages.get(offset, [])

    collected = list(paginate(fetch_page, page_size=2))
    assert collected == [1, 2, 3, 4, 5]


def test_paginate_stops_on_empty_first_page():
    assert list(paginate(lambda limit, offset: [], page_size=10)) == []


def test_collect_all_returns_flat_list():
    pages = {0: ["a", "b"], 2: ["c"]}
    result = collect_all(lambda limit, offset: pages.get(offset, []), page_size=2)
    assert result == ["a", "b", "c"]
