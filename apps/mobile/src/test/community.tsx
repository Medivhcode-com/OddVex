import { render } from '@testing-library/react-native';
import type { ReactElement } from 'react';

import type { Flags } from '@/api/types';
import type { SessionValue } from '@/providers/session';
import { installFetch, serveRoutes } from '@/test/api';
import { flagsCommunityOn } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

/** Renders a community screen with both flags on and the fixture user signed in, unless told otherwise. */
export async function showCommunity(
  ui: ReactElement,
  routes: Record<string, unknown>,
  options: { flags?: Flags; session?: SessionValue } = {},
) {
  const { fetchMock, sent } = installFetch();
  serveRoutes(fetchMock, routes);
  const session = options.session ?? fakeSession();
  await render(
    <WithFlags flags={options.flags ?? flagsCommunityOn}>
      <WithSession value={session}>{ui}</WithSession>
    </WithFlags>,
  );
  return { fetchMock, sent, session, serve: (next: Record<string, unknown>) => serveRoutes(fetchMock, next) };
}
