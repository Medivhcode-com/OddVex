import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { describeError, follow, unfollow } from '@/api/client';
import type { WatchKind } from '@/api/types';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { openLogin, useSession } from '@/providers/session';
import { radius, space, touchTarget } from '@/theme';

/**
 * Follow or unfollow a team, player or game. Signed-out people are sent to log in.
 * The state is carried by the word ("Follow" / "Following"), a filled or hollow star and the selected state,
 * not by color.
 */
export function WatchButton({ kind, refId, name, itemId }: { kind: WatchKind; refId: string; name: string; itemId: string | null }) {
  const theme = useTheme();
  const session = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const watching = itemId !== null;
  const label = `${watching ? 'Following' : 'Follow'} ${name}`;

  async function toggle() {
    if (!session.user) return openLogin();
    setBusy(true);
    setError(null);
    try {
      if (itemId) await unfollow(itemId);
      else await follow(kind, refId);
      session.changed('watchlist');
    } catch (caught) {
      setError(describeError(caught, "That didn't work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.wrap}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint={watching ? 'Stops following' : session.user ? 'Adds to your watchlist' : 'Opens log in'}
        accessibilityState={{ selected: watching, disabled: busy, busy }}
        disabled={busy}
        onPress={toggle}
        style={({ pressed }) => [
          styles.button,
          { borderColor: watching ? theme.accent : theme.border, backgroundColor: watching ? theme.accentSoft : 'transparent' },
          pressed && { backgroundColor: theme.raised },
          busy && styles.busy,
        ]}>
        <Txt variant="secondary" tone={watching ? 'accent' : 'muted'} accessibilityElementsHidden importantForAccessibility="no">
          {watching ? '★' : '☆'}
        </Txt>
        <Txt variant="secondary" weight="medium" tone={watching ? 'text' : 'muted'}>
          {label}
        </Txt>
      </Pressable>
      {error ? (
        <Txt variant="caption" tone="error" accessibilityRole="alert" accessibilityLiveRegion="assertive">
          {error}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'flex-start', gap: space[1] },
  button: {
    minHeight: touchTarget,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    paddingHorizontal: space[3],
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  busy: { opacity: 0.6 },
});
