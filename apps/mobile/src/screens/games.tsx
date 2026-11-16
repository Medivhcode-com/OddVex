import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, SectionList, StyleSheet, View } from 'react-native';

import { getEvents, getLeagues, getWatchlistEvents } from '@/api/client';
import type { EventStatus, EventSummary, League } from '@/api/types';
import { FilterChips } from '@/components/choice';
import { GameCard } from '@/components/game-card';
import { Button, EmptyState, ErrorState, Notice, Panel, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { useWatchlist } from '@/hooks/use-watchlist';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { useMeta } from '@/providers/meta';
import { CommunityEntry } from '@/components/community-entry';
import { ValueEntry } from '@/components/value-entry';
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

const WATCHED_SHOWN = 6;

/** "Your watchlist": live and upcoming games for what the user follows, and the players they follow. */
export function Watchlist({ userId, leagues }: { userId: string; leagues: readonly League[] }) {
  const router = useRouter();
  const { revision } = useSession();
  const items = useWatchlist();
  const events = useResource(`watchlist-events:${userId}`, getWatchlistEvents, revision.watchlist);
  const players = (items.data ?? []).filter((item) => item.kind === 'player');
  const retry = () => {
    items.reload();
    events.reload();
  };

  return (
    <View style={styles.watchlist}>
      <Txt variant="heading" accessibilityRole="header">
        Your watchlist
      </Txt>
      {items.status === 'loading' || events.status === 'loading' ? (
        <SkeletonCards label="Loading your watchlist" count={1} />
      ) : items.status === 'error' || events.status === 'error' ? (
        <Panel>
          <View style={styles.watchError} accessibilityRole="alert">
            <Txt variant="secondary" tone="muted">
              OddVex can&apos;t reach its data service, so your watchlist did not load. Your follows are safe.
            </Txt>
            <Button label="Try again" variant="secondary" accessibilityLabel="Try loading your watchlist again" onPress={retry} />
          </View>
        </Panel>
      ) : (items.data ?? []).length === 0 ? (
        <EmptyState title="Nothing followed yet" body="Open a game or a player and choose Follow. Their upcoming games show up here." />
      ) : (
        <>
          {(events.data ?? []).length ? (
            (events.data ?? []).slice(0, WATCHED_SHOWN).map((event) => (
              <Link key={event.id} href={{ pathname: '/event/[id]', params: { id: event.id } }} asChild>
                <GameCard event={event} leagueName={leagueLabel(leagues, event.league)} />
              </Link>
            ))
          ) : (
            <Txt variant="secondary" tone="muted">
              No live or upcoming games for what you follow.
            </Txt>
          )}
          {players.length ? (
            <View style={styles.players}>
              {players.map((item) => (
                <Button
                  key={item.id}
                  label={item.label}
                  variant="ghost"
                  compact
                  accessibilityLabel={`${item.label}, followed player`}
                  accessibilityHint="Opens the prop analyzer for this player"
                  onPress={() => router.push({ pathname: '/player/[id]', params: { id: item.ref_id } })}
                />
              ))}
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

/** The way in to OddVex AI from the first screen. */
function AskCard() {
  const router = useRouter();
  return (
    <Panel>
      <View style={styles.ask}>
        <Txt variant="heading" accessibilityRole="header">
          Ask OddVex AI
        </Txt>
        <Txt variant="secondary" tone="muted">
          Find a best price, check a player&apos;s recent form or get a formula explained, with sources.
        </Txt>
        <Button label="Ask a question" variant="secondary" compact onPress={() => router.push('/assistant')} />
      </View>
    </Panel>
  );
}

export function GamesScreen() {
  const session = useSession();
  const theme = useTheme();
  const meta = useMeta();
  const valueScreen = useFlag('value_screen');
  const community = useFlag('community');
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
          <AskCard />
          {valueScreen ? <ValueEntry compact /> : null}
          {community ? <CommunityEntry /> : null}
          {session.user ? <Watchlist userId={session.user.id} leagues={leagueList} /> : null}
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
  header: { gap: space[3], marginBottom: space[2], paddingTop: space[4] },
  watchlist: { gap: space[3] },
  watchError: { gap: space[3] },
  players: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  ask: { gap: space[2] },
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
