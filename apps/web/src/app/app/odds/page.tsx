import type { Metadata } from "next";
import Link from "next/link";
import { StatusBadge } from "@/components/app/event-bits";
import { Price } from "@/components/app/odds-format";
import { AutoRefresh } from "@/components/app/auto-refresh";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState, Panel, Segmented } from "@/components/ui/primitives";
import { api, withQuery } from "@/lib/api";
import { flagOn, getFlags } from "@/lib/flags";
import { formatLine, formatPercent } from "@/lib/format";
import { getLeagues, MARKETS, pick } from "@/lib/leagues";
import type { EventSummary, OddsComparison } from "@/lib/types";

export const metadata: Metadata = { title: "Odds" };

const MAX_EVENTS = 12;

export default async function OddsPage({ searchParams }: { searchParams: Promise<{ league?: string; market?: string }> }) {
  const params = await searchParams;
  const leagues = await getLeagues();
  const league = pick(params.league, leagues.map((l) => l.key), leagues[0]?.key ?? "nba");
  const market = pick(params.market, MARKETS.map((m) => m.value), "moneyline");
  const events = (await api<EventSummary[]>("/v1/events", { query: { league } })).filter((event) => event.status !== "final");
  const shown = events.slice(0, MAX_EVENTS);
  const boards = await Promise.all(
    shown.map((event) =>
      api<OddsComparison>(`/v1/events/${encodeURIComponent(event.id)}/odds`, { query: { market } }).catch(() => null),
    ),
  );
  const valueScreen = flagOn(await getFlags(), "value_screen");
  const href = (next: { league?: string; market?: string }) =>
    withQuery("/app/odds", { league: next.league ?? league, market: next.market ?? market });

  return (
    <>
      <PageHeader title="Odds" description="The best open price for every outcome, and what the market implies once the vig is removed." actions={<AutoRefresh seconds={60} />} />
      <div className="mb-6 space-y-1">
        <Segmented label="League" current={league} options={leagues.map((l) => ({ value: l.key, label: l.name, href: href({ league: l.key }) }))} />
        <Segmented label="Market" current={market} options={MARKETS.map((m) => ({ value: m.value, label: m.label, href: href({ market: m.value }) }))} />
      </div>

      {valueScreen ? (
        <p className="mb-4 text-sm text-muted">
          <Link href={withQuery("/app/value", { league, market })} className="inline-flex min-h-11 items-center text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
            Compare the best prices with the consensus of the other books
          </Link>
        </p>
      ) : null}

      {shown.length === 0 ? (
        <Panel>
          <EmptyState title="No live or upcoming games in this league">Pick another league to see open markets.</EmptyState>
        </Panel>
      ) : (
        <ul className="space-y-3">
          {shown.map((event, index) => {
            const board = boards[index];
            const consensus = new Map(board?.consensus.outcomes.map((o) => [o.key, o]) ?? []);
            const open = board?.books.filter((b) => b.status === "open" && !b.is_stale).length ?? 0;
            return (
              <li key={event.id}>
                <Panel as="article" className="p-4 sm:p-5">
                  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                    <h2 className="font-semibold">
                      <Link href={`/app/games/${event.id}?market=${market}`} className="underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                        {event.away_team.name} at {event.home_team.name}
                      </Link>
                    </h2>
                    <StatusBadge event={event} />
                  </div>
                  {!board || board.best.length === 0 ? (
                    <p className="mt-3 text-sm text-muted">No book has this market open right now.</p>
                  ) : (
                    <>
                      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {board.best.map((best) => {
                          const outcome = consensus.get(best.outcome_key);
                          const book = board.books.find((b) => b.sportsbook.key === best.sportsbook_key);
                          const line =
                            best.line === null || best.line === undefined ? "" : ` ${formatLine(best.line, { signed: market === "spread" })}`;
                          return (
                            <div key={best.outcome_key} className="rounded-cell bg-accent-soft px-3 py-2.5 shadow-[inset_2px_0_0_var(--ov-accent)]">
                              <dt className="truncate text-sm">
                                {outcome?.name ?? best.outcome_key}
                                <span className="num">{line}</span>
                              </dt>
                              <dd className="mt-1 flex items-baseline justify-between gap-3">
                                <span>
                                  <Price price={best.price} className="text-lg font-medium text-accent" />
                                  <span className="ml-2 text-xs text-muted">Best, {book?.sportsbook.name ?? best.sportsbook_key}</span>
                                </span>
                                {outcome ? (
                                  <span className="num text-sm text-muted" title="No-vig consensus probability">
                                    {formatPercent(outcome.no_vig_probability)} no-vig
                                  </span>
                                ) : null}
                              </dd>
                            </div>
                          );
                        })}
                      </dl>
                      <p className="mt-3 text-xs text-muted">
                        {open} of {board.books.length} books open and current.
                      </p>
                    </>
                  )}
                </Panel>
              </li>
            );
          })}
        </ul>
      )}
      {events.length > MAX_EVENTS ? (
        <p className="mt-4 text-sm text-muted">
          Showing the next {MAX_EVENTS} of {events.length} games. <Link href={`/app/games?league=${league}`} className="underline">See all games</Link>
        </p>
      ) : null}
    </>
  );
}
