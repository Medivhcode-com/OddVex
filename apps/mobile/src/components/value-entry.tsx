import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { Button, Panel } from '@/components/states';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { radius, space, touchTarget } from '@/theme';

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
  cardHead: { gap: 2 },
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
