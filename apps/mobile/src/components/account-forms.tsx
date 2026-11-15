import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError } from '@/api/client';
import { Field } from '@/components/form';
import { Button, Notice } from '@/components/states';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

/** The same checks, in the same words, as the web form. */
export function validatePasswordChange(current: string, next: string): string | null {
  if (!current) return 'Enter your current password.';
  if (next.length < 10) return 'Use at least 10 characters for the new password.';
  if (next === current) return 'The new password must be different from the current one.';
  return null;
}

/** Changing the password signs out every other device; this one keeps going on the new token the API returns. */
export function ChangePasswordForm() {
  const session = useSession();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  async function submit() {
    setDone(false);
    const problem = validatePasswordChange(current, next);
    if (problem) return setError(problem);
    setError(null);
    setPending(true);
    try {
      await session.changePassword(current, next);
      setCurrent('');
      setNext('');
      setDone(true);
    } catch (caught) {
      setError(describeError(caught, 'The password was not changed.'));
    } finally {
      setPending(false);
    }
  }

  return (
    <View style={styles.form}>
      {error ? <Notice tone="error" text={error} /> : null}
      {done ? <Notice tone="accent" text="Password changed. Other devices have been signed out." /> : null}
      <Field
        label="Current password"
        value={current}
        onChangeText={setCurrent}
        secureTextEntry
        autoComplete="current-password"
        textContentType="password"
      />
      <Field
        label="New password"
        value={next}
        onChangeText={setNext}
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        hint="At least 10 characters."
      />
      <Button label={pending ? 'Changing password' : 'Change password'} variant="secondary" disabled={pending} onPress={submit} />
    </View>
  );
}

/** Deleting needs the word DELETE typed out, like the web form. */
export function DeleteAccountForm() {
  const session = useSession();
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    if (confirm.trim().toUpperCase() !== 'DELETE') return setError('Type DELETE to confirm.');
    setError(null);
    setPending(true);
    try {
      await session.deleteAccount();
    } catch (caught) {
      setError(describeError(caught, 'The account could not be deleted.'));
      setPending(false);
    }
  }

  return (
    <View style={styles.form}>
      {error ? <Notice tone="error" text={error} /> : null}
      <Field label="Type DELETE to confirm" value={confirm} onChangeText={setConfirm} autoCapitalize="characters" autoComplete="off" />
      <Button label={pending ? 'Deleting account' : 'Delete account and data'} variant="danger" disabled={pending} onPress={submit} />
    </View>
  );
}

const styles = StyleSheet.create({ form: { gap: space[3] } });
