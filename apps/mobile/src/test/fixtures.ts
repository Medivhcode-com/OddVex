import type { BookRow, EventSummary, OddsComparison, Outcome, PriceT } from '@/api/types';

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
