import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { getBets, getBetSummary, getLeagues, getSyncConnections, getSyncProviders } from '@/api/client';
import type { Bet, League } from '@/api/types';
import { AutoSettleButton } from '@/components/auto-settle';
import { BetCard } from '@/components/bet-card';
import { StakeReminderNotice } from '@/components/notification-settings';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, PanelHeading, SkeletonCards, Stat, StatGrid } from '@/components/states';
import { SyncPanel } from '@/components/sync-panel';
import { Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useStakeReminder } from '@/hooks/use-notifications';
import { useResource } from '@/hooks/use-resource';
import { openLogin, useSession } from '@/providers/session';
import { leagueLabel } from '@/screens/games';
import { space } from '@/theme';
import { formatMoney, formatPercent, formatSignedPercent } from '@/utils/format';

const SETTLED_SHOWN = 50;

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
  const summary = useResource(`bet-summary:${userId}`, getBetSummary, revision.bets);
  const bets = useResource(`bets:${userId}`, getBets, revision.bets);
  const leagues = useResource('leagues', getLeagues);
  const providers = useResource(`sync-providers:${userId}`, getSyncProviders);
  const connections = useResource(`sync-connections:${userId}`, getSyncConnections, revision.bets);
  // Extra to the tracker: if it fails to load, the tracker simply shows no reminder notice.
  const reminder = useStakeReminder(userId);

  const onChanged = () => changed('bets');
  const refresh = () => {
    summary.reload();
    bets.reload();
    connections.reload();
    reminder.reload();
    if (leagues.status === 'error') leagues.reload();
    if (providers.status === 'error') providers.reload();
  };

  const failed = bets.status === 'error' ? bets.error : summary.status === 'error' ? summary.error : undefined;
  const loading = bets.status === 'loading' || summary.status === 'loading';
  const all = bets.data ?? [];
  const open = all.filter((bet) => bet.status === 'pending');
  const settled = all.filter((bet) => bet.status === 'settled');
  const totals = summary.data?.totals;
  const leagueList = leagues.data ?? [];

  return (
    <Screen refreshing={bets.refreshing || summary.refreshing} onRefresh={refresh}>
      {reminder.data ? <StakeReminderNotice reminder={reminder.data} /> : null}
      <Txt variant="secondary" tone="muted">
        Results you enter yourself are self-reported. Past results don&apos;t predict future ones.
      </Txt>

      {failed !== undefined ? (
        <ErrorState error={failed} onRetry={refresh} />
      ) : loading ? (
        <SkeletonCards label="Loading your bets" />
      ) : (
        <>
          {bets.error !== undefined || summary.error !== undefined ? (
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

          <Panel>
            <View style={styles.block}>
              <PanelHeading title="Log a bet" description="OddVex records the bet. It does not place it." />
              <Button label="Log a bet" onPress={() => router.push('/log-bet')} />
            </View>
          </Panel>

          <SectionTitle title="Open bets" detail={`${open.length} open`} />
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
              settled.length > SETTLED_SHOWN
                ? `Latest ${SETTLED_SHOWN} of ${settled.length}, most recent first`
                : `${settled.length} settled, most recent first`
            }
          />
          {settled.length === 0 ? (
            <EmptyState title="Nothing settled yet" body="Settle an open bet to start building your record." />
          ) : (
            <BetList bets={settled.slice(0, SETTLED_SHOWN)} leagues={leagueList} onChanged={onChanged} />
          )}

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
