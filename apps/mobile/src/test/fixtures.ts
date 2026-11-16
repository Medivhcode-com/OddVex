import type {
  AlertRule,
  AuthResponse,
  Bet,
  BetAnalytics,
  BetLeg,
  BookRow,
  CommunityGuidelines,
  CommunityPick,
  CommunityProfile,
  CommunityRecord,
  Leaderboard,
  MyCommunityProfile,
  PickComment,
  EventSummary,
  GameLogEntry,
  Notification,
  OddsComparison,
  Outcome,
  PriceT,
  PropAnalysis,
  StakeReminder,
  User,
  ValueRow,
  ValueScreen,
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
  email_verified: true,
  plan: 'free',
};

export const unverifiedUser: User = { ...user, id: 'usr_2', email: 'riley@example.test', display_name: 'Riley', email_verified: false };

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

/** The method and caveat are the API's own sentences (services/api, board.py). */
export const valueRow: ValueRow = {
  event: upcomingEvent,
  market: 'spread',
  outcome_key: 'home',
  outcome_name: 'Harbor City Gulls',
  line: -3.5,
  best_price: price(105, 2.05, 0.4878),
  sportsbook: { key: 'book_c', name: 'Cedar Book' },
  consensus_probability: 0.5031,
  books_in_consensus: 3,
  edge: 0.0314,
  breakeven_probability: 0.4878,
  last_updated: '2026-11-15T19:59:18Z',
  stale_after_seconds: 900,
};

export const valueScreen: ValueScreen = {
  rows: [
    valueRow,
    {
      ...valueRow,
      event: liveEvent,
      market: 'total',
      outcome_key: 'over',
      outcome_name: 'Over',
      line: 44.5,
      best_price: price(-102, 1.98, 0.5051),
      sportsbook: { key: 'book_a', name: 'Northstar Sports' },
      consensus_probability: 0.5112,
      books_in_consensus: 2,
      edge: 0.0122,
      breakeven_probability: 0.5051,
    },
  ],
  min_edge: 0,
  as_of: '2026-11-15T19:59:30Z',
  data_mode: 'synthetic',
  method:
    'For each outcome, the best open, non-stale price is compared with the mean no-vig probability of the other open, non-stale sportsbooks quoting the same line. The sportsbook with the best price is left out of that consensus, and at least 2 other sportsbooks are required. Edge is the expected value per 1 unit staked at the best price if the consensus probability were the true probability.',
  caveat:
    'A price above the consensus is not proof of an edge. The consensus can be wrong, limits and availability vary by sportsbook, and prices move. This compares prices; it is not a prediction.',
};

function analyticsRow(key: string, label: string, bets = 0, staked = 0, profit = 0, roi: number | null = null, win_rate: number | null = null) {
  return { key, label, bets, staked, profit, roi, win_rate };
}

export const analytics: BetAnalytics = {
  settled_count: 12,
  by_odds_band: [
    analyticsRow('heavy_favorite', '-200 or shorter'),
    analyticsRow('favorite', '-199 to -110', 7, 175, -12.5, -0.0714, 0.4286),
    analyticsRow('near_even', '-109 to +100', 3, 75, 20.45, 0.2727, 0.6667),
    analyticsRow('underdog', '+101 to +200', 2, 40, 24, 0.6, 0.5),
    analyticsRow('long_shot', 'Longer than +200'),
  ],
  by_weekday: [
    analyticsRow('monday', 'Monday'),
    analyticsRow('tuesday', 'Tuesday'),
    analyticsRow('wednesday', 'Wednesday'),
    analyticsRow('thursday', 'Thursday', 4, 100, -18, -0.18, 0.25),
    analyticsRow('friday', 'Friday'),
    analyticsRow('saturday', 'Saturday', 3, 70, 9.95, 0.1421, 0.6667),
    analyticsRow('sunday', 'Sunday', 5, 120, 40, 0.3333, 0.6),
  ],
  by_month: [analyticsRow('2026-10', 'October 2026', 5, 120, -6, -0.05, 0.4), analyticsRow('2026-11', 'November 2026', 7, 170, 37.95, 0.2232, 0.5714)],
  longest_win_streak: 3,
  longest_loss_streak: 2,
  current_streak: { kind: 'loss', length: 2 },
  average_stake: 24.17,
  average_odds: price(-104, 1.96, 0.5102),
  clv: {
    sample: 6,
    average: 0.0125,
    share_beating_close: 0.6667,
    buckets: [
      { key: 'negative', label: 'Below 0%', count: 2 },
      { key: 'small', label: '0% to 2%', count: 3 },
      { key: 'large', label: 'Above 2%', count: 1 },
    ],
  },
  stake_distribution: [
    { key: 'under_25', label: 'Under $25', bets: 8, staked: 150 },
    { key: '25_to_50', label: '$25 to $50', bets: 4, staked: 140 },
  ],
  sample_note: 'Only 12 settled bets. Results from a sample this small are mostly noise.',
  note: 'Computed from your settled bets only. Past results do not predict future results.',
};

export const emptyAnalytics: BetAnalytics = {
  ...analytics,
  settled_count: 0,
  by_odds_band: analytics.by_odds_band.map((row) => analyticsRow(row.key, row.label)),
  by_weekday: analytics.by_weekday.map((row) => analyticsRow(row.key, row.label)),
  by_month: [],
  longest_win_streak: 0,
  longest_loss_streak: 0,
  current_streak: { kind: 'none', length: 0 },
  average_stake: null,
  average_odds: null,
  clv: { sample: 0, average: null, share_beating_close: null, buckets: [] },
  stake_distribution: [],
  sample_note: null,
};

export const flagsAllOn = { community: false, value_screen: true, tracker_analytics: true, email_flows: true, premium_gating: false };

/** Both community flags on, next to the others. */
export const flagsCommunityOn = { ...flagsAllOn, community: true, community_leaderboard: true };

/** Worded differently from the API's real rules on purpose, so a test can tell they were not written in the app. */
export const guidelines: CommunityGuidelines = {
  version: '2026-11-16',
  intro: 'Fixture intro: this community is for discussing research.',
  rules: [
    { key: 'be_civil', title: 'Fixture rule one', text: 'Discuss the pick, not the person.' },
    { key: 'no_selling_or_links', title: 'Fixture rule two', text: 'No paid picks and no links of any kind.' },
  ],
  enforcement: 'Fixture enforcement: moderators can hide content.',
  help: '21+. OddVex does not accept wagers. Gambling problem? Call 1-800-GAMBLER.',
};

export const smallRecord: CommunityRecord = {
  verified: true,
  picks: 6,
  wins: 2,
  losses: 3,
  pushes: 1,
  win_rate: 0.4,
  win_rate_interval: { low: 0.1176, high: 0.7693, confidence_level: 0.95 },
  average_price: price(107, 2.07, 0.4831),
  flat_stake_roi: -0.0825,
  units_profit: -0.495,
  method: 'Fixture method: the same flat amount on every graded pick at the price recorded when it was posted.',
  sample_note: 'Small sample: 6 graded picks. Fewer than 30 is too few to tell skill from luck.',
  caveat: 'A record describes picks that were already graded. Past results do not predict future results.',
};

export const fullRecord: CommunityRecord = {
  ...smallRecord,
  picks: 36,
  wins: 18,
  losses: 18,
  pushes: 0,
  win_rate: 0.5,
  win_rate_interval: { low: 0.3447, high: 0.6553, confidence_level: 0.95 },
  average_price: price(119, 2.19, 0.4561),
  flat_stake_roi: 0.0431,
  sample_note: null,
};

export const myProfile: MyCommunityProfile = {
  handle: 'sam_reads_lines',
  bio: 'Totals and closing lines.',
  joined: '2026-11',
  follower_count: 2,
  following_count: 3,
  record: smallRecord,
  is_following: false,
  is_blocked: false,
  is_me: true,
  is_public: true,
  can_post: true,
  moderation_status: 'visible',
  moderation_note: null,
};
export const privateProfile: MyCommunityProfile = { ...myProfile, is_public: false, can_post: false };

export const otherProfile: CommunityProfile = {
  handle: 'fictional_fox',
  bio: 'Fictional profile. <b>Not markup</b> https://example.test',
  joined: '2026-10',
  follower_count: 1,
  following_count: 4,
  record: fullRecord,
  is_following: false,
  is_blocked: false,
  is_me: false,
};

function pick(id: string, extra: Partial<CommunityPick> = {}): CommunityPick {
  return {
    id,
    author: { handle: 'fictional_fox' },
    event_id: 'evt_2',
    event_label: 'Iron Valley Forge at Harbor City Gulls',
    event_start_time: '2026-11-16T18:00:00Z',
    league: 'nfl',
    market: 'spread',
    outcome_key: 'home',
    line: -3.5,
    selection: 'Harbor City Gulls -3.5 spread',
    price: price(-108, 1.93, 0.5192),
    sportsbook: { key: 'book_a', name: 'Northstar Sports' },
    posted_at: '2026-11-15T17:00:00Z',
    status: 'pending',
    result: null,
    graded_at: null,
    final_score: null,
    analysis: 'The line moved half a point since open.',
    verified: true,
    like_count: 2,
    comment_count: 1,
    liked_by_me: false,
    is_mine: false,
    moderation_status: 'visible',
    moderation_note: null,
    data_mode: 'synthetic',
    ...extra,
  };
}

export const upcomingPick = pick('pick_1');
export const wonPick = pick('pick_2', {
  market: 'moneyline',
  line: null,
  selection: 'Harbor City Gulls moneyline',
  status: 'graded',
  result: 'won',
  graded_at: '2026-11-15T19:00:00Z',
  final_score: { home: 17, away: 14 },
  event_start_time: '2026-11-14T18:00:00Z',
  analysis: null,
  like_count: 1,
  liked_by_me: true,
  comment_count: 0,
});
export const lostPick = pick('pick_3', { ...wonPick, id: 'pick_3', result: 'lost', selection: 'Iron Valley Forge moneyline', outcome_key: 'away', liked_by_me: false, like_count: 0 });
export const pushPick = pick('pick_4', { ...wonPick, id: 'pick_4', result: 'push', market: 'total', selection: 'Over 31 in Iron Valley Forge at Harbor City Gulls', line: 31, outcome_key: 'over', liked_by_me: false, like_count: 0 });
export const voidPick = pick('pick_5', { status: 'void', event_start_time: '2026-11-01T18:00:00Z', analysis: null, like_count: 0, comment_count: 0 });
export const myUpcomingPick = pick('pick_6', { author: { handle: 'sam_reads_lines' }, is_mine: true });
export const myGradedPick = pick('pick_7', { ...wonPick, id: 'pick_7', author: { handle: 'sam_reads_lines' }, is_mine: true });

export function comment(id: string, extra: Partial<PickComment> = {}): PickComment {
  return {
    id,
    pick_id: 'pick_1',
    author: { handle: 'madeup_mara' },
    body: 'Which book moved first? <script>alert(1)</script> www.example.test',
    created_at: '2026-11-15T18:00:00Z',
    is_mine: false,
    moderation_status: 'visible',
    moderation_note: null,
    ...extra,
  };
}

export const leaderboard: Leaderboard = {
  window: '90d',
  league: null,
  minimum_graded_picks: 30,
  ranked_by: 'wilson_lower_bound',
  items: [
    { rank: 1, handle: 'fictional_fox', record: fullRecord },
    { rank: 2, handle: 'sample_sam', record: { ...fullRecord, picks: 32, wins: 15, losses: 17, win_rate: 0.4688, win_rate_interval: { low: 0.3087, high: 0.6356, confidence_level: 0.95 } } },
  ],
  method: 'Fixture ranking method: ordered by the lower bound of the interval of the win rate.',
  caveat: 'This ranking describes graded picks from the past. Past results do not predict future results.',
  as_of: '2026-11-15T19:59:30Z',
  data_mode: 'synthetic',
};
