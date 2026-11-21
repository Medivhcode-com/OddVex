import { ClientApiError } from "@/lib/client-api";
import { tryAgainText } from "@/lib/retry";

/**
 * Safe retries for the forms that create a bet (`POST /v1/bets`).
 *
 * An answer can be lost after the API stored the bet: the bridge gives up after 10 seconds, or
 * the connection drops. Each filled-in form therefore carries a `client_request_id`. Sent again
 * unchanged, the same id makes the API answer 200 with the bet it stored the first time instead
 * of storing a second one. The API returns that stored bet even when the repeated body differs,
 * so an edited form must get a new id: `edited()` is called on every change to the form.
 */

/** 32 hex characters: within the API's rule (8 to 64 of `A-Z a-z 0-9 _ -`). Works over plain http too. */
export function newClientRequestId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** The id of one filled-in form. Keep one instance per form. */
export class ClientRequestIds {
  private id: string | null = null;
  private sent: string | null = null;

  constructor(private readonly make: () => string = newClientRequestId) {}

  /**
   * The id to send for `body`: the earlier one when this exact value was sent before, otherwise a
   * new one. Pass what the user entered; a form that fills in live prices passes only the user's
   * part (see `quickBetRequest`), so a refreshed price does not make a resend a second bet.
   */
  forSend(body: unknown): string {
    const key = JSON.stringify(body);
    if (this.id === null || this.sent !== key) {
      this.id = this.make();
      this.sent = key;
    }
    return this.id;
  }

  /** The form changed, so the next send is a different bet. */
  edited(): void {
    this.id = null;
    this.sent = null;
  }

  /** The bet was saved, so the next send is a new bet. */
  saved(): void {
    this.edited();
  }
}

/** Null when the stake can be sent. The API rounds to cents and refuses a stake that rounds to 0.00. */
export function stakeProblem(raw: string): string | null {
  const value = Number(raw.trim());
  if (!raw.trim() || !Number.isFinite(value) || value <= 0) return "Enter a stake greater than zero.";
  if (value < 0.01) return "Enter a stake of at least $0.01.";
  return null;
}

/** What to say when a bet could not be saved. */
export function betSaveError(caught: unknown): string {
  if (!(caught instanceof ClientApiError)) return "The bet was not saved. Try again.";
  if (caught.status === 429) return `Too many requests. ${tryAgainText(caught.details)}`;
  // No answer from the API (offline, the bridge gave up, or a proxy in front of the web answered
  // 502 or 504): the bet may have been stored. The same unchanged form carries the same
  // client_request_id, so sending it again cannot store it twice.
  if (caught.status === 0 || caught.code === "api_unavailable" || caught.status === 502 || caught.status === 504) {
    return "OddVex didn't get an answer, so the bet may already be saved. Check your open bets, or send the form again unchanged: it won't be recorded twice.";
  }
  // 409 bet_limit_reached and every other refusal: the API's own sentence.
  return caught.message || "The bet was not saved. Try again.";
}
