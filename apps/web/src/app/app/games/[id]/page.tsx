import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { StatusBadge } from "@/components/app/event-bits";
import { AutoRefresh } from "@/components/app/auto-refresh";
import { Freshness } from "@/components/app/freshness";
import { OddsTable } from "@/components/app/odds-table";
import { LineHistoryChart, type Series } from "@/components/ui/charts";
import { Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api, apiOrNull } from "@/lib/api";
import { formatAmerican, formatLine } from "@/lib/format";
import { getLeagues, leagueLabel, MARKETS, pick } from "@/lib/leagues";
import type { EventDetail, LineHistory, OddsComparison } from "@/lib/types";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ market?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await apiOrNull<EventDetail>(`/v1/events/${encodeURIComponent((await params).id)}`).catch(() => null);
  return { title: event ? `${event.away_team.name} at ${event.home_team.name}` : "Game" };
}

function historySeries(history: LineHistory, market: string, bestBooks: Set<string>): { series: Series[]; unit: "price" | "line"; outcome: string } | null {
  const first = history.series[0];
  if (!first) return null;
  // Chart one outcome so the lines are comparable: the first outcome the API lists.
  const chosen = history.series.filter((s) => s.outcome_key === first.outcome_key);
  const unit = market === "moneyline" ? "price" : "line";
  const series = chosen.map((s) => ({
    name: s.sportsbook.name,
    emphasis: bestBooks.has(`${s.sportsbook.key}:${s.outcome_key}`),
    points: s.points
      .map((p) => ({ t: new Date(p.timestamp).getTime(), v: unit === "price" ? p.price.american : (p.line ?? Number.NaN) }))
      .filter((p) => Number.isFinite(p.v)),
  }));
  return { series: series.filter((s) => s.points.length), unit, outcome: first.outcome_name };
}

export default async function GamePage({ params, searchParams }: Props) {
  const id = encodeURIComponent((await params).id);
  const event = await apiOrNull<EventDetail>(`/v1/events/${id}`);
  if (!event) notFound();
  const available = MARKETS.filter((m) => event.available_markets.includes(m.value));
  const market = pick((await searchParams).market, available.map((m) => m.value), available[0]?.value ?? "moneyline");
  const [leagues, odds, history] = await Promise.all([
    getLeagues(),
    available.length ? api<OddsComparison>(`/v1/events/${id}/odds`, { query: { market } }) : null,
    available.length ? api<LineHistory>(`/v1/events/${id}/line-history`, { query: { market } }).catch(() => null) : null,
  ]);
  const bestBooks = new Set((odds?.best ?? []).map((b) => `${b.sportsbook_key}:${b.outcome_key}`));
  const chart = history ? historySeries(history, market, bestBooks) : null;
  const span = chart ? Math.max(...chart.series.flatMap((s) => s.points.map((p) => p.t))) : 0;

  return (
    <>
      <Link href="/app/games" className="text-sm text-muted underline underline-offset-4 hover:text-ink">
        All games
      </Link>
      <div className="mb-6 mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-sm text-muted">{leagueLabel(leagues, event.league)}</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            {event.away_team.name} <span className="font-normal text-muted">at</span> {event.home_team.name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <StatusBadge event={event} />
            {event.score ? (
              <span className="num text-lg font-medium">
                {event.away_team.abbreviation} {event.score.away}, {event.home_team.abbreviation} {event.score.home}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {!odds ? (
        <Notice title="No markets for this game">Sportsbooks are not offering odds on this game.</Notice>
      ) : (
        <div className="space-y-5">
          {event.status === "final" ? (
            <Notice title="This game is over">Its markets are closed, so there are no current prices. Line movement below runs up to the close.</Notice>
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmented
              label="Market"
              current={market}
              options={available.map((m) => ({ value: m.value, label: m.label, href: `/app/games/${id}?market=${m.value}` }))}
            />
            {event.status !== "final" ? <AutoRefresh seconds={event.status === "live" ? 20 : 60} /> : null}
          </div>
          <Panel aria-labelledby="odds-heading">
            <PanelHeader
              id="odds-heading"
              title="Odds comparison"
              description="Best price is marked per outcome. Other cells show the price's implied probability."
              action={<Freshness at={odds.as_of} />}
            />
            <OddsTable odds={odds} />
            <p className="border-t border-line px-4 py-2.5 text-xs text-muted sm:px-5">
              Stale and suspended prices are excluded from best price and from the consensus.{" "}
              <Link href="/methodology" className="underline">
                How this is calculated
              </Link>
            </p>
          </Panel>

          <Panel aria-labelledby="history-heading">
            <PanelHeader
              id="history-heading"
              title="Line movement"
              description={chart ? `${chart.outcome}, ${chart.unit === "price" ? "price" : "line"} by book over the last 48 hours` : undefined}
            />
            <div className="p-4 sm:p-5">
              {chart && chart.series.length ? (
                <LineHistoryChart
                  series={chart.series}
                  summary={`Line movement for ${chart.outcome} across ${chart.series.length} sportsbooks`}
                  formatValue={(v) => (chart.unit === "price" ? formatAmerican(v) : formatLine(Math.round(v * 2) / 2, { signed: market === "spread" }))}
                  formatTime={(t) => {
                    const hours = Math.round((span - t) / 3600000);
                    return hours <= 0 ? "Latest" : `${hours}h earlier`;
                  }}
                />
              ) : (
                <p className="py-6 text-center text-sm text-muted">No line history is available for this market.</p>
              )}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
