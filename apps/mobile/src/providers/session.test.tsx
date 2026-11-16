import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, render, screen, waitFor } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import { router } from 'expo-router';
import { useEffect } from 'react';
import { Text } from 'react-native';

import { getAuthToken, getBets, setAuthToken } from '@/api/client';
import { SessionProvider, useSession, type SessionValue } from '@/providers/session';
import { clearSession, saveSession, SESSION_KEY } from '@/session/store';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { auth, user } from '@/test/fixtures';

let session: SessionValue;

function Probe() {
  const value = useSession();
  useEffect(() => {
    session = value;
  }, [value]);
  return <Text>{value.status === 'signedIn' ? `in:${value.user?.display_name}` : value.status}</Text>;
}

async function mount() {
  await render(
    <SessionProvider>
      <Probe />
    </SessionProvider>,
  );
}

const stored = async () => {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  return raw ? (JSON.parse(raw) as { token: string }) : null;
};

beforeEach(async () => {
  await clearSession();
  await AsyncStorage.clear();
  setAuthToken(null);
  jest.mocked(router.push).mockClear();
});

describe('SessionProvider', () => {
  it('starts signed out when nothing is stored', async () => {
    installFetch();
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    expect(getAuthToken()).toBeNull();
  });

  it('logs in, keeps the token in SecureStore and never in AsyncStorage', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(auth));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());

    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    expect(screen.getByText('in:Sam')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({
      method: 'POST',
      path: '/v1/auth/login',
      body: { email: 'sam@example.test', password: 'correct horse battery' },
    });
    expect(sent()[0].headers.authorization).toBeUndefined();
    expect(getAuthToken()).toBe('token-1');
    expect((await stored())?.token).toBe('token-1');
    expect(await AsyncStorage.getAllKeys()).toEqual([]);
  });

  it('stays signed out and stores nothing when the password is wrong', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(401, 'invalid_credentials', 'Incorrect email or password'));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());

    let failure: unknown;
    await act(async () => {
      failure = await session.logIn('sam@example.test', 'wrong').catch((caught: unknown) => caught);
    });

    expect(failure).toMatchObject({ status: 401, message: 'Incorrect email or password' });
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    expect(await stored()).toBeNull();
    expect(router.push).not.toHaveBeenCalled();
  });

  it('restores a saved session at launch and confirms it with the API', async () => {
    await saveSession(auth);
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ ...user, display_name: 'Samantha' }));
    await mount();

    await waitFor(() => expect(screen.getByText('in:Samantha')).toBeOnTheScreen());
    expect(sent()[0]).toMatchObject({ method: 'GET', path: '/v1/me' });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
  });

  it('keeps a saved session when the launch check cannot reach the API', async () => {
    await saveSession(auth);
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await mount();

    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());
    expect((await stored())?.token).toBe('token-1');
  });

  it('clears the session and opens log in when an authed call gets a 401', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(auth));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    fetchMock.mockResolvedValueOnce(errorResponse(401, 'unauthorized', 'Token expired'));
    await act(async () => {
      await getBets().catch(() => {});
    });

    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    expect(getAuthToken()).toBeNull();
    await waitFor(async () => expect(await stored()).toBeNull());
    expect(router.push).toHaveBeenCalledWith('/login');
  });

  it('signs out locally and flags the account when an authed call gets 401 account_suspended', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(auth));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));
    expect(session.suspended).toBe(false);
    expect((await stored())?.token).toBe('token-1');

    fetchMock.mockResolvedValueOnce(errorResponse(401, 'account_suspended', 'This account is suspended'));
    await act(async () => {
      await getBets().catch(() => {});
    });

    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await waitFor(() => expect(session.suspended).toBe(true));
    expect(getAuthToken()).toBeNull();
    await waitFor(async () => expect(await stored()).toBeNull());
    expect(router.push).toHaveBeenCalledWith('/login');

    // A later successful log in clears the flag.
    fetchMock.mockResolvedValueOnce(jsonResponse(auth));
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));
    expect(session.suspended).toBe(false);
  });

  it('clears a saved session when log in answers 403 account_suspended', async () => {
    await saveSession(auth);
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    fetchMock.mockResolvedValueOnce(errorResponse(403, 'account_suspended', "This account can't be used right now. Contact support."));
    let failure: unknown;
    await act(async () => {
      failure = await session.logIn('sam@example.test', 'correct horse battery').catch((caught: unknown) => caught);
    });

    expect(failure).toMatchObject({ status: 403, code: 'account_suspended' });
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    expect(session.suspended).toBe(true);
    expect(getAuthToken()).toBeNull();
    expect(await stored()).toBeNull();
  });

  it('does not flag the account for an ordinary 401', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(auth));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    fetchMock.mockResolvedValueOnce(errorResponse(401, 'invalid_token', 'The access token is invalid or has expired'));
    await act(async () => {
      await getBets().catch(() => {});
    });
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    expect(session.suspended).toBe(false);
  });

  it('reads the user again on request', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...auth, user: { ...user, email_verified: false } }));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));
    expect(session.user?.email_verified).toBe(false);

    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await act(() => session.refreshUser());
    expect(session.user?.email_verified).toBe(true);
  });

  it('stores the new token the API returns after a password change', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(auth));
    await mount();
    await waitFor(() => expect(screen.getByText('signedOut')).toBeOnTheScreen());
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    fetchMock.mockResolvedValueOnce(jsonResponse({ ...auth, access_token: 'token-2' }));
    await act(() => session.changePassword('correct horse battery', 'a much newer password'));

    expect(sent()[1]).toMatchObject({
      path: '/v1/me/password',
      body: { current_password: 'correct horse battery', new_password: 'a much newer password' },
    });
    expect(sent()[1].headers.authorization).toBe('Bearer token-1');
    expect(getAuthToken()).toBe('token-2');
    expect((await stored())?.token).toBe('token-2');
    expect(screen.getByText('in:Sam')).toBeOnTheScreen();
  });

  it('logs out through the API first, then deletes the stored token', async () => {
    await saveSession(auth);
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    // The token is still stored and still in use at the moment the API is asked to end the sessions.
    let storedDuringCall: string | undefined;
    let tokenDuringCall: string | null = null;
    fetchMock.mockImplementationOnce(async () => {
      storedDuringCall = (await stored())?.token;
      tokenDuringCall = getAuthToken();
      return { ok: true, status: 204, json: async () => null };
    });
    await act(() => session.logOut());

    expect(sent()[1]).toMatchObject({ method: 'POST', path: '/v1/auth/logout' });
    expect(sent()[1].headers.authorization).toBe('Bearer token-1');
    expect(sent()[1].body).toBeUndefined();
    expect(storedDuringCall).toBe('token-1');
    expect(tokenDuringCall).toBe('token-1');
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    expect(getAuthToken()).toBeNull();
    expect(await stored()).toBeNull();
  });

  it('still clears the token on this device when the API cannot be reached', async () => {
    await saveSession(auth);
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed'));
    await act(() => session.logOut());

    expect(sent()[1]).toMatchObject({ method: 'POST', path: '/v1/auth/logout' });
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    expect(getAuthToken()).toBeNull();
    expect(await stored()).toBeNull();
    expect(router.push).not.toHaveBeenCalled();
  });

  it('clears the token without a surprise log in screen when the API rejects the logout', async () => {
    await saveSession(auth);
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    for (const response of [errorResponse(401, 'invalid_token', 'The access token is invalid or has expired'), errorResponse(500, 'server_error', 'Something went wrong')]) {
      await saveSession(auth);
      setAuthToken('token-1');
      fetchMock.mockResolvedValueOnce(response);
      await act(() => session.logOut());
      expect(getAuthToken()).toBeNull();
      expect(await stored()).toBeNull();
    }
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    // A 401 to the logout itself is not the "your session ended" case: the log in screen is not pushed.
    expect(router.push).not.toHaveBeenCalled();
  });

  it('clears only this device after a password reset, without calling the logout route', async () => {
    await saveSession(auth);
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user));
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    await act(() => session.logOut({ local: true }));

    expect(sent()).toHaveLength(1);
    expect(getAuthToken()).toBeNull();
    expect(await stored()).toBeNull();
  });

  it('deletes the account, then ends the session', async () => {
    await saveSession(auth);
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(user)).mockResolvedValueOnce({ ok: true, status: 204, json: async () => null });
    await mount();
    await waitFor(() => expect(screen.getByText('in:Sam')).toBeOnTheScreen());

    await act(() => session.deleteAccount());

    expect(sent()[1]).toMatchObject({ method: 'DELETE', path: '/v1/me' });
    expect(screen.getByText('signedOut')).toBeOnTheScreen();
    expect(await stored()).toBeNull();
  });
});
