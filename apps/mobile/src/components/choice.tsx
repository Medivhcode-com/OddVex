import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { radius, space, touchTarget } from '@/theme';

type Option<T extends string> = { value: T; label: string };

/**
 * Equal-width single choice, used for the market switcher and the odds format.
 * The selected option is filled and announced as checked; the unselected ones are outlined.
 */
export function Segmented<T extends string>({
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
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={label}
      style={[styles.segmented, { backgroundColor: theme.surface, borderColor: theme.border }]}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="radio"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={option.label}
            onPress={() => onChange(option.value)}
            style={({ pressed }) => [
              styles.segment,
              selected && { backgroundColor: theme.raised, borderColor: theme.borderStrong },
              pressed && !selected && { backgroundColor: theme.raised },
            ]}>
            <Txt variant="secondary" weight={selected ? 'semibold' : 'regular'} tone={selected ? 'text' : 'muted'}>
              {option.label}
            </Txt>
            {selected ? <View style={[styles.notch, { backgroundColor: theme.accent }]} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

/** A horizontally scrolling row of filter pills. `null` is the "All" option. */
export function FilterChips({
  label,
  allLabel,
  options,
  value,
  onChange,
}: {
  label: string;
  allLabel: string;
  options: readonly Option<string>[];
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  const theme = useTheme();
  const all: { value: string | null; label: string }[] = [{ value: null, label: allLabel }, ...options];
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      accessibilityLabel={label}
      contentContainerStyle={styles.chips}>
      {all.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value ?? '__all'}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            accessibilityLabel={`${option.label}${selected ? ', selected' : ''}`}
            onPress={() => onChange(option.value)}
            style={({ pressed }) => [
              styles.chip,
              { borderColor: selected ? theme.accent : theme.border, backgroundColor: theme.surface },
              selected && { backgroundColor: theme.accentSoft },
              pressed && !selected && { backgroundColor: theme.raised },
            ]}>
            <Txt variant="secondary" weight={selected ? 'semibold' : 'regular'} tone={selected ? 'accent' : 'muted'}>
              {option.label}
            </Txt>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  segmented: {
    flexDirection: 'row',
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.panel,
    padding: space[1],
    gap: space[1],
  },
  segment: {
    flex: 1,
    minHeight: touchTarget,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space[2],
    borderRadius: radius.cell + 2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'transparent',
  },
  notch: { position: 'absolute', bottom: 4, width: 16, height: 2, borderRadius: 1 },
  chips: { gap: space[2], paddingHorizontal: space[4], paddingVertical: space[2] },
  chip: {
    minHeight: touchTarget,
    minWidth: touchTarget,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space[4],
    borderRadius: radius.pill,
    borderWidth: 1,
  },
});
