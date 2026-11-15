import { Pressable, StyleSheet, View, type PressableProps } from 'react-native';

import type { BestSide, EventSummary } from '@/api/types';
import { Badge } from '@/components/badge';
import { Price } from '@/components/price';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { fontSize, radius, space, touchTarget } from '@/theme';
import { formatPrice, formatStart, type OddsFormat } from '@/utils/format';

/** The status in words: "Live, Q3 4:12", "Final", or "Starts Sat, Nov 15, 7:30 PM". */
export function statusText(event: EventSummary): string {
  if (event.status === 'live') return event.status_detail ? `Live, ${event.status_detail}` : 'Live';
  if (event.status === 'final') return 'Final';
  return `Starts ${formatStart(event.start_time)}`;
}

export function EventStatus({ event }: { event: EventSummary }) {
  if (event.status === 'live') return <Badge label={statusText(event)} tone="accent" mark="dot" />;
  if (event.status === 'final') return <Badge label="Final" />;
  return (
    <Txt variant="secondary" tone="muted">
      {statusText(event)}
    </Txt>
  );
}

function Side({
  name,
  abbreviation,
  score,
  best,
  showPrice,
  winner,
}: {
  name: string;
  abbreviation: string;
  score?: number;
  best?: BestSide;
  showPrice: boolean;
  winner: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={styles.side}>
      <View style={[styles.abbr, { backgroundColor: theme.raised }]}>
        <Num size={11} tone="muted" weight="semibold" maxFontSizeMultiplier={1.2}>
          {abbreviation}
        </Num>
      </View>
      <Txt weight={winner ? 'semibold' : 'medium'} numberOfLines={2} style={styles.team}>
        {name}
      </Txt>
      {score !== undefined ? (
        <Num size={fontSize.score} tone={winner ? 'text' : 'muted'} weight={winner ? 'semibold' : 'medium'}>
          {score}
        </Num>
      ) : null}
      {showPrice ? (
        <View style={styles.best}>
          {best ? (
            <>
              <Price price={best.price} />
              <Txt variant="caption" tone="muted" numberOfLines={1}>
                {best.sportsbook.name}
              </Txt>
            </>
          ) : (
            <Txt variant="caption" tone="muted">
              No price
            </Txt>
          )}
        </View>
      ) : null}
    </View>
  );
}

function sideLabel(name: string, score: number | undefined, best: BestSide | undefined, showPrice: boolean, format: OddsFormat) {
  const parts = [name];
  if (score !== undefined) parts.push(`${score}`);
  if (showPrice) parts.push(best ? `best moneyline ${formatPrice(best.price, format)} at ${best.sportsbook.name}` : 'no price');
  return parts.join(', ');
}

/** One game as a tappable card: status, both sides, score if any, and the best moneyline on each side. */
export function GameCard({
  event,
  leagueName,
  ...pressable
}: Omit<PressableProps, 'children' | 'style'> & { event: EventSummary; leagueName: string }) {
  const theme = useTheme();
  const { format } = useOddsFormat();
  const { score } = event;
  const final = event.status === 'final' && score ? score : null;
  const showPrices = event.status !== 'final';
  // Three-way markets (soccer) also price the draw.
  const draw = showPrices ? event.best_moneyline?.draw : undefined;
  const label = [
    `${event.away_team.name} at ${event.home_team.name}`,
    leagueName,
    statusText(event),
    sideLabel(event.away_team.name, score?.away, event.best_moneyline?.away, showPrices, format),
    sideLabel(event.home_team.name, score?.home, event.best_moneyline?.home, showPrices, format),
    draw ? sideLabel('Draw', undefined, draw, true, format) : null,
  ]
    .filter(Boolean)
    .join('. ');

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint="Opens the price comparison for this game"
      {...pressable}
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: theme.surface, borderColor: pressed ? theme.borderStrong : theme.border },
      ]}>
      <View style={styles.top}>
        <EventStatus event={event} />
        <Txt variant="caption" tone="muted">
          {leagueName}
        </Txt>
      </View>
      <Side
        name={event.away_team.name}
        abbreviation={event.away_team.abbreviation}
        score={score?.away}
        best={event.best_moneyline?.away}
        showPrice={showPrices}
        winner={Boolean(final && final.away > final.home)}
      />
      <Side
        name={event.home_team.name}
        abbreviation={event.home_team.abbreviation}
        score={score?.home}
        best={event.best_moneyline?.home}
        showPrice={showPrices}
        winner={Boolean(final && final.home > final.away)}
      />
      {draw ? <Side name="Draw" abbreviation="X" best={draw} showPrice winner={false} /> : null}
      {showPrices ? (
        <Txt variant="caption" tone="muted" style={styles.footnote}>
          Best moneyline
        </Txt>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: touchTarget,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.panel,
    padding: space[4],
    gap: space[3],
  },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3] },
  side: { flexDirection: 'row', alignItems: 'center', gap: space[3] },
  abbr: { width: 36, height: 32, borderRadius: radius.cell, alignItems: 'center', justifyContent: 'center' },
  team: { flex: 1 },
  best: { minWidth: 88, alignItems: 'flex-end', gap: 2 },
  footnote: { textAlign: 'right' },
});
