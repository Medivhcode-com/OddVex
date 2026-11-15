import { Stack } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { getPlayerProps } from '@/api/client';
import type { PriceT, PropAnalysis, PropOffer, PropSplit, PropWindow } from '@/api/types';
import { Choice } from '@/components/form';
import { Freshness } from '@/components/freshness';
import { GameLogChart, GameLogList } from '@/components/game-log-chart';
import { Price } from '@/components/price';
import { Screen } from '@/components/screen';
import { ErrorState, Notice, Panel, PanelHeading, SkeletonCards, Stat, StatGrid } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { WatchButton } from '@/components/watch-button';
import { useNow } from '@/hooks/use-now';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { useWatchlist, watchId } from '@/hooks/use-watchlist';
import { useOddsFormat } from '@/providers/odds-format';
import { fontSize, radius, space } from '@/theme';
import { formatDay, formatLine, formatPercent, formatPrice, titleCase } from '@/utils/format';

const WINDOWS: readonly { value: PropWindow; label: string }[] = [
  { value: '5', label: 'Last 5' },
  { value: '10', label: 'Last 10' },
  { value: '20', label: 'Last 20' },
  { value: 'season', label: 'Season' },
];
const SPLITS: readonly { value: PropSplit; label: string }[] = [
  { value: 'all', label: 'All games' },
  { value: 'home', label: 'Home' },
  { value: 'away', label: 'Away' },
  { value: 'vs_opponent', label: 'Vs opponent' },
];
const CHART_GAMES = 20;

const average = (value: number | null | undefined) => (value === null || value === undefined ? 'n/a' : value.toFixed(1));

/** "6 of 10 games", plus how many pushes the API left out of the sample. */
export function sampleText(hit: PropAnalysis['hit_rate']): string {
  const pushes = hit.pushes ? `, ${hit.pushes} push${hit.pushes > 1 ? 'es' : ''} excluded` : '';
  return `${hit.over_count} of ${hit.sample_size} games${pushes}`;
}

/** The API's 95% Wilson interval as "31% to 83%", or "n/a" when the sample is empty. */
export function rangeText(hit: PropAnalysis['hit_rate']): string {
  if (hit.ci_low === null || hit.ci_low === undefined || hit.ci_high === null || hit.ci_high === undefined) return 'n/a';
  return `${formatPercent(hit.ci_low, 0)} to ${formatPercent(hit.ci_high, 0)}`;
}

function OfferPrice({ side, price, best, stale }: { side: 'Over' | 'Under'; price?: PriceT | null; best: boolean; stale: boolean }) {
  const theme = useTheme();
  const { format } = useOddsFormat();
  if (!price) {
    return (
      <View style={[styles.cell, { borderLeftColor: 'transparent' }]}>
        <Txt variant="caption" tone="muted">
          {side}
        </Txt>
        <Txt variant="caption" tone="muted">
          Not offered
        </Txt>
      </View>
    );
  }
  const implied = formatPercent(price.implied_probability);
  return (
    <View
      accessible
      accessibilityLabel={[side, formatPrice(price, format), best ? 'best price' : null, `implied probability ${implied}`].filter(Boolean).join(', ')}
      style={[styles.cell, { borderLeftColor: best ? theme.accent : 'transparent' }, best && { backgroundColor: theme.accentSoft }]}>
      <Txt variant="caption" tone="muted">
        {side}
      </Txt>
      <Price price={price} tone={best ? 'accent' : stale ? 'muted' : 'text'} />
      {best ? (
        <Txt variant="caption" tone="accent" weight="semibold">
          Best
        </Txt>
      ) : (
        <Num size={fontSize.caption} tone="muted" weight="regular">
          {implied}
        </Num>
      )}
    </View>
  );
}

/** One sportsbook's line and prices for this prop. Closed markets are spelled out; stale prices are labelled. */
export function OfferRow({ offer, now }: { offer: PropOffer; now: Date }) {
  const theme = useTheme();
  const open = offer.status === 'open';
  return (
    <View style={[styles.offer, { borderTopColor: theme.border }]}>
      <View style={styles.offerHead}>
        <View style={styles.grow}>
          <Txt variant="heading">{offer.sportsbook.name}</Txt>
          {!open ? (
            <Txt variant="caption" tone="muted" weight="medium">
              {offer.status === 'suspended' ? 'Suspended' : 'Not offered'}
            </Txt>
          ) : offer.last_updated ? (
            <Freshness at={offer.last_updated} stale={offer.is_stale} now={now} />
          ) : offer.is_stale ? (
            <Txt variant="caption" tone="warn">
              Stale
            </Txt>
          ) : null}
        </View>
        {open ? (
          <View style={styles.offerLine} accessible accessibilityLabel={`Line ${formatLine(offer.line) || 'not posted'}`}>
            <Txt variant="caption" tone="muted">
              Line
            </Txt>
            <Num>{formatLine(offer.line) || 'n/a'}</Num>
          </View>
        ) : null}
      </View>
      {open ? (
        <View style={styles.cells}>
          <OfferPrice side="Over" price={offer.over} best={offer.is_best_over} stale={offer.is_stale} />
          <OfferPrice side="Under" price={offer.under} best={offer.is_best_under} stale={offer.is_stale} />
        </View>
      ) : (
        <Txt variant="secondary" tone="muted">
          {offer.status === 'suspended' ? 'Market suspended by this book' : 'Not offered by this book'}
        </Txt>
      )}
    </View>
  );
}

/** Everything below the selectors: the record against the line, the chart, the caveat, offers and the game log. */
export function PropAnalysisView({ data, now }: { data: PropAnalysis; now: Date }) {
  const line = data.consensus_line;
  const hit = data.hit_rate;
  const stat = titleCase(data.market);
  const log = [...data.game_log].sort((a, b) => a.date.localeCompare(b.date));
  const posted = line !== null && line !== undefined;

  return (
    <>
      <Panel>
        <View style={styles.block}>
          <PanelHeading
            title={`${stat} against the line`}
            description={posted ? `Consensus line ${formatLine(line)}` : 'No line is posted, so there is nothing to measure against.'}
          />
          <StatGrid>
            <Stat label="Over rate" value={formatPercent(hit.rate, 0)} hint={sampleText(hit)} />
            <Stat label="95% range" value={rangeText(hit)} hint="Wilson interval. Wider means less evidence." />
            <Stat label="Average, this view" value={average(data.averages.window)} />
            <Stat
              label="Season average"
              value={average(data.averages.season)}
              hint={`Home ${average(data.averages.home)}, away ${average(data.averages.away)}`}
            />
          </StatGrid>
          {!posted ? (
            <Txt variant="secondary" tone="muted" style={styles.center}>
              The game log will chart here once a line is posted.
            </Txt>
          ) : log.length === 0 ? (
            <Txt variant="secondary" tone="muted" style={styles.center}>
              No games in this view. Try a wider window or another split.
            </Txt>
          ) : (
            <GameLogChart
              line={line}
              games={log.slice(-CHART_GAMES)}
              summary={`${data.player.name} ${stat}: over ${formatLine(line)} in ${hit.over_count} of ${hit.sample_size} games shown`}
            />
          )}
          <Notice tone="neutral" title="A record, not a forecast" text={data.caveat} />
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <PanelHeading
            title="Lines and prices by book"
            description="Books can post different lines. Best is marked among books at the consensus line."
          />
          {data.offers.length === 0 ? (
            <Txt variant="secondary" tone="muted">
              No sportsbook is offering this prop right now.
            </Txt>
          ) : (
            <View>
              {data.offers.map((offer) => (
                <OfferRow key={offer.sportsbook.key} offer={offer} now={now} />
              ))}
            </View>
          )}
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Game log" description={`${log.length} ${log.length === 1 ? 'game' : 'games'} in this view, most recent first`} />
          <GameLogList games={[...log].reverse()} />
        </View>
      </Panel>
    </>
  );
}

export function PropAnalyzerScreen({ playerId, initialMarket }: { playerId: string; initialMarket?: string }) {
  const now = useNow();
  const watchlist = useWatchlist();
  const [market, setMarket] = useState<string | undefined>(initialMarket);
  const [window, setWindow] = useState<PropWindow>('10');
  const [split, setSplit] = useState<PropSplit>('all');
  const analysis = useResource(`player-props:${playerId}:${market ?? ''}:${window}:${split}`, (signal) =>
    getPlayerProps(playerId, { market, window, split }, signal),
  );
  // Selectors stay on screen while a new view loads, so they are drawn from the last answer for this player.
  const [shown, setShown] = useState<PropAnalysis | undefined>(undefined);
  if (analysis.data && analysis.data !== shown) setShown(analysis.data);
  const frame = analysis.data ?? (shown?.player.id === playerId ? shown : undefined);
  const player = frame?.player;

  return (
    <Screen refreshing={analysis.refreshing} onRefresh={analysis.reload}>
      <Stack.Screen options={{ title: player?.name ?? 'Player props' }} />

      {player && frame ? (
        <>
          <View style={styles.block}>
            <Txt variant="title" accessibilityRole="header">
              {player.name}
            </Txt>
            <Txt variant="secondary" tone="muted">
              {player.team.name}
              {player.position ? `, ${player.position}` : ''}
              {frame.opponent ? `. Next: ${frame.opponent.name}` : ''}
              {frame.next_event ? `, ${formatDay(frame.next_event.start_time)}` : ''}
            </Txt>
            <WatchButton kind="player" refId={player.id} name={player.name} itemId={watchId(watchlist.data, 'player', player.id)} />
          </View>
          <Panel>
            <View style={styles.block}>
              <Choice
                label="Stat"
                options={frame.available_markets.map((item) => ({ value: item, label: titleCase(item) }))}
                value={frame.market}
                onChange={setMarket}
              />
              <Choice label="Games" options={WINDOWS} value={window} onChange={setWindow} />
              <Choice label="Split" options={SPLITS} value={split} onChange={setSplit} />
            </View>
          </Panel>
        </>
      ) : null}

      {analysis.status === 'loading' ? (
        <SkeletonCards label="Loading the prop analysis" />
      ) : analysis.status === 'error' ? (
        <ErrorState error={analysis.error} onRetry={analysis.reload} />
      ) : analysis.data ? (
        <>
          {analysis.error !== undefined ? <Notice text="Couldn't refresh. Showing the last analysis loaded." /> : null}
          <PropAnalysisView data={analysis.data} now={now} />
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  center: { textAlign: 'center', paddingVertical: space[4] },
  grow: { flex: 1, gap: 2 },
  offer: { gap: space[2], paddingVertical: space[3], borderTopWidth: StyleSheet.hairlineWidth },
  offerHead: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3] },
  offerLine: { alignItems: 'flex-end', gap: 2 },
  cells: { flexDirection: 'row', gap: space[2] },
  cell: { flex: 1, gap: 2, paddingVertical: space[2], paddingHorizontal: space[2], borderLeftWidth: 3, borderRadius: radius.cell },
});
