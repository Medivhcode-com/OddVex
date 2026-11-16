import { StyleSheet, View } from 'react-native';

import type { CommunityRecord } from '@/api/types';
import { Notice, Stat, StatGrid } from '@/components/states';
import { Txt } from '@/components/text';
import { useOddsFormat } from '@/providers/odds-format';
import { space } from '@/theme';
import { formatPercent, formatPrice, formatSignedPercent } from '@/utils/format';

/** "95% interval 34.5% to 65.5%", from the API's Wilson interval. Null when there is none yet. */
export function intervalText(record: Pick<CommunityRecord, 'win_rate_interval'>): string | null {
  const interval = record.win_rate_interval;
  if (!interval) return null;
  return `${formatPercent(interval.confidence_level, 0)} interval ${formatPercent(interval.low)} to ${formatPercent(interval.high)}`;
}

/** "36 graded picks", the sample every rate here is drawn from. */
export function sampleText(record: Pick<CommunityRecord, 'picks'>): string {
  return `${record.picks} graded ${record.picks === 1 ? 'pick' : 'picks'}`;
}

/**
 * A profile's graded record. Every number is the API's: wins, losses and pushes, the win rate with its
 * interval and sample size, the average price and the flat-stake return. The API's `method` says how the
 * return is worked out, `sample_note` is shown as a caution when it is set, and `caveat` closes the panel.
 */
export function CommunityRecordView({ record }: { record: CommunityRecord }) {
  const { format } = useOddsFormat();
  const interval = intervalText(record);
  return (
    <View style={styles.block}>
      {record.sample_note ? <Notice tone="warn" title="Small sample" text={record.sample_note} /> : null}
      <StatGrid>
        <Stat label="Graded picks" value={String(record.picks)} />
        <Stat label="Won-lost-push" value={`${record.wins}-${record.losses}-${record.pushes}`} hint={`${record.wins} won, ${record.losses} lost, ${record.pushes} push`} />
        <Stat
          label="Win rate"
          value={formatPercent(record.win_rate)}
          hint={interval ? `${interval}, from ${sampleText(record)}` : `From ${sampleText(record)}`}
        />
        <Stat label="Average price" value={record.average_price ? formatPrice(record.average_price, format) : 'n/a'} />
        <Stat label="Flat-stake ROI" value={formatSignedPercent(record.flat_stake_roi)} hint="See how it is calculated below" />
      </StatGrid>
      <Notice tone="neutral" title="How this record is calculated" text={record.method} />
      <Txt variant="caption" tone="muted">
        {record.caveat}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
});
