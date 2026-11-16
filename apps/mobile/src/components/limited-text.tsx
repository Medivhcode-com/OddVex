import { Field } from '@/components/form';

/** Whether the text is longer than the API accepts. Counted the way the API counts: every character typed. */
export function tooLong(value: string, max: number): boolean {
  return value.length > max;
}

/**
 * A multi-line plain-text field with a live count ("42 / 280"). Going over the limit turns the count into an
 * announced error; the text is never cut silently.
 */
export function LimitedText({
  label,
  value,
  onChangeText,
  max,
  error,
  placeholder,
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  max: number;
  error?: string | null;
  placeholder?: string;
}) {
  const count = `${value.length} / ${max}`;
  return (
    <Field
      label={label}
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      multiline
      autoCapitalize="sentences"
      autoCorrect
      textAlignVertical="top"
      style={{ minHeight: 88 }}
      hint={`${count} characters`}
      error={error ?? (tooLong(value, max) ? `${count} characters. Shorten it to ${max} or fewer.` : null)}
    />
  );
}
