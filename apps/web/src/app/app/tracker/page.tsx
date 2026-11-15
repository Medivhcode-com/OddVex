import type { Metadata } from "next";
import { AutoSettleButton } from "@/components/app/auto-settle";
import { BetActions } from "@/components/app/bet-actions";
import { BetForm } from "@/components/app/bet-form";
import { SyncPanel } from "@/components/app/sync-panel";
import type { Schemas } from "@oddvex/types";
import { Price } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { ProfitChart } from "@/components/ui/charts";
import { Badge, ButtonLink, EmptyState, Panel, PanelHeader, Stat } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { formatDay, formatMoney, formatPercent, formatSignedPercent, titleCase } from "@/lib/format";
import { getLeagues, leagueLabel } from "@/lib/leagues";
import { currentUser } from "@/lib/session";
import type { Bet, BetSummary, Book, Breakdown, League } from "@/lib/types";

export const metadata: Metadata = { title: "Bet tracker" };

const RESULT_TONE: Record<string, "accent" | "error" | "neutral" | "warn"> = {
  won: "accent", half_won: "accent", lost: "error", half_lost: "error", push: "neutral", void: "neutral", cashout: "warn",
};

function BreakdownTable({ title, rows, label }: { title: string; rows: Breakdown[]; label: (key: string) => string }) {
  return (
    <Panel>
      <PanelHeader title={title} />
      {rows.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted">No settled bets yet.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr className="text-xs text-muted">
              <th scope="col" className="px-4 py-2 text-left font-medium sm:px-5">Group</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Bets</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Profit</th>
              <th scope="col" className="px-4 py-2 text-right font-medium sm:px-5">ROI</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t border-line">
                <th scope="row" className="px-4 py-2.5 text-left font-medium sm:px-5">{label(row.key)}</th>
                <td className="num px-2 py-2.5 text-right text-muted">{row.bets}</td>
                <td className={`num px-2 py-2.5 text-right ${row.profit > 0 ? "text-accent" : row.profit < 0 ? "text-error" : ""}`}>{formatMoney(row.profit, { signed: true })}</td>
                <td className="num px-4 py-2.5 text-right text-muted sm:px-5">{formatPercent(row.roi)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function BetRow({ bet, leagues }: { bet: Bet; leagues: League[] }) {
  const title = bet.legs.length === 1 ? bet.legs[0].selection : `${bet.legs.length}-leg ${bet.bet_type === "sgp" ? "same-game parlay" : "parlay"}`;
  const league = bet.legs[0]?.league;
  return (
    <li className="border-t border-line px-4 py-3.5 first:border-t-0 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="font-medium">{title}</p>
          {bet.legs.length > 1 ? (
            <ul className="mt-1 space-y-0.5 text-sm text-muted">
              {bet.legs.map((leg) => (
                <li key={leg.id}>
                  {leg.selection} <Price price={leg.price} />
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-1 text-sm text-muted">
            {[bet.legs.length === 1 ? bet.legs[0].event_label : null, league ? leagueLabel(leagues, league) : null, bet.sportsbook, formatDay(bet.placed_at)].filter(Boolean).join(", ")}
            {bet.source === "sync" ? <Badge className="ml-2">Synced</Badge> : null}
          </p>
          {bet.notes ? <p className="mt-1 text-sm text-muted">Note: {bet.notes}</p> : null}
        </div>
        <dl className="flex shrink-0 items-start gap-5 text-right text-sm">
          <div>
            <dt className="text-xs text-muted">Odds</dt>
            <dd><Price price={bet.combined_price} className="font-medium" /></dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Stake</dt>
            <dd className="num">{formatMoney(bet.stake)}</dd>
          </div>
          {bet.clv !== null && bet.clv !== undefined ? (
            <div>
              <dt className="text-xs text-muted">CLV</dt>
              <dd className="num">{formatSignedPercent(bet.clv)}</dd>
            </div>
          ) : null}
          {bet.status === "pending" ? (
            <div>
              <dt className="text-xs text-muted">To return</dt>
              <dd className="num">{formatMoney(bet.potential_payout)}</dd>
            </div>
          ) : (
            <div>
              <dt className="text-xs text-muted">Profit</dt>
              <dd className={`num font-medium ${(bet.profit ?? 0) > 0 ? "text-accent" : (bet.profit ?? 0) < 0 ? "text-error" : ""}`}>{formatMoney(bet.profit ?? 0, { signed: true })}</dd>
            </div>
          )}
        </dl>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-1.5">
          {bet.status === "settled" && bet.result ? <Badge tone={RESULT_TONE[bet.result] ?? "neutral"}>{titleCase(bet.result)}</Badge> : <Badge tone="second">Open</Badge>}
          {bet.settled_by === "auto" ? <Badge>Settled from final score</Badge> : null}
          {bet.status === "pending" && bet.legs.every((leg) => leg.gradeable) ? <Badge>Tied to a game</Badge> : null}
        </span>
        <BetActions key={`${bet.id}-${bet.status}-${bet.updated_at}`} bet={bet} label={title} />
      </div>
    </li>
  );
}

export default async function TrackerPage() {
  const user = await currentUser();
  if (!user) {
    return (
      <>
        <PageHeader title="Bet tracker" description="Log bets in any odds format, settle them, and see profit, ROI and closing line value by sport, market and book." />
        <Panel>
          <EmptyState
            title="Log in to track your bets"
            action={
              <div className="flex gap-3">
                <ButtonLink href="/signup?next=/app/tracker">Create an account</ButtonLink>
                <ButtonLink href="/login?next=/app/tracker" variant="secondary">Log in</ButtonLink>
              </div>
            }
          >
            Your bets are private to your account. You can delete them, and your account, at any time.
          </EmptyState>
        </Panel>
      </>
    );
  }

  const [summary, bets, leagues, books, syncProviders, syncConnections] = await Promise.all([
    api<BetSummary>("/v1/bets/summary", { auth: true }),
    api<Bet[]>("/v1/bets", { auth: true }),
    getLeagues(),
    api<Book[]>("/v1/sportsbooks"),
    api<Schemas["SyncProviderOut"][]>("/v1/sync/providers", { auth: true }).catch(() => []),
    api<Schemas["SyncConnectionOut"][]>("/v1/sync/connections", { auth: true }).catch(() => []),
  ]);
  const { totals } = summary;
  const open = bets.filter((bet) => bet.status === "pending");
  const settled = bets.filter((bet) => bet.status === "settled");
  const timeline = summary.timeline.map((point) => ({ t: new Date(point.date).getTime(), v: point.cumulative_profit }));

  return (
    <>
      <PageHeader title="Bet tracker" description="Results you enter yourself are self-reported. Past results don't predict future ones." />
      <div className="space-y-5">
        <Panel aria-labelledby="perf-heading">
          <PanelHeader id="perf-heading" title="Performance" description={`${totals.settled_count} settled ${totals.settled_count === 1 ? "bet" : "bets"}`} />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-5 p-4 sm:p-5 md:grid-cols-5">
            <Stat label="Profit" value={formatMoney(totals.profit, { signed: true })} tone={totals.profit > 0 ? "accent" : totals.profit < 0 ? "error" : undefined} />
            <Stat label="ROI" value={formatPercent(totals.roi)} hint={`${formatMoney(totals.staked)} staked`} />
            <Stat label="Record" value={`${totals.wins}-${totals.losses}-${totals.pushes}`} hint="Won, lost, push" />
            <Stat label="Closing line value" value={formatSignedPercent(totals.avg_clv)} hint="Average, where a closing price was recorded" />
            <Stat label="Open bets" value={totals.pending_count} hint={`${formatMoney(totals.pending_exposure)} at risk`} />
          </dl>
          <div className="border-t border-line p-3 sm:p-5">
            <ProfitChart points={timeline} summary={`Cumulative profit over time, currently ${formatMoney(totals.profit, { signed: true })}`} />
          </div>
        </Panel>

        <Panel aria-labelledby="log-heading">
          <PanelHeader id="log-heading" title="Log a bet" description="OddVex records the bet. It does not place it." />
          <BetForm leagues={leagues} sportsbooks={books.map((book) => book.name)} />
        </Panel>

        <Panel aria-labelledby="open-heading">
          <PanelHeader id="open-heading" title="Open bets" description={`${open.length} open`} action={open.length ? <AutoSettleButton /> : undefined} />
          {open.length === 0 ? <EmptyState title="No open bets">Bets you log appear here until you settle them.</EmptyState> : <ul>{open.map((bet) => <BetRow key={bet.id} bet={bet} leagues={leagues} />)}</ul>}
        </Panel>

        <div className="grid gap-5 lg:grid-cols-2">
          <BreakdownTable title="By sport" rows={summary.by_sport} label={(key) => leagueLabel(leagues, key)} />
          <BreakdownTable title="By market" rows={summary.by_market} label={titleCase} />
          <BreakdownTable title="By sportsbook" rows={summary.by_sportsbook} label={(key) => key} />
          <BreakdownTable title="By bet type" rows={summary.by_bet_type} label={(key) => (key === "sgp" ? "Same-game parlay" : titleCase(key))} />
        </div>

        <Panel aria-labelledby="sync-heading">
          <PanelHeader id="sync-heading" title="Sportsbook sync" description="Import bets from a connected account without typing them in." />
          <SyncPanel providers={syncProviders} connections={syncConnections} />
        </Panel>

        <Panel aria-labelledby="settled-heading">
          <PanelHeader id="settled-heading" title="Settled bets" description={`${settled.length} settled, most recent first`} />
          {settled.length === 0 ? <EmptyState title="Nothing settled yet">Settle an open bet to start building your record.</EmptyState> : <ul>{settled.slice(0, 50).map((bet) => <BetRow key={bet.id} bet={bet} leagues={leagues} />)}</ul>}
        </Panel>
      </div>
    </>
  );
}
