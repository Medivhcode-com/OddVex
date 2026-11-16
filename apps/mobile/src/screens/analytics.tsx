import { StyleSheet, View } from 'react-native';

import { getBetAnalytics } from '@/api/client';
import type { AnalyticsRow, BetAnalytics } from '@/api/types';
import { BarRows, type BarRow } from '@/components/bar-rows';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, PanelHeading, SkeletonCards, Stat, StatGrid } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useOddsFormat } from '@/providers/odds-format';
import { openLogin, useSession } from '@/providers/session';
import { space } from '@/theme';
import { formatMoney, formatPercent, formatPrice, formatSignedPercent } from '@/utils/format';

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** "7 bets · $175.00 staked · profit −$12.50 · ROI −7.1% · win rate 42.9%", or "No settled bets". */
export function rowDetail(row: AnalyticsRow): string {
  if (row.bets === 0) return 'No settled bets';
  return [
    plural(row.bets, 'bet', 'bets'),
    `${formatMoney(row.staked)} staked`,
    `profit ${formatMoney(row.profit, { signed: true })}`,
    `ROI ${formatSignedPercent(row.roi)}`,
    `win rate ${formatPercent(row.win_rate)}`,
  ].join(' · ');
}

function breakdown(rows: readonly AnalyticsRow[]): BarRow[] {
  return rows.map((row) => ({ key: row.key, label: row.label, count: row.bets, detail: rowDetail(row) }));
}

/** A run described without praise or alarm: "2 losses in a row", "1 win", "No current run". */
export function streakText(streak: BetAnalytics['current_streak']): string {
  if (streak.kind === 'none' || streak.length === 0) return 'No current run';
  const word = streak.kind === 'win' ? plural(streak.length, 'win', 'wins') : plural(streak.length, 'loss', 'losses');
  return streak.length === 1 ? word : `${word} in a row`;
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Panel>
      <View style={styles.block}>
        <PanelHeading title={title} description={description} />
        {children}
      </View>
    </Panel>
  );
}

function Loaded({ data }: { data: BetAnalytics }) {
  const { format } = useOddsFormat();
  if (data.settled_count === 0) {
    return (
      <EmptyState
        title="No settled bets yet"
        body="Analytics are built from settled bets only. Settle a bet in the tracker and its numbers show up here."
      />
    );
  }
  const { clv } = data;
  return (
    <>
      {data.sample_note ? <Notice tone="warn" title="Small sample" text={data.sample_note} /> : null}

      <Section title="Overview" description={plural(data.settled_count, 'settled bet', 'settled bets')}>
        <StatGrid>
          <Stat label="Average stake" value={data.average_stake === null || data.average_stake === undefined ? 'n/a' : formatMoney(data.average_stake)} />
          <Stat label="Average odds" value={data.average_odds ? formatPrice(data.average_odds, format) : 'n/a'} hint="Mean of the bets' decimal odds" />
        </StatGrid>
      </Section>

      <Section title="By odds" description="Grouped by the price of the bet, shortest prices first.">
        <BarRows label="Results by odds band" rows={breakdown(data.by_odds_band)} />
      </Section>

      <Section title="By weekday" description="The day the bet was placed, in UTC.">
        <BarRows label="Results by weekday" rows={breakdown(data.by_weekday)} />
      </Section>

      <Section title="By month" description="The month the bet was settled, in UTC.">
        {data.by_month.length ? (
          <BarRows label="Results by month" rows={breakdown(data.by_month)} />
        ) : (
          <Txt variant="secondary" tone="muted">
            No months to show yet.
          </Txt>
        )}
      </Section>

      <Section title="Runs" description="Consecutive wins or losses. A push or a void neither extends nor ends a run.">
        <StatGrid>
          <Stat label="Current run" value={streakText(data.current_streak)} />
          <Stat label="Longest run of wins" value={String(data.longest_win_streak)} />
          <Stat label="Longest run of losses" value={String(data.longest_loss_streak)} />
        </StatGrid>
        {data.streak_note ? (
          <Txt variant="secondary" tone="muted">
            {data.streak_note}
          </Txt>
        ) : null}
      </Section>

      <Section title="Closing line value" description="How the price you took compares with the closing price, where one was recorded on every leg.">
        {clv.sample === 0 ? (
          <Txt variant="secondary" tone="muted">
            No settled bet has a closing price on every leg yet.
          </Txt>
        ) : (
          <>
            <StatGrid>
              <Stat label="Average" value={formatSignedPercent(clv.average)} hint={`From ${plural(clv.sample, 'bet', 'bets')}`} />
              <Stat label="Share above the close" value={formatPercent(clv.share_beating_close)} hint="Bets with a value above 0" />
            </StatGrid>
            <BarRows
              label="Closing line value by size"
              rows={clv.buckets.map((bucket) => ({ key: bucket.key, label: bucket.label, count: bucket.count, detail: plural(bucket.count, 'bet', 'bets') }))}
            />
          </>
        )}
      </Section>

      <Section title="Stake sizes" description="How many settled bets fall in each stake range.">
        {data.stake_distribution.length ? (
          <BarRows
            label="Bets by stake size"
            rows={data.stake_distribution.map((bucket) => ({
              key: bucket.key,
              label: bucket.label,
              count: bucket.bets,
              detail: `${plural(bucket.bets, 'bet', 'bets')} · ${formatMoney(bucket.staked)} staked`,
            }))}
          />
        ) : (
          <Txt variant="secondary" tone="muted">
            No stakes to show yet.
          </Txt>
        )}
      </Section>

      {data.note ? (
        <Txt variant="caption" tone="muted">
          {data.note}
        </Txt>
      ) : null}
    </>
  );
}

function SignedIn({ userId }: { userId: string }) {
  const { revision } = useSession();
  const analytics = useResource(`bet-analytics:${userId}`, getBetAnalytics, revision.bets);
  return (
    <Screen refreshing={analytics.refreshing} onRefresh={analytics.reload}>
      <Txt variant="secondary" tone="muted">
        A record of your settled bets. Past results don&apos;t predict future ones.
      </Txt>
      {analytics.status === 'loading' ? (
        <SkeletonCards label="Loading your analytics" />
      ) : analytics.status === 'error' || !analytics.data ? (
        <ErrorState error={analytics.error} onRetry={analytics.reload} />
      ) : (
        <>
          {analytics.error !== undefined ? <Notice text="Couldn't refresh. Showing the last results loaded." /> : null}
          <Loaded data={analytics.data} />
        </>
      )}
    </Screen>
  );
}

/** Breakdowns of the user's settled bets (`GET /v1/bets/analytics`, flag `tracker_analytics`). Every number is the API's. */
export function AnalyticsScreen() {
  const session = useSession();
  if (session.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Checking your account" count={2} />
      </Screen>
    );
  }
  if (!session.user) {
    return (
      <Screen>
        <EmptyState title="Log in to see your analytics" body="Analytics are built from the bets you track, which are private to your account.">
          <Button label="Log in" variant="secondary" onPress={openLogin} />
        </EmptyState>
      </Screen>
    );
  }
  return <SignedIn userId={session.user.id} />;
}

const styles = StyleSheet.create({ block: { gap: space[3] } });
