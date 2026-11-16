import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { PREVIEW_EMAIL_NOTE } from '@/components/account-forms';
import {
  ForgotPasswordScreen,
  LINK_EXPIRED,
  LINK_INCOMPLETE,
  linkToken,
  RESET_REQUESTED,
  ResetPasswordScreen,
  validateNewPassword,
  VerifyEmailScreen,
} from '@/screens/email-flows';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { fakeSession, WithSession } from '@/test/session';

const TOKEN = 'tok_0123456789abcdefghijklmnopqrstuvwxyz';
const NEUTRAL = { message: 'If an account exists for that address, a reset link has been sent.' };

beforeEach(() => {
  jest.mocked(router.back).mockClear();
  jest.mocked(router.replace).mockClear();
  setAuthToken(null);
});

describe('ForgotPasswordScreen', () => {
  it('uses the agreed wording', () => {
    expect(RESET_REQUESTED).toBe('If an account exists for that address, a reset link has been sent.');
    expect(PREVIEW_EMAIL_NOTE).toBe('In this preview no email is actually sent, so the link will not arrive in your inbox.');
  });

  it.each([
    ['an address with an account', 'sam@example.test'],
    ['an address nobody registered', 'nobody@example.test'],
  ])('shows the same neutral result for %s', async (_case, address) => {
    const { fetchMock, sent } = installFetch();
    // The API answers 202 with the same body either way; the screen never looks at the body.
    fetchMock.mockResolvedValue(jsonResponse(NEUTRAL, 202));
    await render(<ForgotPasswordScreen />);
    expect(screen.getByText(PREVIEW_EMAIL_NOTE)).toBeOnTheScreen();

    await fireEvent.changeText(screen.getByLabelText('Email'), ` ${address} `);
    await fireEvent.press(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByText(RESET_REQUESTED)).toBeOnTheScreen();
    expect(screen.getByText(PREVIEW_EMAIL_NOTE)).toBeOnTheScreen();
    expect(screen.queryByText(address)).toBeNull();
    expect(screen.queryByLabelText('Email')).toBeNull();
    expect(sent()).toHaveLength(1);
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/auth/password-reset/request', body: { email: address } });
    expect(sent()[0].headers.authorization).toBeUndefined();

    await fireEvent.press(screen.getByRole('button', { name: 'Back to log in' }));
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it('checks the address before calling the API', async () => {
    const { fetchMock } = installFetch();
    await render(<ForgotPasswordScreen />);

    await fireEvent.changeText(screen.getByLabelText('Email'), 'not-an-address');
    await fireEvent.press(screen.getByRole('button', { name: 'Send reset link' }));

    expect(screen.getByText('Enter a valid email address.')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('uses the "Too many attempts" copy for a 429 and does not claim anything was sent', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(429, 'rate_limited', 'Rate limit exceeded'));
    await render(<ForgotPasswordScreen />);

    await fireEvent.changeText(screen.getByLabelText('Email'), 'sam@example.test');
    await fireEvent.press(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByText('Too many attempts. Wait a minute, then try again.')).toBeOnTheScreen();
    expect(screen.getByRole('alert')).toBeOnTheScreen();
    expect(screen.queryByText(RESET_REQUESTED)).toBeNull();
  });

  it('says so plainly when email flows are switched off', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(404, 'feature_disabled', 'This feature is not available'));
    await render(<ForgotPasswordScreen />);

    await fireEvent.changeText(screen.getByLabelText('Email'), 'sam@example.test');
    await fireEvent.press(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(screen.queryByText(RESET_REQUESTED)).toBeNull();
  });
});

describe('ResetPasswordScreen', () => {
  it('reads the token from the link', () => {
    expect(linkToken(` ${TOKEN} `)).toBe(TOKEN);
    expect(linkToken([TOKEN, 'second'])).toBe(TOKEN);
    expect(linkToken(undefined)).toBe('');
  });

  it('checks the length and that both fields match', () => {
    expect(validateNewPassword('short', 'short')).toEqual({ password: 'Use at least 10 characters.' });
    expect(validateNewPassword('long enough one', 'long enough two')).toEqual({ confirmation: "The two passwords don't match." });
    expect(validateNewPassword('x'.repeat(129), 'x'.repeat(129))).toEqual({ password: 'Use 128 characters or fewer.' });
    expect(validateNewPassword('0123456789', '0123456789')).toEqual({});
  });

  it('will not call the API until the password is long enough and confirmed', async () => {
    const { fetchMock } = installFetch();
    await render(<ResetPasswordScreen token={TOKEN} />);

    await fireEvent.changeText(screen.getByLabelText('New password'), 'too short');
    await fireEvent.changeText(screen.getByLabelText('Confirm new password'), 'too short');
    await fireEvent.press(screen.getByRole('button', { name: 'Set new password' }));
    expect(screen.getByText('Use at least 10 characters.')).toBeOnTheScreen();

    await fireEvent.changeText(screen.getByLabelText('New password'), 'a much newer password');
    await fireEvent.changeText(screen.getByLabelText('Confirm new password'), 'a much newer passwrod');
    await fireEvent.press(screen.getByRole('button', { name: 'Set new password' }));
    expect(screen.getByText("The two passwords don't match.")).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('sends the token and the new password, signs out locally and goes to log in', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue({ ok: true, status: 204, json: async () => undefined });
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <ResetPasswordScreen token={TOKEN} />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('New password'), 'a much newer password');
    await fireEvent.changeText(screen.getByLabelText('Confirm new password'), 'a much newer password');
    await fireEvent.press(screen.getByRole('button', { name: 'Set new password' }));

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith({ pathname: '/login', params: { reset: 'done' } }));
    expect(sent()).toHaveLength(1);
    expect(sent()[0]).toMatchObject({
      method: 'POST',
      path: '/v1/auth/password-reset/confirm',
      body: { token: TOKEN, new_password: 'a much newer password' },
    });
    expect(sent()[0].headers.authorization).toBeUndefined();
    expect(session.logOut).toHaveBeenCalledTimes(1);
    // Only this device's copy is cleared: the reset already ended every session of that account.
    expect(session.logOut).toHaveBeenCalledWith({ local: true });
  });

  it('explains a used or expired link and offers a new one', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(400, 'invalid_or_expired_token', 'This link is invalid or has expired'));
    const session = fakeSession({ user: null });
    await render(
      <WithSession value={session}>
        <ResetPasswordScreen token={TOKEN} />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('New password'), 'a much newer password');
    await fireEvent.changeText(screen.getByLabelText('Confirm new password'), 'a much newer password');
    await fireEvent.press(screen.getByRole('button', { name: 'Set new password' }));

    expect(await screen.findByText(LINK_EXPIRED)).toBeOnTheScreen();
    expect(session.logOut).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByRole('button', { name: 'Request a new reset link' }));
    expect(router.replace).toHaveBeenCalledWith('/forgot-password');
  });

  it('asks for the full link when the token is missing', async () => {
    const { fetchMock } = installFetch();
    await render(<ResetPasswordScreen token="" />);

    expect(screen.getByText(LINK_INCOMPLETE)).toBeOnTheScreen();
    expect(screen.queryByLabelText('New password')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('VerifyEmailScreen', () => {
  it('confirms the address with the token and refreshes the signed-in user', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ email_verified: true }));
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <VerifyEmailScreen token={TOKEN} />
      </WithSession>,
    );
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByRole('button', { name: 'Confirm email address' }));

    expect(await screen.findByText('Email address confirmed.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/auth/verify-email/confirm', body: { token: TOKEN } });
    expect(session.refreshUser).toHaveBeenCalledTimes(1);
    await fireEvent.press(screen.getByRole('button', { name: 'Open the app' }));
    expect(router.replace).toHaveBeenCalledWith('/');
  });

  it('works signed out, where there is no user to refresh', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ email_verified: true }));
    const session = fakeSession({ user: null });
    await render(
      <WithSession value={session}>
        <VerifyEmailScreen token={TOKEN} />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Confirm email address' }));
    expect(await screen.findByText('Email address confirmed.')).toBeOnTheScreen();
    expect(session.refreshUser).not.toHaveBeenCalled();
  });

  it('says the link is invalid or expired', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(400, 'invalid_or_expired_token', 'This link is invalid or has expired'));
    await render(<VerifyEmailScreen token={TOKEN} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Confirm email address' }));

    expect(await screen.findByText(LINK_EXPIRED)).toBeOnTheScreen();
    expect(screen.getByRole('alert')).toBeOnTheScreen();
    expect(screen.queryByText('Email address confirmed.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Confirm email address' })).toBeNull();
  });

  it('asks for the full link when the token is missing', async () => {
    const { fetchMock } = installFetch();
    await render(<VerifyEmailScreen token="" />);

    expect(screen.getByText(LINK_INCOMPLETE)).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('keeps the button after a failure that is not about the link', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(429, 'rate_limited', 'Rate limit exceeded'));
    await render(<VerifyEmailScreen token={TOKEN} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Confirm email address' }));

    expect(await screen.findByText('Too many attempts. Wait a minute, then try again.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Confirm email address' })).toBeEnabled();
  });
});
