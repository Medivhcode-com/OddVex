import { StyleSheet, View } from 'react-native';

import { Mark } from '@/components/badge';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { space } from '@/theme';
import { formatAge } from '@/utils/format';

/**
 * "42s ago" for a fresh price, "Stale, 9 min ago" for a stale one.
 * Stale gets the word and a diamond instead of a dot, so the state does not depend on color.
 */
export function Freshness({ at, stale, now }: { at: string; stale: boolean; now: Date }) {
  const theme = useTheme();
  const age = formatAge(at, now);
  return (
    <View style={styles.row}>
      <Mark shape={stale ? 'diamond' : 'dot'} color={stale ? theme.warn : theme.accent} />
      <Txt variant="caption" tone={stale ? 'warn' : 'muted'}>
        {stale ? `Stale, ${age}` : age}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space[1] + 2 },
});
