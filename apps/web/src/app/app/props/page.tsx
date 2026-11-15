import type { Metadata } from "next";
import Link from "next/link";
import { Price } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { Meter } from "@/components/ui/charts";
import { EmptyState, Notice, Panel, Segmented } from "@/components/ui/primitives";
import { api, withQuery } from "@/lib/api";
import { formatLine, formatPercent, titleCase } from "@/lib/format";
import { getLeagues, pick } from "@/lib/leagues";
import type { PropBoardRow } from "@/lib/types";

export const metadata: Metadata = { title: "Player props" };

export default async function PropsPage({ searchParams }: { searchParams: Promise<{ league?: string; market?: string }> }) {
  const params = await searchParams;
  const leagues = await getLeagues();
  const league = pick(params.league, leagues.map((l) => l.key), leagues[0]?.key ?? "nba");
  const all = await api<PropBoardRow[]>("/v1/props", { query: { league } });
  const markets = [...new Set(all.map((row) => row.market))];
  const market = pick(params.market, ["all", ...markets], "all");
  const rows = market === "all" ? all : all.filter((row) => row.market === market);
  const href = (next: { league?: string; market?: string }) =>
    withQuery("/app/props", { league: next.league ?? league, market: next.league ? undefined : (next.market ?? market) === "all" ? undefined : (next.market ?? market) });

  return (
    <>
      <PageHeader title="Player props" description="Tonight's posted props with the consensus line, best prices and each player's last ten games against that line." />
      <div className="mb-5 space-y-1">
        <Segmented label="League" current={league} options={leagues.map((l) => ({ value: l.key, label: l.name, href: href({ league: l.key }) }))} />
        {markets.length > 1 ? (
          <Segmented
            label="Stat"
            current={market}
            options={[{ value: "all", label: "All stats", href: href({ market: "all" }) }, ...markets.map((m) => ({ value: m, label: titleCase(m), href: href({ market: m }) }))]}
          />
        ) : null}
      </div>
      <div className="mb-5">
        <Notice>Hit rate is how often the player went over this line in recent games. It is a record of the past, not a prediction.</Notice>
      </div>
      <Panel>
        {rows.length === 0 ? (
          <EmptyState title="No props posted for this league">Props appear when sportsbooks open player markets for upcoming games.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] border-collapse text-sm">
              <caption className="sr-only">Player props board</caption>
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Player</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">Stat</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">Line</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">Best over</th>
                  <th scope="col" className="px-2 py-2.5 text-right font-medium">Best under</th>
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Over rate, last 10</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.player.id}-${row.market}`} className="border-t border-line">
                    <th scope="row" className="px-4 py-3 text-left font-medium sm:px-5">
                      <Link href={`/app/props/${row.player.id}?market=${row.market}`} className="underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                        {row.player.name}
                      </Link>
                      <span className="block text-xs font-normal text-muted">
                        {row.event.away_team.abbreviation} at {row.event.home_team.abbreviation}
                      </span>
                    </th>
                    <td className="px-2 py-3">{titleCase(row.market)}</td>
                    <td className="num px-2 py-3 text-right font-medium">{formatLine(row.consensus_line) || "n/a"}</td>
                    {[row.best_over, row.best_under].map((best, i) => (
                      <td key={i} className="px-2 py-3 text-right">
                        {best ? (
                          <>
                            <Price price={best.price} className="font-medium" />
                            <span className="block text-xs text-muted">{best.sportsbook.name}</span>
                          </>
                        ) : (
                          <span className="text-xs text-muted">None open</span>
                        )}
                      </td>
                    ))}
                    <td className="px-4 py-3 sm:px-5">
                      {row.l10_hit_rate === null || row.l10_hit_rate === undefined ? (
                        <span className="text-xs text-muted">Not enough games</span>
                      ) : (
                        <div className="flex min-w-32 items-center gap-3">
                          <span className="num w-12">{formatPercent(row.l10_hit_rate, 0)}</span>
                          <Meter value={row.l10_hit_rate} label={`${row.player.name} over rate`} />
                          <span className="num text-xs text-muted">n={row.l10_sample}</span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
