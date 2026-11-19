import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { useEffect, type ReactElement } from 'react';
import { Button, Text, TextInput } from 'react-native';

import { getUnreadCount, setAuthToken } from '@/api/client';
import type { StakeReminder } from '@/api/types';
import { REPORT_SENT } from '@/components/community-copy';
import { ProfileForm } from '@/components/profile-form';
import { SessionProvider, useSession, type SessionValue } from '@/providers/session';
import { CommunityPickScreen } from '@/screens/community-pick';
import { CommunityProfileEditScreen } from '@/screens/community-profile-edit';
import { GameDetailScreen } from '@/screens/game-detail';
import { SettingsScreen } from '@/screens/settings';
import { TrackerScreen } from '@/screens/tracker';
import { DRAFT_KEPT, draftsSaved, dropDrafts, holdDrafts, releaseDrafts, useDraft, useDraftKept } from '@/session/drafts';
import { clearSession } from '@/session/store';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { auth, flagsCommunityOn, liveEvent, moneyline, myProfile, openBet, reminderExceeded, spread, upcomingEvent, upcomingPick } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';

/** "Save" is a form whose save succeeded and that keeps its fields; "Save and clear" is one that empties them. */
function Form() {
  const [text, setText] = useDraft('form:text', '');
  const [untouched] = useDraft('form:untouched', 'as it was');
  const [kept, , saved] = useDraftKept('form');
  return (
    <>
      <TextInput accessibilityLabel="Text" value={text} onChangeText={setText} />
      <Text>{untouched}</Text>
      <Text>{kept ? 'kept' : 'fresh'}</Text>
      <Button title="Save" onPress={saved} />
      <Button
        title="Save and clear"
        onPress={() => {
          setText('');
          saved();
        }}
      />
    </>
  );
}

/** What happens to a form when the session ends unexpectedly and the same person logs in again. */
async function signOutAndBackIn(form: { unmount: () => Promise<void> | void }) {
  holdDrafts();
  await form.unmount();
  releaseDrafts();
}

describe('useDraft', () => {
  it('forgets a field when its form leaves the screen in the ordinary way', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'half a thought');
    await first.unmount();

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('keeps a changed field across an unexpected sign-out, hands it back once, then forgets it', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'half a thought');
    holdDrafts();
    await first.unmount();
    releaseDrafts();

    const second = await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('half a thought');
    expect(screen.getByText('kept')).toBeOnTheScreen();
    await second.unmount();

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('does not report a form nobody typed in as kept', async () => {
    const first = await render(<Form />);
    holdDrafts();
    await first.unmount();
    releaseDrafts();

    await render(<Form />);
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('does not keep a field that was saved after it was changed', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'saved as typed');
    await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
    await signOutAndBackIn(first);

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('does not keep a field the form emptied as it was saved', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'saved, then cleared');
    await fireEvent.press(screen.getByRole('button', { name: 'Save and clear' }));
    await signOutAndBackIn(first);

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('keeps what is changed after a save', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'saved as typed');
    await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
    await fireEvent.changeText(screen.getByLabelText('Text'), 'typed after the save');
    await signOutAndBackIn(first);

    const second = await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('typed after the save');
    expect(screen.getByText('kept')).toBeOnTheScreen();

    // Going back to the saved text leaves nothing unsaved. Before any save, that is the starting value.
    await fireEvent.changeText(screen.getByLabelText('Text'), '');
    await signOutAndBackIn(second);

    await render(<Form />);
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('forgets a kept field when the save that was on its way succeeds after the form left the screen', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'sent just before the sign-out');
    await signOutAndBackIn(first);
    draftsSaved('form');

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });

  it('stops saying nothing was saved when that save succeeds after the form is back on screen', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'sent just before the sign-out');
    await signOutAndBackIn(first);

    const second = await render(<Form />);
    expect(screen.getByText('kept')).toBeOnTheScreen();
    await act(async () => draftsSaved('form'));
    expect(screen.getByText('fresh')).toBeOnTheScreen();

    // What came back is what was saved, so it is not kept a second time.
    await signOutAndBackIn(second);
    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
  });

  it('leaves other forms alone when one form is saved', async () => {
    function Other() {
      const [text, setText] = useDraft('form-two:text', '');
      return <TextInput accessibilityLabel="Other text" value={text} onChangeText={setText} />;
    }
    const first = await render(
      <>
        <Form />
        <Other />
      </>,
    );
    await fireEvent.changeText(screen.getByLabelText('Other text'), 'not saved');
    await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
    await signOutAndBackIn(first);

    await render(<Other />);
    expect(screen.getByLabelText('Other text')).toHaveDisplayValue('not saved');
  });

  it('discards everything when told to', async () => {
    const first = await render(<Form />);
    await fireEvent.changeText(screen.getByLabelText('Text'), 'half a thought');
    holdDrafts();
    await first.unmount();
    dropDrafts();

    await render(<Form />);
    expect(screen.getByLabelText('Text')).toHaveDisplayValue('');
    expect(screen.getByText('fresh')).toBeOnTheScreen();
  });
});

// The forms below sit on screens that replace them with a log in prompt when the session ends.

let session: SessionValue;

function Probe() {
  const value = useSession();
  useEffect(() => {
    session = value;
  }, [value]);
  return <Text>{value.status}</Text>;
}

const expired = () => errorResponse(401, 'invalid_token', 'The access token is invalid or has expired');

/** The real session provider around a screen, signed in as the fixture user. */
async function open(ui: ReactElement, routes: Record<string, unknown>) {
  const { fetchMock, sent } = installFetch();
  const serve = (extra: Record<string, unknown> = {}) =>
    serveRoutes(fetchMock, {
      'POST /v1/auth/login': auth,
      'GET /v1/notifications/unread-count': expired,
      'GET /v1/community/profile': myProfile,
      ...routes,
      ...extra,
    });
  serve();
  await render(
    <WithFlags flags={flagsCommunityOn}>
      <SessionProvider>
        <Probe />
        {ui}
      </SessionProvider>
    </WithFlags>,
  );
  expect(await screen.findByText('signedOut')).toBeOnTheScreen();
  await act(() => session.logIn('sam@example.test', 'correct horse battery'));
  return { sent, serve };
}

/** The API rejects the token on a request the person did not make, then the same person logs in again. */
async function expireAndLogInAgain() {
  await act(async () => {
    await getUnreadCount().catch(() => {});
  });
  expect(await screen.findByText('signedOut')).toBeOnTheScreen();
  await act(() => session.logIn('sam@example.test', 'correct horse battery'));
}

beforeEach(async () => {
  await clearSession();
  setAuthToken(null);
});

describe('form input when the session ends', () => {
  it('comes back on a game: the bet to track, the alert and the pick', async () => {
    const detail = { ...liveEvent, ...upcomingEvent, available_markets: ['moneyline'], league_name: 'NFL', has_draw: false, players: [], as_of: moneyline.as_of, data_mode: 'synthetic' };
    await open(<GameDetailScreen eventId="evt_2" />, {
      'GET /v1/events/evt_2': detail,
      'GET /v1/events/evt_2/odds?market=moneyline': moneyline,
      'GET /v1/watchlist': { items: [] },
    });
    await fireEvent.changeText(await screen.findByLabelText('Stake ($)'), '40');
    await fireEvent.changeText(await screen.findByLabelText('Your reasoning (optional)'), 'The line moved half a point since open.');
    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '+175');

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Stake ($)')).toHaveDisplayValue('40');
    expect(await screen.findByLabelText('Your reasoning (optional)')).toHaveDisplayValue('The line moved half a point since open.');
    expect(screen.getByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+175');
    expect(screen.getAllByText(DRAFT_KEPT)).toHaveLength(3);
  });

  it('says nothing was kept on a game where nothing was typed', async () => {
    const detail = { ...liveEvent, ...upcomingEvent, available_markets: ['moneyline'], league_name: 'NFL', has_draw: false, players: [], as_of: moneyline.as_of, data_mode: 'synthetic' };
    await open(<GameDetailScreen eventId="evt_2" />, {
      'GET /v1/events/evt_2': detail,
      'GET /v1/events/evt_2/odds?market=moneyline': moneyline,
      'GET /v1/watchlist': { items: [] },
    });
    expect(await screen.findByLabelText('Stake ($)')).toBeOnTheScreen();

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Stake ($)')).toHaveDisplayValue('');
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();
  });

  it('comes back on a pick: the comment and an open report', async () => {
    await open(<CommunityPickScreen pickId={upcomingPick.id} />, {
      [`GET /v1/community/picks/${upcomingPick.id}`]: upcomingPick,
      [`GET /v1/community/picks/${upcomingPick.id}/comments?limit=20`]: { items: [], next_before: null },
    });
    await fireEvent.changeText(await screen.findByLabelText('Add a comment'), 'Which book had that number?');
    await fireEvent.press(screen.getByRole('button', { name: `Report this pick by ${upcomingPick.author.handle}` }));
    await fireEvent.press(screen.getByRole('radio', { name: /Misleading claims$/ }));
    await fireEvent.changeText(screen.getByLabelText('Details (optional)'), 'Claims a record it does not have.');

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Add a comment')).toHaveDisplayValue('Which book had that number?');
    expect(screen.getByLabelText('Details (optional)')).toHaveDisplayValue('Claims a record it does not have.');
    expect(screen.getByRole('radio', { name: /Misleading claims$/ })).toBeChecked();
  });

  it('comes back on the community profile form', async () => {
    await open(<CommunityProfileEditScreen />, {});
    await fireEvent.changeText(await screen.findByLabelText('Handle'), 'sam_reads_totals');
    await fireEvent.changeText(screen.getByLabelText('Bio (optional)'), 'Totals only.');
    await fireEvent.press(screen.getByRole('switch', { name: 'Make my profile public' }));

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Handle')).toHaveDisplayValue('sam_reads_totals');
    expect(screen.getByLabelText('Bio (optional)')).toHaveDisplayValue('Totals only.');
    expect(screen.getByRole('switch', { name: 'Make my profile public' })).not.toBeChecked();
    expect(screen.getByText(DRAFT_KEPT)).toBeOnTheScreen();
  });

  it('comes back only in the profile form it was typed in when two are in the stack', async () => {
    // The community's first screen with the profile screen opened over it: both hold the form.
    const stack = (
      <>
        <ProfileForm draft="community-setup-profile" />
        <ProfileForm />
      </>
    );
    const first = await render(stack);
    await fireEvent.changeText(screen.getAllByLabelText('Handle')[1], 'sam_reads_totals');
    holdDrafts();
    await first.unmount();
    releaseDrafts();

    await render(stack);
    expect(screen.getAllByLabelText('Handle')[0]).toHaveDisplayValue('');
    expect(screen.getAllByLabelText('Handle')[1]).toHaveDisplayValue('sam_reads_totals');
    expect(screen.getAllByText(DRAFT_KEPT)).toHaveLength(1);
  });

  it('comes back on the tracker: a bet being edited or settled, but not a delete confirmation', async () => {
    const totals = { settled_count: 0, pending_count: 1, pending_exposure: 25, staked: 0, profit: 0, roi: null, wins: 0, losses: 0, pushes: 0, avg_clv: null, clv_sample: 0 };
    const routes = {
      'GET /v1/bets/summary': { totals, by_sport: [], by_market: [], by_sportsbook: [], by_bet_type: [], timeline: [], note: '' },
      'GET /v1/bets?status=pending&limit=1000': [openBet],
      'GET /v1/bets?status=settled&limit=50&offset=0': [],
      'GET /v1/leagues': [{ key: 'nfl', name: 'NFL' }],
      'GET /v1/sync/providers': [],
      'GET /v1/sync/connections': [],
      'GET /v1/me/stake-reminder': { weekly_stake_threshold: null, staked_this_week: 25, week_start: '2026-11-16T00:00:00Z', exceeded: false },
    };
    await open(<TrackerScreen />, routes);
    await fireEvent.press(await screen.findByRole('button', { name: 'Edit Harbor City Gulls ML' }));
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '30');
    await fireEvent.changeText(screen.getByLabelText('Notes'), 'Limit was cut after this one.');

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Notes')).toHaveDisplayValue('Limit was cut after this one.');
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('30');
    expect(screen.getByText(DRAFT_KEPT)).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete Harbor City Gulls ML' }));
    expect(screen.getByText('Delete this bet for good?')).toBeOnTheScreen();

    await expireAndLogInAgain();

    expect(await screen.findByRole('button', { name: 'Delete Harbor City Gulls ML' })).toBeOnTheScreen();
    expect(screen.queryByText('Delete this bet for good?')).toBeNull();
  });

  it('comes back in Settings for the staking reminder, and never for a password or the delete confirmation', async () => {
    await open(<SettingsScreen />, {
      'GET /v1/me/notification-preferences': { in_app: {} },
      'GET /v1/me/stake-reminder': reminderExceeded,
      'GET /v1/me/entitlements': { plan: 'free', preview: true, features: {} },
    });
    await fireEvent.changeText(await screen.findByLabelText('Weekly amount ($)'), '150');
    await fireEvent.changeText(screen.getByLabelText('Current password'), 'correct horse battery');
    await fireEvent.changeText(screen.getByLabelText('New password'), 'another long password');
    await fireEvent.changeText(screen.getByLabelText('Type DELETE to confirm'), 'DELETE');

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Weekly amount ($)')).toHaveDisplayValue('150');
    expect(screen.getByLabelText('Current password')).toHaveDisplayValue('');
    expect(screen.getByLabelText('New password')).toHaveDisplayValue('');
    expect(screen.getByLabelText('Type DELETE to confirm')).toHaveDisplayValue('');
  });
});

// A form that stays on screen after a successful save still differs from how it was first drawn. That is
// saved work, not unsaved input: a later sign-out must not bring it back, or say that nothing was saved.
describe('form input that was saved before the session ended', () => {
  const game = {
    'GET /v1/events/evt_2': { ...liveEvent, ...upcomingEvent, available_markets: ['moneyline'], league_name: 'NFL', has_draw: false, players: [], as_of: moneyline.as_of, data_mode: 'synthetic' },
    'GET /v1/events/evt_2/odds?market=moneyline': moneyline,
    'GET /v1/watchlist': { items: [] },
  };
  const count = (requests: { method: string; path: string }[], method: string, path: string) =>
    requests.filter((request) => request.method === method && request.path === path).length;

  it('is not brought back in Settings: a staking reminder that was saved, or turned off', async () => {
    const saved: StakeReminder = { ...reminderExceeded, weekly_stake_threshold: 150 };
    const off: StakeReminder = { ...reminderExceeded, weekly_stake_threshold: null, exceeded: false };
    const { sent, serve } = await open(<SettingsScreen />, {
      'GET /v1/me/notification-preferences': { in_app: {} },
      'GET /v1/me/stake-reminder': reminderExceeded,
      'PUT /v1/me/stake-reminder': saved,
      'GET /v1/me/entitlements': { plan: 'free', preview: true, features: {} },
    });
    await fireEvent.changeText(await screen.findByLabelText('Weekly amount ($)'), '150');
    await fireEvent.press(screen.getByRole('button', { name: 'Save reminder' }));
    expect(await screen.findByText('Reminder saved.')).toBeOnTheScreen();
    serve({ 'GET /v1/me/stake-reminder': saved, 'PUT /v1/me/stake-reminder': off });

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Weekly amount ($)')).toHaveDisplayValue('150');
    expect(screen.getByText('Your reminder is set at $150.00 a week.')).toBeOnTheScreen();
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();

    await fireEvent.press(screen.getByRole('button', { name: 'Turn off the reminder' }));
    expect(await screen.findByText('Reminder turned off.')).toBeOnTheScreen();
    serve({ 'GET /v1/me/stake-reminder': off });

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Weekly amount ($)')).toHaveDisplayValue('');
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();
    expect(count(sent(), 'PUT', '/v1/me/stake-reminder')).toBe(2);
  });

  it('is not brought back on a game: a saved alert, a tracked bet and a posted pick', async () => {
    // The spread market has two sides with a price, so a side other than the first can be chosen.
    const { sent } = await open(<GameDetailScreen eventId="evt_2" initialMarket="spread" />, {
      'GET /v1/events/evt_2': { ...game['GET /v1/events/evt_2'], available_markets: ['moneyline', 'spread'] },
      'GET /v1/events/evt_2/odds?market=spread': spread,
      'GET /v1/watchlist': { items: [] },
      'POST /v1/alerts': () => jsonResponse({}, 201),
      'POST /v1/bets': () => jsonResponse(openBet, 201),
      'POST /v1/community/picks': () => jsonResponse(upcomingPick, 201),
    });

    await fireEvent.changeText(await screen.findByLabelText('Price to reach (American odds)'), '+175');
    await fireEvent.press(screen.getByRole('button', { name: 'Save alert' }));
    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();

    // A side other than the first: the form keeps it after the save, so it differs from how it was drawn.
    await fireEvent.press(screen.getByRole('radio', { name: /^Side, at the best current price: Harbor City Gulls/ }));
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '40');
    await fireEvent.press(screen.getByRole('button', { name: 'Add to tracker' }));
    expect(await screen.findByText(/^Bet saved\./)).toBeOnTheScreen();

    await fireEvent.press(await screen.findByRole('radio', { name: /^Outcome, at the best current price: Harbor City Gulls/ }));
    await fireEvent.changeText(screen.getByLabelText('Your reasoning (optional)'), 'The line moved half a point since open.');
    await fireEvent.press(screen.getByRole('button', { name: 'Post pick' }));
    expect(await screen.findByRole('button', { name: 'Open your pick' })).toBeOnTheScreen();

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Price to reach (American odds)')).not.toHaveDisplayValue('+175');
    expect(screen.queryByText('Alert saved.')).toBeNull();
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
    expect(screen.getByRole('radio', { name: /^Side, at the best current price: Harbor City Gulls/ })).not.toBeChecked();
    expect(await screen.findByLabelText('Your reasoning (optional)')).toHaveDisplayValue('');
    expect(screen.getByRole('radio', { name: /^Outcome, at the best current price: Harbor City Gulls/ })).not.toBeChecked();
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();
    expect(count(sent(), 'POST', '/v1/alerts')).toBe(1);
    expect(count(sent(), 'POST', '/v1/bets')).toBe(1);
    expect(count(sent(), 'POST', '/v1/community/picks')).toBe(1);
  });

  it('still keeps what is typed after a save and not saved itself', async () => {
    await open(<GameDetailScreen eventId="evt_2" />, { ...game, 'POST /v1/alerts': () => jsonResponse({}, 201) });
    await fireEvent.changeText(await screen.findByLabelText('Price to reach (American odds)'), '+175');
    await fireEvent.press(screen.getByRole('button', { name: 'Save alert' }));
    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '+200');

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+200');
    expect(screen.getByText(DRAFT_KEPT)).toBeOnTheScreen();
  });

  it('keeps a typed price when only a team alert, which sends none of the fields, was saved', async () => {
    const { sent } = await open(<GameDetailScreen eventId="evt_2" />, { ...game, 'POST /v1/alerts': () => jsonResponse({}, 201) });
    await fireEvent.changeText(await screen.findByLabelText('Price to reach (American odds)'), '+175');
    await fireEvent.press(screen.getByRole('button', { name: "Alert me before Harbor City Gulls's games" }));
    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent().find((request) => request.path === '/v1/alerts')?.body).toEqual({ kind: 'game_start', team_id: upcomingEvent.home_team.id, minutes_before: 60 });

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+175');
    expect(screen.getByText(DRAFT_KEPT)).toBeOnTheScreen();
  });

  it('is not brought back on the community profile form', async () => {
    const changed = { ...myProfile, bio: 'Totals only.' };
    const { sent, serve } = await open(<CommunityProfileEditScreen />, { 'PUT /v1/community/profile': changed });
    await fireEvent.changeText(await screen.findByLabelText('Bio (optional)'), 'Totals only.');
    await fireEvent.press(screen.getByRole('button', { name: 'Save profile' }));
    expect(await screen.findByText('Profile saved.')).toBeOnTheScreen();
    serve({ 'GET /v1/community/profile': changed });

    await expireAndLogInAgain();

    expect(await screen.findByLabelText('Bio (optional)')).toHaveDisplayValue('Totals only.');
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();
    expect(count(sent(), 'PUT', '/v1/community/profile')).toBe(1);
  });

  it('is not brought back on a pick: a posted comment and a sent report', async () => {
    const comment = { id: 'cmt_9', body: 'Which book had that number?', created_at: '2026-11-19T12:00:00Z', author: upcomingPick.author, is_mine: true };
    await open(<CommunityPickScreen pickId={upcomingPick.id} />, {
      [`GET /v1/community/picks/${upcomingPick.id}`]: upcomingPick,
      [`GET /v1/community/picks/${upcomingPick.id}/comments?limit=20`]: { items: [], next_before: null },
      [`POST /v1/community/picks/${upcomingPick.id}/comments`]: () => jsonResponse(comment, 201),
      'POST /v1/community/reports': () => jsonResponse({}, 201),
    });
    const report = `Report this pick by ${upcomingPick.author.handle}`;
    await fireEvent.changeText(await screen.findByLabelText('Add a comment'), 'Which book had that number?');
    await fireEvent.press(screen.getByRole('button', { name: 'Post comment' }));
    await waitFor(() => expect(screen.getByLabelText('Add a comment')).toHaveDisplayValue(''));
    await fireEvent.press(screen.getByRole('button', { name: report }));
    await fireEvent.press(screen.getByRole('radio', { name: /Misleading claims$/ }));
    await fireEvent.press(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByText(REPORT_SENT)).toBeOnTheScreen();

    await expireAndLogInAgain();

    // The report control is drawn afresh: closed, and with nothing chosen when it is opened.
    await fireEvent.press(await screen.findByRole('button', { name: report }));
    expect(screen.getByRole('radio', { name: /Misleading claims$/ })).not.toBeChecked();
    expect(screen.getByLabelText('Add a comment')).toHaveDisplayValue('');
    expect(screen.queryByText(DRAFT_KEPT)).toBeNull();
  });
});
