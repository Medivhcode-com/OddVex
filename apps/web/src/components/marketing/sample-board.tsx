"use client";

import { useState } from "react";
import clsx from "clsx";
import { formatAmerican, formatDecimal, type OddsFormat } from "@/lib/format";

/**
 * Illustrative board for the marketing site. The teams, books and prices are fictional and static:
 * the real product reads the API. The implied and no-vig figures below were derived from these prices
 * with the same formulas documented on /methodology.
 */
type Cell = { american: number; state?: "suspended" | "stale" };
const BOOKS = ["Northline", "Cardinal", "Summit", "Beacon"] as const;
const ROWS: { team: string; record: string; fair: string; cells: Cell[]; trend: number[] }[] = [
  {
    team: "Harbor City Tides",
    record: "Away",
    fair: "40.4%",
    cells: [{ american: 136 }, { american: 142 }, { american: 130, state: "stale" }, { american: 138 }],
    trend: [128, 128, 132, 130, 136, 140, 142],
  },
  {
    team: "Granite Peak Rams",
    record: "Home",
    fair: "59.6%",
    cells: [{ american: -158 }, { american: -165 }, { american: -150, state: "stale" }, { american: 0, state: "suspended" }],
    trend: [-150, -152, -150, -156, -160, -158, -158],
  },
];

function toDecimal(american: number) {
  return american > 0 ? 1 + american / 100 : 1 + 100 / -american;
}

function bestIndex(cells: Cell[]) {
  let best = -1;
  cells.forEach((cell, i) => {
    if (cell.state) return;
    if (best === -1 || cell.american > cells[best].american) best = i;
  });
  return best;
}

export function SampleBoard() {
  const [format, setFormat] = useState<OddsFormat>("american");
  const show = (american: number) => (format === "american" ? formatAmerican(american) : formatDecimal(toDecimal(american)));

  return (
    <div className="ov-resolve rounded-panel border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <p className="text-sm font-semibold">Moneyline, Tides at Rams</p>
          <p className="text-xs text-muted">Sample board. Fictional teams, books and prices.</p>
        </div>
        <div role="group" aria-label="Odds format" className="flex rounded-full border border-line p-0.5 text-xs">
          {(["american", "decimal"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={format === option}
              onClick={() => setFormat(option)}
              className={clsx(
                "min-h-8 rounded-full px-3 font-medium capitalize",
                format === option ? "bg-ink text-bg" : "text-muted hover:text-ink",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <caption className="sr-only">Sample moneyline prices across four fictional sportsbooks</caption>
          <thead>
            <tr className="text-left text-xs text-muted">
              <th scope="col" className="px-4 py-2.5 font-medium">
                Team
              </th>
              {BOOKS.map((book) => (
                <th key={book} scope="col" className="px-2 py-2.5 text-right font-medium">
                  {book}
                </th>
              ))}
              <th scope="col" className="px-4 py-2.5 text-right font-medium">
                No-vig
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const best = bestIndex(row.cells);
              return (
                <tr key={row.team} className="border-t border-line">
                  <th scope="row" className="px-4 py-3 text-left font-medium">
                    {row.team}
                    <span className="block text-xs font-normal text-muted">{row.record}</span>
                  </th>
                  {row.cells.map((cell, i) => (
                    <td key={BOOKS[i]} className="px-2 py-3 text-right">
                      {cell.state === "suspended" ? (
                        <span className="text-xs text-muted">Suspended</span>
                      ) : (
                        <span
                          className={clsx(
                            "num inline-flex min-w-16 flex-col items-end rounded-cell px-2 py-1",
                            i === best && "bg-accent-soft text-accent shadow-[inset_2px_0_0_var(--ov-accent)]",
                            cell.state === "stale" && "text-muted",
                          )}
                        >
                          <span className="font-medium">{show(cell.american)}</span>
                          <span className="font-sans text-[0.6875rem] leading-4">
                            {i === best ? "Best" : cell.state === "stale" ? "9 min old" : " "}
                          </span>
                        </span>
                      )}
                    </td>
                  ))}
                  <td className="num px-4 py-3 text-right text-muted">{row.fair}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-2.5 text-xs text-muted">
        Best price is marked per row. Stale and suspended prices are never counted as best.
      </p>
    </div>
  );
}
