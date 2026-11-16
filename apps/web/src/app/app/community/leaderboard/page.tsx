import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { CommunityHeader, intervalText, SignedOut } from "@/components/app/community/chrome";
import { EmptyState, Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api, withQuery } from "@/lib/api";
import { COMMUNITY_HOME, communityContext, profileHref } from "@/lib/community";
import { formatDateTime, formatPercent } from "@/lib/format";
import { getLeagues, pick } from "@/lib/leagues";

export const metadata: Metadata = { title: "Community leaderboard" };

const WINDOWS = [
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
] as const;

/** Behind two flags: `community` and `community_leaderboard`. Rows are shown in the API's order. */
export default async function LeaderboardPage({ searchParams }: { searchParams: Promise<{ league?: string; window?: string }> }) {
  const context = await communityContext("community_leaderboard");
  if (!context.user) return <SignedOut next="/app/community/leaderboard" />;
  if (!context.me) redirect(COMMUNITY_HOME);

  const params = await searchParams;
  const leagues = await getLeagues();
  const league = pick(params.league, ["all", ...leagues.map((entry) => entry.key)], "all");
  const window = pick(params.window, WINDOWS.map((entry) => entry.value), "all");
  const board = await api<Schemas["LeaderboardOut"]>("/v1/community/leaderboard", { auth: true, query: { league: league === "all" ? undefined : league, window } });
  const href = (next: { league?: string; window?: string }) => {
    const nextLeague = next.league ?? league;
    const nextWindow = next.window ?? window;
    return withQuery("/app/community/leaderboard", { league: nextLeague === "all" ? undefined : nextLeague, window: nextWindow === "all" ? undefined : nextWindow });
  };

  return (
    <>
      <CommunityHeader
        title="Leaderboard"
        description="Profiles ordered by their graded picks. A description of the past, not a recommendation."
        current="leaderboard"
        me={context.me}
        leaderboard={context.leaderboard}
      />
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <Segmented label="League" current={league} options={[{ value: "all", label: "All leagues", href: href({ league: "all" }) }, ...leagues.map((entry) => ({ value: entry.key, label: entry.name, href: href({ league: entry.key }) }))]} />
          <Segmented label="Window" current={window} options={WINDOWS.map((entry) => ({ value: entry.value, label: entry.label, href: href({ window: entry.value }) }))} />
        </div>

        <Notice tone="warn" title="Read this first">
          {board.caveat}
        </Notice>

        <Panel aria-labelledby="leaderboard-heading">
          <PanelHeader
            id="leaderboard-heading"
            title="Ranking"
            description="Ranked by the lower end of the win-rate interval, not the win rate itself, so a small sample can't top the list."
          />
          {board.items.length === 0 ? (
            <EmptyState title="Nobody is ranked in this view yet">
              A profile is ranked once it has at least {board.minimum_graded_picks} graded picks in the window. Try a longer window or all leagues.
            </EmptyState>
          ) : (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Ranking table, scrolls sideways">
              <table className="w-full min-w-[36rem] border-collapse text-sm">
                <caption className="sr-only">Profiles ranked by the lower end of the 95% interval of their win rate</caption>
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Rank</th>
                    <th scope="col" className="px-2 py-2.5 font-medium">Profile</th>
                    <th scope="col" className="px-2 py-2.5 text-right font-medium">Graded picks</th>
                    <th scope="col" className="px-2 py-2.5 text-right font-medium">Win rate</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium sm:px-5">95% interval</th>
                  </tr>
                </thead>
                <tbody>
                  {board.items.map((row) => (
                    <tr key={row.handle} className="border-t border-line">
                      <td className="num px-4 py-2.5 sm:px-5">{row.rank}</td>
                      <th scope="row" className="px-2 py-2.5 text-left font-medium">
                        <Link href={profileHref(row.handle)} className="inline-flex min-h-11 items-center underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                          @{row.handle}
                        </Link>
                      </th>
                      <td className="num px-2 py-2.5 text-right">{row.record.picks}</td>
                      <td className="num px-2 py-2.5 text-right">{formatPercent(row.record.win_rate)}</td>
                      <td className="num px-4 py-2.5 text-right sm:px-5">{intervalText(row.record) ?? "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="space-y-1.5 border-t border-line px-4 py-3 text-xs text-muted sm:px-5">
            <p className="max-w-prose">{board.method}</p>
            <p>
              As of <time dateTime={board.as_of}>{formatDateTime(board.as_of)}</time>. Synthetic data: teams, games and sportsbooks are fictional.
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
