/**
 * Response shapes the mobile app consumes. Copied from apps/web/src/lib/types.ts, which mirrors the API's
 * response models, and checked by hand against services/api/openapi.json. The API sends more fields than
 * are listed here; only the ones this app reads are typed. Keep in step when the API schema changes.
 */
export type PriceT = { american: number; decimal: number; fractional: string; implied_probability: number };
export type Book = { key: string; name: string };
export type Team = { id: string; name: string; abbreviation: string };
export type EventStatus = 'live' | 'upcoming' | 'final';
export type BestSide = { price: PriceT; sportsbook: Book } | null;

export type EventSummary = {
  id: string;
  league: string;
  home_team: Team;
  away_team: Team;
  start_time: string;
  status: EventStatus;
  status_detail?: string | null;
  score?: { home: number; away: number } | null;
  best_moneyline?: { home?: BestSide; away?: BestSide; draw?: BestSide } | null;
};
export type EventDetail = EventSummary & { available_markets: string[]; league_name?: string; has_draw?: boolean };

export type Outcome = { key: string; name: string; line?: number | null; price: PriceT; is_best: boolean };
export type BookStatus = 'open' | 'suspended' | 'unavailable';
export type BookRow = {
  sportsbook: Book;
  status: BookStatus;
  last_updated?: string | null;
  is_stale: boolean;
  outcomes: Outcome[];
};
export type ConsensusOutcome = { key: string; name: string; no_vig_probability: number };
export type OddsComparison = {
  event: EventSummary;
  market: string;
  as_of: string;
  books: BookRow[];
  consensus: { outcomes: ConsensusOutcome[]; books_used: number };
  holds: { sportsbook_key: string; hold: number }[];
  best: { outcome_key: string; sportsbook_key: string; price: PriceT; line?: number | null }[];
};

export type Meta = { data_mode: string; provider: string; version: string; server_time: string; notice?: string };
export type League = { key: string; name: string };

export type Market = 'moneyline' | 'spread' | 'total';
export const MARKETS: readonly { value: Market; label: string }[] = [
  { value: 'moneyline', label: 'Moneyline' },
  { value: 'spread', label: 'Spread' },
  { value: 'total', label: 'Total' },
];
