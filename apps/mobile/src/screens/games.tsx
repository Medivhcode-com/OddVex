import { Link } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, SectionList, StyleSheet, View } from 'react-native';

import { getEvents, getLeagues } from '@/api/client';
import type { EventStatus, EventSummary, League } from '@/api/types';
import { FilterChips } from '@/components/choice';
import { GameCard } from '@/components/game-card';
import { EmptyState, ErrorState, Notice, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { useMeta } from '@/providers/meta';
import { space } from '@/theme';

const GROUPS: readonly { status: EventStatus; title: string }[] = [
  { status: 'live', title: 'Live' },
  { status: 'upcoming', title: 'Upcoming' },
  { status: 'final', title: 'Final' },
];

/** Groups events by status, keeping the API's order inside each group and dropping empty groups. */
export function groupEvents(events: readonly EventSummary[]) {
  return GROUPS.map((group) => ({
    title: group.title,
    data: events.filter((event) => event.status === group.status),
  })).filter((section) => section.data.length > 0);
}

export function leagueLabel(leagues: readonly League[], key: string): string {
  return leagues.find((league) => league.key === key)?.name ?? key.toUpperCase();
}

export function GamesScreen() {
  const theme = useTheme();
  const meta = useMeta();
  const [league, setLeague] = useState<string | null>(null);
  const leagues = useResource('leagues', getLeagues);
  const events = useResource(`events:${league ?? ''}`, (signal) => getEvents({ league }, signal));

  const leagueList = leagues.data ?? [];
  const sections = events.data ? groupEvents(events.data) : [];

  const refresh = () => {
    events.reload();
    if (leagues.status === 'error') leagues.reload();
    if (meta.status === 'error') meta.reload();
  };

  return (
    <SectionList
      style={{ backgroundColor: theme.bg }}
      contentContainerStyle={styles.content}
      contentInsetAdjustmentBehavior="automatic"
      sections={sections}
      keyExtractor={(event) => event.id}
      stickySectionHeadersEnabled={false}
      refreshControl={<RefreshControl refreshing={events.refreshing} onRefresh={refresh} tintColor={theme.muted} />}
      ListHeaderComponent={
        <View style={styles.header}>
          <View style={styles.chips}>
            <FilterChips
              label="Filter by league"
              allLabel="All leagues"
              options={leagueList.map((item) => ({ value: item.key, label: item.name }))}
              value={league}
              onChange={setLeague}
            />
          </View>
          {events.data && events.error !== undefined ? (
            <Notice text="Couldn't refresh. Showing the last prices loaded." />
          ) : null}
        </View>
      }
      ListEmptyComponent={
        events.status === 'loading' ? (
          <SkeletonCards label="Loading games" />
        ) : events.status === 'error' ? (
          <ErrorState error={events.error} onRetry={refresh} />
        ) : (
          <EmptyState
            title="No games to show"
            body={
              league
                ? `There are no ${leagueLabel(leagueList, league)} games on the board right now. Try another league or pull down to refresh.`
                : 'There are no games on the board right now. Pull down to refresh.'
            }
          />
        )
      }
      renderSectionHeader={({ section }) => (
        <View style={styles.sectionHeader} accessibilityRole="header">
          <Txt variant="heading">{section.title}</Txt>
          <Txt variant="caption" tone="muted">
            {section.data.length} {section.data.length === 1 ? 'game' : 'games'}
          </Txt>
        </View>
      )}
      renderItem={({ item }) => (
        <View style={styles.item}>
          <Link href={{ pathname: '/event/[id]', params: { id: item.id } }} asChild>
            <GameCard event={item} leagueName={leagueLabel(leagueList, item.league)} />
          </Link>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: space[4], paddingBottom: space[8] },
  header: { gap: space[2], marginBottom: space[2] },
  chips: { marginHorizontal: -space[4] },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    paddingTop: space[4],
    paddingBottom: space[2],
  },
  item: { marginBottom: space[3] },
});
