import { StyleSheet, View } from 'react-native';

import type { BookRow, ConsensusOutcome, Outcome } from '@/api/types';
import { Freshness } from '@/components/freshness';
import { Price } from '@/components/price';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { fontSize, radius, space } from '@/theme';
import { formatLine, formatPercent, formatPrice } from '@/utils/format';

export type OddsColumn = { key: string; name: string };

/** "+3.5" for a spread, "O 44.5" / "U 44.5" for a total, nothing for a moneyline. */
export function lineText(market: string, outcome: Pick<Outcome, 'key' | 'line'>): string | null {
  if (outcome.line === null || outcome.line === undefined) return null;
  if (market === 'spread') return formatLine(outcome.line, { signed: true });
  const side = outcome.key.startsWith('over') ? 'O' : outcome.key.startsWith('under') ? 'U' : '';
  return `${side} ${formatLine(outcome.line)}`.trim();
}

const closedCopy = {
  suspended: { status: 'Suspended', detail: 'Market suspended by this book' },
  unavailable: { status: 'Not offered', detail: 'Not offered by this book' },
} as const;

function PriceCell({ market, column, outcome, stale }: { market: string; column: OddsColumn; outcome?: Outcome; stale: boolean }) {
  const theme = useTheme();
  const { format } = useOddsFormat();

  if (!outcome) {
    return (
      <View style={[styles.cell, { borderLeftColor: 'transparent' }]}>
        <Txt variant="caption" tone="muted" numberOfLines={1}>
          {column.name}
        </Txt>
        <Txt variant="caption" tone="muted">
          Not offered
        </Txt>
      </View>
    );
  }

  const line = lineText(market, outcome);
  const best = outcome.is_best;
  const tone = best ? 'accent' : stale ? 'muted' : 'text';
  const implied = formatPercent(outcome.price.implied_probability);
  const label = [
    line ? `${outcome.name} ${line}` : outcome.name,
    formatPrice(outcome.price, format),
    best ? 'best price' : null,
    `implied probability ${implied}`,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <View
      accessible
      accessibilityLabel={label}
      style={[
        styles.cell,
        { borderLeftColor: best ? theme.accent : 'transparent' },
        best && { backgroundColor: theme.accentSoft },
      ]}>
      <Txt variant="caption" tone="muted" numberOfLines={1}>
        {outcome.name}
      </Txt>
      <View style={styles.priceLine}>
        {line ? (
          <Num size={fontSize.caption} tone={best ? 'accent' : 'muted'} weight="regular">
            {line}
          </Num>
        ) : null}
        <Price price={outcome.price} tone={tone} />
      </View>
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

/**
 * One sportsbook: name, freshness, hold, and a price cell per outcome.
 * The best price gets the accent bar, the tint and the word "Best". Closed markets are spelled out.
 */
export function OddsRow({
  book,
  market,
  columns,
  hold,
  now,
}: {
  book: BookRow;
  market: string;
  columns: readonly OddsColumn[];
  hold?: number;
  now: Date;
}) {
  const theme = useTheme();
  const open = book.status === 'open';
  // Anything that is not open and not explicitly suspended is treated as not offered.
  const closed = book.status === 'suspended' ? closedCopy.suspended : closedCopy.unavailable;
  return (
    <View style={[styles.row, { borderTopColor: theme.border }]}>
      <View style={styles.head}>
        <View style={styles.book}>
          <Txt variant="heading" numberOfLines={2}>
            {book.sportsbook.name}
          </Txt>
          {!open ? (
            <Txt variant="caption" tone="muted" weight="medium">
              {closed.status}
            </Txt>
          ) : book.last_updated ? (
            <Freshness at={book.last_updated} stale={book.is_stale} now={now} />
          ) : book.is_stale ? (
            <Txt variant="caption" tone="warn">
              Stale
            </Txt>
          ) : null}
        </View>
        {open && hold !== undefined ? (
          <View style={styles.hold} accessible accessibilityLabel={`Hold ${formatPercent(hold)}`}>
            <Txt variant="caption" tone="muted">
              Hold
            </Txt>
            <Num size={fontSize.secondary} tone="muted">
              {formatPercent(hold)}
            </Num>
          </View>
        ) : null}
      </View>
      {open ? (
        <View style={styles.cells}>
          {columns.map((column) => (
            <PriceCell
              key={column.key}
              market={market}
              column={column}
              outcome={book.outcomes.find((outcome) => outcome.key === column.key)}
              stale={book.is_stale}
            />
          ))}
        </View>
      ) : (
        <Txt variant="secondary" tone="muted">
          {closed.detail}
        </Txt>
      )}
    </View>
  );
}

/** The API's no-vig consensus probability per outcome, and how many books went into it. */
export function ConsensusRow({ outcomes, booksUsed }: { outcomes: readonly ConsensusOutcome[]; booksUsed: number }) {
  const theme = useTheme();
  return (
    <View style={[styles.row, { borderTopColor: theme.borderStrong }]}>
      <View style={styles.book}>
        <Txt variant="heading">No-vig consensus</Txt>
        <Txt variant="caption" tone="muted">
          {booksUsed} {booksUsed === 1 ? 'book' : 'books'}
        </Txt>
      </View>
      <View style={styles.cells}>
        {outcomes.map((outcome) => (
          <View
            key={outcome.key}
            accessible
            accessibilityLabel={`${outcome.name}, no-vig probability ${formatPercent(outcome.no_vig_probability)}`}
            style={[styles.cell, { borderLeftColor: 'transparent' }]}>
            <Txt variant="caption" tone="muted" numberOfLines={1}>
              {outcome.name}
            </Txt>
            <Num>{formatPercent(outcome.no_vig_probability)}</Num>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { borderTopWidth: StyleSheet.hairlineWidth, paddingVertical: space[3], gap: space[2] },
  head: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: space[3] },
  book: { flex: 1, gap: 2 },
  hold: { alignItems: 'flex-end', gap: 2 },
  cells: { flexDirection: 'row', gap: space[2] },
  cell: {
    flex: 1,
    minHeight: 64,
    justifyContent: 'center',
    gap: 2,
    paddingVertical: space[2],
    paddingHorizontal: space[2],
    borderRadius: radius.cell,
    borderLeftWidth: 3,
  },
  priceLine: { flexDirection: 'row', alignItems: 'baseline', flexWrap: 'wrap', columnGap: space[1] + 2 },
});
