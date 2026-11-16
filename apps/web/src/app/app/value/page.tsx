import type { Metadata } from "next";
import Link from "next/link";
import type { Schemas } from "@oddvex/types";
import { AutoRefresh } from "@/components/app/auto-refresh";
import { StatusBadge } from "@/components/app/event-bits";
import { Freshness } from "@/components/app/freshness";
import { Price } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState, Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api, withQuery } from "@/lib/api";
import { requireFlag } from "@/lib/flags";
import { formatLine, formatPercent, formatSignedPercent, titleCase } from "@/lib/format";
import { getLeagues, MARKETS, pick } from "@/lib/leagues";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Value" };

type ValueScreen = Schemas["ValueScreenOut"];
type Row = Schemas["ValueRowOut"];

/** Minimum edge choices, as the fraction the API takes. */
const MIN_EDGES = [
  { value: "0", label: "Any" },
  { value: "0.005", label: "0.5% or more" },
  { value: "0.01", label: "1% or more" },
  { value: "0.02", label: "2% or more" },
  { value: "0.05", label: "5% or more" },
] as const;

function lineText(row: Row): string {
  if (row.line === null || row.line === undefined) return "";
  return formatLine(row.line, { signed: row.market === "spread" });
}

function gameHref(row: Row): string {
  return `/app/games/${encodeURIComponent(row.event.id)}?market=${encodeURIComponent(row.market)}`;
}

function gameName(row: Row): string {
  return `${row.event.away_team.name} at ${row.event.home_team.name}`;
}

function consensusLabel(row: Row): string {
  return `Consensus of ${row.books_in_consensus} other ${row.books_in_consensus === 1 ? "book" : "books"}`;
}

function TrackLink({ row }: { row: Row }) {
  return (
    <Link href={`${gameHref(row)}#quickbet-heading`} className="inline-flex min-h-11 items-center text-sm font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink">
      Track this
      <span className="sr-only">
        : {row.outcome_name} {lineText(row)}, {gameName(row)}
      </span>
    </Link>
  );
}

export default async function ValuePage({ searchParams }: { searchParams: Promise<{ league?: string; market?: string; min_edge?: string }> }) {
  await requireFlag("value_screen");
  const params = await searchParams;
  const [leagues, user] = await Promise.all([getLeagues(), currentUser()]);
  const league = pick(params.league, ["all", ...leagues.map((l) => l.key)], "all");
  const market = pick(params.market, ["all", ...MARKETS.map((m) => m.value)], "all");
  const minEdge = pick(params.min_edge, MIN_EDGES.map((m) => m.value), "0");
  const screen = await api<ValueScreen>("/v1/value", {
    query: { league: league === "all" ? undefined : league, market: market === "all" ? undefined : market, min_edge: minEdge },
  });
  const { rows } = screen;

  const href = (next: { league?: string; market?: string; min_edge?: string }) => {
    const merged = { league, market, min_edge: minEdge, ...next };
    return withQuery("/app/value", {
      league: merged.league === "all" ? undefined : merged.league,
      market: merged.market === "all" ? undefined : merged.market,
      min_edge: merged.min_edge === "0" ? undefined : merged.min_edge,
    });
  };
  const filtered = league !== "all" || market !== "all" || minEdge !== "0";

  return (
    <>
      <PageHeader
        title="Value"
        description="Where one sportsbook's price is longer than the other books' no-vig consensus. A comparison of prices, not a prediction."
        actions={<AutoRefresh seconds={60} />}
      />

      <div className="mb-5 space-y-3">
        <Notice tone="warn" title="Read this first">
          {screen.caveat}
          {screen.data_mode === "synthetic" ? " This preview runs on synthetic data: every book is the same model plus a margin and noise, so no row here reflects a real edge." : null}
        </Notice>
        <Notice tone="second" title="How it is calculated">
          {screen.method} <Link href="/methodology#edge-vs-consensus">Formula and a worked example</Link>
        </Notice>
      </div>

      <div className="mb-6 space-y-1">
        <Segmented
          label="League"
          current={league}
          options={[{ value: "all", label: "All leagues", href: href({ league: "all" }) }, ...leagues.map((l) => ({ value: l.key, label: l.name, href: href({ league: l.key }) }))]}
        />
        <Segmented
          label="Market"
          current={market}
          options={[{ value: "all", label: "All markets", href: href({ market: "all" }) }, ...MARKETS.map((m) => ({ value: m.value, label: m.label, href: href({ market: m.value }) }))]}
        />
        <Segmented label="Minimum edge" current={minEdge} options={MIN_EDGES.map((m) => ({ value: m.value, label: m.value === "0" ? "Any edge" : m.label, href: href({ min_edge: m.value }) }))} />
      </div>

      <Panel aria-labelledby="value-heading">
        <PanelHeader
          id="value-heading"
          title="Prices above the consensus"
          description={`${rows.length} ${rows.length === 1 ? "outcome" : "outcomes"}, largest edge first`}
          action={<Freshness at={screen.as_of} prefix="Checked" />}
        />
        {rows.length === 0 ? (
          <EmptyState title="Nothing qualifies right now" action={filtered ? <Link href="/app/value" className="inline-flex min-h-11 items-center underline underline-offset-4">Clear filters</Link> : undefined}>
            On many slates no price sits above the consensus of the other books, and that is normal. Prices move, so
            the list changes through the day.{filtered ? " A lower minimum edge or another league may show more." : ""}
          </EmptyState>
        ) : (
          <>
            {/* Phones: one card per outcome. */}
            <ul className="divide-y divide-line md:hidden">
              {rows.map((row) => (
                <li key={`${row.event.id}-${row.market}-${row.outcome_key}-${row.line ?? ""}`} className="space-y-3 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                    <Link href={gameHref(row)} className="font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                      {gameName(row)}
                    </Link>
                    <StatusBadge event={row.event} />
                  </div>
                  <p>
                    {row.outcome_name} <span className="num">{lineText(row)}</span>
                    <span className="text-sm text-muted">, {titleCase(row.market).toLowerCase()}</span>
                  </p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                    <div>
                      <dt className="text-xs text-muted">Best price</dt>
                      <dd>
                        <Price price={row.best_price} className="font-medium" /> <span className="text-muted">at {row.sportsbook.name}</span>
                      </dd>
                      {row.last_updated ? (
                        <dd>
                          <Freshness at={row.last_updated} />
                        </dd>
                      ) : null}
                    </div>
                    <div>
                      <dt className="text-xs text-muted">Edge vs consensus</dt>
                      <dd className="num font-medium">{formatSignedPercent(row.edge, 2)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">{consensusLabel(row)}</dt>
                      <dd className="num">{formatPercent(row.consensus_probability)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">Break-even at the best price</dt>
                      <dd className="num">{formatPercent(row.breakeven_probability)}</dd>
                    </div>
                  </dl>
                  {user ? <TrackLink row={row} /> : null}
                </li>
              ))}
            </ul>

            {/* From tablet width: a table. */}
            <div className="hidden overflow-x-auto md:block" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
              <table className="w-full min-w-[52rem] border-collapse text-sm">
                <caption className="sr-only">Outcomes where the best price is above the no-vig consensus of the other sportsbooks</caption>
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="px-5 py-2.5 font-medium">Game</th>
                    <th scope="col" className="px-2 py-2.5 font-medium">Outcome</th>
                    <th scope="col" className="px-2 py-2.5 font-medium">Best price</th>
                    <th scope="col" className="px-2 py-2.5 text-right font-medium">Consensus of other books</th>
                    <th scope="col" className="px-2 py-2.5 text-right font-medium">Break-even at the best price</th>
                    <th scope="col" className="px-2 py-2.5 text-right font-medium">Edge vs consensus</th>
                    {user ? <th scope="col" className="px-5 py-2.5 font-medium"><span className="sr-only">Actions</span></th> : null}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.event.id}-${row.market}-${row.outcome_key}-${row.line ?? ""}`} className="border-t border-line align-top">
                      <th scope="row" className="px-5 py-3 text-left font-medium">
                        <Link href={gameHref(row)} className="underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                          {gameName(row)}
                        </Link>
                        <span className="mt-1 block font-normal">
                          <StatusBadge event={row.event} />
                        </span>
                      </th>
                      <td className="px-2 py-3">
                        {row.outcome_name} <span className="num">{lineText(row)}</span>
                        <span className="block text-xs text-muted">{titleCase(row.market)}</span>
                      </td>
                      <td className="px-2 py-3">
                        <Price price={row.best_price} className="font-medium" /> <span className="text-muted">at {row.sportsbook.name}</span>
                        {row.last_updated ? <Freshness at={row.last_updated} className="mt-1 flex" /> : null}
                      </td>
                      <td className="px-2 py-3 text-right">
                        <span className="num">{formatPercent(row.consensus_probability)}</span>
                        <span className="block text-xs text-muted">{consensusLabel(row)}</span>
                      </td>
                      <td className="num px-2 py-3 text-right">{formatPercent(row.breakeven_probability)}</td>
                      <td className="num px-2 py-3 text-right font-medium">{formatSignedPercent(row.edge, 2)}</td>
                      {user ? (
                        <td className="whitespace-nowrap px-5 py-1 text-right">
                          <TrackLink row={row} />
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-line px-4 py-2.5 text-xs text-muted sm:px-5">
              Edge vs consensus is the expected return per $1 staked at the best price, if the consensus probability were the true one. It often is not.
              {user ? " Track this opens the game, where you can record a bet you placed elsewhere. OddVex does not place bets." : ""}
            </p>
          </>
        )}
      </Panel>
    </>
  );
}
