import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, isAccountSuspended } from '@/api/client';
import { SuspendedNotice } from '@/components/account-forms';
import { Field, SwitchRow } from '@/components/form';
import { Screen } from '@/components/screen';
import { Button, Notice, Panel } from '@/components/states';
import { Txt } from '@/components/text';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

export const AGE_CONFIRMATION = 'I am 21 or older, and I understand OddVex provides information only and does not take bets.';

/** Closes the log in or sign up screen and returns to wherever the person came from. */
function useDone() {
  const router = useRouter();
  return () => (router.canGoBack() ? router.back() : router.replace('/'));
}

export const PASSWORD_RESET_DONE = 'Password changed. Log in with your new password.';

/** `passwordReset` is set when the reset screen sends the user here after a new password was saved. */
export function LoginScreen({ passwordReset = false }: { passwordReset?: boolean }) {
  const router = useRouter();
  const session = useSession();
  const emailFlows = useFlag('email_flows');
  const done = useDone();
  const [suspended, setSuspended] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    if (!email.trim() || !password) return setError('Enter your email and password.');
    setPending(true);
    setError(null);
    setSuspended(false);
    try {
      await session.logIn(email.trim(), password);
      done();
    } catch (caught) {
      // The session provider has already cleared anything saved on this device.
      if (isAccountSuspended(caught)) setSuspended(true);
      else setError(describeError(caught, "That email and password don't match an account."));
    } finally {
      setPending(false);
    }
  }

  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        Log in to track bets and follow teams, players and games. Odds, props and calculators work without an account.
      </Txt>
      {suspended || session.suspended ? <SuspendedNotice /> : null}
      {passwordReset && !error && !suspended ? <Notice tone="accent" text={PASSWORD_RESET_DONE} /> : null}
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
            returnKeyType="next"
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="current-password"
            textContentType="password"
            returnKeyType="go"
            onSubmitEditing={submit}
          />
          <Button label={pending ? 'Logging in' : 'Log in'} onPress={submit} disabled={pending} />
          {emailFlows ? <Button label="Forgot password?" variant="ghost" compact onPress={() => router.push('/forgot-password')} /> : null}
        </View>
      </Panel>
      <View style={styles.switch}>
        <Txt variant="secondary" tone="muted">
          New to OddVex?
        </Txt>
        <Button label="Create an account" variant="ghost" compact onPress={() => router.replace('/signup')} />
      </View>
    </Screen>
  );
}

type SignupErrors = { email?: string; display_name?: string; password?: string; age_confirmed?: string };

/** The same checks, in the same words, as the web sign up form. */
export function validateSignup(input: { email: string; displayName: string; password: string; ageConfirmed: boolean }): SignupErrors {
  const fields: SignupErrors = {};
  if (!/^\S+@\S+\.\S+$/.test(input.email)) fields.email = 'Enter a valid email address.';
  if (!input.displayName) fields.display_name = 'Enter a name to show on your account.';
  if (input.password.length < 10) fields.password = 'Use at least 10 characters.';
  if (!input.ageConfirmed) fields.age_confirmed = 'You must be 21 or over to use OddVex.';
  return fields;
}

export function SignupScreen() {
  const router = useRouter();
  const session = useSession();
  const done = useDone();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [fields, setFields] = useState<SignupErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    const input = { email: email.trim(), displayName: displayName.trim(), password, ageConfirmed };
    const problems = validateSignup(input);
    setFields(problems);
    setError(null);
    if (Object.keys(problems).length) return;
    setPending(true);
    try {
      await session.createAccount({ email: input.email, password, display_name: input.displayName });
      done();
    } catch (caught) {
      setError(describeError(caught, 'The account could not be created.'));
    } finally {
      setPending(false);
    }
  }

  return (
    <Screen>
      <Panel>
        <View style={styles.form}>
          {error ? <Notice tone="error" text={error} /> : null}
          <Field
            label="Name"
            value={displayName}
            onChangeText={setDisplayName}
            autoCapitalize="words"
            autoComplete="name"
            textContentType="nickname"
            error={fields.display_name}
          />
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoComplete="email"
            textContentType="username"
            error={fields.email}
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            hint="At least 10 characters."
            error={fields.password}
          />
          <SwitchRow label={AGE_CONFIRMATION} value={ageConfirmed} onChange={setAgeConfirmed} error={fields.age_confirmed} />
          <Button label={pending ? 'Creating account' : 'Create account'} onPress={submit} disabled={pending} />
        </View>
      </Panel>
      <Txt variant="caption" tone="muted">
        By creating an account you agree to the OddVex terms and privacy policy, which are on the website.
      </Txt>
      <View style={styles.switch}>
        <Txt variant="secondary" tone="muted">
          Already have an account?
        </Txt>
        <Button label="Log in" variant="ghost" compact onPress={() => router.replace('/login')} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[4] },
  switch: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[3] },
});
