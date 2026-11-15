import type {
  AlertRule,
  AuthResponse,
  Bet,
  BetLeg,
  BookRow,
  EventSummary,
  GameLogEntry,
  Notification,
  OddsComparison,
  Outcome,
  PriceT,
  PropAnalysis,
  StakeReminder,
  User,
} from '@/api/types';

/** Test data only. Every team and sportsbook here is fictional, like the API's synthetic mode. */
export function price(american: number, decimal: number, implied_probability: number): PriceT {
  return { american, decimal, fractional: '', implied_probability };
}

export function outcome(key: string, name: string, p: PriceT, extra: Partial<Outcome> = {}): Outcome {
  return { key, name, price: p, is_best: false, ...extra };
}

export const liveEvent: EventSummary = {
  id: 'evt_1',
  league: 'nfl',
  home_team: { id: 't_home', name: 'Harbor City Gulls', abbreviation: 'HCG' },
  away_team: { id: 't_away', name: 'Iron Valley Forge', abbreviation: 'IVF' },
  start_time: '2026-11-15T18:00:00Z',
  status: 'live',
  status_detail: 'Q3 4:12',
  score: { home: 17, away: 14 },
  best_moneyline: {
    home: { price: price(-135, 1.74, 0.5745), sportsbook: { key: 'book_a', name: 'Northstar Sports' } },
    away: { price: price(118, 2.18, 0.4587), sportsbook: { key: 'book_c', name: 'Cedar Book' } },
  },
};

export const openBook: BookRow = {
  sportsbook: { key: 'book_a', name: 'Northstar Sports' },
  status: 'open',
  last_updated: '2026-11-15T19:59:18Z',
  is_stale: false,
  outcomes: [
    outcome('away', 'Iron Valley Forge', price(118, 2.18, 0.4587), { is_best: true }),
    outcome('home', 'Harbor City Gulls', price(-140, 1.71, 0.5833)),
  ],
};

export const staleBook: BookRow = {
  sportsbook: { key: 'book_b', name: 'Beacon Bets' },
  status: 'open',
  last_updated: '2026-11-15T19:51:00Z',
  is_stale: true,
  outcomes: [
    outcome('away', 'Iron Valley Forge', price(125, 2.25, 0.4444)),
    outcome('home', 'Harbor City Gulls', price(-150, 1.67, 0.6)),
  ],
};

export const suspendedBook: BookRow = {
  sportsbook: { key: 'book_c', name: 'Cedar Book' },
  status: 'suspended',
  last_updated: '2026-11-15T19:58:00Z',
  is_stale: false,
  outcomes: [],
};

export const unavailableBook: BookRow = {
  sportsbook: { key: 'book_d', name: 'Delta Lines' },
  status: 'unavailable',
  last_updated: null,
  is_stale: false,
  outcomes: [],
};

/** 2026-11-15T20:00:00Z: 42 seconds after `openBook`, 9 minutes after `staleBook`. */
export const now = new Date('2026-11-15T20:00:00Z');

export const columns = [
  { key: 'away', name: 'Iron Valley Forge' },
  { key: 'home', name: 'Harbor City Gulls' },
];

export const moneyline: OddsComparison = {
  event: liveEvent,
  market: 'moneyline',
  data_mode: 'synthetic',
  stale_after_seconds: 300,
  as_of: '2026-11-15T19:59:30Z',
  books: [openBook, staleBook, suspendedBook, unavailableBook],
  consensus: {
    outcomes: [
      { key: 'away', name: 'Iron Valley Forge', no_vig_probability: 0.4402 },
      { key: 'home', name: 'Harbor City Gulls', no_vig_probability: 0.5598 },
    ],
    books_used: 1,
  },
  holds: [
    { sportsbook_key: 'book_a', hold: 0.042 },
    { sportsbook_key: 'book_b', hold: 0.0444 },
  ],
  best: [{ outcome_key: 'away', sportsbook_key: 'book_a', price: price(118, 2.18, 0.4587) }],
};

export const user: User = {
  id: 'usr_1',
  email: 'sam@example.test',
  display_name: 'Sam',
  role: 'user',
  created_at: '2026-11-01T00:00:00Z',
  age_confirmed_at: '2026-11-01T00:00:00Z',
};

export const auth: AuthResponse = { access_token: 'token-1', token_type: 'bearer', expires_in: 3600, user };

function leg(id: string, selection: string, extra: Partial<BetLeg> = {}): BetLeg {
  return { id, position: 0, selection, market: 'moneyline', league: 'nfl', price: price(-110, 1.91, 0.5238), gradeable: false, ...extra };
}

export const openBet: Bet = {
  id: 'bet_1',
  bet_type: 'straight',
  status: 'pending',
  source: 'manual',
  sport: 'nfl',
  sportsbook: 'Northstar Sports',
  stake: 25,
  combined_decimal_odds: 1.91,
  combined_price: price(-110, 1.91, 0.5238),
  odds_source: 'legs',
  potential_payout: 47.73,
  potential_profit: 22.73,
  placed_at: '2026-11-14T18:00:00Z',
  created_at: '2026-11-14T18:00:00Z',
  updated_at: '2026-11-14T18:00:00Z',
  legs: [leg('leg_1', 'Harbor City Gulls ML', { event_label: 'Forge at Gulls' })],
};

export const parlayBet: Bet = {
  ...openBet,
  id: 'bet_2',
  bet_type: 'parlay',
  combined_decimal_odds: 3.64,
  combined_price: price(264, 3.64, 0.2747),
  potential_payout: 91,
  legs: [leg('leg_a', 'Harbor City Gulls ML'), leg('leg_b', 'Iron Valley Forge +3.5', { position: 1, market: 'spread' })],
};

export const wonBet: Bet = {
  ...openBet,
  id: 'bet_3',
  status: 'settled',
  result: 'won',
  profit: 22.73,
  payout: 47.73,
  clv: 0.0125,
  settled_by: 'auto',
  settled_at: '2026-11-15T01:00:00Z',
};

export const lostSyncedBet: Bet = { ...openBet, id: 'bet_4', status: 'settled', result: 'lost', profit: -25, payout: 0, source: 'sync' };

const forge = { id: 't_away', name: 'Iron Valley Forge', abbreviation: 'IVF' };

function game(date: string, value: number, result: GameLogEntry['result'], is_home: boolean): GameLogEntry {
  return { date, event_id: `evt_${date}`, value, result, is_home, opponent: forge };
}

export const propAnalysis: PropAnalysis = {
  player: {
    id: 'plr_1',
    name: 'Corwin Ashdown',
    league: 'nba',
    position: 'C',
    jersey_number: 11,
    prop_markets: ['points', 'rebounds'],
    team: { id: 't_home', name: 'Harbor City Gulls', abbreviation: 'HCG' },
  },
  market: 'points',
  available_markets: ['points', 'rebounds'],
  window: '10',
  split: 'all',
  consensus_line: 22.5,
  data_mode: 'synthetic',
  as_of: '2026-11-15T19:59:30Z',
  caveat: 'Hit rate describes past games only. It is not a probability for the next one.',
  hit_rate: { line: 22.5, line_source: 'consensus', sample_size: 4, over_count: 2, under_count: 2, pushes: 1, rate: 0.5, ci_low: 0.15, ci_high: 0.85 },
  averages: { window: 23.4, season: 21.9, home: 22.6, away: 21.1 },
  game_log: [
    game('2026-11-10', 28, 'over', true),
    game('2026-11-08', 19, 'under', false),
    game('2026-11-06', 22.5, 'push', true),
    game('2026-11-04', 25, 'over', false),
    game('2026-11-02', 17, 'under', true),
  ],
  offers: [
    {
      sportsbook: { key: 'book_a', name: 'Northstar Sports' },
      status: 'open',
      line: 22.5,
      last_updated: '2026-11-15T19:59:18Z',
      is_stale: false,
      over: price(-105, 1.95, 0.5122),
      under: price(-115, 1.87, 0.5349),
      is_best_over: true,
      is_best_under: false,
    },
    {
      sportsbook: { key: 'book_b', name: 'Beacon Bets' },
      status: 'open',
      line: 23.5,
      last_updated: '2026-11-15T19:51:00Z',
      is_stale: true,
      over: price(110, 2.1, 0.4762),
      under: null,
      is_best_over: false,
      is_best_under: false,
    },
    { sportsbook: { key: 'book_c', name: 'Cedar Book' }, status: 'suspended', is_stale: false, is_best_over: false, is_best_under: false },
    { sportsbook: { key: 'book_d', name: 'Delta Lines' }, status: 'unavailable', is_stale: false, is_best_over: false, is_best_under: false },
  ],
};

export const upcomingEvent: EventSummary = { ...liveEvent, id: 'evt_2', status: 'upcoming', status_detail: null, score: null, start_time: '2026-11-16T18:00:00Z' };

/** The spread on `upcomingEvent`: Gulls −3.5 best at Northstar, Forge +3.5 best at Beacon. */
export const spread: OddsComparison = {
  ...moneyline,
  event: upcomingEvent,
  market: 'spread',
  books: [
    {
      ...openBook,
      outcomes: [
        outcome('away', 'Iron Valley Forge', price(-112, 1.89, 0.5283), { line: 3.5 }),
        outcome('home', 'Harbor City Gulls', price(-108, 1.93, 0.5192), { line: -3.5, is_best: true }),
      ],
    },
    {
      ...staleBook,
      is_stale: false,
      outcomes: [
        outcome('away', 'Iron Valley Forge', price(-105, 1.95, 0.5122), { line: 3.5, is_best: true }),
        outcome('home', 'Harbor City Gulls', price(-115, 1.87, 0.5349), { line: -3.5 }),
      ],
    },
  ],
  best: [
    { outcome_key: 'away', sportsbook_key: 'book_b', price: price(-105, 1.95, 0.5122), line: 3.5 },
    { outcome_key: 'home', sportsbook_key: 'book_a', price: price(-108, 1.93, 0.5192), line: -3.5 },
  ],
};

function notification(id: string, kind: Notification['kind'], title: string, body: string, extra: Partial<Notification> = {}): Notification {
  return { id, kind, title, body, data: {}, created_at: '2026-11-15T19:54:00Z', read_at: null, ...extra };
}

export const priceNotification = notification(
  'ntf_1',
  'price_alert',
  'Price reached +120',
  'Iron Valley Forge spread +3.5 is +120 at Cedar Book, at or above your +115 alert.',
  { href: '/app/games/evt_2?market=spread' },
);
export const finalNotification = notification('ntf_2', 'game_final', 'Final: IVF 14, HCG 17', 'Final score: Iron Valley Forge 14, Harbor City Gulls 17.', {
  href: '/app/games/evt_1',
  read_at: '2026-11-15T19:00:00Z',
});
export const stakeNotification = notification(
  'ntf_3',
  'stake_reminder',
  'Weekly staking reminder',
  'You have staked $250.00 this week, at or above the $200.00 reminder you set.',
  { href: '/terms' },
);
export const settledNotification = notification('ntf_4', 'bet_settled', 'Bet settled: won', 'Harbor City Gulls ML settled as won from the final score.', {
  href: '/app/tracker',
});

function rule(id: string, state: AlertRule['state'], summary: string, extra: Partial<AlertRule> = {}): AlertRule {
  return {
    id,
    kind: 'price_at_least',
    state,
    summary,
    label: 'Iron Valley Forge at Harbor City Gulls',
    event_id: 'evt_2',
    market: 'moneyline',
    available: true,
    created_at: '2026-11-15T18:00:00Z',
    updated_at: '2026-11-15T18:00:00Z',
    ...extra,
  };
}

export const activeRule = rule('alr_1', 'active', 'Iron Valley Forge moneyline at +130 or higher');
export const triggeredRule = rule('alr_2', 'triggered', 'Harbor City Gulls moneyline at -120 or higher');
export const pausedRule = rule('alr_3', 'paused', 'Each Harbor City Gulls game, 60 minutes before the start', {
  kind: 'game_start',
  event_id: null,
  team_id: 't_home',
  market: null,
  label: 'Harbor City Gulls',
});
export const expiredRule = rule('alr_4', 'expired', 'Iron Valley Forge at Harbor City Gulls spread line moves 1 point or more from 3.5', {
  kind: 'line_move',
  market: 'spread',
  available: false,
});

export const reminderOff: StakeReminder = { weekly_stake_threshold: null, staked_this_week: 190, week_start: '2026-11-09T00:00:00Z', exceeded: false };
export const reminderExceeded: StakeReminder = { weekly_stake_threshold: 200, staked_this_week: 250, week_start: '2026-11-09T00:00:00Z', exceeded: true };
