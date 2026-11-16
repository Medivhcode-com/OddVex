import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, getEntitlements, requestEmailVerification } from '@/api/client';
import { Field } from '@/components/form';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

/** Said wherever the app asks the API for an email. The API writes the message to an outbox table and sends nothing. */
export const PREVIEW_EMAIL_NOTE = 'In this preview no email is actually sent, so the link will not arrive in your inbox.';

export const SUSPENDED_TITLE = "This account can't be used right now";
export const SUSPENDED_BODY =
  'You have been signed out on this device. Your bets and settings are kept. To ask for a copy of your data, or to have it deleted, contact OddVex support and give the email address on the account. The privacy policy on the OddVex website explains your options.';

/** Shown on the log in screen after the API reports `account_suspended`. Text only: there is nothing to tap. */
export function SuspendedNotice() {
  return <Notice tone="warn" title={SUSPENDED_TITLE} text={SUSPENDED_BODY} />;
}

/**
 * "Email verified" or "Email not verified". While it is not, and the `email_flows` flag is on, a button asks
 * the API for a new confirmation message and shows the API's answer next to the preview statement.
 */
export function EmailVerificationStatus() {
  const session = useSession();
  const emailFlows = useFlag('email_flows');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  if (!session.user) return null;

  if (session.user.email_verified) {
    return <Txt variant="secondary">Email verified</Txt>;
  }

  async function send() {
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      setMessage((await requestEmailVerification()).message);
      // Picks up an address that was confirmed somewhere else in the meantime.
      await session.refreshUser().catch(() => {});
    } catch (caught) {
      setError(describeError(caught, 'The verification email could not be requested. Try again.'));
    } finally {
      setPending(false);
    }
  }

  return (
    <View style={styles.form}>
      <View style={styles.status}>
        <Txt variant="secondary">Email not verified</Txt>
        <Txt variant="caption" tone="muted">
          Nothing in OddVex is held back while your address is unconfirmed.
        </Txt>
      </View>
      {emailFlows ? (
        <>
          {error ? <Notice tone="error" text={error} /> : null}
          {message ? <Notice tone="accent" text={message} /> : null}
          <Button label={pending ? 'Sending verification email' : 'Send verification email'} variant="secondary" disabled={pending} onPress={send} />
          <Txt variant="caption" tone="muted">
            {PREVIEW_EMAIL_NOTE}
          </Txt>
        </>
      ) : null}
    </View>
  );
}

export const PREVIEW_ENTITLEMENTS_LINE = 'Preview: every feature is included';

/** One line while plans are not enforced. There is nothing to buy in this app. If the read fails, nothing is shown. */
export function EntitlementsLine({ userId }: { userId: string }) {
  const entitlements = useResource(`entitlements:${userId}`, getEntitlements);
  if (!entitlements.data?.preview) return null;
  return (
    <Txt variant="caption" tone="muted">
      {PREVIEW_ENTITLEMENTS_LINE}
    </Txt>
  );
}

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

const styles = StyleSheet.create({ form: { gap: space[3] }, status: { gap: 2 } });
