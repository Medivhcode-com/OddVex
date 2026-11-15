import clsx from "clsx";
import { Freshness } from "@/components/app/freshness";
import { Price } from "@/components/app/odds-format";
import { formatLine, formatPercent } from "@/lib/format";
import type { OddsComparison, Outcome } from "@/lib/types";

function lineText(market: string, outcome: Outcome) {
  if (outcome.line === null || outcome.line === undefined) return null;
  if (market === "spread") return formatLine(outcome.line, { signed: true });
  return `${outcome.key.startsWith("over") ? "O" : outcome.key.startsWith("under") ? "U" : ""} ${formatLine(outcome.line)}`.trim();
}

/**
 * Books as rows, outcomes as columns. On a phone the table scrolls sideways with the book column pinned.
 * Best price = mint notch + the word "Best". Stale and closed markets are spelled out.
 */
export function OddsTable({ odds }: { odds: OddsComparison }) {
  const columns = odds.consensus.outcomes.length
    ? odds.consensus.outcomes.map((o) => ({ key: o.key, name: o.name }))
    : (odds.books.find((b) => b.outcomes.length)?.outcomes.map((o) => ({ key: o.key, name: o.name })) ?? []);
  const holds = new Map(odds.holds.map((h) => [h.sportsbook_key, h.hold]));
  const open = odds.books.filter((b) => b.status === "open");

  if (columns.length === 0) {
    return <p className="px-5 py-10 text-center text-muted">No sportsbook is offering this market right now.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <caption className="sr-only">
          {odds.market} prices by sportsbook. {open.length} of {odds.books.length} books are open.
        </caption>
        <thead>
          <tr className="text-xs text-muted">
            <th scope="col" className="sticky left-0 z-10 bg-surface px-4 py-2.5 text-left font-medium sm:px-5">
              Sportsbook
            </th>
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-2 py-2.5 text-right font-medium">
                {column.name}
              </th>
            ))}
            <th scope="col" className="px-4 py-2.5 text-right font-medium sm:px-5">
              Hold
            </th>
          </tr>
        </thead>
        <tbody>
          {odds.books.map((book) => {
            const hold = holds.get(book.sportsbook.key);
            return (
              <tr key={book.sportsbook.key} className="border-t border-line">
                <th scope="row" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left font-medium sm:px-5">
                  {book.sportsbook.name}
                  <span className="mt-0.5 block font-normal">
                    {book.status === "open" && book.last_updated ? (
                      <Freshness at={book.last_updated} stale={book.is_stale} prefix="" />
                    ) : (
                      <span className="text-xs capitalize text-muted">{book.status}</span>
                    )}
                  </span>
                </th>
                {book.status !== "open" ? (
                  <td colSpan={columns.length} className="px-2 py-3 text-center text-xs text-muted">
                    {book.status === "suspended" ? "Market suspended by this book" : "Not offered by this book"}
                  </td>
                ) : (
                  columns.map((column) => {
                    const outcome = book.outcomes.find((o) => o.key === column.key);
                    if (!outcome) {
                      return (
                        <td key={column.key} className="px-2 py-3 text-right text-xs text-muted">
                          Not offered
                        </td>
                      );
                    }
                    const line = lineText(odds.market, outcome);
                    return (
                      <td key={column.key} className="px-2 py-2 text-right">
                        <span
                          className={clsx(
                            "inline-flex min-w-[4.5rem] flex-col items-end rounded-cell px-2 py-1",
                            outcome.is_best && "bg-accent-soft text-accent shadow-[inset_2px_0_0_var(--ov-accent)]",
                            book.is_stale && "text-muted",
                          )}
                        >
                          <span className="flex items-baseline gap-1.5">
                            {line ? <span className="num text-xs opacity-80">{line}</span> : null}
                            <Price price={outcome.price} className="font-medium" />
                          </span>
                          <span className="text-[0.6875rem] leading-4">
                            {outcome.is_best ? "Best" : formatPercent(outcome.price.implied_probability)}
                          </span>
                        </span>
                      </td>
                    );
                  })
                )}
                <td className="num px-4 py-3 text-right text-muted sm:px-5">{hold === undefined ? "" : formatPercent(hold)}</td>
              </tr>
            );
          })}
        </tbody>
        {odds.consensus.outcomes.length ? (
          <tfoot>
            <tr className="border-t border-line-strong">
              <th scope="row" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left font-medium sm:px-5">
                No-vig consensus
                <span className="block text-xs font-normal text-muted">
                  {odds.consensus.books_used} {odds.consensus.books_used === 1 ? "book" : "books"}
                </span>
              </th>
              {odds.consensus.outcomes.map((outcome) => (
                <td key={outcome.key} className="num px-2 py-3 pr-4 text-right font-medium">
                  {formatPercent(outcome.no_vig_probability)}
                </td>
              ))}
              <td />
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}
