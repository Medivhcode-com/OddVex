import type { Metadata } from "next";
import Link from "next/link";
import { EventCard } from "@/components/app/event-bits";
import { Price } from "@/components/app/odds-format";
import { ButtonLink, EmptyState, Panel, PanelHeader, Stat } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { formatLine, formatMoney, formatPercent, titleCase } from "@/lib/format";
import { getLeagues, leagueLabel } from "@/lib/leagues";
import { currentUser } from "@/lib/session";
import type { BetSummary, EventSummary, PropBoardRow } from "@/lib/types";

export const metadata: Metadata = { title: "Home" };

export default async function DashboardPage() {
  const user = await currentUser();
  const [events, leagues, props, summary] = await Promise.all([
    api<EventSummary[]>("/v1/events"),
    getLeagues(),
    api<PropBoardRow[]>("/v1/props").catch(() => [] as PropBoardRow[]),
    user ? api<BetSummary>("/v1/bets/summary", { auth: true }).catch(() => null) : null,
  ]);
  const live = events.filter((event) => event.status === "live");
  const upcoming = events.filter((event) => event.status === "upcoming").sort((a, b) => a.start_time.localeCompare(b.start_time));
  const board = [...live, ...upcoming].slice(0, 6);
  const topProps = props.filter((row) => row.l10_hit_rate !== null && row.l10_hit_rate !== undefined && row.best_over).slice(0, 5);

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{user ? `Welcome back, ${user.display_name}` : "Tonight's board"}</h1>
        <p className="mt-1 text-muted">
          {live.length} live, {upcoming.length} upcoming across {leagues.length} leagues.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <section aria-labelledby="board-heading" className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="board-heading" className="font-semibold">
              {live.length ? "Live and next up" : "Next up"}
            </h2>
            <Link href="/app/games" className="text-sm text-muted underline underline-offset-4 hover:text-ink">
              All games
            </Link>
          </div>
          {board.length === 0 ? (
            <Panel>
              <EmptyState title="No games on the board">Check back when the next slate opens.</EmptyState>
            </Panel>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {board.map((event) => (
                <li key={event.id}>
                  <EventCard event={event} leagueName={leagueLabel(leagues, event.league)} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-5">
          <Panel aria-labelledby="tracker-heading">
            <PanelHeader id="tracker-heading" title="Your tracker" action={<Link href="/app/tracker" className="text-sm text-muted underline underline-offset-4 hover:text-ink">Open</Link>} />
            {summary ? (
              <dl className="grid grid-cols-2 gap-4 p-4 sm:p-5">
                <Stat label="Profit" value={formatMoney(summary.totals.profit, { signed: true })} tone={summary.totals.profit > 0 ? "accent" : summary.totals.profit < 0 ? "error" : undefined} />
                <Stat label="ROI" value={formatPercent(summary.totals.roi)} />
                <Stat label="Record" value={`${summary.totals.wins}-${summary.totals.losses}-${summary.totals.pushes}`} />
                <Stat label="Open bets" value={summary.totals.pending_count} hint={`${formatMoney(summary.totals.pending_exposure)} at risk`} />
              </dl>
            ) : (
              <EmptyState title="Keep an honest record" action={<ButtonLink href="/signup?next=/app/tracker" size="sm">Create an account</ButtonLink>}>
                Log bets and see profit, ROI and closing line value.
              </EmptyState>
            )}
          </Panel>

          <Panel aria-labelledby="ask-heading">
            <PanelHeader id="ask-heading" title="Ask OddVex AI" />
            <div className="p-4 sm:p-5">
              <p className="text-sm text-muted">Find a best price, check a player&rsquo;s recent form or get a formula explained, with sources.</p>
              <ButtonLink href="/app/assistant" variant="secondary" size="sm" className="mt-3">
                Ask a question
              </ButtonLink>
            </div>
          </Panel>
        </div>

        <Panel aria-labelledby="props-heading" className="lg:col-span-3">
          <PanelHeader
            id="props-heading"
            title="Props on tonight's board"
            description="Over rate is the last ten games against the current line. A record, not a prediction."
            action={<Link href="/app/props" className="text-sm text-muted underline underline-offset-4 hover:text-ink">All props</Link>}
          />
          {topProps.length === 0 ? (
            <EmptyState title="No props posted yet">Player markets appear here when books open them.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {topProps.map((row) => (
                <li key={`${row.player.id}-${row.market}`}>
                  <Link href={`/app/props/${row.player.id}?market=${row.market}`} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-raised sm:grid-cols-[1.5fr_1fr_auto_auto] sm:px-5">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{row.player.name}</span>
                      <span className="block truncate text-sm text-muted">{leagueLabel(leagues, row.player.league)}, {row.player.team.name}</span>
                    </span>
                    <span className="text-right sm:text-left">
                      {titleCase(row.market)} <span className="num font-medium">{formatLine(row.consensus_line)}</span>
                    </span>
                    <span className="text-sm text-muted">
                      Over <span className="num text-ink">{formatPercent(row.l10_hit_rate, 0)}</span> <span className="num">(n={row.l10_sample})</span>
                    </span>
                    <span className="text-right text-sm">
                      {row.best_over ? (
                        <>
                          <Price price={row.best_over.price} className="font-medium" /> <span className="text-muted">over, {row.best_over.sportsbook.name}</span>
                        </>
                      ) : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
