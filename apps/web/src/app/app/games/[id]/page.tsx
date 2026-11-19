import type { Metadata } from "next";
import Link from "next/link";
import { notFound, unstable_rethrow } from "next/navigation";
import { StatusBadge } from "@/components/app/event-bits";
import { AlertForm } from "@/components/app/alert-form";
import { AutoRefresh } from "@/components/app/auto-refresh";
import { SharePick } from "@/components/app/community/share-pick";
import { QuickBet, type QuickBetOption } from "@/components/app/quick-bet";
import { WatchButton } from "@/components/app/watch-button";
import { ButtonLink } from "@/components/ui/primitives";
import { currentUser } from "@/lib/session";
import { getWatchlist, watchId } from "@/lib/watchlist";
import { Freshness } from "@/components/app/freshness";
import { OddsTable } from "@/components/app/odds-table";
import { LineHistoryChart } from "@/components/ui/charts";
import { Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api, apiOrNull } from "@/lib/api";
import { getMyProfile } from "@/lib/community";
import { flagOn, getFlags } from "@/lib/flags";
import { formatLine } from "@/lib/format";
import { getLeagues, leagueLabel, MARKETS, pick } from "@/lib/leagues";
import { lineMovementChart } from "@/lib/line-history";
import type { EventDetail, LineHistory, OddsComparison } from "@/lib/types";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ market?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await apiOrNull<EventDetail>(`/v1/events/${encodeURIComponent((await params).id)}`).catch(() => null);
  return { title: event ? `${event.away_team.name} at ${event.home_team.name}` : "Game" };
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
  // The page still renders when the account cannot be read; a redirect that ends a dead session must get through.
  const user = await currentUser().catch((error) => {
    unstable_rethrow(error);
    return null;
  });
  const watchlist = await getWatchlist(Boolean(user));
  // Sharing a pick exists only while the community flag is on, and only on a game that has not started.
  const community = event.status === "upcoming" && flagOn(await getFlags(), "community");
  const profile = community && user ? await getMyProfile().catch(() => null) : null;
  const returnTo = `/app/games/${id}`;
  const quickOptions: QuickBetOption[] = (odds?.best ?? []).flatMap((best) => {
    if (!["home", "away", "draw", "over", "under"].includes(best.outcome_key)) return [];
    const name = odds?.consensus.outcomes.find((o) => o.key === best.outcome_key)?.name ?? best.outcome_key;
    const book = odds?.books.find((b) => b.sportsbook.key === best.sportsbook_key)?.sportsbook.name ?? best.sportsbook_key;
    const line = best.line ?? null;
    const lineText = line === null ? "" : ` ${formatLine(line, { signed: market === "spread" })}`;
    return [{ outcomeKey: best.outcome_key, label: `${name}${lineText}${market === "moneyline" ? " ML" : ""}`, line, american: best.price.american, sportsbook: book }];
  });
  const bestBooks = new Set((odds?.best ?? []).map((b) => `${b.sportsbook_key}:${b.outcome_key}`));
  const chart = history ? lineMovementChart(history, market, bestBooks) : null;
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
          <div className="mt-3 flex flex-wrap gap-2">
            <WatchButton kind="event" refId={event.id} name="this game" itemId={watchId(watchlist, "event", event.id)} signedIn={Boolean(user)} returnTo={returnTo} />
            <WatchButton kind="team" refId={event.away_team.id} name={event.away_team.name} itemId={watchId(watchlist, "team", event.away_team.id)} signedIn={Boolean(user)} returnTo={returnTo} />
            <WatchButton kind="team" refId={event.home_team.id} name={event.home_team.name} itemId={watchId(watchlist, "team", event.home_team.id)} signedIn={Boolean(user)} returnTo={returnTo} />
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

          {event.status !== "final" && quickOptions.length ? (
            <Panel aria-labelledby="quickbet-heading">
              <PanelHeader id="quickbet-heading" title="Track a bet on this game" description="OddVex records the bet. It does not place it." />
              {user ? (
                <QuickBet key={market} eventId={event.id} eventLabel={`${event.away_team.name} at ${event.home_team.name}`} league={event.league} market={market} options={quickOptions} />
              ) : (
                <div className="flex flex-wrap items-center gap-3 p-4 sm:p-5">
                  <p className="text-sm text-muted">Log in to add this game to your tracker.</p>
                  <ButtonLink href={`/login?next=${encodeURIComponent(returnTo)}`} variant="secondary" size="sm">
                    Log in
                  </ButtonLink>
                </div>
              )}
            </Panel>
          ) : null}

          {event.status !== "final" ? (
            <Panel aria-labelledby="alert-heading">
              <PanelHeader id="alert-heading" title="Set an alert" description="Hear about a change on this game. Alerts appear inside OddVex." />
              {user ? (
                <AlertForm
                  key={market}
                  eventId={event.id}
                  market={market}
                  canStart={event.status === "upcoming"}
                  outcomes={quickOptions.map((option) => ({ outcomeKey: option.outcomeKey, label: option.label, line: option.line, american: option.american }))}
                />
              ) : (
                <div className="flex flex-wrap items-center gap-3 p-4 sm:p-5">
                  <p className="text-sm text-muted">Log in to set alerts on this game.</p>
                  <ButtonLink href={`/login?next=${encodeURIComponent(returnTo)}`} variant="secondary" size="sm">
                    Log in
                  </ButtonLink>
                </div>
              )}
            </Panel>
          ) : null}

          {community && quickOptions.length ? (
            <Panel aria-labelledby="sharepick-heading">
              <PanelHeader id="sharepick-heading" title="Share a pick" description="Post this game to the community. No stake and no confidence rating: a pick is a selection and your reasoning." />
              {!user ? (
                <div className="flex flex-wrap items-center gap-3 p-4 sm:p-5">
                  <p className="text-sm text-muted">Log in to share a pick on this game.</p>
                  <ButtonLink href={`/login?next=${encodeURIComponent(returnTo)}`} variant="secondary" size="sm">
                    Log in
                  </ButtonLink>
                </div>
              ) : profile?.can_post ? (
                <SharePick key={market} eventId={event.id} market={market} options={quickOptions} />
              ) : (
                <div className="flex flex-wrap items-center gap-3 p-4 sm:p-5">
                  <p className="max-w-prose text-sm text-muted">
                    {!profile
                      ? "You need a community profile to share a pick."
                      : profile.is_public
                        ? "Moderators hid your profile, so you can't share picks right now."
                        : "Your community profile is private, so you can't share picks. Make it public to post."}
                  </p>
                  <ButtonLink href={profile ? "/app/community/settings" : "/app/community"} variant="secondary" size="sm">
                    {profile ? "Open community settings" : "Create a profile"}
                  </ButtonLink>
                </div>
              )}
            </Panel>
          ) : null}

          <Panel aria-labelledby="history-heading">
            <PanelHeader
              id="history-heading"
              title="Line movement"
              description={
                chart
                  ? chart.unit === "probability"
                    ? `${chart.outcome}: each book's price over the last 48 hours. The legend gives the latest American price; point at a mark for an earlier one.`
                    : `${chart.outcome}, line by book over the last 48 hours`
                  : undefined
              }
            />
            <div className="p-4 sm:p-5">
              {chart && chart.series.length ? (
                <LineHistoryChart
                  series={chart.series}
                  summary={chart.summary}
                  axisTitle={chart.axisTitle}
                  formatValue={chart.formatValue}
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
