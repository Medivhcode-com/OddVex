import type { ReactNode } from 'react';

import { NO_CHANGES, SessionContext, type SessionValue } from '@/providers/session';
import { user } from '@/test/fixtures';

/** A session for component tests. Signed in as the fixture user unless `user: null` is passed. */
export function fakeSession(overrides: Partial<SessionValue> = {}): SessionValue {
  const signedIn = overrides.user !== null;
  return {
    status: signedIn ? 'signedIn' : 'signedOut',
    user: signedIn ? user : null,
    logIn: jest.fn(async () => {}),
    createAccount: jest.fn(async () => {}),
    logOut: jest.fn(async () => {}),
    changePassword: jest.fn(async () => {}),
    deleteAccount: jest.fn(async () => {}),
    revision: NO_CHANGES,
    changed: jest.fn(),
    ...overrides,
  };
}

export function WithSession({ value, children }: { value: SessionValue; children: ReactNode }) {
  return <SessionContext value={value}>{children}</SessionContext>;
}
