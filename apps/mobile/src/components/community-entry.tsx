import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { radius, space, touchTarget } from '@/theme';

/** The way in from the Games tab. Rendered only while the `community` flag is on. */
export function CommunityEntry() {
  const router = useRouter();
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel="Community: picks posted before the game and graded from the final score"
      onPress={() => router.push('/community')}
      style={({ pressed }) => [
        styles.linkRow,
        { backgroundColor: theme.surface, borderColor: theme.border },
        pressed && { backgroundColor: theme.raised },
      ]}>
      <View style={styles.linkText}>
        <Txt variant="secondary" weight="semibold">
          Community
        </Txt>
        <Txt variant="caption" tone="muted">
          Picks posted before the game and graded from the final score
        </Txt>
      </View>
      <Txt tone="muted" accessibilityElementsHidden importantForAccessibility="no">
        ›
      </Txt>
    </Pressable>
  );
}

const styles = StyleSheet.create({
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
});
