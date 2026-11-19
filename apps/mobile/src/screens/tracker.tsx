import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { describeError, getBets, getBetSummary, getLeagues, getSyncConnections, getSyncProviders } from '@/api/client';
import type { Bet, League } from '@/api/types';
import { AutoSettleButton } from '@/components/auto-settle';
import { BetCard } from '@/components/bet-card';
import { HelpLine } from '@/components/help-link';
import { StakeReminderNotice } from '@/components/notification-settings';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, PanelHeading, SkeletonCards, Stat, StatGrid } from '@/components/states';
import { SyncPanel } from '@/components/sync-panel';
import { Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useStakeReminder } from '@/hooks/use-notifications';
import { useResource } from '@/hooks/use-resource';
import { useSettledBets } from '@/hooks/use-settled-bets';
import { useFlag } from '@/providers/flags';
import { openLogin, useSession } from '@/providers/session';
import { leagueLabel } from '@/screens/games';
import { space } from '@/theme';
import { formatMoney, formatPercent, formatSignedPercent } from '@/utils/format';

/** Open bets are read in one request of their own, at the API's largest `limit`, so none falls outside it. */
const OPEN_LIMIT = 1000;

function SignedOut() {
  const router = useRouter();
  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        Log bets in any odds format, settle them, and see profit, ROI and closing line value.
      </Txt>
      <EmptyState
        title="Log in to track your bets"
        body="Your bets are private to your account. You can delete them, and your account, at any time.">
        <View style={styles.row}>
          <Button label="Create an account" onPress={() => router.push('/signup')} />
          <Button label="Log in" variant="secondary" onPress={openLogin} />
        </View>
      </EmptyState>
      <HelpLine />
    </Screen>
  );
}

function BetList({ bets, leagues, onChanged }: { bets: readonly Bet[]; leagues: readonly League[]; onChanged: () => void }) {
  return (
    <>
      {bets.map((bet) => {
        const league = bet.legs[0]?.league;
        return (
          <BetCard
            // A fresh card after every change, so its form fields start from the saved values.
            key={`${bet.id}-${bet.status}-${bet.updated_at}`}
            bet={bet}
            leagueName={league ? leagueLabel(leagues, league) : undefined}
            onChanged={onChanged}
          />
        );
      })}
    </>
  );
}

function SectionTitle({ title, detail }: { title: string; detail: string }) {
  return (
    <View style={styles.section} accessibilityRole="header">
      <Txt variant="heading">{title}</Txt>
      <Txt variant="caption" tone="muted">
        {detail}
      </Txt>
    </View>
  );
}

function SignedIn({ userId }: { userId: string }) {
  const router = useRouter();
  const now = useNow();
  const { revision, changed } = useSession();
  const analyticsOn = useFlag('tracker_analytics');
  const summary = useResource(`bet-summary:${userId}`, getBetSummary, revision.bets);
  const openBets = useResource(`bets-open:${userId}`, (signal) => getBets({ status: 'pending', limit: OPEN_LIMIT }, signal), revision.bets);
  const settledBets = useSettledBets(userId, revision.bets);
  const leagues = useResource('leagues', getLeagues);
  const providers = useResource(`sync-providers:${userId}`, getSyncProviders);
  const connections = useResource(`sync-connections:${userId}`, getSyncConnections, revision.bets);
  // Extra to the tracker: if it fails to load, the tracker simply shows no reminder notice.
  const reminder = useStakeReminder(userId);

  const onChanged = () => changed('bets');
  const refresh = () => {
    summary.reload();
    openBets.reload();
    settledBets.reload();
    connections.reload();
    reminder.reload();
    if (leagues.status === 'error') leagues.reload();
    if (providers.status === 'error') providers.reload();
  };

  const lists = [openBets, settledBets, summary];
  const failed = lists.find((list) => list.status === 'error')?.error;
  const loading = lists.some((list) => list.status === 'loading');
  const open = openBets.data ?? [];
  const settled = settledBets.bets;
  const totals = summary.data?.totals;
  // The counts are the summary's: the lists hold only what has been loaded so far.
  const openCount = totals?.pending_count ?? open.length;
  const settledCount = totals?.settled_count ?? settled.length;
  // A full page with nothing behind it (exactly 50 settled bets, say) offers no "Show more".
  const moreSettled = settledBets.hasMore && (!totals || settled.length < settledCount);
  const leagueList = leagues.data ?? [];

  return (
    <Screen refreshing={lists.some((list) => list.refreshing)} onRefresh={refresh}>
      {reminder.data ? <StakeReminderNotice reminder={reminder.data} /> : null}
      <Txt variant="secondary" tone="muted">
        Results you enter yourself are self-reported. Past results don&apos;t predict future ones.
      </Txt>
      <HelpLine />

      {failed !== undefined ? (
        <ErrorState error={failed} onRetry={refresh} />
      ) : loading ? (
        <SkeletonCards label="Loading your bets" />
      ) : (
        <>
          {lists.some((list) => list.error !== undefined) ? (
            <Notice text="Couldn't refresh. Showing the last results loaded." />
          ) : null}

          {totals ? (
            <Panel>
              <View style={styles.block}>
                <PanelHeading title="Performance" description={`${totals.settled_count} settled ${totals.settled_count === 1 ? 'bet' : 'bets'}`} />
                <StatGrid>
                  <Stat
                    label="Profit"
                    value={formatMoney(totals.profit, { signed: true })}
                    tone={totals.profit > 0 ? 'accent' : totals.profit < 0 ? 'error' : undefined}
                  />
                  <Stat label="ROI" value={formatPercent(totals.roi)} hint={`${formatMoney(totals.staked)} staked`} />
                  <Stat label="Record" value={`${totals.wins}-${totals.losses}-${totals.pushes}`} hint="Won, lost, push" />
                  <Stat label="Closing line value" value={formatSignedPercent(totals.avg_clv)} hint="Average, where a closing price was recorded" />
                  <Stat label="Open bets" value={String(totals.pending_count)} hint={`${formatMoney(totals.pending_exposure)} at risk`} />
                </StatGrid>
              </View>
            </Panel>
          ) : null}

          {analyticsOn ? (
            <Panel>
              <View style={styles.block}>
                <PanelHeading title="Analytics" description="Your settled bets by odds, weekday and month, with runs, stake sizes and closing line value." />
                <Button label="Open analytics" variant="secondary" onPress={() => router.push('/analytics')} />
              </View>
            </Panel>
          ) : null}

          <Panel>
            <View style={styles.block}>
              <PanelHeading title="Log a bet" description="OddVex records the bet. It does not place it." />
              <Button label="Log a bet" onPress={() => router.push('/log-bet')} />
            </View>
          </Panel>

          <SectionTitle
            title="Open bets"
            // Only an account with more open bets than one request can carry sees the longer wording.
            detail={open.length >= OPEN_LIMIT && open.length < openCount ? `Showing ${open.length} of ${openCount} open, most recently placed first` : `${openCount} open`}
          />
          {open.length === 0 ? (
            <EmptyState title="No open bets" body="Bets you log appear here until you settle them." />
          ) : (
            <>
              <AutoSettleButton onSettled={onChanged} />
              <BetList bets={open} leagues={leagueList} onChanged={onChanged} />
            </>
          )}

          <SectionTitle
            title="Settled bets"
            detail={
              moreSettled
                ? `Showing ${settled.length} of ${settledCount}, most recently placed first`
                : `${settledCount} settled, most recently placed first`
            }
          />
          {settled.length === 0 ? (
            <EmptyState title="Nothing settled yet" body="Settle an open bet to start building your record." />
          ) : (
            <BetList bets={settled} leagues={leagueList} onChanged={onChanged} />
          )}
          {settledBets.moreError !== undefined ? (
            <Notice tone="error" text={describeError(settledBets.moreError, "Couldn't load more bets. Try again.")} />
          ) : null}
          {moreSettled ? (
            <Button
              label={settledBets.loadingMore ? 'Loading more' : 'Show more'}
              variant="secondary"
              disabled={settledBets.loadingMore}
              accessibilityLabel={settledBets.loadingMore ? 'Loading more settled bets' : 'Show more settled bets'}
              onPress={settledBets.showMore}
            />
          ) : null}

          <Panel>
            <View style={styles.block}>
              <PanelHeading title="Sportsbook sync" description="Import bets from a connected account without typing them in." />
              {providers.status === 'error' || connections.status === 'error' ? (
                <Txt variant="secondary" tone="muted">
                  Sync is unavailable right now. Pull down to try again.
                </Txt>
              ) : providers.data && connections.data ? (
                <SyncPanel providers={providers.data} connections={connections.data} now={now} onChanged={onChanged} />
              ) : (
                <Txt variant="secondary" tone="muted">
                  Loading connections.
                </Txt>
              )}
            </View>
          </Panel>
        </>
      )}
    </Screen>
  );
}

export function TrackerScreen() {
  const session = useSession();
  if (session.status === 'loading') {
    return (
      <Screen>
        <HelpLine />
        <SkeletonCards label="Checking your account" count={2} />
      </Screen>
    );
  }
  if (!session.user) return <SignedOut />;
  return <SignedIn userId={session.user.id} />;
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  row: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space[3] },
  section: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', paddingTop: space[2] },
});
