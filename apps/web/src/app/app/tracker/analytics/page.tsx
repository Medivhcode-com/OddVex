import type { Metadata } from "next";
import type { Schemas } from "@oddvex/types";
import { Price } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { Meter } from "@/components/ui/charts";
import { ButtonLink, EmptyState, Notice, Panel, PanelHeader, Stat } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { requireFlag } from "@/lib/flags";
import { formatMoney, formatPercent, formatSignedPercent, formatStreak, shareOf, typographicMinus } from "@/lib/format";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Tracker analytics" };

/** `streak_note` is rendered when the API sends it; older API versions do not. */
type Analytics = Schemas["BetAnalyticsOut"] & { streak_note?: string | null };
type GroupRow = Schemas["AnalyticsRowOut"];

const DESCRIPTION = "Your settled bets by price, weekday and month, with runs, closing line value and stake sizes. A record of what happened, not a forecast.";

function profitClass(profit: number) {
  return profit > 0 ? "text-accent" : profit < 0 ? "text-error" : "";
}

/** The count with a bar for its share of the total. The number carries the meaning; the bar repeats it. */
function CountWithBar({ count, total, label }: { count: number; total: number; label: string }) {
  return (
    <span className="flex items-center justify-end gap-2">
      <Meter value={shareOf(count, total)} label={`${label}: ${count} of ${total} bets`} className="w-16 shrink-0 sm:w-24" />
      <span className="num w-8 text-right">{count}</span>
    </span>
  );
}

function ScrollTable({ children, minWidth = "min-w-[38rem]" }: { children: React.ReactNode; minWidth?: string }) {
  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
      <table className={`w-full ${minWidth} border-collapse text-sm`}>{children}</table>
    </div>
  );
}

function GroupTable({ id, title, description, groupLabel, rows, total }: { id: string; title: string; description: string; groupLabel: string; rows: GroupRow[]; total: number }) {
  return (
    <Panel aria-labelledby={id}>
      <PanelHeader id={id} title={title} description={description} />
      {rows.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted">No settled bets in this view yet.</p>
      ) : (
        <ScrollTable>
          <caption className="sr-only">{title}: bets, staked, profit, return on investment and win rate</caption>
          <thead>
            <tr className="text-xs text-muted">
              <th scope="col" className="px-4 py-2 text-left font-medium sm:px-5">{groupLabel}</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Bets</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Staked</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Profit</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">ROI</th>
              <th scope="col" className="px-4 py-2 text-right font-medium sm:px-5">Win rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const label = typographicMinus(row.label);
              return (
                <tr key={row.key} className="border-t border-line">
                  <th scope="row" className="num whitespace-nowrap px-4 py-2.5 text-left font-medium sm:px-5">{label}</th>
                  <td className="px-2 py-2.5"><CountWithBar count={row.bets} total={total} label={label} /></td>
                  <td className="num px-2 py-2.5 text-right text-muted">{formatMoney(row.staked)}</td>
                  <td className={`num px-2 py-2.5 text-right ${profitClass(row.profit)}`}>{formatMoney(row.profit, { signed: true })}</td>
                  <td className="num px-2 py-2.5 text-right text-muted">{formatPercent(row.roi)}</td>
                  <td className="num px-4 py-2.5 text-right text-muted sm:px-5">{formatPercent(row.win_rate)}</td>
                </tr>
              );
            })}
          </tbody>
        </ScrollTable>
      )}
    </Panel>
  );
}

export default async function TrackerAnalyticsPage() {
  await requireFlag("tracker_analytics");
  const user = await currentUser();
  if (!user) {
    return (
      <>
        <PageHeader title="Tracker analytics" description={DESCRIPTION} />
        <Panel>
          <EmptyState
            title="Log in to see your analytics"
            action={
              <div className="flex gap-3">
                <ButtonLink href="/signup?next=/app/tracker/analytics">Create an account</ButtonLink>
                <ButtonLink href="/login?next=/app/tracker/analytics" variant="secondary">Log in</ButtonLink>
              </div>
            }
          >
            Analytics are computed from the bets you track, and are private to your account.
          </EmptyState>
        </Panel>
      </>
    );
  }

  const data = await api<Analytics>("/v1/bets/analytics", { auth: true });
  const back = (
    <ButtonLink href="/app/tracker" variant="secondary">
      Back to the tracker
    </ButtonLink>
  );

  if (data.settled_count === 0) {
    return (
      <>
        <PageHeader title="Tracker analytics" description={DESCRIPTION} actions={back} />
        <Panel>
          <EmptyState title="No settled bets yet" action={<ButtonLink href="/app/tracker">Open the tracker</ButtonLink>}>
            Analytics use settled bets only. Log a bet and settle it, and the breakdowns appear here.
          </EmptyState>
        </Panel>
      </>
    );
  }

  const total = data.settled_count;
  const clv = data.clv;

  return (
    <>
      <PageHeader title="Tracker analytics" description={DESCRIPTION} actions={back} />
      <div className="space-y-5">
        {data.sample_note ? (
          <Notice tone="warn" title="Small sample">
            {data.sample_note}
          </Notice>
        ) : null}

        <Panel aria-labelledby="analytics-overview">
          <PanelHeader id="analytics-overview" title="Overview" description={`${total} settled ${total === 1 ? "bet" : "bets"}`} />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-5 p-4 sm:p-5 md:grid-cols-3">
            <Stat label="Average stake" value={data.average_stake === null || data.average_stake === undefined ? "n/a" : formatMoney(data.average_stake)} hint="Void bets left out" />
            <Stat label="Average odds" value={data.average_odds ? <Price price={data.average_odds} /> : "n/a"} hint="Mean of decimal odds, not weighted by stake" />
            <Stat label="Settled bets" value={total} />
          </dl>
        </Panel>

        <Panel aria-labelledby="analytics-streaks">
          <PanelHeader id="analytics-streaks" title="Streaks" description="Consecutive wins or losses in the order bets settled. A push or a void neither extends nor ends a run." />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-5 p-4 sm:p-5 md:grid-cols-3">
            <Stat label="Current run" value={formatStreak(data.current_streak.kind, data.current_streak.length)} />
            <Stat label="Longest run of wins" value={data.longest_win_streak} />
            <Stat label="Longest run of losses" value={data.longest_loss_streak} />
          </dl>
          {data.streak_note ? <p className="border-t border-line px-4 py-2.5 text-sm text-muted sm:px-5">{data.streak_note}</p> : null}
        </Panel>

        <GroupTable id="analytics-bands" title="By odds band" description="Grouped by the price of the bet. A parlay uses its combined price." groupLabel="American odds" rows={data.by_odds_band} total={total} />
        <GroupTable id="analytics-weekdays" title="By weekday" description="The day the bet was placed, in UTC." groupLabel="Day" rows={data.by_weekday} total={total} />
        <GroupTable id="analytics-months" title="By month" description="The month the bet was settled, in UTC." groupLabel="Month" rows={data.by_month} total={total} />

        <Panel aria-labelledby="analytics-clv">
          <PanelHeader id="analytics-clv" title="Closing line value" description="Bets with a closing price recorded on every leg. Closing prices are entered by you or the import source and are not verified." />
          {clv.sample === 0 ? (
            <p className="px-5 py-6 text-sm text-muted">No settled bet has a closing price yet. Add one when you edit a bet to see how your prices compare with the close.</p>
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-5 p-4 sm:p-5 md:grid-cols-3">
                <Stat label="Bets with a closing price" value={clv.sample} />
                <Stat label="Average CLV" value={formatSignedPercent(clv.average, 2)} hint="Price taken against the closing price" />
                <Stat label="Share above the close" value={formatPercent(clv.share_beating_close)} hint="Bets with CLV above 0" />
              </dl>
              <div className="border-t border-line">
                <ScrollTable minWidth="min-w-[20rem]">
                  <caption className="sr-only">Closing line value: number of bets in each range</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      <th scope="col" className="px-4 py-2 text-left font-medium sm:px-5">CLV range</th>
                      <th scope="col" className="px-4 py-2 text-right font-medium sm:px-5">Bets</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clv.buckets.map((bucket) => {
                      const label = typographicMinus(bucket.label);
                      return (
                        <tr key={bucket.key} className="border-t border-line">
                          <th scope="row" className="num whitespace-nowrap px-4 py-2.5 text-left font-medium sm:px-5">{label}</th>
                          <td className="px-4 py-2.5 sm:px-5"><CountWithBar count={bucket.count} total={clv.sample} label={label} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </ScrollTable>
              </div>
              <p className="border-t border-line px-4 py-2.5 text-sm text-muted sm:px-5">
                CLV describes the prices you took over many bets. It does not say whether any one bet wins.
              </p>
            </>
          )}
        </Panel>

        <Panel aria-labelledby="analytics-stakes">
          <PanelHeader id="analytics-stakes" title="Stake sizes" description="How many bets fall in each stake range, and the amount staked there." />
          <ScrollTable minWidth="min-w-[24rem]">
            <caption className="sr-only">Stake sizes: bets and amount staked in each range</caption>
            <thead>
              <tr className="text-xs text-muted">
                <th scope="col" className="px-4 py-2 text-left font-medium sm:px-5">Stake</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Bets</th>
                <th scope="col" className="px-4 py-2 text-right font-medium sm:px-5">Staked</th>
              </tr>
            </thead>
            <tbody>
              {data.stake_distribution.map((bucket) => (
                <tr key={bucket.key} className="border-t border-line">
                  <th scope="row" className="num whitespace-nowrap px-4 py-2.5 text-left font-medium sm:px-5">{bucket.label}</th>
                  <td className="px-2 py-2.5"><CountWithBar count={bucket.bets} total={total} label={bucket.label} /></td>
                  <td className="num px-4 py-2.5 text-right text-muted sm:px-5">{formatMoney(bucket.staked)}</td>
                </tr>
              ))}
            </tbody>
          </ScrollTable>
        </Panel>

        <p className="max-w-3xl text-sm text-muted">{data.note}</p>
      </div>
    </>
  );
}
