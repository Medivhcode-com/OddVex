import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getLeagues, getValueScreen } from '@/api/client';
import { MARKETS, type League, type Market, type ValueRow } from '@/api/types';
import { FilterChips } from '@/components/choice';
import { Freshness } from '@/components/freshness';
import { statusText } from '@/components/game-card';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, SkeletonCards } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { leagueLabel } from '@/screens/games';
import { fontSize, radius, space, touchTarget } from '@/theme';
import { formatAge, formatLine, formatPercent, formatPrice, formatSignedPercent } from '@/utils/format';

/** The name of the number on this screen. It is a comparison with other books' prices, never a forecast. */
export const EDGE_LABEL = 'Edge vs consensus';

export const VALUE_INTRO =
  'Where the best price for an outcome sits above the average of the other sportsbooks. OddVex compares prices. It does not take bets or tell you what to bet.';

/** Smallest edge to list, as the fraction the API takes. Fixed choices: nothing is calculated here. */
const MIN_EDGES: readonly { value: string; label: string; fraction: number }[] = [
  { value: '0.01', label: '1% or more', fraction: 0.01 },
  { value: '0.02', label: '2% or more', fraction: 0.02 },
  { value: '0.05', label: '5% or more', fraction: 0.05 },
];

/** "Harbor City Gulls −3.5", "Over 44.5", or just the name on a moneyline. */
export function outcomeText(row: Pick<ValueRow, 'market' | 'outcome_name' | 'line'>): string {
  if (row.line === null || row.line === undefined) return row.outcome_name;
  return `${row.outcome_name} ${formatLine(row.line, { signed: row.market === 'spread' })}`;
}

export function consensusText(row: Pick<ValueRow, 'books_in_consensus' | 'consensus_probability'>): string {
  return `Consensus of ${row.books_in_consensus} other books: ${formatPercent(row.consensus_probability)}`;
}

function marketLabel(market: Market): string {
  return MARKETS.find((item) => item.value === market)?.label ?? market;
}

function ValueRowCard({ row, leagues, now }: { row: ValueRow; leagues: readonly League[]; now: Date }) {
  const router = useRouter();
  const theme = useTheme();
  const { format } = useOddsFormat();
  const game = `${row.event.away_team.name} at ${row.event.home_team.name}`;
  const market = marketLabel(row.market);
  const outcome = outcomeText(row);
  const breakEven = `Break-even at this price: ${formatPercent(row.breakeven_probability)}`;
  const edge = formatSignedPercent(row.edge);
  const updated = row.last_updated ? `, updated ${formatAge(row.last_updated, now)}` : '';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${game}. ${market}: ${outcome}. Best price ${formatPrice(row.best_price, format)} at ${row.sportsbook.name}${updated}. ${consensusText(row)}. ${breakEven}. ${EDGE_LABEL}: ${edge}.`}
      accessibilityHint={`Opens this game on the ${market.toLowerCase()} market`}
      onPress={() => router.push({ pathname: '/event/[id]', params: { id: row.event.id, market: row.market } })}
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: theme.surface, borderColor: theme.border },
        pressed && { backgroundColor: theme.raised },
      ]}>
      <View style={styles.cardHead}>
        <Txt variant="caption" tone="muted">
          {leagueLabel(leagues, row.event.league)} · {statusText(row.event)}
        </Txt>
        <Txt weight="medium">{game}</Txt>
      </View>

      <View style={styles.cardHead}>
        <Txt variant="caption" tone="muted">
          {market}
        </Txt>
        <Txt weight="semibold">{outcome}</Txt>
      </View>

      <View style={[styles.best, { backgroundColor: theme.raised }]}>
        <View style={styles.bestPrice}>
          <Txt variant="caption" tone="muted">
            Best price
          </Txt>
          <Num size={fontSize.score} weight="semibold">
            {formatPrice(row.best_price, format)}
          </Num>
        </View>
        <View style={styles.bestBook}>
          <Txt variant="secondary">at {row.sportsbook.name}</Txt>
          {row.last_updated ? <Freshness at={row.last_updated} stale={false} now={now} /> : null}
        </View>
      </View>

      <Txt variant="secondary" tone="muted">
        {consensusText(row)}
      </Txt>
      <Txt variant="secondary" tone="muted">
        {breakEven}
      </Txt>
      <View style={[styles.edge, { borderTopColor: theme.border }]}>
        <Txt variant="secondary" weight="medium">
          {EDGE_LABEL}
        </Txt>
        <Num size={fontSize.body} weight="semibold">
          {edge}
        </Num>
      </View>
    </Pressable>
  );
}

/**
 * Best price against the consensus of the other sportsbooks (`GET /v1/value`, flag `value_screen`). Every number
 * is the API's; the API's own method and caveat sit above the rows.
 */
export function ValueScreen() {
  const now = useNow();
  const [league, setLeague] = useState<string | null>(null);
  const [market, setMarket] = useState<string | null>(null);
  const [minEdge, setMinEdge] = useState<string | null>(null);
  const leagues = useResource('leagues', getLeagues);
  const selectedMarket = MARKETS.find((item) => item.value === market)?.value ?? null;
  const edgeFraction = MIN_EDGES.find((item) => item.value === minEdge)?.fraction ?? null;
  const value = useResource(`value:${league ?? ''}:${selectedMarket ?? ''}:${minEdge ?? ''}`, (signal) =>
    getValueScreen({ league, market: selectedMarket, minEdge: edgeFraction }, signal),
  );

  const leagueList = leagues.data ?? [];
  const filtered = league !== null || market !== null || minEdge !== null;
  const refresh = () => {
    value.reload();
    if (leagues.status === 'error') leagues.reload();
  };

  return (
    <Screen refreshing={value.refreshing} onRefresh={refresh}>
      <Txt variant="secondary" tone="muted">
        {VALUE_INTRO}
      </Txt>

      {value.data ? (
        <>
          <Notice tone="warn" title="What this does not tell you" text={value.data.caveat} />
          <Notice tone="neutral" title="How it is calculated" text={value.data.method} />
        </>
      ) : null}

      <View style={styles.filters}>
        <FilterChips
          label="Filter by league"
          allLabel="All leagues"
          options={leagueList.map((item) => ({ value: item.key, label: item.name }))}
          value={league}
          onChange={setLeague}
        />
        <FilterChips label="Filter by market" allLabel="All markets" options={MARKETS} value={market} onChange={setMarket} />
        <FilterChips label={`Smallest ${EDGE_LABEL.toLowerCase()}`} allLabel="Any size" options={MIN_EDGES} value={minEdge} onChange={setMinEdge} />
      </View>

      {value.status === 'loading' ? (
        <SkeletonCards label="Loading prices" />
      ) : value.status === 'error' || !value.data ? (
        <ErrorState error={value.error} onRetry={refresh} />
      ) : (
        <>
          {value.error !== undefined ? <Notice text="Couldn't refresh. Showing the last prices loaded." /> : null}
          <Txt variant="caption" tone="muted">
            {value.data.rows.length} {value.data.rows.length === 1 ? 'outcome' : 'outcomes'}, largest first. Prices checked{' '}
            {formatAge(value.data.as_of, now)}.
          </Txt>
          {value.data.rows.length === 0 ? (
            <EmptyState
              title="Nothing qualifies right now"
              body={
                filtered
                  ? 'No best price sits above the consensus of the other books with these filters. On many slates nothing qualifies, and that is normal. Try another league, market or size, or pull down to refresh.'
                  : 'No best price sits above the consensus of the other books. On many slates nothing qualifies, and that is normal. Pull down to refresh.'
              }
            />
          ) : (
            value.data.rows.map((row) => (
              <ValueRowCard key={`${row.event.id}:${row.market}:${row.outcome_key}:${row.line ?? ''}`} row={row} leagues={leagueList} now={now} />
            ))
          )}
        </>
      )}
    </Screen>
  );
}

/** The way in from the Tools tab and from Games. Rendered only while the `value_screen` flag is on. */
export function ValueEntry({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const theme = useTheme();
  if (compact) {
    return (
      <Pressable
        accessibilityRole="link"
        accessibilityLabel="Value screen: best prices against the consensus of other books"
        onPress={() => router.push('/value')}
        style={({ pressed }) => [
          styles.linkRow,
          { backgroundColor: theme.surface, borderColor: theme.border },
          pressed && { backgroundColor: theme.raised },
        ]}>
        <View style={styles.linkText}>
          <Txt variant="secondary" weight="semibold">
            Value screen
          </Txt>
          <Txt variant="caption" tone="muted">
            Best prices against the consensus of other books
          </Txt>
        </View>
        <Txt tone="muted" accessibilityElementsHidden importantForAccessibility="no">
          ›
        </Txt>
      </Pressable>
    );
  }
  return (
    <Panel>
      <View style={styles.entry}>
        <View style={styles.cardHead}>
          <Txt variant="heading" accessibilityRole="header">
            Value screen
          </Txt>
          <Txt variant="secondary" tone="muted">
            See where the best price for an outcome sits above the consensus of the other sportsbooks. A comparison of prices, not a prediction.
          </Txt>
        </View>
        <Button label="Open value screen" variant="secondary" onPress={() => router.push('/value')} />
      </View>
    </Panel>
  );
}

const styles = StyleSheet.create({
  filters: { marginHorizontal: -space[4] },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.panel, padding: space[4], gap: space[3], minHeight: touchTarget },
  cardHead: { gap: 2 },
  best: { flexDirection: 'row', alignItems: 'center', gap: space[4], padding: space[3], borderRadius: radius.cell },
  bestPrice: { gap: 2 },
  bestBook: { flex: 1, gap: space[1] },
  edge: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: space[3],
    paddingTop: space[3],
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  linkRow: {
    minHeight: touchTarget,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    paddingHorizontal: space[4],
    paddingVertical: space[2],
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.panel,
  },
  linkText: { flex: 1, gap: 2 },
  entry: { gap: space[3] },
});
