/**
 * Paging for the tracker page. The API returns bets a window at a time (`limit`, `offset`),
 * newest placed first, so the page asks for exactly the window it shows:
 *
 * - settled bets come 50 to a page, and the page number is in the address (`?page=2`), so
 *   Edit and Delete, which refresh the route, keep the place;
 * - open bets are loaded in their own request, in batches until a short one, so none can fall
 *   outside a window however many settled bets the account has;
 * - counts in the headings come from the summary totals, never from the rows that happen to
 *   be loaded.
 */

export const SETTLED_PAGE_SIZE = 50;
/** Open bets asked for per request. The API allows up to 1,000. */
export const OPEN_BATCH = 500;

export type SettledPaging = {
  page: number;
  pages: number;
  offset: number;
  limit: number;
  /** False when the address asked for a page that does not exist or was not a page number. */
  canonical: boolean;
};

/** The page of settled bets to show for the `page` value in the address and the summary's settled count. */
export function settledPaging(raw: string | string[] | undefined, settledCount: number): SettledPaging {
  const pages = Math.max(1, Math.ceil(Math.max(0, settledCount) / SETTLED_PAGE_SIZE));
  const valid = typeof raw === "string" && /^[1-9]\d{0,5}$/.test(raw);
  const asked = valid ? Number(raw) : 1;
  const page = Math.min(asked, pages);
  return { page, pages, offset: (page - 1) * SETTLED_PAGE_SIZE, limit: SETTLED_PAGE_SIZE, canonical: raw === undefined || (valid && asked === page) };
}

/** The tracker address for a page of settled bets. Page 1 is the plain address. */
export function trackerHref(page: number, anchor?: string): string {
  return `/app/tracker${page > 1 ? `?page=${page}` : ""}${anchor ? `#${anchor}` : ""}`;
}

/** The line under "Settled bets". `total` is the summary's count; `shown` is the number of rows on this page. */
export function settledDescription(paging: SettledPaging, shown: number, total: number): string {
  if (total <= 1) return `${total} settled`;
  if (paging.pages === 1) return `${total} settled, most recently placed first`;
  if (shown === 1) return `Showing bet ${paging.offset + 1} of ${total}, most recently placed first`;
  return `Showing ${paging.offset + 1} to ${paging.offset + shown} of ${total}, most recently placed first`;
}

/**
 * Reads a whole list through a windowed source: batch after batch until one comes back short.
 * `maxBatches` is a stop for a source that never does.
 */
export async function loadEvery<T>(fetchBatch: (offset: number, limit: number) => Promise<T[]>, batch = OPEN_BATCH, maxBatches = 40): Promise<T[]> {
  const rows: T[] = [];
  for (let i = 0; i < maxBatches; i += 1) {
    const next = await fetchBatch(rows.length, batch);
    rows.push(...next);
    if (next.length < batch) break;
  }
  return rows;
}
