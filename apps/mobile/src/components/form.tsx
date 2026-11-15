import { Pressable, StyleSheet, Switch, TextInput, View, type TextInputProps } from 'react-native';

import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, monoFallback, monoFont, radius, space, touchTarget } from '@/theme';
import { useMonoFontLoaded } from '@/providers/fonts';

/**
 * A text input with a visible label, an optional hint and an optional error.
 * The input's accessible name is the label, and the error is announced when it appears.
 */
export function Field({
  label,
  hint,
  error,
  mono = false,
  style,
  ...input
}: Omit<TextInputProps, 'accessibilityLabel'> & { label: string; hint?: string; error?: string | null; mono?: boolean }) {
  const theme = useTheme();
  const monoLoaded = useMonoFontLoaded();
  return (
    <View style={styles.field}>
      <Txt variant="secondary" weight="medium">
        {label}
      </Txt>
      <TextInput
        accessibilityLabel={label}
        accessibilityHint={error ?? hint}
        aria-invalid={error ? true : undefined}
        placeholderTextColor={theme.muted}
        autoCapitalize="none"
        autoCorrect={false}
        {...input}
        style={[
          styles.input,
          { color: theme.text, backgroundColor: theme.bg, borderColor: error ? theme.error : theme.borderStrong },
          mono && { fontFamily: monoLoaded ? monoFont.regular : monoFallback },
          style,
        ]}
      />
      {error ? (
        <Txt variant="caption" tone="error" accessibilityRole="alert" accessibilityLiveRegion="assertive">
          {error}
        </Txt>
      ) : hint ? (
        <Txt variant="caption" tone="muted">
          {hint}
        </Txt>
      ) : null}
    </View>
  );
}

type Option<T extends string> = { value: T; label: string };

/**
 * Single choice from a short list, as wrapping pills. Stands in for a select menu, with no extra dependency.
 * The chosen pill is filled, outlined in the accent, and announced as checked.
 */
export function Choice<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly Option<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <Txt variant="secondary" weight="medium">
        {label}
      </Txt>
      <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.options}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={option.value}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={`${label}: ${option.label}`}
              onPress={() => onChange(option.value)}
              style={({ pressed }) => [
                styles.option,
                { borderColor: selected ? theme.accent : theme.border, backgroundColor: selected ? theme.accentSoft : theme.surface },
                pressed && !selected && { backgroundColor: theme.raised },
              ]}>
              <Txt variant="secondary" weight={selected ? 'semibold' : 'regular'} tone={selected ? 'text' : 'muted'}>
                {selected ? '✓ ' : ''}
                {option.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

/** A labelled on/off switch. The whole row is the control, so the target is well over 44pt. */
export function SwitchRow({
  label,
  value,
  onChange,
  error,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: string | null;
}) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <Pressable
        accessibilityRole="switch"
        accessibilityState={{ checked: value }}
        accessibilityLabel={label}
        accessibilityHint={error ?? undefined}
        onPress={() => onChange(!value)}
        style={styles.switchRow}>
        <Txt variant="secondary" style={styles.switchLabel}>
          {label}
        </Txt>
        <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Switch value={value} trackColor={{ true: theme.accent, false: theme.borderStrong }} />
        </View>
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
  field: { gap: space[1] + 2 },
  input: {
    minHeight: touchTarget,
    borderWidth: 1,
    borderRadius: radius.cell,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    fontSize: fontSize.body,
  },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  option: {
    minHeight: touchTarget,
    minWidth: touchTarget,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space[3],
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  switchRow: { minHeight: touchTarget, flexDirection: 'row', alignItems: 'center', gap: space[3] },
  switchLabel: { flex: 1 },
});
