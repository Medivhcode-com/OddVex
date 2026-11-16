import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError, confirmEmailVerification, confirmPasswordReset, describeError, isFeatureDisabled, requestPasswordReset } from '@/api/client';
import { PREVIEW_EMAIL_NOTE } from '@/components/account-forms';
import { Field } from '@/components/form';
import { Screen } from '@/components/screen';
import { Button, FeatureUnavailable, Notice, Panel } from '@/components/states';
import { Txt } from '@/components/text';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

/** The same sentence whether or not an account exists, so the screen never reveals which addresses are registered. */
export const RESET_REQUESTED = 'If an account exists for that address, a reset link has been sent.';
export const LINK_EXPIRED = 'This link has expired or was already used.';
export const LINK_INCOMPLETE = 'This link is incomplete. Open the full link from the message, or start again.';

/** The `token` from a link's query string. A repeated parameter arrives as a list; the first one is used. */
export function linkToken(param: string | string[] | undefined): string {
  return (Array.isArray(param) ? param[0] : param)?.trim() ?? '';
}

/** A used, expired, unknown or malformed token: the API answers 400 `invalid_or_expired_token`, or 422 for the shape. */
function isBadToken(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 400 || error.status === 422);
}

export function ForgotPasswordScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  const backToLogin = () => (router.canGoBack() ? router.back() : router.replace('/login'));

  async function submit() {
    const address = email.trim();
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(address)) return setFieldError('Enter a valid email address.');
    setFieldError(null);
    setPending(true);
    try {
      await requestPasswordReset(address);
      setDone(true);
    } catch (caught) {
      if (isFeatureDisabled(caught)) setUnavailable(true);
      else if (caught instanceof ApiError && caught.status === 422) setFieldError('Enter a valid email address.');
      else setError(describeError(caught, 'The request could not be sent. Try again.'));
    } finally {
      setPending(false);
    }
  }

  if (unavailable) {
    return (
      <Screen>
        <FeatureUnavailable />
        <Button label="Back to log in" variant="secondary" onPress={backToLogin} />
      </Screen>
    );
  }

  if (done) {
    return (
      <Screen>
        <Notice tone="accent" title="Check your email" text={RESET_REQUESTED} />
        <Notice tone="neutral" text={PREVIEW_EMAIL_NOTE} />
        <Txt variant="secondary" tone="muted">
          A reset link works once and then expires.
        </Txt>
        <Button label="Back to log in" variant="secondary" onPress={backToLogin} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        Enter the email address on your account and OddVex will prepare a link to set a new password.
      </Txt>
      <Panel>
        <View style={styles.form}>
          {error ? <Notice tone="error" text={error} /> : null}
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoComplete="email"
            textContentType="username"
            returnKeyType="send"
            onSubmitEditing={submit}
            error={fieldError}
          />
          <Button label={pending ? 'Sending reset link' : 'Send reset link'} onPress={submit} disabled={pending} />
        </View>
      </Panel>
      <Notice tone="neutral" text={PREVIEW_EMAIL_NOTE} />
    </Screen>
  );
}

type ResetErrors = { password?: string; confirmation?: string };

export function validateNewPassword(password: string, confirmation: string): ResetErrors {
  const fields: ResetErrors = {};
  if (password.length < 10) fields.password = 'Use at least 10 characters.';
  else if (password.length > 128) fields.password = 'Use 128 characters or fewer.';
  if (confirmation !== password) fields.confirmation = "The two passwords don't match.";
  return fields;
}

/** Opened from a reset link with its `token`. Saving signs out every session; the user then logs in again. */
export function ResetPasswordScreen({ token }: { token: string }) {
  const router = useRouter();
  const session = useSession();
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [fields, setFields] = useState<ResetErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [pending, setPending] = useState(false);

  const requestNew = <Button label="Request a new reset link" variant="secondary" onPress={() => router.replace('/forgot-password')} />;

  async function submit() {
    const problems = validateNewPassword(password, confirmation);
    setFields(problems);
    setError(null);
    if (Object.keys(problems).length) return;
    setPending(true);
    try {
      await confirmPasswordReset(token, password);
    } catch (caught) {
      if (isFeatureDisabled(caught)) setUnavailable(true);
      else if (isBadToken(caught)) setExpired(true);
      else setError(describeError(caught, 'The password was not changed.'));
      setPending(false);
      return;
    }
    // The reset rejects every earlier token, including one saved on this device, so only the local copy is
    // cleared. Calling the logout route here could end the sessions of a different account signed in on this device.
    await session.logOut({ local: true });
    router.replace({ pathname: '/login', params: { reset: 'done' } });
  }

  if (unavailable) {
    return (
      <Screen>
        <FeatureUnavailable />
      </Screen>
    );
  }
  if (!token || expired) {
    return (
      <Screen>
        <Notice tone="error" text={token ? LINK_EXPIRED : LINK_INCOMPLETE} />
        {requestNew}
      </Screen>
    );
  }

  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        Choose a password you don&apos;t use anywhere else.
      </Txt>
      <Panel>
        <View style={styles.form}>
          {error ? <Notice tone="error" text={error} /> : null}
          <Field
            label="New password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            hint="At least 10 characters."
            error={fields.password}
          />
          <Field
            label="Confirm new password"
            value={confirmation}
            onChangeText={setConfirmation}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="go"
            onSubmitEditing={submit}
            error={fields.confirmation}
          />
          <Button label={pending ? 'Saving password' : 'Set new password'} onPress={submit} disabled={pending} />
        </View>
      </Panel>
      <Txt variant="caption" tone="muted">
        Setting a new password signs you out everywhere. You then log in with the new one.
      </Txt>
    </Screen>
  );
}

/**
 * Opened from a confirmation link with its `token`. Like the web page, opening the link confirms nothing by
 * itself: the token works once, so it is spent only when the person presses the button.
 */
export function VerifyEmailScreen({ token }: { token: string }) {
  const router = useRouter();
  const session = useSession();
  const [state, setState] = useState<'idle' | 'pending' | 'done' | 'expired' | 'unavailable'>('idle');
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setState('pending');
    setError(null);
    try {
      await confirmEmailVerification(token);
    } catch (caught) {
      if (isFeatureDisabled(caught)) return setState('unavailable');
      if (isBadToken(caught)) return setState('expired');
      setError(describeError(caught, 'The address could not be confirmed. Try again.'));
      return setState('idle');
    }
    setState('done');
    // Settings reads the user from the session; pick up the confirmed address if someone is signed in.
    if (session.user) await session.refreshUser().catch(() => {});
  }

  if (state === 'unavailable') {
    return (
      <Screen>
        <FeatureUnavailable />
      </Screen>
    );
  }
  if (state === 'done') {
    return (
      <Screen>
        <Notice tone="accent" text="Email address confirmed." />
        <Button label="Open the app" variant="secondary" onPress={() => router.replace('/')} />
      </Screen>
    );
  }
  if (!token || state === 'expired') {
    return (
      <Screen>
        <Notice tone="error" text={token ? LINK_EXPIRED : LINK_INCOMPLETE} />
        <Txt variant="secondary" tone="muted">
          When you are logged in, Settings can prepare a new confirmation link.
        </Txt>
        <Button label="Open the app" variant="secondary" onPress={() => router.replace('/')} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        Confirming shows the address is yours. Nothing in OddVex is held back until you do.
      </Txt>
      {error ? <Notice tone="error" text={error} /> : null}
      <Button label={state === 'pending' ? 'Confirming' : 'Confirm email address'} onPress={confirm} disabled={state === 'pending'} />
    </Screen>
  );
}

const styles = StyleSheet.create({ form: { gap: space[4] } });
