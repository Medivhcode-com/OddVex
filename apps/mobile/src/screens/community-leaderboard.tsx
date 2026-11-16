import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getLeaderboard, getLeagues } from '@/api/client';
import type { LeaderboardRow, LeaderboardWindow } from '@/api/types';
import { RANKING_EXPLAINED } from '@/components/community-copy';
import { CommunityGate } from '@/components/community-gate';
import { intervalText, sampleText } from '@/components/community-record';
import { Choice } from '@/components/form';
import { Screen } from '@/components/screen';
import { EmptyState, ErrorState, Notice, SkeletonCards } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, radius, space, touchTarget } from '@/theme';
import { formatAge, formatPercent } from '@/utils/format';

const WINDOWS: readonly { value: LeaderboardWindow; label: string }[] = [
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'all', label: 'All time' },
];
const ALL_LEAGUES = 'all';

function Row({ row }: { row: LeaderboardRow }) {
  const router = useRouter();
  const theme = useTheme();
  const { record } = row;
  const interval = intervalText(record);
  const winRate = `Win rate ${formatPercent(record.win_rate)}`;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Rank ${row.rank}. ${row.handle}. ${sampleText(record)}. ${winRate}${interval ? `, ${interval}` : ''}.`}
      accessibilityHint="Opens this profile"
      onPress={() => router.push({ pathname: '/community/profiles/[handle]', params: { handle: row.handle } })}
      style={({ pressed }) => [styles.row, { backgroundColor: theme.surface, borderColor: theme.border }, pressed && { backgroundColor: theme.raised }]}>
      <Num size={fontSize.score} tone="muted" style={styles.rank}>
        {row.rank}
      </Num>
      <View style={styles.rowText}>
        <Txt weight="semibold">@{row.handle}</Txt>
        <Txt variant="secondary" tone="muted">
          {sampleText(record)} · {record.wins}-{record.losses}-{record.pushes}
        </Txt>
        <Txt variant="secondary">{winRate}</Txt>
        {interval ? (
          <Txt variant="secondary" tone="muted">
            {interval}
          </Txt>
        ) : null}
      </View>
    </Pressable>
  );
}

function Leaderboard() {
  const now = useNow();
  const [league, setLeague] = useState<string>(ALL_LEAGUES);
  const [period, setPeriod] = useState<LeaderboardWindow>('90d');
  const leagues = useResource('leagues', getLeagues);
  const board = useResource(`community-leaderboard:${league}:${period}`, (signal) =>
    getLeaderboard({ league: league === ALL_LEAGUES ? null : league, window: period }, signal),
  );
  const refresh = () => {
    board.reload();
    if (leagues.status === 'error') leagues.reload();
  };
  const leagueOptions = [{ value: ALL_LEAGUES, label: 'All leagues' }, ...(leagues.data ?? []).map((item) => ({ value: item.key, label: item.name }))];

  return (
    <Screen refreshing={board.refreshing} onRefresh={refresh}>
      {board.data ? <Notice tone="warn" title="What a ranking does not tell you" text={board.data.caveat} /> : null}
      <Txt variant="secondary" tone="muted">
        {RANKING_EXPLAINED}
      </Txt>
      <Choice label="League" options={leagueOptions} value={league} onChange={setLeague} />
      <Choice label="Period" options={WINDOWS} value={period} onChange={setPeriod} />
      {board.status === 'loading' ? (
        <SkeletonCards label="Loading the leaderboard" />
      ) : board.status === 'error' || !board.data ? (
        <ErrorState error={board.error} onRetry={refresh} />
      ) : (
        <>
          {board.error !== undefined ? <Notice text="Couldn't refresh. Showing the last ranking loaded." /> : null}
          <Notice tone="neutral" title="How profiles are ranked" text={board.data.method} />
          {board.data.items.length === 0 ? (
            <EmptyState
              title="Nobody is ranked yet"
              body={`Only profiles with at least ${board.data.minimum_graded_picks} graded picks in this period are ranked. Try a longer period or another league.`}
            />
          ) : (
            <>
              {board.data.items.map((row) => (
                <Row key={row.handle} row={row} />
              ))}
              <Txt variant="caption" tone="muted" style={styles.end}>
                {board.data.items.length} {board.data.items.length === 1 ? 'profile' : 'profiles'} with at least {board.data.minimum_graded_picks} graded picks. Checked{' '}
                {formatAge(board.data.as_of, now)}.
              </Txt>
            </>
          )}
        </>
      )}
    </Screen>
  );
}

/**
 * Profiles ranked by the API (flags `community` and `community_leaderboard`). The API's caveat sits above the
 * rows; each row carries its sample size and interval. Nothing is sorted, scored or decorated here.
 */
export function CommunityLeaderboardScreen() {
  return <CommunityGate leaderboard>{(user) => (user ? <Leaderboard /> : null)}</CommunityGate>;
}

const styles = StyleSheet.create({
  row: {
    minHeight: touchTarget,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space[3],
    padding: space[4],
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.panel,
  },
  rank: { minWidth: 28 },
  rowText: { flex: 1, gap: 2 },
  end: { textAlign: 'center' },
});
