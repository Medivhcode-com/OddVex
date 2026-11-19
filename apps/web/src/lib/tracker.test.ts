import { describe, expect, it } from "vitest";
import { loadEvery, OPEN_BATCH, SETTLED_PAGE_SIZE, settledDescription, settledPaging, trackerHref } from "./tracker";

describe("settledPaging", () => {
  it("shows the first 50 on page 1", () => {
    expect(SETTLED_PAGE_SIZE).toBe(50);
    expect(settledPaging(undefined, 120)).toEqual({ page: 1, pages: 3, offset: 0, limit: 50, canonical: true });
  });

  it("reaches every settled bet: the last page starts where the one before ended", () => {
    expect(settledPaging("2", 120)).toMatchObject({ page: 2, pages: 3, offset: 50 });
    expect(settledPaging("3", 120)).toMatchObject({ page: 3, pages: 3, offset: 100 });
    expect(settledPaging("2", 51)).toMatchObject({ page: 2, pages: 2, offset: 50 });
    expect(settledPaging("1", 50)).toMatchObject({ page: 1, pages: 1, offset: 0 });
    // The API allows 5,000 bets an account: page 100 is the last.
    expect(settledPaging("100", 5000)).toMatchObject({ page: 100, pages: 100, offset: 4950 });
  });

  it("goes to the last page when the address asks for one past it, as after deleting the only bet on a page", () => {
    expect(settledPaging("3", 100)).toEqual({ page: 2, pages: 2, offset: 50, limit: 50, canonical: false });
    expect(settledPaging("9", 0)).toEqual({ page: 1, pages: 1, offset: 0, limit: 50, canonical: false });
  });

  it("treats anything that is not a whole page number as page 1", () => {
    for (const raw of ["0", "-1", "abc", "2.5", "1e2", "", " 2", "9999999999", ["2", "3"]]) {
      expect(settledPaging(raw, 500), JSON.stringify(raw)).toMatchObject({ page: 1, offset: 0, canonical: false });
    }
  });

  it("has one page when nothing is settled", () => {
    expect(settledPaging(undefined, 0)).toEqual({ page: 1, pages: 1, offset: 0, limit: 50, canonical: true });
  });
});

describe("trackerHref", () => {
  it("keeps page 1 at the plain address and carries later pages in the query", () => {
    expect(trackerHref(1)).toBe("/app/tracker");
    expect(trackerHref(2)).toBe("/app/tracker?page=2");
    expect(trackerHref(2, "settled")).toBe("/app/tracker?page=2#settled");
    expect(trackerHref(1, "settled")).toBe("/app/tracker#settled");
  });
});

describe("settledDescription", () => {
  it("counts from the summary total, not from the rows on the page", () => {
    expect(settledDescription(settledPaging(undefined, 0), 0, 0)).toBe("0 settled");
    expect(settledDescription(settledPaging(undefined, 1), 1, 1)).toBe("1 settled");
    expect(settledDescription(settledPaging(undefined, 37), 37, 37)).toBe("37 settled, most recently placed first");
    expect(settledDescription(settledPaging(undefined, 120), 50, 120)).toBe("Showing 1 to 50 of 120, most recently placed first");
    expect(settledDescription(settledPaging("3", 120), 20, 120)).toBe("Showing 101 to 120 of 120, most recently placed first");
  });
});

describe("loadEvery", () => {
  const rows = Array.from({ length: 1234 }, (_, i) => i);

  it("asks for batch after batch until one comes back short, so no row is left outside the window", async () => {
    const calls: [number, number][] = [];
    const out = await loadEvery(async (offset, limit) => {
      calls.push([offset, limit]);
      return rows.slice(offset, offset + limit);
    });
    expect(OPEN_BATCH).toBe(500);
    expect(out).toEqual(rows);
    expect(calls).toEqual([[0, 500], [500, 500], [1000, 500]]);
  });

  it("makes one request when everything fits in it", async () => {
    let calls = 0;
    const out = await loadEvery(async (offset, limit) => {
      calls += 1;
      return rows.slice(0, 3).slice(offset, offset + limit);
    });
    expect(out).toEqual([0, 1, 2]);
    expect(calls).toBe(1);
  });

  it("stops after a fixed number of batches if the source never comes back short", async () => {
    let calls = 0;
    const out = await loadEvery(async (_offset, limit) => {
      calls += 1;
      return Array.from({ length: limit }, () => 0);
    }, 10, 4);
    expect(calls).toBe(4);
    expect(out).toHaveLength(40);
  });
});
