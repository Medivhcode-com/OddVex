import type { ClientRequestIds } from "@/lib/bet-request";

/** One side of the game, at the best current price the API returned. */
export type QuickBetPick = { outcomeKey: string; label: string; line: number | null; american: number; sportsbook: string };
export type QuickBetGame = { eventId: string; eventLabel: string; league: string; market: string };

/**
 * The `POST /v1/bets` body of the game screen's quick bet: the chosen side at the best current
 * price, with its `client_request_id`.
 *
 * The id follows only what the user entered (game, market, side, stake), not the price or book.
 * The game screen refreshes itself every 20 to 60 seconds and the best price can move between a
 * lost answer and the resend. Sent with the same id, the API returns the bet it stored the first
 * time (at the price recorded then) or, if nothing was stored, stores it at the current price:
 * either way one bet. Any edit to the form calls `edited()` and gets a new id.
 */
export function quickBetRequest(ids: ClientRequestIds, game: QuickBetGame, option: QuickBetPick, stake: string) {
  const body = {
    bet_type: "straight",
    stake: Number(stake),
    sportsbook: option.sportsbook,
    legs: [
      {
        selection: option.label,
        market: game.market,
        league: game.league,
        event_id: game.eventId,
        event_label: game.eventLabel,
        outcome_key: option.outcomeKey,
        line: option.line,
        odds: String(Math.round(option.american)),
        odds_format: "american",
      },
    ],
  };
  const entered = { event_id: game.eventId, market: game.market, outcome_key: option.outcomeKey, stake: stake.trim() };
  return { ...body, client_request_id: ids.forSend(entered) };
}
