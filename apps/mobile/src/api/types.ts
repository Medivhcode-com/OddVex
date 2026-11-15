/**
 * Friendly names for the API's generated response models (`@oddvex/types`, built from services/api/openapi.json).
 * Type-only: nothing here reaches the bundle. Regenerate with `pnpm types:generate` when the API schema changes.
 */
import type { Schemas } from '@oddvex/types';

export type PriceT = Schemas['PriceOut'];
export type Book = Schemas['SportsbookRef'];
export type Team = Schemas['TeamRef'];
export type EventStatus = Schemas['EventSummaryOut']['status'];
export type BestSide = Schemas['BestPriceOut'] | null | undefined;
export type EventSummary = Schemas['EventSummaryOut'];
export type EventDetail = Schemas['EventDetailOut'];
export type Outcome = Schemas['OddsOutcomeOut'];
export type BookStatus = Schemas['BookOddsOut']['status'];
export type BookRow = Schemas['BookOddsOut'];
export type ConsensusOutcome = Schemas['ConsensusOutcomeOut'];
export type OddsComparison = Schemas['EventOddsOut'];
export type Meta = Schemas['MetaOut'];
export type League = Schemas['LeagueOut'];

export type User = Schemas['UserOut'];
export type AuthResponse = Schemas['TokenResponse'];

export type Bet = Schemas['BetOut'];
export type BetLeg = Schemas['BetLegOut'];
/**
 * The generator marks request fields that have a server-side default as required. They are not: the API fills
 * them in. `Defaulted` makes those optional again so request bodies match what the web app sends.
 */
type Defaulted<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type BetLegIn = Defaulted<Schemas['BetLegIn'], 'odds_format'>;
export type BetCreate = Omit<Defaulted<Schemas['BetCreate'], 'bet_type' | 'odds_format'>, 'legs'> & { legs: BetLegIn[] };
export type BetUpdate = Omit<Defaulted<Schemas['BetUpdate'], 'odds_format'>, 'legs'> & { legs?: BetLegIn[] | null };
export type BetSettle = Schemas['BetSettleRequest'];
export type BetResult = NonNullable<Schemas['BetOut']['result']>;
export type LegResult = Schemas['LegResultIn']['result'];
export type BetSummary = Schemas['BetSummaryOut'];
export type AutoSettle = Schemas['AutoSettleOut'];
export type BetType = Schemas['BetOut']['bet_type'];
export type EntryOddsFormat = NonNullable<Schemas['BetLegIn']['odds_format']>;

export type WatchItem = Schemas['WatchlistItemOut'];
export type WatchKind = WatchItem['kind'];

export type Player = Schemas['PlayerOut'];
export type PropBoardRow = Schemas['PropBoardRowOut'];
export type PropAnalysis = Schemas['PlayerPropsOut'];
export type PropOffer = Schemas['PropOfferOut'];
export type GameLogEntry = Schemas['GameLogEntryOut'];
export type PropWindow = PropAnalysis['window'];
export type PropSplit = PropAnalysis['split'];

export type ConvertResult = Schemas['ConvertResponse'];
export type NoVigResult = Schemas['NoVigResponse'];
export type EvResult = Schemas['EVResponse'];
export type ClvResult = Schemas['CLVResponse'];
export type ParlayRequest = Omit<Schemas['ParlayRequest'], 'legs'> & {
  legs: Defaulted<Schemas['ParlayLegIn'], 'odds_format' | 'result'>[];
};
export type ParlayResult = Schemas['ParlayResponse'];

export type AssistantReply = Schemas['AssistantResponse'];

export type SyncProvider = Schemas['SyncProviderOut'];
export type SyncConnection = Schemas['SyncConnectionOut'];
export type SyncRun = Schemas['SyncRunOut'];
export type SyncDelete = Schemas['SyncConnectionDeleteOut'];

export type Market = Schemas['EventOddsOut']['market'];
export const MARKETS: readonly { value: Market; label: string }[] = [
  { value: 'moneyline', label: 'Moneyline' },
  { value: 'spread', label: 'Spread' },
  { value: 'total', label: 'Total' },
];
