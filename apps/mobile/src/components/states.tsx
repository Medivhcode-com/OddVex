import { Pressable, StyleSheet, View, type DimensionValue } from 'react-native';

import { ApiError, ApiUnavailableError } from '@/api/client';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { radius, space, touchTarget } from '@/theme';

export function Button({ label, onPress }: { label: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.button, { backgroundColor: theme.accent }, pressed && styles.pressed]}>
      <Txt variant="body" weight="semibold" tone="accentInk">
        {label}
      </Txt>
    </Pressable>
  );
}

export function Panel({ children }: { children: React.ReactNode }) {
  const theme = useTheme();
  return <View style={[styles.panel, { backgroundColor: theme.surface, borderColor: theme.border }]}>{children}</View>;
}

/** Placeholder blocks while a screen loads. Static on purpose: nothing moves unless the user acts. */
export function SkeletonCards({ count = 3, label }: { count?: number; label: string }) {
  const theme = useTheme();
  const bar = (width: DimensionValue, height = 14) => (
    <View style={{ width, height, borderRadius: radius.cell, backgroundColor: theme.raised }} />
  );
  return (
    <View accessible accessibilityLabel={label} accessibilityLiveRegion="polite" style={styles.stack}>
      {Array.from({ length: count }, (_, index) => (
        <Panel key={index}>
          <View style={styles.skeleton}>
            {bar('35%', 12)}
            {bar('70%')}
            {bar('62%')}
          </View>
        </Panel>
      ))}
    </View>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <Panel>
      <View style={styles.message}>
        <Txt variant="heading" style={styles.center}>
          {title}
        </Txt>
        <Txt variant="secondary" tone="muted" style={styles.center}>
          {body}
        </Txt>
      </View>
    </Panel>
  );
}

export function errorCopy(error: unknown): { title: string; body: string } {
  if (error instanceof ApiUnavailableError) {
    return {
      title: "OddVex can't reach its data service",
      body: 'The data service is not responding, so there are no prices to show. Check your connection and try again.',
    };
  }
  if (error instanceof ApiError && error.status === 404) {
    return { title: 'Nothing found here', body: error.message };
  }
  return {
    title: 'This screen failed to load',
    body: error instanceof ApiError ? error.message : 'Something went wrong while loading this data.',
  };
}

/** What happened, in plain words, plus a retry. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const copy = errorCopy(error);
  return (
    <Panel>
      <View accessibilityRole="alert" style={styles.message}>
        <Txt variant="heading" style={styles.center}>
          {copy.title}
        </Txt>
        <Txt variant="secondary" tone="muted" style={styles.center}>
          {copy.body}
        </Txt>
        <Button label="Try again" onPress={onRetry} />
      </View>
    </Panel>
  );
}

/** Inline caution, used when a refresh fails but earlier data is still on screen. */
export function Notice({ text }: { text: string }) {
  const theme = useTheme();
  return (
    <View
      accessibilityRole="alert"
      style={[styles.notice, { backgroundColor: theme.warnSoft, borderColor: theme.warn }]}>
      <Txt variant="secondary" tone="warn">
        {text}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space[3] },
  panel: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.panel, padding: space[4] },
  skeleton: { gap: space[3] },
  message: { alignItems: 'center', gap: space[3], paddingVertical: space[4] },
  center: { textAlign: 'center' },
  button: {
    minHeight: touchTarget,
    minWidth: 120,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space[5],
    borderRadius: radius.cell,
    marginTop: space[1],
  },
  pressed: { opacity: 0.8 },
  notice: { borderLeftWidth: 3, borderRadius: radius.cell, padding: space[3] },
});
