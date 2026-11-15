import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import clsx from "clsx";
import { Freshness } from "@/components/app/freshness";
import { WatchButton } from "@/components/app/watch-button";
import { currentUser } from "@/lib/session";
import { getWatchlist, watchId } from "@/lib/watchlist";
import { Price } from "@/components/app/odds-format";
import { GameLogBars } from "@/components/ui/charts";
import { Notice, Panel, PanelHeader, Segmented, Stat } from "@/components/ui/primitives";
import { apiOrNull, withQuery } from "@/lib/api";
import { formatDay, formatLine, formatPercent, titleCase } from "@/lib/format";
import { pick } from "@/lib/leagues";
import type { PriceT, PropAnalysis } from "@/lib/types";

type Props = { params: Promise<{ playerId: string }>; searchParams: Promise<{ market?: string; window?: string; split?: string }> };

const WINDOWS = ["5", "10", "20", "season"] as const;
const SPLITS = ["all", "home", "away", "vs_opponent"] as const;
const SPLIT_LABEL = { all: "All games", home: "Home", away: "Away", vs_opponent: "Vs opponent" };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const data = await apiOrNull<PropAnalysis>(`/v1/players/${encodeURIComponent((await params).playerId)}/props`).catch(() => null);
  return { title: data ? `${data.player.name} props` : "Player props" };
}

function avg(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : value.toFixed(1);
}

function PriceCell({ price, best }: { price?: PriceT | null; best: boolean }) {
  if (!price) return <span className="text-xs text-muted">Not offered</span>;
  return (
    <span className={clsx("inline-flex min-w-16 flex-col items-end rounded-cell px-2 py-1", best && "bg-accent-soft text-accent shadow-[inset_2px_0_0_var(--ov-accent)]")}>
      <Price price={price} className="font-medium" />
      <span className="text-[0.6875rem] leading-4">{best ? "Best" : formatPercent(price.implied_probability)}</span>
    </span>
  );
}

export default async function PropAnalyzerPage({ params, searchParams }: Props) {
  const playerId = encodeURIComponent((await params).playerId);
  const query = await searchParams;
  const window = pick(query.window, WINDOWS, "10");
  const split = pick(query.split, SPLITS, "all");
  const data = await apiOrNull<PropAnalysis>(`/v1/players/${playerId}/props`, { query: { market: query.market, window, split } });
  if (!data) notFound();
  const user = await currentUser().catch(() => null);
  const watchlist = await getWatchlist(Boolean(user));
  const market = data.market;
  const href = (next: { market?: string; window?: string; split?: string }) =>
    withQuery(`/app/props/${playerId}`, { market: next.market ?? market, window: next.window ?? window, split: next.split ?? split });
  const line = data.consensus_line;
  const { hit_rate: hit } = data;
  const log = [...data.game_log].sort((a, b) => a.date.localeCompare(b.date));
  const chartGames = log.slice(-20);

  return (
    <>
      <Link href={`/app/props?league=${data.player.league}`} className="text-sm text-muted underline underline-offset-4 hover:text-ink">
        All props
      </Link>
      <div className="mb-5 mt-3">
        <h1 className="text-2xl font-semibold tracking-tight">{data.player.name}</h1>
        <p className="mt-1 text-muted">
          {data.player.team.name}
          {data.player.position ? `, ${data.player.position}` : ""}
          {data.opponent ? `. Next: ${data.opponent.name}` : ""}
          {data.next_event ? `, ${formatDay(data.next_event.start_time)}` : ""}
        </p>
        <div className="mt-3">
          <WatchButton kind="player" refId={data.player.id} name={data.player.name} itemId={watchId(watchlist, "player", data.player.id)} signedIn={Boolean(user)} returnTo={`/app/props/${playerId}`} />
        </div>
      </div>

      <div className="mb-5 space-y-1">
        <Segmented label="Stat" current={market} options={data.available_markets.map((m) => ({ value: m, label: titleCase(m), href: href({ market: m }) }))} />
        <Segmented label="Games" current={window} options={WINDOWS.map((w) => ({ value: w, label: w === "season" ? "Season" : `Last ${w}`, href: href({ window: w }) }))} />
        <Segmented label="Split" current={split} options={SPLITS.map((s) => ({ value: s, label: SPLIT_LABEL[s], href: href({ split: s }) }))} />
      </div>

      <div className="space-y-5">
        <Panel aria-labelledby="hit-heading">
          <PanelHeader
            id="hit-heading"
            title={`${titleCase(market)} against the line`}
            description={line === null || line === undefined ? "No line is posted, so there is nothing to measure against." : `Consensus line ${formatLine(line)}`}
          />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-5 border-b border-line p-4 sm:p-5 md:grid-cols-4">
            <Stat
              label="Over rate"
              value={formatPercent(hit.rate, 0)}
              hint={`${hit.over_count} of ${hit.sample_size} games${hit.pushes ? `, ${hit.pushes} push${hit.pushes > 1 ? "es" : ""} excluded` : ""}`}
            />
            <Stat
              label="95% range"
              value={hit.ci_low === null || hit.ci_low === undefined || hit.ci_high === null || hit.ci_high === undefined ? "n/a" : `${formatPercent(hit.ci_low, 0)} to ${formatPercent(hit.ci_high, 0)}`}
              hint="Wilson interval. Wider means less evidence."
            />
            <Stat label="Average, this view" value={avg(data.averages.window)} />
            <Stat label="Season average" value={avg(data.averages.season)} hint={`Home ${avg(data.averages.home)}, away ${avg(data.averages.away)}`} />
          </dl>
          <div className="p-3 sm:p-5">
            {line === null || line === undefined ? (
              <p className="py-6 text-center text-sm text-muted">The game log will chart here once a line is posted.</p>
            ) : (
              <GameLogBars
                line={line}
                summary={`${data.player.name} ${titleCase(market)}: over ${formatLine(line)} in ${hit.over_count} of ${hit.sample_size} games shown`}
                games={chartGames.map((game) => ({
                  label: `${game.is_home ? "v" : "@"}${game.opponent.abbreviation}`,
                  value: game.value,
                  detail: `${formatDay(game.date)} ${game.is_home ? "vs" : "at"} ${game.opponent.name}: ${game.value} (${game.result})`,
                }))}
              />
            )}
          </div>
          <div className="border-t border-line p-4 sm:p-5">
            <Notice title="A record, not a forecast">{data.caveat}</Notice>
          </div>
        </Panel>

        <Panel aria-labelledby="offers-heading">
          <PanelHeader id="offers-heading" title="Lines and prices by book" description="Books can post different lines. Best is marked among books at the consensus line." />
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
            <table className="w-full min-w-[30rem] border-collapse text-sm">
              <caption className="sr-only">Prop offers by sportsbook</caption>
              <thead>
                <tr className="text-xs text-muted">
                  <th scope="col" className="px-4 py-2.5 text-left font-medium sm:px-5">Sportsbook</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">Line</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">Over</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium sm:px-5">Under</th>
                </tr>
              </thead>
              <tbody>
                {data.offers.map((offer) => (
                  <tr key={offer.sportsbook.key} className="border-t border-line">
                    <th scope="row" className="px-4 py-3 text-left font-medium sm:px-5">
                      {offer.sportsbook.name}
                      <span className="mt-0.5 block font-normal">
                        {offer.status === "open" && offer.last_updated ? (
                          <Freshness at={offer.last_updated} stale={offer.is_stale} prefix="" />
                        ) : (
                          <span className="text-xs capitalize text-muted">{offer.status}</span>
                        )}
                      </span>
                    </th>
                    {offer.status !== "open" ? (
                      <td colSpan={3} className="px-4 py-3 text-center text-xs text-muted">
                        {offer.status === "suspended" ? "Market suspended by this book" : "Not offered by this book"}
                      </td>
                    ) : (
                      <>
                        <td className="num px-2 py-3 text-right font-medium">{formatLine(offer.line)}</td>
                        <td className={clsx("px-2 py-2 text-right", offer.is_stale && "text-muted")}>
                          <PriceCell price={offer.over} best={offer.is_best_over} />
                        </td>
                        <td className={clsx("px-4 py-2 text-right sm:px-5", offer.is_stale && "text-muted")}>
                          <PriceCell price={offer.under} best={offer.is_best_under} />
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel aria-labelledby="log-heading">
          <PanelHeader id="log-heading" title="Game log" description={`${log.length} games in this view, most recent first`} />
          <div className="max-h-96 overflow-auto" tabIndex={0} role="region" aria-label="Game log, scrollable">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Game log</caption>
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-xs text-muted">
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Date</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">Opponent</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">{titleCase(market)}</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium sm:px-5">Vs line</th>
                </tr>
              </thead>
              <tbody>
                {[...log].reverse().map((game) => (
                  <tr key={`${game.date}-${game.opponent.id}`} className="border-t border-line">
                    <td className="px-4 py-2.5 text-muted sm:px-5">{formatDay(game.date)}</td>
                    <td className="px-2 py-2.5">
                      {game.is_home ? "vs" : "at"} {game.opponent.name}
                    </td>
                    <td className="num px-2 py-2.5 text-right font-medium">{game.value}</td>
                    <td className={clsx("px-4 py-2.5 text-right capitalize sm:px-5", game.result === "over" ? "text-accent" : "text-muted")}>
                      {game.result === "over" ? "▲ Over" : game.result === "under" ? "▽ Under" : "Push"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  );
}
