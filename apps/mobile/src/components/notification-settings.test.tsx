import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import type { NotificationPreferences } from '@/api/types';
import { NotificationPreferencesForm, StakeReminderForm, StakeReminderNotice } from '@/components/notification-settings';
import { errorResponse, installFetch, serveRoutes } from '@/test/api';
import { reminderExceeded, reminderOff } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

const allOn: NotificationPreferences = {
  in_app: {
    price_alert: true,
    line_move: true,
    game_start: true,
    game_final: true,
    bet_settled: true,
    sync_finished: true,
    stake_reminder: true,
    new_follower: true,
    pick_comment: true,
    pick_graded: true,
  },
};
const PREFS = '/v1/me/notification-preferences';
const REMINDER = '/v1/me/stake-reminder';

async function show(ui: React.ReactElement, routes: Record<string, unknown>) {
  const { fetchMock, sent } = installFetch();
  serveRoutes(fetchMock, routes);
  const session = fakeSession();
  await render(<WithSession value={session}>{ui}</WithSession>);
  return { fetchMock, sent, session };
}

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('NotificationPreferencesForm', () => {
  it('shows a switch for every kind of notification', async () => {
    await show(<NotificationPreferencesForm userId="usr_1" />, { [`GET ${PREFS}`]: { in_app: { ...allOn.in_app, sync_finished: false } } });

    for (const label of ['Price alerts', 'Line moves', 'Game start', 'Final scores', 'Settled bets', 'Weekly staking reminder']) {
      expect(await screen.findByRole('switch', { name: label })).toBeChecked();
    }
    expect(screen.getByRole('switch', { name: 'Sync results' })).not.toBeChecked();
    await fireEvent.press(screen.getByRole('button', { name: 'Open notifications' }));
    expect(router.push).toHaveBeenCalledWith('/notifications');
  });

  it('has no community switches while the community flag is off', async () => {
    await show(<NotificationPreferencesForm userId="usr_1" />, { [`GET ${PREFS}`]: allOn });

    expect(await screen.findByRole('switch', { name: 'Price alerts' })).toBeOnTheScreen();
    expect(screen.getAllByRole('switch')).toHaveLength(7);
    for (const label of ['New followers', 'Comments on your picks', 'Graded picks']) expect(screen.queryByRole('switch', { name: label })).toBeNull();
  });

  it('adds the three community switches while the flag is on, and sends only the one that changed', async () => {
    const { sent } = await show(
      <WithFlags flags={{ community: true }}>
        <NotificationPreferencesForm userId="usr_1" />
      </WithFlags>,
      {
        // `null` is how the schema types a kind an older API might leave out: it means the default, on.
        [`GET ${PREFS}`]: { in_app: { ...allOn.in_app, new_follower: null, pick_graded: false } },
        [`PUT ${PREFS}`]: { in_app: { ...allOn.in_app, pick_comment: false, pick_graded: false } },
      },
    );

    expect(await screen.findByRole('switch', { name: 'New followers' })).toBeChecked();
    expect(screen.getByRole('switch', { name: 'Comments on your picks' })).toBeChecked();
    expect(screen.getByRole('switch', { name: 'Graded picks' })).not.toBeChecked();
    expect(screen.getAllByRole('switch')).toHaveLength(10);

    await fireEvent.press(screen.getByRole('switch', { name: 'Comments on your picks' }));
    await waitFor(() => expect(sent()).toHaveLength(2));
    expect(sent()[1]).toMatchObject({ method: 'PUT', path: PREFS });
    expect(sent()[1].body).toEqual({ in_app: { pick_comment: false } });
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Comments on your picks' })).not.toBeChecked());
  });

  it('sends only the kind that was switched', async () => {
    const { sent } = await show(<NotificationPreferencesForm userId="usr_1" />, {
      [`GET ${PREFS}`]: allOn,
      [`PUT ${PREFS}`]: { in_app: { ...allOn.in_app, price_alert: false } },
    });

    await fireEvent.press(await screen.findByRole('switch', { name: 'Price alerts' }));
    await waitFor(() => expect(sent()).toHaveLength(2));
    expect(sent()[1]).toMatchObject({ method: 'PUT', path: PREFS, body: { in_app: { price_alert: false } } });
    expect(sent()[1].body).toEqual({ in_app: { price_alert: false } });
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Price alerts' })).not.toBeChecked());
    expect(screen.getByRole('switch', { name: 'Line moves' })).toBeChecked();
  });

  it('switches a kind back on with true', async () => {
    const { sent } = await show(<NotificationPreferencesForm userId="usr_1" />, {
      [`GET ${PREFS}`]: { in_app: { ...allOn.in_app, bet_settled: false } },
      [`PUT ${PREFS}`]: allOn,
    });

    await fireEvent.press(await screen.findByRole('switch', { name: 'Settled bets' }));
    await waitFor(() => expect(sent()).toHaveLength(2));
    expect(sent()[1].body).toEqual({ in_app: { bet_settled: true } });
  });

  it('puts the switch back and says so when the change is not saved', async () => {
    await show(<NotificationPreferencesForm userId="usr_1" />, {
      [`GET ${PREFS}`]: allOn,
      [`PUT ${PREFS}`]: () => errorResponse(500, 'server_error', 'Something went wrong on our side.'),
    });

    await fireEvent.press(await screen.findByRole('switch', { name: 'Line moves' }));
    expect(await screen.findByText('Something went wrong on our side.')).toBeOnTheScreen();
    expect(screen.getByRole('switch', { name: 'Line moves' })).toBeChecked();
  });

  it('offers a retry when the settings do not load', async () => {
    const { fetchMock } = await show(<NotificationPreferencesForm userId="usr_1" />, {});

    expect(await screen.findByText("OddVex can't reach its data service, so your notification settings did not load.")).toBeOnTheScreen();
    serveRoutes(fetchMock, { [`GET ${PREFS}`]: allOn });
    await fireEvent.press(screen.getByRole('button', { name: 'Try loading notification settings again' }));
    expect(await screen.findByRole('switch', { name: 'Price alerts' })).toBeChecked();
  });
});

describe('StakeReminderForm', () => {
  it('shows this week and saves a weekly amount', async () => {
    const { sent, session } = await show(<StakeReminderForm userId="usr_1" />, {
      [`GET ${REMINDER}`]: reminderOff,
      [`PUT ${REMINDER}`]: { ...reminderOff, weekly_stake_threshold: 300 },
    });

    expect(await screen.findByText('You have staked $190.00 this week.')).toBeOnTheScreen();
    expect(screen.getByText('The reminder is off.')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Turn off the reminder' })).toBeNull();

    await fireEvent.changeText(screen.getByLabelText('Weekly amount ($)'), '300');
    await fireEvent.press(screen.getByRole('button', { name: 'Save reminder' }));

    expect(await screen.findByText('Reminder saved.')).toBeOnTheScreen();
    expect(sent()[1]).toMatchObject({ method: 'PUT', path: REMINDER });
    expect(sent()[1].body).toEqual({ weekly_stake_threshold: 300 });
    expect(screen.getByText('Your reminder is set at $300.00 a week.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Turn off the reminder' })).toBeOnTheScreen();
    expect(session.changed).toHaveBeenCalledWith('reminder');
  });

  it('asks for an amount above zero before sending anything', async () => {
    const { sent } = await show(<StakeReminderForm userId="usr_1" />, { [`GET ${REMINDER}`]: reminderOff });

    await fireEvent.press(await screen.findByRole('button', { name: 'Save reminder' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a weekly amount greater than zero.');
    await fireEvent.changeText(screen.getByLabelText('Weekly amount ($)'), '-5');
    await fireEvent.press(screen.getByRole('button', { name: 'Save reminder' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a weekly amount greater than zero.');
    expect(sent()).toHaveLength(1);
  });

  it('turns the reminder off with null', async () => {
    const { sent } = await show(<StakeReminderForm userId="usr_1" />, {
      [`GET ${REMINDER}`]: reminderExceeded,
      [`PUT ${REMINDER}`]: { ...reminderExceeded, weekly_stake_threshold: null, exceeded: false },
    });

    expect(await screen.findByLabelText('Weekly amount ($)')).toHaveDisplayValue('200');
    expect(screen.getByText('You have reached your weekly staking reminder')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Turn off the reminder' }));

    expect(await screen.findByText('Reminder turned off.')).toBeOnTheScreen();
    expect(sent()[1]).toMatchObject({ method: 'PUT', path: REMINDER });
    expect(sent()[1].body).toEqual({ weekly_stake_threshold: null });
    expect(screen.getByText('The reminder is off.')).toBeOnTheScreen();
    expect(screen.queryByText('You have reached your weekly staking reminder')).toBeNull();
    expect(screen.getByLabelText('Weekly amount ($)')).toHaveDisplayValue('');
  });
});

describe('StakeReminderNotice', () => {
  it('states both amounts, that nothing is blocked, and the helpline', async () => {
    await render(<StakeReminderNotice reminder={reminderExceeded} />);

    expect(screen.getByText('You have reached your weekly staking reminder')).toBeOnTheScreen();
    expect(
      screen.getByText(
        'You have staked $250.00 this week. Your reminder is set at $200.00. This is a reminder, not a limit: OddVex will not stop you logging bets. If betting is causing you stress, free, confidential help is available at 1-800-GAMBLER.',
      ),
    ).toBeOnTheScreen();
    // Supportive, not an alarm.
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows nothing below the amount or with the reminder off', async () => {
    await render(
      <>
        <StakeReminderNotice reminder={reminderOff} />
        <StakeReminderNotice reminder={{ ...reminderExceeded, staked_this_week: 150, exceeded: false }} />
      </>,
    );
    expect(screen.queryByText(/1-800-GAMBLER/)).toBeNull();
  });
});
