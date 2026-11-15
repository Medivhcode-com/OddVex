import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { Txt } from '@/components/text';
import { useUnreadCount } from '@/hooks/use-notifications';
import { useTheme } from '@/hooks/use-theme';
import { radius, touchTarget } from '@/theme';

/** "Notifications" at zero, "Notifications, 3 unread" otherwise. */
export function bellLabel(unread: number): string {
  return unread > 0 ? `Notifications, ${unread} unread` : 'Notifications';
}

/** A bell drawn from plain views (dome, rim, clapper), so no icon dependency is needed. */
function BellIcon({ color }: { color: string }) {
  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.icon}>
      <View style={[styles.dome, { borderColor: color }]} />
      <View style={[styles.rim, { backgroundColor: color }]} />
      <View style={[styles.clapper, { backgroundColor: color }]} />
    </View>
  );
}

/**
 * Header button that opens Notifications. The unread count is a number in a badge and part of the label, so
 * it never depends on color; the badge is not rendered at zero.
 */
export function NotificationBell() {
  const theme = useTheme();
  const router = useRouter();
  const unread = useUnreadCount();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={bellLabel(unread)}
      accessibilityHint="Opens your notifications and alerts"
      onPress={() => router.push('/notifications')}
      style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
      <BellIcon color={theme.text} />
      {unread > 0 ? (
        <View style={[styles.badge, { backgroundColor: theme.accent, borderColor: theme.bg }]}>
          <Txt variant="caption" weight="semibold" tone="accentInk" maxFontSizeMultiplier={1.3}>
            {unread > 99 ? '99+' : unread}
          </Txt>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { minWidth: touchTarget, minHeight: touchTarget, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.6 },
  icon: { width: 20, height: 22, alignItems: 'center' },
  dome: { width: 14, height: 15, borderWidth: 2, borderBottomWidth: 0, borderTopLeftRadius: 7, borderTopRightRadius: 7 },
  rim: { width: 20, height: 2, borderRadius: 1 },
  clapper: { width: 6, height: 3, marginTop: 1, borderBottomLeftRadius: 3, borderBottomRightRadius: 3 },
  badge: {
    position: 'absolute',
    top: 2,
    right: -4,
    minWidth: 20,
    height: 20,
    paddingHorizontal: 5,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    borderWidth: 1,
  },
});
