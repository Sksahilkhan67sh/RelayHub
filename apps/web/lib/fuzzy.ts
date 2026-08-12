/**
 * Minimal fuzzy matcher: true if every character of `query` appears in `text` in
 * order (case-insensitive), with a score rewarding contiguous/early matches so
 * "epts" still matches "Endpoints" but "Endpoints" scores higher for "end".
 * No dependency added -- this is intentionally small rather than pulling in a
 * fuzzy-search library for a handful of short strings per keystroke.
 */
export function fuzzyMatch(text: string, query: string): { matched: boolean; score: number } {
  if (!query) return { matched: true, score: 0 };

  const t = text.toLowerCase();
  const q = query.toLowerCase();

  if (t.includes(q)) {
    // Prefer earlier, tighter substring matches.
    const index = t.indexOf(q);
    return { matched: true, score: 100 - index };
  }

  let qi = 0;
  let score = 0;
  let lastMatchIndex = -1;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += lastMatchIndex === ti - 1 ? 3 : 1; // reward contiguous runs
      lastMatchIndex = ti;
      qi++;
    }
  }
  return { matched: qi === q.length, score };
}

export function fuzzyFilterAndSort<T>(items: T[], query: string, getText: (item: T) => string, limit?: number): T[] {
  if (!query) return limit ? items.slice(0, limit) : items;
  const scored = items
    .map((item) => ({ item, ...fuzzyMatch(getText(item), query) }))
    .filter((r) => r.matched)
    .sort((a, b) => b.score - a.score);
  const result = scored.map((r) => r.item);
  return limit ? result.slice(0, limit) : result;
}
