/**
 * The shape the API accepts for `client_request_id` on `POST /v1/bets`: 8 to 64 letters, digits, `_` or `-`.
 * The API answers a repeat of an id it has already stored with that bet (200) instead of saving a second one.
 */
export const CLIENT_REQUEST_ID = /^[A-Za-z0-9_-]{8,64}$/;

/**
 * A new id for one filled-in form: a UUID where the platform has `crypto.randomUUID`, otherwise 32 base-36
 * characters from the clock and `Math.random`. The id only has to be unique among one account's bets.
 */
export function newClientRequestId(): string {
  const uuid = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto?.randomUUID?.();
  if (uuid && CLIENT_REQUEST_ID.test(uuid)) return uuid;
  let id = Date.now().toString(36);
  while (id.length < 32) id += Math.random().toString(36).slice(2);
  return id.slice(0, 32);
}
