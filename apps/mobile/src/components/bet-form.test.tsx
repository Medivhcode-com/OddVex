import { act, fireEvent, render, screen } from '@testing-library/react-native';

import { BET_SAVE_UNCONFIRMED, setAuthToken } from '@/api/client';
import { BetForm, buildBetPayload, emptyLeg, type BetDraft } from '@/components/bet-form';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { openBet } from '@/test/fixtures';
import { onPressOf } from '@/test/press';
import { CLIENT_REQUEST_ID } from '@/utils/request-id';

const leagues = [
  { key: 'nfl', name: 'NFL' },
  { key: 'nba', name: 'NBA' },
];
const books = ['Northstar Sports', 'Cedar Book'];

const draft = (overrides: Partial<BetDraft> = {}): BetDraft => ({
  betType: 'straight',
  format: 'american',
  league: 'nfl',
  sportsbook: 'Northstar Sports',
  stake: '25',
  legs: [{ ...emptyLeg(), selection: 'Harbor City Gulls ML', odds: '−110' }],
  ...overrides,
});

beforeEach(() => setAuthToken('token-1'));
afterEach(() => setAuthToken(null));

describe('buildBetPayload', () => {
  it.each([
    [{ stake: '' }, 'Enter a stake greater than zero.'],
    [{ stake: '0' }, 'Enter a stake greater than zero.'],
    [{ stake: 'ten' }, 'Enter a stake greater than zero.'],
    [{ stake: '0.004' }, 'Enter a stake of at least $0.01.'],
    [{ stake: '0.009' }, 'Enter a stake of at least $0.01.'],
    [{ sportsbook: '  ' }, 'Enter the sportsbook.'],
    [{ betType: 'parlay' as const }, 'A parlay needs at least two legs.'],
    [{ legs: [{ ...emptyLeg(), selection: 'Gulls ML' }] }, 'Each leg needs a selection and odds.'],
    [{ legs: [{ ...emptyLeg(), odds: '-110' }] }, 'Each leg needs a selection and odds.'],
  ])('rejects %j', (overrides, message) => {
    expect(buildBetPayload(draft(overrides))).toEqual({ error: message });
  });

  it('accepts the smallest stake the tracker can store', () => {
    expect(buildBetPayload(draft({ stake: '0.01' }))).toMatchObject({ body: { stake: 0.01 } });
  });

  it('builds a straight bet, sending the odds as typed with a plain minus sign', () => {
    expect(buildBetPayload(draft())).toEqual({
      body: {
        bet_type: 'straight',
        stake: 25,
        sportsbook: 'Northstar Sports',
        legs: [
          {
            selection: 'Harbor City Gulls ML',
            market: 'moneyline',
            league: 'nfl',
            event_label: null,
            odds: '-110',
            odds_format: 'american',
            closing_odds: null,
          },
        ],
      },
    });
  });

  it('ignores extra legs on a straight bet and sends no league for "Other"', () => {
    const built = buildBetPayload(draft({ league: 'other', legs: [draft().legs[0], { ...emptyLeg(), selection: 'Left over', odds: '2.0' }] }));
    expect(built).toMatchObject({ body: { legs: [{ selection: 'Harbor City Gulls ML', league: null }] } });
    expect('body' in built && built.body.legs).toHaveLength(1);
  });

  it('builds a parlay with every leg, the chosen format and optional closing odds', () => {
    const built = buildBetPayload(
      draft({
        betType: 'parlay',
        format: 'decimal',
        stake: '10.50',
        legs: [
          { selection: ' Gulls ML ', market: 'moneyline', odds: '1.91', closing_odds: '1.87', event_label: 'Forge at Gulls' },
          { selection: 'Over 44.5', market: 'total', odds: '2.05', closing_odds: '', event_label: '' },
        ],
      }),
    );
    expect(built).toEqual({
      body: {
        bet_type: 'parlay',
        stake: 10.5,
        sportsbook: 'Northstar Sports',
        legs: [
          { selection: 'Gulls ML', market: 'moneyline', league: 'nfl', event_label: 'Forge at Gulls', odds: '1.91', odds_format: 'decimal', closing_odds: '1.87' },
          { selection: 'Over 44.5', market: 'total', league: 'nfl', event_label: null, odds: '2.05', odds_format: 'decimal', closing_odds: null },
        ],
      },
    });
  });
});

describe('BetForm', () => {
  it('shows what is missing and sends nothing', async () => {
    const { fetchMock } = installFetch();
    const onSaved = jest.fn();
    await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={onSaved} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));

    expect(screen.getByText('Enter a stake greater than zero.')).toBeOnTheScreen();
    expect(screen.getByRole('alert')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('saves a straight bet with the bearer token and confirms it', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
    const onSaved = jest.fn();
    await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={onSaved} />);

    await fireEvent.changeText(screen.getByLabelText('Pick'), 'Harbor City Gulls ML');
    await fireEvent.changeText(screen.getByLabelText('Odds'), '+150');
    await fireEvent.changeText(screen.getByLabelText('Closing odds'), '+135');
    await fireEvent.press(screen.getByRole('button', { name: 'Use Cedar Book as the sportsbook' }));
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '25');
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));

    expect(await screen.findByText('Bet saved. It is in your open bets.')).toBeOnTheScreen();
    expect(sent()).toHaveLength(1);
    expect(sent()[0]).toMatchObject({
      method: 'POST',
      path: '/v1/bets',
      body: {
        bet_type: 'straight',
        stake: 25,
        sportsbook: 'Cedar Book',
        legs: [{ selection: 'Harbor City Gulls ML', market: 'moneyline', league: 'nfl', odds: '+150', odds_format: 'american', closing_odds: '+135' }],
      },
    });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
  });

  it('adds and removes parlay legs and sends the ones that are left', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
    await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

    await fireEvent.press(screen.getByRole('radio', { name: 'Bet type: Parlay' }));
    expect(screen.getByLabelText('Leg 2 pick')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Remove leg 1' })).toBeNull();

    await fireEvent.press(screen.getByRole('button', { name: 'Add a leg' }));
    await fireEvent.changeText(screen.getByLabelText('Leg 1 pick'), 'Gulls ML');
    await fireEvent.changeText(screen.getByLabelText('Leg 1 odds'), '10/11');
    await fireEvent.changeText(screen.getByLabelText('Leg 2 pick'), 'Dropped leg');
    await fireEvent.changeText(screen.getByLabelText('Leg 2 odds'), '1/1');
    await fireEvent.changeText(screen.getByLabelText('Leg 3 pick'), 'Over 44.5');
    await fireEvent.changeText(screen.getByLabelText('Leg 3 odds'), '6/5');
    await fireEvent.press(screen.getByRole('radio', { name: 'Leg 3 market: Total' }));
    await fireEvent.press(screen.getByRole('radio', { name: 'Odds format: Fractional' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Remove leg 2' }));
    expect(screen.queryByLabelText('Leg 3 pick')).toBeNull();

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '10');
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    await screen.findByText('Bet saved. It is in your open bets.');

    expect(sent()[0].body).toMatchObject({
      bet_type: 'parlay',
      stake: 10,
      legs: [
        { selection: 'Gulls ML', market: 'moneyline', odds: '10/11', odds_format: 'fractional' },
        { selection: 'Over 44.5', market: 'total', odds: '6/5', odds_format: 'fractional' },
      ],
    });
  });

  it("shows the API's message when it rejects the bet", async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(422, 'invalid_odds', 'American odds cannot be between -100 and 100.'));
    const onSaved = jest.fn();
    await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={onSaved} />);

    await fireEvent.changeText(screen.getByLabelText('Pick'), 'Gulls ML');
    await fireEvent.changeText(screen.getByLabelText('Odds'), '50');
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '25');
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));

    expect(await screen.findByText('American odds cannot be between -100 and 100.')).toBeOnTheScreen();
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('25');
  });
  describe('saving again after a failure', () => {
    const fill = async (stake = '25') => {
      await fireEvent.changeText(screen.getByLabelText('Pick'), 'Harbor City Gulls ML');
      await fireEvent.changeText(screen.getByLabelText('Odds'), '+150');
      await fireEvent.changeText(screen.getByLabelText('Stake ($)'), stake);
    };
    const save = () => fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    const ids = (sent: () => { body: unknown }[]) => sent().map((request) => (request.body as { client_request_id?: string }).client_request_id);

    it('sends the same id again when the unchanged form is retried after no answer, and takes 200 as saved', async () => {
      const { fetchMock, sent } = installFetch();
      fetchMock.mockRejectedValueOnce(new TypeError('Network request failed')).mockResolvedValueOnce(jsonResponse(openBet, 200));
      const onSaved = jest.fn();
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={onSaved} />);

      await fill();
      await save();
      expect(await screen.findByText(BET_SAVE_UNCONFIRMED)).toBeOnTheScreen();
      expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('25');
      expect(onSaved).not.toHaveBeenCalled();

      await save();
      expect(await screen.findByText('Bet saved. It is in your open bets.')).toBeOnTheScreen();
      const [first, second] = ids(sent);
      expect(first).toMatch(CLIENT_REQUEST_ID);
      expect(second).toBe(first);
      expect(onSaved).toHaveBeenCalledTimes(1);
      expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
    });

    it('uses a new id once the form is edited after a failure', async () => {
      const { fetchMock, sent } = installFetch();
      fetchMock.mockRejectedValueOnce(new TypeError('Network request failed')).mockResolvedValueOnce(jsonResponse(openBet, 201));
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

      await fill();
      await save();
      await screen.findByText(BET_SAVE_UNCONFIRMED);
      await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '30');
      await save();
      await screen.findByText('Bet saved. It is in your open bets.');

      const [first, second] = ids(sent);
      expect(second).toMatch(CLIENT_REQUEST_ID);
      expect(second).not.toBe(first);
    });

    it('sends one id for two presses in the same frame', async () => {
      const { fetchMock, sent } = installFetch();
      fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

      await fill();
      const press = onPressOf(screen.getByRole('button', { name: 'Save bet' }));
      await act(async () => {
        // Both presses run before React renders the disabled button.
        press();
        press();
      });
      await screen.findByText('Bet saved. It is in your open bets.');

      const [first, second] = ids(sent);
      expect(first).toMatch(CLIENT_REQUEST_ID);
      expect(second).toBe(first);
    });

    it('gives the next bet its own id after a save', async () => {
      const { fetchMock, sent } = installFetch();
      fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

      await fill();
      await save();
      await screen.findByText('Bet saved. It is in your open bets.');
      await fill();
      await save();

      const [first, second] = ids(sent);
      expect(first).toMatch(CLIENT_REQUEST_ID);
      expect(second).toMatch(CLIENT_REQUEST_ID);
      expect(second).not.toBe(first);
    });

    it("shows the API's words when the account holds the most bets it can, or the write limit is reached", async () => {
      const { fetchMock } = installFetch();
      fetchMock
        .mockResolvedValueOnce(errorResponse(409, 'bet_limit_reached', 'An account holds at most 5000 bets. Delete some to add another.', { max_bets: 5000 }))
        .mockResolvedValueOnce(errorResponse(429, 'rate_limited', 'Too many requests. Try again in 12 seconds.'));
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

      await fill();
      await save();
      expect(await screen.findByText('An account holds at most 5000 bets. Delete some to add another.')).toBeOnTheScreen();
      await save();
      expect(await screen.findByText('Too many requests. Try again in 12 seconds.')).toBeOnTheScreen();
    });

    it('refuses a stake under one cent and sends nothing', async () => {
      const { fetchMock } = installFetch();
      await render(<BetForm leagues={leagues} sportsbooks={books} onSaved={() => {}} />);

      await fill('0.004');
      await save();

      expect(screen.getByText('Enter a stake of at least $0.01.')).toBeOnTheScreen();
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});
