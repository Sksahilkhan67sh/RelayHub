/**
 * RelayHub's list endpoints return a plain JSON array (no envelope, no cursor) and
 * take `limit`/`offset` query params -- see e.g. GET /v1/dlq, GET /v1/logs,
 * GET /v1/admin/organizations. This wraps any such "fetch a page" function into an
 * async iterator so callers can walk an entire result set without manually
 * tracking offsets:
 *
 *   for await (const job of paginate((p) => client.dlq.list({ ...p }))) { ... }
 */
export async function* paginate<T>(
  fetchPage: (page: { limit: number; offset: number }) => Promise<T[]>,
  pageSize = 50
): AsyncGenerator<T, void, unknown> {
  let offset = 0;
  for (;;) {
    const page = await fetchPage({ limit: pageSize, offset });
    for (const item of page) yield item;
    if (page.length < pageSize) return;
    offset += pageSize;
  }
}

/** Collects every page into a single array. Convenient for small result sets; prefer `paginate` for large ones. */
export async function collectAll<T>(fetchPage: (page: { limit: number; offset: number }) => Promise<T[]>, pageSize = 50): Promise<T[]> {
  const out: T[] = [];
  for await (const item of paginate(fetchPage, pageSize)) out.push(item);
  return out;
}
