import * as SecureStore from 'expo-secure-store';

import type { AuthResponse, User } from '@/api/types';

export const SESSION_KEY = 'oddvex.session';

export type StoredSession = { token: string; expiresAt: number; user: User };

/**
 * The bearer token is kept in the platform keystore (Keychain on iOS, Keystore-backed storage on Android)
 * through expo-secure-store. It is never written to AsyncStorage or logged.
 */
export async function saveSession(auth: AuthResponse, now: number = Date.now()): Promise<StoredSession> {
  const session: StoredSession = { token: auth.access_token, expiresAt: now + auth.expires_in * 1000, user: auth.user };
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
  return session;
}

/** The saved session, or null when there is none, it cannot be read, or its token has expired. */
export async function loadSession(now: number = Date.now()): Promise<StoredSession | null> {
  let raw: string | null;
  try {
    raw = await SecureStore.getItemAsync(SESSION_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as Partial<StoredSession>;
    if (typeof session.token === 'string' && typeof session.expiresAt === 'number' && session.user && session.expiresAt > now) {
      return session as StoredSession;
    }
  } catch {
    // Unreadable. Fall through and remove it.
  }
  await clearSession();
  return null;
}

export async function clearSession(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(SESSION_KEY);
  } catch {
    // Nothing more to do: the in-memory session is cleared either way.
  }
}
