import { useState } from 'react';
import { Pressable, StyleSheet, View, type DimensionValue } from 'react-native';

import { ApiError, ApiUnavailableError } from '@/api/client';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, radius, space, touchTarget } from '@/theme';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

/**
 * The one button. `primary` is the filled accent action; `secondary` and `ghost` are quieter; `danger` deletes.
 * Disabled buttons say so to assistive technology and dim, and their label still reads the same.
 */
export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  compact = false,
  accessibilityLabel,
  accessibilityHint,
  selected,
}: {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  /** Hugs its label and drops the minimum width. Height stays at the 44pt touch target. */
  compact?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  selected?: boolean;
}) {
  const theme = useTheme();
  const fill = variant === 'primary' ? theme.accent : variant === 'secondary' ? theme.raised : 'transparent';
  const border =
    variant === 'danger' ? theme.error : variant === 'secondary' ? theme.borderStrong : variant === 'ghost' ? theme.border : fill;
  const tone = variant === 'primary' ? 'accentInk' : variant === 'danger' ? 'error' : 'text';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled, ...(selected === undefined ? null : { selected }) }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        compact && styles.compact,
        { backgroundColor: fill, borderColor: border },
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}>
      <Txt variant={compact ? 'secondary' : 'body'} weight="semibold" tone={tone}>
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

export function EmptyState({ title, body, children }: { title: string; body: string; children?: React.ReactNode }) {
  return (
    <Panel>
      <View style={styles.message}>
        <Txt variant="heading" style={styles.center}>
          {title}
        </Txt>
        <Txt variant="secondary" tone="muted" style={styles.center}>
          {body}
        </Txt>
        {children}
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

type NoticeTone = 'warn' | 'error' | 'accent' | 'neutral';

/**
 * Inline message. `warn` is the default (a refresh failed but earlier data is still on screen). Errors and
 * cautions are announced as alerts; confirmations and notes are announced politely. Each tone has its own
 * leading word or title, so the tone is never carried by color alone.
 */
export function Notice({ text, title, tone = 'warn', children }: { text?: string; title?: string; tone?: NoticeTone; children?: React.ReactNode }) {
  const theme = useTheme();
  const palette = {
    warn: { bg: theme.warnSoft, edge: theme.warn, ink: 'warn' },
    error: { bg: theme.errorSoft, edge: theme.error, ink: 'error' },
    accent: { bg: theme.accentSoft, edge: theme.accent, ink: 'text' },
    neutral: { bg: theme.raised, edge: theme.borderStrong, ink: 'muted' },
  } as const;
  const { bg, edge, ink } = palette[tone];
  const urgent = tone === 'warn' || tone === 'error';
  return (
    <View
      accessible
      accessibilityRole={urgent ? 'alert' : undefined}
      accessibilityLiveRegion={urgent ? 'assertive' : 'polite'}
      style={[styles.notice, { backgroundColor: bg, borderColor: edge }]}>
      {title ? (
        <Txt variant="secondary" weight="semibold" tone={tone === 'neutral' ? 'text' : ink}>
          {title}
        </Txt>
      ) : null}
      {text ? (
        <Txt variant="secondary" tone={title && tone !== 'error' ? 'muted' : ink}>
          {text}
        </Txt>
      ) : null}
      {children}
    </View>
  );
}

/** Panel title with an optional one-line description. */
export function PanelHeading({ title, description }: { title: string; description?: string }) {
  return (
    <View style={styles.heading}>
      <Txt variant="heading" accessibilityRole="header">
        {title}
      </Txt>
      {description ? (
        <Txt variant="secondary" tone="muted">
          {description}
        </Txt>
      ) : null}
    </View>
  );
}

/** A label over a monospace value, with an optional hint. Read out as one phrase. */
export function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'accent' | 'error' }) {
  return (
    <View accessible accessibilityLabel={[label, value, hint].filter(Boolean).join(', ')} style={styles.stat}>
      <Txt variant="caption" tone="muted">
        {label}
      </Txt>
      <Num size={fontSize.score} tone={tone ?? 'text'} weight="semibold">
        {value}
      </Num>
      {hint ? (
        <Txt variant="caption" tone="muted">
          {hint}
        </Txt>
      ) : null}
    </View>
  );
}

/** Two-column grid for `Stat`s. */
export function StatGrid({ children }: { children: React.ReactNode }) {
  return <View style={styles.statGrid}>{children}</View>;
}

/** The API's `steps`, behind a "Show the working" toggle. */
export function Working({ steps }: { steps: readonly string[] }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;
  return (
    <View style={[styles.working, { borderColor: theme.border }]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={open ? 'Hide the working' : 'Show the working'}
        onPress={() => setOpen((value) => !value)}
        style={styles.workingToggle}>
        <Txt variant="secondary" weight="medium">
          {open ? 'Hide the working' : 'Show the working'}
        </Txt>
      </Pressable>
      {open ? (
        <View style={[styles.steps, { borderTopColor: theme.border }]}>
          {steps.map((step, index) => (
            <Num key={index} size={fontSize.caption} tone="muted" weight="regular">
              {index + 1}. {step}
            </Num>
          ))}
        </View>
      ) : null}
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
    borderWidth: 1,
  },
  compact: { minWidth: touchTarget, paddingHorizontal: space[3], alignSelf: 'flex-start' },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.5 },
  notice: { borderLeftWidth: 3, borderRadius: radius.cell, padding: space[3], gap: space[1] },
  heading: { gap: 2 },
  stat: { width: '47%', flexGrow: 1, gap: 2 },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[4], rowGap: space[4] },
  working: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.cell },
  workingToggle: { minHeight: touchTarget, justifyContent: 'center', paddingHorizontal: space[3] },
  steps: { borderTopWidth: StyleSheet.hairlineWidth, padding: space[3], gap: space[2] },
});
