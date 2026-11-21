import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OddsTable } from "@/components/app/odds-table";
import type { BookRow, OddsComparison } from "@/lib/types";

const price = (american: number, decimal: number) => ({ american, decimal, fractional: "1/1", implied_probability: 1 / decimal });

function book(key: string, overrides: Partial<BookRow>): BookRow {
  return {
    sportsbook: { key, name: key.toUpperCase() },
    status: "open",
    is_stale: false,
    last_updated: "2026-11-21T00:00:00Z",
    outcomes: [
      { key: "home", name: "Home", price: price(-110, 1.909091), is_best: false, line: null },
      { key: "away", name: "Away", price: price(100, 2), is_best: false, line: null },
    ],
    ...overrides,
  } as BookRow;
}

function table(books: BookRow[]): string {
  const odds = {
    market: "moneyline",
    books,
    holds: [],
    consensus: { outcomes: [], books_used: 0 },
  } as unknown as OddsComparison;
  return renderToStaticMarkup(createElement(OddsTable, { odds }))
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ");
}

describe("the stale marker in the odds table", () => {
  it("is shown for a stale quote that has no update time", () => {
    const text = table([book("north", { is_stale: true, last_updated: null })]);
    expect(text).toMatch(/NORTH Stale/);
    expect(text).not.toMatch(/NORTH open/i);
  });

  it("is shown for a stale quote with a time", () => {
    expect(table([book("north", { is_stale: true })])).toMatch(/NORTH Stale,/);
  });

  it("is not shown for a fresh quote, and a quote with no time and not stale says it has no time", () => {
    expect(table([book("north", {})])).not.toContain("Stale");
    expect(table([book("north", { last_updated: null })])).toMatch(/NORTH No update time/);
  });

  it("a closed book still says why", () => {
    expect(table([book("north", { status: "suspended", is_stale: true, last_updated: null })])).toMatch(/NORTH suspended/);
  });
});
