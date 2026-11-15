import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { ApiError, ApiUnavailableError } from '@/api/client';
import { AGE_CONFIRMATION, LoginScreen, SignupScreen, validateSignup } from '@/screens/auth';
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
