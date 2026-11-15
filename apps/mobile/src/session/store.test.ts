import * as SecureStore from 'expo-secure-store';

import { clearSession, loadSession, saveSession, SESSION_KEY } from '@/session/store';
import { auth } from '@/test/fixtures';

const NOW = Date.parse('2026-11-15T20:00:00Z');

beforeEach(() => clearSession());

describe('session store', () => {
  it('keeps the token in SecureStore with its expiry', async () => {
    await saveSession(auth, NOW);

    const raw = await SecureStore.getItemAsync(SESSION_KEY);
    expect(JSON.parse(raw as string)).toEqual({ token: 'token-1', expiresAt: NOW + 3600_000, user: auth.user });
    await expect(loadSession(NOW + 1000)).resolves.toMatchObject({ token: 'token-1', user: { email: 'sam@example.test' } });
  });

  it('drops a session whose token has expired', async () => {
    await saveSession(auth, NOW);

    await expect(loadSession(NOW + 3600_001)).resolves.toBeNull();
    await expect(SecureStore.getItemAsync(SESSION_KEY)).resolves.toBeNull();
  });

  it('drops a stored value it cannot read', async () => {
    await SecureStore.setItemAsync(SESSION_KEY, 'not json');

    await expect(loadSession(NOW)).resolves.toBeNull();
    await expect(SecureStore.getItemAsync(SESSION_KEY)).resolves.toBeNull();
  });

  it('has nothing after clearing', async () => {
    await saveSession(auth, NOW);
    await clearSession();

    await expect(loadSession(NOW)).resolves.toBeNull();
  });
});
