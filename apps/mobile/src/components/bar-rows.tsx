import { StyleSheet, View } from 'react-native';

import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, radius, space } from '@/theme';

export type BarRow = { key: string; label: string; count: number; detail: string };

/**
 * Labelled bars drawn from plain views. The bar's length is the row's count against the largest count in the
 * list, which is layout only; every value is also written out as text, so nothing depends on the bar or on
 * color. Each row is read out as one phrase.
 */
export function BarRows({ label, rows }: { label: string; rows: readonly BarRow[] }) {
  const theme = useTheme();
  const largest = Math.max(1, ...rows.map((row) => row.count));
  return (
    <View accessibilityLabel={label} style={styles.rows}>
      {rows.map((row) => (
        <View key={row.key} accessible accessibilityLabel={`${row.label}: ${row.detail}`} style={styles.row}>
          <Txt variant="secondary" weight="medium">
            {row.label}
          </Txt>
          <View style={[styles.track, { backgroundColor: theme.raised }]}>
            <View style={[styles.bar, { backgroundColor: theme.second, width: `${Math.round((row.count / largest) * 100)}%` }]} />
          </View>
          <Num size={fontSize.caption} tone="muted" weight="regular">
            {row.detail}
          </Num>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  rows: { gap: space[3] },
  row: { gap: space[1] },
  track: { height: 8, borderRadius: radius.cell, overflow: 'hidden' },
  bar: { height: 8, borderRadius: radius.cell },
});
