import { Stack } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { getEvent, getEventOdds } from '@/api/client';
import { MARKETS, type EventSummary, type Market, type OddsComparison } from '@/api/types';
import { Segmented } from '@/components/choice';
import { EventStatus } from '@/components/game-card';
import { ConsensusRow, OddsRow, type OddsColumn } from '@/components/odds-row';
import { ErrorState, Notice, Panel, SkeletonCards } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, space } from '@/theme';
import { formatAge } from '@/utils/format';

/** Outcome columns come from the consensus when there is one, otherwise from the first book with prices. */
export function oddsColumns(odds: OddsComparison): OddsColumn[] {
  if (odds.consensus.outcomes.length) return odds.consensus.outcomes.map(({ key, name }) => ({ key, name }));
  const first = odds.books.find((book) => book.outcomes.length);
  return first ? first.outcomes.map(({ key, name }) => ({ key, name })) : [];
}

function Scoreboard({ event }: { event: EventSummary }) {
  const sides = [
    { team: event.away_team, score: event.score?.away, role: 'Away' },
    { team: event.home_team, score: event.score?.home, role: 'Home' },
  ];
  return (
    <Panel>
      <View style={styles.scoreboard}>
        <EventStatus event={event} />
        {sides.map(({ team, score, role }) => (
          <View key={role} style={styles.teamRow}>
            <View style={styles.teamName}>
              <Txt weight="semibold">{team.name}</Txt>
              <Txt variant="caption" tone="muted">
                {role}
              </Txt>
            </View>
            {score !== undefined ? <Num size={fontSize.title}>{score}</Num> : null}
          </View>
        ))}
      </View>
    </Panel>
  );
}

function OddsBoard({ odds, now }: { odds: OddsComparison; now: Date }) {
  const columns = oddsColumns(odds);
  if (columns.length === 0) {
    return (
      <Txt variant="secondary" tone="muted" style={styles.none}>
        No sportsbook is offering this market right now.
      </Txt>
    );
  }
  const holds = new Map(odds.holds.map((hold) => [hold.sportsbook_key, hold.hold]));
  const open = odds.books.filter((book) => book.status === 'open').length;
  return (
    <View>
      <Txt variant="caption" tone="muted" style={styles.summary}>
        {open} of {odds.books.length} sportsbooks open. Prices as of {formatAge(odds.as_of, now)}.
      </Txt>
      {odds.books.map((book) => (
        <OddsRow
          key={book.sportsbook.key}
          book={book}
          market={odds.market}
          columns={columns}
          hold={holds.get(book.sportsbook.key)}
          now={now}
        />
      ))}
      {odds.consensus.outcomes.length ? (
        <ConsensusRow outcomes={odds.consensus.outcomes} booksUsed={odds.consensus.books_used} />
      ) : null}
    </View>
  );
}

export function GameDetailScreen({ eventId }: { eventId: string }) {
  const theme = useTheme();
  const now = useNow();
  const [market, setMarket] = useState<Market>('moneyline');
  const event = useResource(`event:${eventId}`, (signal) => getEvent(eventId, signal));
  const odds = useResource(`odds:${eventId}:${market}`, (signal) => getEventOdds(eventId, market, signal));

  const summary = event.data ?? odds.data?.event;
  const offered = event.data?.available_markets ?? [];
  const markets = MARKETS.filter((item) => offered.length === 0 || offered.includes(item.value) || item.value === market);

  const refresh = () => {
    odds.reload();
    event.reload();
  };

  return (
    <ScrollView
      style={{ backgroundColor: theme.bg }}
      contentContainerStyle={styles.content}
      contentInsetAdjustmentBehavior="automatic"
      refreshControl={
        <RefreshControl refreshing={odds.refreshing || event.refreshing} onRefresh={refresh} tintColor={theme.muted} />
      }>
      <Stack.Screen
        options={{ title: summary ? `${summary.away_team.abbreviation} at ${summary.home_team.abbreviation}` : 'Game' }}
      />

      {summary ? <Scoreboard event={summary} /> : null}

      <Segmented label="Market" options={markets} value={market} onChange={setMarket} />

      {odds.status === 'loading' ? (
        <SkeletonCards label="Loading prices" />
      ) : odds.status === 'error' ? (
        <ErrorState error={odds.error} onRetry={refresh} />
      ) : odds.data ? (
        <>
          {odds.error !== undefined ? <Notice text="Couldn't refresh. Showing the last prices loaded." /> : null}
          <Panel>
            <OddsBoard odds={odds.data} now={now} />
          </Panel>
          <Txt variant="caption" tone="muted">
            Stale and suspended prices are excluded from the best price and from the consensus. Hold is the
            sportsbook&apos;s margin on this market. Implied probability includes that margin; no-vig consensus removes
            it.
          </Txt>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: space[4], paddingBottom: space[8], gap: space[4] },
  scoreboard: { gap: space[3] },
  teamRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3] },
  teamName: { flex: 1, gap: 2 },
  summary: { paddingBottom: space[3] },
  none: { textAlign: 'center', paddingVertical: space[6] },
});
