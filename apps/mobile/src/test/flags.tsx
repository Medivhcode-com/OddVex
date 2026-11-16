import type { ReactNode } from 'react';

import type { Flags } from '@/api/types';
import { flagOn, FlagsContext, type FlagsValue } from '@/providers/flags';

/** Flags for component tests. Without this wrapper every flag is off, like the app before the flags load. */
export function fakeFlags(flags: Flags, overrides: Partial<FlagsValue> = {}): FlagsValue {
  return { status: 'ready', isOn: (flag) => flagOn(flags, flag), reload: jest.fn(), ...overrides };
}

export function WithFlags({ flags, value, children }: { flags?: Flags; value?: FlagsValue; children: ReactNode }) {
  return <FlagsContext value={value ?? fakeFlags(flags ?? {})}>{children}</FlagsContext>;
}
