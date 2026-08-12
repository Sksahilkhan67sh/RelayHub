import { test } from "node:test";
import assert from "node:assert/strict";
import { paginate, collectAll } from "../src/pagination.js";

test("paginate walks every page until a short page signals the end", async () => {
  const pages = [
    [1, 2],
    [3, 4],
    [5],
  ];
  let calls = 0;
  const fetchPage = async ({ offset }: { limit: number; offset: number }) => {
    calls++;
    return pages[offset / 2] ?? [];
  };

  const collected: number[] = [];
  for await (const item of paginate(fetchPage, 2)) collected.push(item);

  assert.deepEqual(collected, [1, 2, 3, 4, 5]);
  assert.equal(calls, 3);
});

test("paginate stops immediately on an empty first page", async () => {
  const fetchPage = async () => [] as number[];
  const collected: number[] = [];
  for await (const item of paginate(fetchPage, 10)) collected.push(item);
  assert.deepEqual(collected, []);
});

test("collectAll returns a flat array across pages", async () => {
  const pages = [["a", "b"], ["c"]];
  const fetchPage = async ({ offset }: { limit: number; offset: number }) => pages[offset / 2] ?? [];
  const all = await collectAll(fetchPage, 2);
  assert.deepEqual(all, ["a", "b", "c"]);
});
