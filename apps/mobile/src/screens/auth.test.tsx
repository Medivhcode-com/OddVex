import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';
import { Linking } from 'react-native';

import { ApiError, ApiUnavailableError } from '@/api/client';
import { SUSPENDED_BODY, SUSPENDED_TITLE } from '@/components/account-forms';
import { AGE_CONFIRMATION, LoginScreen, PASSWORD_RESET_DONE, SignupScreen, validateSignup } from '@/screens/auth';
import { flagsAllOn } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

beforeEach(() => {
  jest.mocked(router.back).mockClear();
  jest.mocked(router.replace).mockClear();
});

describe('LoginScreen', () => {
  it('asks for both fields before calling the API', async () => {
    const session = fakeSession({ user: null });
    await render(
      <WithSession value={session}>
        <LoginScreen />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));

    expect(screen.getByText('Enter your email and password.')).toBeOnTheScreen();
    expect(session.logIn).not.toHaveBeenCalled();
  });

  it('logs in with the trimmed email and returns to the previous screen', async () => {
    const session = fakeSession({ user: null });
    await render(
      <WithSession value={session}>
        <LoginScreen />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Email'), ' sam@example.test ');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'correct horse battery');
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));

    expect(session.logIn).toHaveBeenCalledWith('sam@example.test', 'correct horse battery');
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it.each([
    [new ApiError(429, 'rate_limited', 'Rate limit exceeded'), 'Too many attempts. Wait a minute, then try again.'],
    [new ApiError(401, 'invalid_credentials', 'Incorrect email or password'), 'Incorrect email or password'],
    [new ApiUnavailableError(), "OddVex can't reach its data service right now. Try again in a moment."],
  ])('explains a failed log in', async (failure, message) => {
    const session = fakeSession({ user: null, logIn: jest.fn().mockRejectedValue(failure) });
    await render(
      <WithSession value={session}>
        <LoginScreen />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Email'), 'sam@example.test');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'wrong');
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText(message)).toBeOnTheScreen();
    expect(screen.getByRole('alert')).toBeOnTheScreen();
    expect(router.back).not.toHaveBeenCalled();
  });
});

describe('LoginScreen account states', () => {
  it('opens the reset screen from "Forgot password?" while email flows are on', async () => {
    jest.mocked(router.push).mockClear();
    await render(
      <WithFlags flags={flagsAllOn}>
        <WithSession value={fakeSession({ user: null })}>
          <LoginScreen />
        </WithSession>
      </WithFlags>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Forgot password?' }));
    expect(router.push).toHaveBeenCalledWith('/forgot-password');
  });

  it('confirms a finished password reset', async () => {
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <LoginScreen passwordReset />
      </WithSession>,
    );
    expect(screen.getByText(PASSWORD_RESET_DONE)).toBeOnTheScreen();
  });

  it('explains a suspended account neutrally when log in answers 403, with where to ask for the data', async () => {
    const session = fakeSession({
      user: null,
      logIn: jest.fn().mockRejectedValue(new ApiError(403, 'account_suspended', "This account can't be used right now. Contact support.")),
    });
    await render(
      <WithSession value={session}>
        <LoginScreen />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Email'), 'sam@example.test');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'correct horse battery');
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText(SUSPENDED_TITLE)).toBeOnTheScreen();
    expect(screen.getByText(SUSPENDED_BODY)).toBeOnTheScreen();
    expect(SUSPENDED_BODY).toMatch(/To ask for a copy of your data, or to have it deleted, write to support@oddvex\.com/);
    expect(SUSPENDED_BODY).toMatch(/from the email address on the account/);
    expect(SUSPENDED_BODY).toMatch(/signed out on this device/);
    expect(router.back).not.toHaveBeenCalled();
  });

  it('offers to write to the support address from the notice', async () => {
    const openURL = jest.mocked(Linking.openURL);
    openURL.mockReset().mockResolvedValue(undefined);
    await render(
      <WithSession value={fakeSession({ user: null, suspended: true })}>
        <LoginScreen />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('link', { name: 'Email support@oddvex.com' }));

    expect(openURL).toHaveBeenCalledWith('mailto:support@oddvex.com');
  });

  it('shows the same message after a 401 elsewhere ended the session', async () => {
    await render(
      <WithSession value={fakeSession({ user: null, suspended: true })}>
        <LoginScreen />
      </WithSession>,
    );
    expect(screen.getByText(SUSPENDED_TITLE)).toBeOnTheScreen();
    expect(screen.getByText(SUSPENDED_BODY)).toBeOnTheScreen();
  });
});

describe('SignupScreen', () => {
  it('uses the web copy for the age confirmation', () => {
    expect(AGE_CONFIRMATION).toBe('I am 21 or older, and I understand OddVex provides information only and does not take bets.');
  });

  it('names every problem and what to do about it', () => {
    expect(validateSignup({ email: 'nope', displayName: '', password: 'short', ageConfirmed: false })).toEqual({
      email: 'Enter a valid email address.',
      display_name: 'Enter a name to show on your account.',
      password: 'Use at least 10 characters.',
      age_confirmed: 'You must be 21 or over to use OddVex.',
    });
    expect(validateSignup({ email: 'sam@example.test', displayName: 'Sam', password: '0123456789', ageConfirmed: true })).toEqual({});
  });

  it('will not create an account until the 21+ switch is on', async () => {
    const session = fakeSession({ user: null });
    await render(
      <WithSession value={session}>
        <SignupScreen />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Name'), 'Sam');
    await fireEvent.changeText(screen.getByLabelText('Email'), 'sam@example.test');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'a long enough password');
    await fireEvent.press(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('You must be 21 or over to use OddVex.')).toBeOnTheScreen();
    expect(session.createAccount).not.toHaveBeenCalled();

    const age = screen.getByRole('switch', { name: AGE_CONFIRMATION });
    expect(age).not.toBeChecked();
    await fireEvent.press(age);
    expect(screen.getByRole('switch', { name: AGE_CONFIRMATION })).toBeChecked();
    await fireEvent.press(screen.getByRole('button', { name: 'Create account' }));

    expect(session.createAccount).toHaveBeenCalledWith({
      email: 'sam@example.test',
      password: 'a long enough password',
      display_name: 'Sam',
    });
    expect(router.back).toHaveBeenCalledTimes(1);
  });
});
