import { Link } from 'expo-router';
import { useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';

import { getLeagues, getProps } from '@/api/client';
import type { BestSide, PropBoardRow } from '@/api/types';
import { FilterChips } from '@/components/choice';
import { Price } from '@/components/price';
import { EmptyState, ErrorState, Notice, SkeletonCards } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { leagueLabel } from '@/screens/games';
import { fontSize, radius, space, touchTarget } from '@/theme';
import { formatLine, formatPercent, formatPrice, titleCase, type OddsFormat } from '@/utils/format';

/** "5 of 10" from the API's counts; nothing is recomputed. */
function overRate(row: PropBoardRow): { text: string; spoken: string } {
  if (row.l10_hit_rate === null || row.l10_hit_rate === undefined) {
    return { text: 'Not enough games', spoken: 'over rate: not enough games' };
  }
  const rate = formatPercent(row.l10_hit_rate, 0);
  return { text: `${rate} (n=${row.l10_sample})`, spoken: `over in ${rate} of the last ${row.l10_sample} games` };
}

function bestSpoken(side: 'over' | 'under', best: BestSide, format: OddsFormat): string {
  return best ? `best ${side} ${formatPrice(best.price, format)} at ${best.sportsbook.name}` : `no ${side} open`;
}

function Best({ label, best }: { label: string; best: BestSide }) {
  return (
    <View style={styles.best}>
      <Txt variant="caption" tone="muted">
        {label}
      </Txt>
      {best ? (
        <>
          <Price price={best.price} />
          <Txt variant="caption" tone="muted" numberOfLines={1}>
            {best.sportsbook.name}
          </Txt>
        </>
      ) : (
        <Txt variant="caption" tone="muted">
          None open
        </Txt>
      )}
    </View>
  );
}

/** One posted prop: player, stat, consensus line, best over and under with their books, last-10 over rate. */
export function PropCard({ row, ...pressable }: { row: PropBoardRow } & Omit<React.ComponentProps<typeof Pressable>, 'children' | 'style'>) {
  const theme = useTheme();
  const { format } = useOddsFormat();
  const rate = overRate(row);
  const stat = titleCase(row.market);
  const line = formatLine(row.consensus_line) || 'n/a';
  const game = `${row.event.away_team.abbreviation} at ${row.event.home_team.abbreviation}`;
  const label = [
    row.player.name,
    game,
    `${stat}, consensus line ${line}`,
    bestSpoken('over', row.best_over, format),
    bestSpoken('under', row.best_under, format),
    rate.spoken,
  ].join('. ');

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint="Opens the prop analyzer for this player"
      {...pressable}
      style={({ pressed }) => [styles.card, { backgroundColor: theme.surface, borderColor: pressed ? theme.borderStrong : theme.border }]}>
      <View style={styles.top}>
        <View style={styles.grow}>
          <Txt weight="semibold">{row.player.name}</Txt>
          <Txt variant="caption" tone="muted">
            {game}
          </Txt>
        </View>
        <View style={styles.lineBox}>
          <Txt variant="caption" tone="muted">
            {stat}
          </Txt>
          <Num size={fontSize.score} weight="semibold">
            {line}
          </Num>
        </View>
      </View>
      <View style={styles.sides}>
        <Best label="Best over" best={row.best_over} />
        <Best label="Best under" best={row.best_under} />
        <View style={styles.best}>
          <Txt variant="caption" tone="muted">
            Over rate, last 10
          </Txt>
          <Num size={fontSize.secondary}>{rate.text}</Num>
        </View>
      </View>
    </Pressable>
  );
}

export function PropsScreen() {
  const theme = useTheme();
  const [league, setLeague] = useState<string | null>(null);
  const [market, setMarket] = useState<string | null>(null);
  const leagues = useResource('leagues', getLeagues);
  const board = useResource(`props:${league ?? ''}`, (signal) => getProps(league, signal));

  const leagueList = leagues.data ?? [];
  const all = board.data ?? [];
  const markets = [...new Set(all.map((row) => row.market))];
  const active = market && markets.includes(market) ? market : null;
  const rows = active ? all.filter((row) => row.market === active) : all;

  const refresh = () => {
    board.reload();
    if (leagues.status === 'error') leagues.reload();
  };

  return (
    <FlatList
      style={{ backgroundColor: theme.bg }}
      contentContainerStyle={styles.content}
      contentInsetAdjustmentBehavior="automatic"
      data={rows}
      keyExtractor={(row) => `${row.player.id}-${row.market}`}
      refreshControl={<RefreshControl refreshing={board.refreshing} onRefresh={refresh} tintColor={theme.muted} />}
      ListHeaderComponent={
        <View style={styles.header}>
          <View style={styles.chips}>
            <FilterChips
              label="Filter by league"
              allLabel="All leagues"
              options={leagueList.map((item) => ({ value: item.key, label: item.name }))}
              value={league}
              onChange={(next) => {
                setLeague(next);
                setMarket(null);
              }}
            />
            {markets.length > 1 ? (
              <FilterChips
                label="Filter by stat"
                allLabel="All stats"
                options={markets.map((item) => ({ value: item, label: titleCase(item) }))}
                value={active}
                onChange={setMarket}
              />
            ) : null}
          </View>
          <Notice
            tone="neutral"
            text="Over rate is how often the player went over this line in recent games. It is a record of the past, not a prediction."
          />
          {board.data && board.error !== undefined ? <Notice text="Couldn't refresh. Showing the last props loaded." /> : null}
        </View>
      }
      ListEmptyComponent={
        board.status === 'loading' ? (
          <SkeletonCards label="Loading props" />
        ) : board.status === 'error' ? (
          <ErrorState error={board.error} onRetry={refresh} />
        ) : (
          <EmptyState
            title={league ? `No props posted for ${leagueLabel(leagueList, league)}` : 'No props posted'}
            body="Props appear when sportsbooks open player markets for upcoming games. Try another league or pull down to refresh."
          />
        )
      }
      renderItem={({ item }) => (
        <View style={styles.item}>
          <Link href={{ pathname: '/player/[id]', params: { id: item.player.id, market: item.market } }} asChild>
            <PropCard row={item} />
          </Link>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: space[4], paddingBottom: space[8] },
  header: { gap: space[2], marginBottom: space[3] },
  chips: { marginHorizontal: -space[4] },
  item: { marginBottom: space[3] },
  card: { minHeight: touchTarget, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.panel, padding: space[4], gap: space[3] },
  top: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3] },
  grow: { flex: 1, gap: 2 },
  lineBox: { alignItems: 'flex-end', gap: 2 },
  sides: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[5], rowGap: space[2] },
  best: { gap: 2 },
});
