import { router } from 'expo-router';
import { createContext, use, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import * as api from '@/api/client';
import type { AuthResponse, User } from '@/api/types';
import { clearSession, loadSession, saveSession } from '@/session/store';

type Topic = 'bets' | 'watchlist';

export type SessionValue = {
  /** `loading` only while the saved session is being read at launch. */
  status: 'loading' | 'signedOut' | 'signedIn';
  user: User | null;
  logIn: (email: string, password: string) => Promise<void>;
  createAccount: (input: { email: string; password: string; display_name: string }) => Promise<void>;
  logOut: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
  /** Counters that go up when the user's bets or watchlist change, so every screen showing them reloads. */
  revision: Record<Topic, number>;
  changed: (topic: Topic) => void;
};

const signedOut: SessionValue = {
  status: 'signedOut',
  user: null,
  logIn: async () => {},
  createAccount: async () => {},
  logOut: async () => {},
  changePassword: async () => {},
  deleteAccount: async () => {},
  revision: { bets: 0, watchlist: 0 },
  changed: () => {},
};

export const SessionContext = createContext<SessionValue>(signedOut);

/**
 * Holds who is logged in. The token is in memory (handed to the API client) and in SecureStore so it survives
 * a restart. When the API rejects the token, the session is cleared and the log in screen opens.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ status: SessionValue['status']; user: User | null }>({ status: 'loading', user: null });
  const [revision, setRevision] = useState<Record<Topic, number>>({ bets: 0, watchlist: 0 });
  // Bumped whenever the session changes, so a slow launch-time check cannot overwrite a newer log in or log out.
  const epoch = useRef(0);

  const end = useCallback(async () => {
    epoch.current += 1;
    api.setAuthToken(null);
    setState({ status: 'signedOut', user: null });
    await clearSession();
  }, []);

  const begin = useCallback(async (auth: AuthResponse) => {
    epoch.current += 1;
    api.setAuthToken(auth.access_token);
    setState({ status: 'signedIn', user: auth.user });
    try {
      await saveSession(auth);
    } catch {
      // The keystore refused the write. The session still works until the app closes.
    }
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(() => {
      void end();
      router.push('/login');
    });
    return () => api.setUnauthorizedHandler(null);
  }, [end]);

  useEffect(() => {
    const started = epoch.current;
    loadSession().then((saved) => {
      if (epoch.current !== started) return;
      if (!saved) {
        setState({ status: 'signedOut', user: null });
        return;
      }
      api.setAuthToken(saved.token);
      setState({ status: 'signedIn', user: saved.user });
      // Confirm the token still works and pick up profile changes. A 401 here ends the session through the
      // handler above; any other failure (offline) leaves the saved session in place.
      api.getMe().then(
        (user) => {
          if (epoch.current === started) setState({ status: 'signedIn', user });
        },
        () => {},
      );
    });
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      ...state,
      revision,
      changed: (topic) => setRevision((current) => ({ ...current, [topic]: current[topic] + 1 })),
      logIn: async (email, password) => begin(await api.login(email, password)),
      createAccount: async (input) => begin(await api.register(input)),
      logOut: end,
      changePassword: async (currentPassword, newPassword) => begin(await api.changePassword(currentPassword, newPassword)),
      deleteAccount: async () => {
        await api.deleteAccount();
        await end();
      },
    }),
    [state, revision, begin, end],
  );

  return <SessionContext value={value}>{children}</SessionContext>;
}

export function useSession(): SessionValue {
  return use(SessionContext);
}

/** Opens the log in screen. Used wherever a signed-out person taps something that needs an account. */
export function openLogin(): void {
  router.push('/login');
}
