/**
 * Shapes the web app consumes. These mirror the API's response models.
 * `types-contract.ts` asserts at compile time that they stay assignable from the generated OpenAPI types.
 */
export type PriceT = { american: number; decimal: number; fractional: string; implied_probability: number };
export type Book = { key: string; name: string };
export type Team = { id: string; name: string; abbreviation: string };
export type EventStatus = "live" | "upcoming" | "final";
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
export type EventDetail = EventSummary & { available_markets: string[] };

export type Outcome = { key: string; name: string; line?: number | null; price: PriceT; is_best: boolean };
export type BookRow = {
  sportsbook: Book;
  status: "open" | "suspended" | "unavailable";
  last_updated?: string | null;
  is_stale: boolean;
  outcomes: Outcome[];
};
export type OddsComparison = {
  event: EventSummary;
  market: string;
  as_of: string;
  books: BookRow[];
  consensus: { outcomes: { key: string; name: string; no_vig_probability: number }[]; books_used: number };
  holds: { sportsbook_key: string; hold: number }[];
  best: { outcome_key: string; sportsbook_key: string; price: PriceT; line?: number | null }[];
};
export type LineHistory = {
  series: { sportsbook: Book; outcome_key: string; outcome_name: string; points: { timestamp: string; line?: number | null; price: PriceT }[] }[];
};

export type Player = { id: string; name: string; league: string; team: Team; position?: string | null };
export type PropOffer = {
  sportsbook: Book;
  status: "open" | "suspended" | "unavailable";
  line?: number | null;
  over?: PriceT | null;
  under?: PriceT | null;
  last_updated?: string | null;
  is_stale: boolean;
  is_best_over: boolean;
  is_best_under: boolean;
};
export type PropAnalysis = {
  player: Player;
  market: string;
  available_markets: string[];
  next_event?: EventSummary | null;
  opponent?: Team | null;
  offers: PropOffer[];
  consensus_line?: number | null;
  game_log: { date: string; opponent: Team; is_home: boolean; value: number; result: "over" | "under" | "push" }[];
  hit_rate: { over_count: number; sample_size: number; rate?: number | null; ci_low?: number | null; ci_high?: number | null; pushes: number };
  averages: { window?: number | null; season?: number | null; home?: number | null; away?: number | null; vs_opponent?: number | null };
  caveat: string;
};
export type PropBoardRow = {
  player: Player;
  event: EventSummary;
  market: string;
  consensus_line?: number | null;
  best_over?: { price: PriceT; sportsbook: Book } | null;
  best_under?: { price: PriceT; sportsbook: Book } | null;
  l10_hit_rate?: number | null;
  l10_sample: number;
};

export type User = { id: string; email: string; display_name: string; role: string };
export type AuthResponse = { access_token: string; token_type: string; expires_in: number; user: User };

export type BetLeg = {
  id: string;
  selection: string;
  market: string;
  league?: string | null;
  event_id?: string | null;
  event_label?: string | null;
  price: PriceT;
  closing_price?: PriceT | null;
  result?: string | null;
};
export type Bet = {
  id: string;
  bet_type: "straight" | "parlay" | "sgp" | "future";
  status: "pending" | "settled";
  result?: string | null;
  stake: number;
  sportsbook: string;
  placed_at: string;
  settled_at?: string | null;
  notes?: string | null;
  source: "manual" | "sync";
  legs: BetLeg[];
  combined_price: PriceT;
  potential_payout: number;
  payout?: number | null;
  profit?: number | null;
};
export type Breakdown = { key: string; bets: number; staked: number; profit: number; roi?: number | null };
export type BetSummary = {
  totals: {
    staked: number;
    profit: number;
    roi?: number | null;
    wins: number;
    losses: number;
    pushes: number;
    pending_count: number;
    pending_exposure: number;
    avg_clv?: number | null;
    settled_count: number;
  };
  by_sport: Breakdown[];
  by_market: Breakdown[];
  by_sportsbook: Breakdown[];
  by_bet_type: Breakdown[];
  timeline: { date: string; cumulative_profit: number }[];
};

export type AssistantReply = {
  intent: string;
  answer: string;
  data?: Record<string, unknown> | null;
  sources: { label: string; as_of: string; data_mode: string }[];
  suggestions: { label: string; href: string }[];
  disclaimer: string;
};
export type Meta = { data_mode: string; provider: string; version: string; server_time: string };
export type League = { key: string; name: string };
export type SyncProviderInfo = { key: string; name: string; description?: string | null };
export type SyncConnection = { id: string; provider: string; status: string; label?: string | null; created_at: string; last_synced_at?: string | null };
