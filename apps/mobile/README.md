# OddVex mobile

The iOS and Android app. Expo SDK 58, React Native 0.88, React 19.3, TypeScript, expo-router.

OddVex is a sports-betting intelligence product. This app compares prices; it never takes or places wagers.

**Status: feature parity with the web app's signed-in loop, not yet run on a device or simulator.** Everything
below was checked by the type checker, the linter, unit and component tests, a JS bundle export for both platforms,
and a scripted run of the real API client against a locally running API. Nobody has looked at these screens on a
phone, in a simulator or in Expo Go. Treat layout, the native tab bar, modals, keyboard avoidance, safe areas,
Dynamic Type, screen reader behavior and SecureStore on real hardware as unverified until someone does. That
includes everything added for alerts and notifications: the bell in the Games header (drawn from plain views, with
no icon library) and its badge, the header's layout next to the "Synthetic data" badge, and refresh on focus. It
also includes everything in the latest slice: the value screen, tracker analytics and their bars, the account lines
in Settings, the forgot-password, reset-password and verify-email screens, and opening those two from a link.
And it includes every community screen described below: the feed, the pick, profile, leaderboard, guidelines and
profile-setup screens, the "Share a pick" panel on a game, multi-line text entry with the keyboard open, and the
inline report, block and delete confirmations. None of it has been seen on a phone. The same goes for the helpline
phone links (whether the dialer opens has only been checked against a mocked `Linking`), the width of the "Data
source not confirmed" badge in a header, and "Show more" on the tracker.

## What is built

Five tabs: Games, Props, Tracker, Tools, Settings. Research screens work signed out; the tracker, its analytics,
the watchlist, alerts, notifications and the community need an account. Four features sit behind the API's feature
flags (see "Feature flags"); the community is one of them and is off by default. There is no sixth tab: the community
is reached from a link row on Games and from notification links.

| Screen | What it does |
|---|---|
| Games (tab) | Events grouped Live / Upcoming / Final, league filter chips, pull to refresh. Best moneyline per side with the sportsbook's name. An "Ask OddVex AI" card. When logged in, "Your watchlist": live and upcoming games for what you follow (`GET /v1/watchlist/events`) and the players you follow. A bell in the header opens Notifications and shows the unread count as a number ("Notifications, 3 unread"); the badge is not drawn at zero. While the `community` flag is on, a "Community" link row sits under the value screen row. |
| Value screen | Flag `value_screen`. Reached from a panel at the top of the Tools tab and from a link row on Games. `GET /v1/value` with league, market and smallest-edge filters (the three fixed sizes are sent as the fractions the API takes). The API's `caveat` ("A price above the consensus is not proof of an edge…") and `method` sit above the rows. Each row: the game, the outcome with its line, the best price with its sportsbook and age, "Consensus of N other books: 47.3%", "Break-even at this price", and "Edge vs consensus" as a signed percentage. Tapping a row opens that game on that market. An empty screen says that on many slates nothing qualifies. Loading, error with retry, pull to refresh. The screen never calls the number anything but "Edge vs consensus"; a test fails if "guarantee", "lock", "free money", "risk-free", "+EV", "pick" or "profit" appears in any string on it. |
| Game detail | Market switcher, one row per sportsbook with price, freshness, hold, the word "Best" on the best price, no-vig consensus. Follow / Following toggles for the game and both teams. On a game that is not over, "Track a bet on this game" logs a structured leg (game, market, side, line, best price, sportsbook) so the tracker can settle it from the final score; signed out, it asks you to log in. Below it, "Set an alert" (also only while the game is not over): "Price reaches" (a side of the market selected in the switcher, with its line for spread and total, and an American price to reach, filled in a little above the current best), "Line moves" (spread and total; points, 1 by default), "Before the game starts" (15 or 30 minutes, 1 or 2 hours; upcoming games only) and "When the game ends", plus "Alert me before {team}'s games" for either team (60 minutes before each game). The API's 422 message is shown as sent. Opens on the market a link names (`/event/{id}?market=spread`). While the `community` flag is on, a signed-in person sees "Share a pick" on a game that has not started (see "Community"). |
| Notifications | Reached from the bell and from Settings; one screen with two segments. **Notifications**: newest first, pull to refresh, "Load more" (`next_before`), the API's `title` and `body` unchanged, the kind in words (including "New follower", "Comment on your pick" and "Graded pick"), the word "New" on unread ones, "Mark all as read", a Delete button on each. Tapping one marks it read and opens the screen its web link maps to; a link with no screen here only marks it read. **Alerts**: your rules grouped Active / Triggered / Paused / Expired with the API's `summary`; Pause, Resume, "Set again" for a triggered rule, Delete after an inline confirmation, "Open game", and "Check now" (`POST /v1/alerts/evaluate`, reported as "Checked 4 alerts. 1 fired."). Signed out, it asks you to log in. |
| OddVex AI | Chat reached from the Games tab and from Settings. Example questions seeded from current games and props, `POST /v1/assistant/query`, suggestion chips that open the matching screen in this app, and the sources line and disclaimer under every answer. A responsible-gambling support reply (the API sets `support` for crisis, distress or under-21 messages) is shown as a calm "Help is available" card instead: the API's wording, phone and text links for the helpline and 988 (a crisis reply puts 988 and 911 first), and its links (the help in Settings, and for distress the staking reminder and the tracker). It has no sources line and no disclaimer, because it carries no data. |
| Props (tab) | Prop board with league and stat filters: consensus line, best over and under with the book, last-10 over rate with its sample size. |
| Prop analyzer | Stat, window (5 / 10 / 20 / season) and split (all / home / away / vs opponent) selectors. Over rate with "x of n games" and the API's 95% Wilson range, averages, a game-log bar chart against the line (plain views, each bar labelled Over, Under or Push), per-book offers with Best / Stale / Suspended / Not offered in words, the API's caveat under "A record, not a forecast", the game log list, and a Follow toggle for the player. |
| Tracker (tab) | Signed out: an invitation to log in. Signed in: profit, ROI, record, average closing line value, open bets and exposure (`GET /v1/bets/summary`); open and settled bets with "Tied to a game", "Settled from final score" and "Synced" badges. Open bets are read in their own request (`GET /v1/bets?status=pending&limit=1000`). Settled bets are read 50 at a time, most recently placed first (`status=settled&limit=50&offset=N`), with "Show more" for the next page until none are left; the heading says "Showing 50 of 120" from the summary's count, and a reload after a change asks again for as many as are on screen. Settle (won, lost, push, void, half won, half lost, cashed out with the amount), settle a parlay leg by leg, edit stake (at least $0.01) / sportsbook / notes / closing odds, delete after confirmation; "Settle from final scores" (one call checks at most 200 open bets; when the API reports `has_more` the result says more are left and a "Check the rest" button runs it again); mock sportsbook sync (connect, sync now, disconnect and delete; a finished sync that left bets out shows the API's `error_message` saying how many and why). When your weekly staking reminder has been reached, a notice at the top says so, says it is a reminder and not a limit, and gives the helpline. Nothing is blocked. The short responsible-gambling line with a "Call 1-800-MY-RESET" phone link sits near the top of the screen in every state, signed out included, and again at the foot of the sync panel (see "Help with problem gambling"). |
| Analytics | Flag `tracker_analytics`. "Open analytics" on the Tracker tab when signed in. `GET /v1/bets/analytics`: results by odds band, weekday and month as labelled bars drawn from plain views, each with its values written out ("7 bets · $175.00 staked · profit −$12.50 · ROI −7.1% · win rate 42.9%"); average stake and average odds; runs ("2 losses in a row", longest run of wins and of losses) in plain text with no color, plus the API's `streak_note` when it sends one; closing line value (average, share above the close, buckets); stake sizes; the API's `sample_note` as a "Small sample" caution when present, and its `note` at the foot. Empty state when nothing is settled. The bar lengths are the only arithmetic: a row's count against the largest count in its list. |
| Log a bet | Straight, parlay, same-game parlay or future; add and remove legs; American, decimal or fractional odds; league, sportsbook, stake (at least $0.01), optional closing odds. OddVex records the bet. It does not place it. If the session ends before the bet is saved, what was typed is back in the form after logging in again (see "Unsaved input when the session ends"). Saving again after a failure cannot record the bet twice (see "Saving a bet again"). |
| Tools (tab) | Odds converter, no-vig (two or three sides), expected value, closing line value. Each posts to `/v1/quant/*`, shows the API's result and caveat, and has a "Show the working" toggle listing the API's steps. |
| Parlay research | Pick moneyline legs from current games or add a custom leg, set a stake, `POST /v1/quant/parlay`. Shows combined odds, payout and break-even. A combined probability is shown only when the API computed one (`probability_status` is `computed`), marked "Assumes the legs are independent"; this screen sends no leg probabilities, so for legs from different games there is no probability stat and no note. Legs from the same game get "These legs are correlated" with one sentence, a custom leg (not tied to a game) gets a sentence saying independence cannot be checked, and a parlay whose legs all pushed or were voided says so. The API's `probability_note` and raw `correlation_warnings` are never shown. |
| Settings (tab) | Account (name, email, "Email verified" or "Email not verified", the plan when the API sends one, "Preview: every feature is included" while `GET /v1/me/entitlements` reports `preview`, log out with the line "Logging out ends every session for this account, on every device where it is signed in."; or log in / create account). While the address is not verified and `email_flows` is on, "Send verification email" (`POST /v1/auth/verify-email/request`) shows the API's confirmation and the preview statement below. There is no purchase or upgrade UI anywhere. Then odds format, data source notice, the responsible-gambling panel (the short line, a "Call 1-800-MY-RESET" phone link, the text line, the statement that the helpline is not an emergency service with a "Call 988" link, and a link to the Council's website), a switch per kind of notification (`PUT /v1/me/notification-preferences` with only the kind that changed; "New followers", "Comments on your picks" and "Graded picks" are listed only while the `community` flag is on), the weekly staking reminder (amount, Save, Turn off, "You have staked $X this week"), change password, delete account with a typed DELETE confirmation, versions. |
| Log in, Create account | Modals above the tabs, so they open from any screen and close back to it. Create account needs a name, an email, a password of at least 10 characters and the "I am 21 or older…" switch. With `email_flows` on, Log in has "Forgot password?". After a suspension it shows "This account can't be used right now" (see "Accounts and the token"). |
| Reset your password (`/forgot-password`) | Takes an email, `POST /v1/auth/password-reset/request`, and always answers "If an account exists for that address, a reset link has been sent." whether or not the address has an account, with the preview statement. 429 shows "Too many attempts. Wait a minute, then try again." |
| Set a new password (`/reset-password?token=`) | New password (at least 10 characters) and a confirmation field, `POST /v1/auth/password-reset/confirm`, then the saved session on the device is cleared and Log in opens with "Password changed. Log in with your new password." A used or expired link says so and offers a new one; a link with no token says it is incomplete. |
| Confirm your email address (`/verify-email?token=`) | A "Confirm email address" button calls `POST /v1/auth/verify-email/confirm` and shows "Email address confirmed." or "This link has expired or was already used." Like the web page, opening the link spends nothing: the token works once, so it is used only when the button is pressed. Works signed out; signed in, the user is read again so Settings shows "Email verified". |

### Community

Flag `community`, off by default. The leaderboard also needs `community_leaderboard`. Research discussion, not
tipping: there is no money, no stake, no size and no confidence rating anywhere, and other people are known by handle
only. Every screen is in the Games tab's stack.

| Screen | What it does |
|---|---|
| Community (`/community`) | Without a profile: the guidelines exactly as `GET /v1/community/guidelines` words them (the app writes none of the rules) and the create-profile form. With one: the feed (`GET /v1/community/feed`), a Following / Everyone switch, pull to refresh and "Load more" with the API's `next_before` cursor, 20 picks a page. One line says every pick is timestamped before the game and graded automatically from the final score. Buttons open your profile, the leaderboard (its flag only) and the guidelines. A private profile gets a notice that it can browse but not post. |
| Profile form (`/community/profile`) | `PUT /v1/community/profile`. Handle: lower-cased as typed, checked on the device for 3 to 20 characters of `a-z`, `0-9` and `_`. Optional bio with a live count out of 280. "Make my profile public", off until switched on, with the statement that a public profile shows the handle, bio, picks and graded record and never the email, name, bets or plan. `handle_taken`, `handle_reserved`, `invalid_handle`, `links_not_allowed` and `content_not_allowed` (by the rule the API names in `details.rule`) each get their own sentence, placed on the field they are about. |
| Pick card | The author's handle (opens the profile), the game and its start, the API's `selection` (which carries the line), "Price when posted: −108 at Northstar Sports", "Posted 3h ago", the status as a word (Upcoming, Won, Lost, Push, Void), the analysis, Like / Liked with the count (`PUT` / `DELETE …/like`; the count shown is the one the API answers) and the comment count. |
| Share a pick (on Game detail) | Upcoming games only, signed in, flag on. Outcome pills built from the current market's best prices (the same options as "Track a bet"), optional reasoning with a live count out of 1000, and a short rules reminder. `POST /v1/community/picks` with `event_id`, `market`, `outcome_key`, `line` for spread and total only, and `analysis` when something was written. The server records the price and the time. Rejections are explained: content rules, links, `event_not_open`, `pick_exists` (with a button to the pick you already have), the daily limit (429), `profile_required`, `price_not_available`. Without a profile, or with a private one, the panel says so and links to the profile form. |
| Pick (`/community/picks/{id}`) | The card, "Final score: Away 14, Home 17" once graded, "Open game", comments newest first with "Load more comments", and "Add a comment" (count out of 500, the same reminder and error sentences). The author can delete the pick, after an inline confirmation, only while its game has not started; otherwise the screen says "Picks can't be deleted after the game starts, so records stay honest." (also shown if the API answers `409 pick_locked`). The author of a comment can delete it. Report on the pick and on each comment that is not yours. |
| Report | Inline: reason pills (Spam, Harassment, Encouraging betting, Misleading claims, Personal information, Other), optional details up to 500 characters, `POST /v1/community/reports`, then "Report sent. A moderator will review it. The person you reported is not told who sent it." |
| Profile (`/community/profiles/{handle}`) | Handle, bio, "Joined November 2026", follower and following counts, Follow / Following, Block and Unblock each after an inline confirmation that says what it does, Report. Graded record: graded picks, won-lost-push, win rate with the API's 95% interval and the sample size, average price, flat-stake ROI with the API's `method` under "How this record is calculated", `sample_note` as a "Small sample" caution when the API sends it, and the API's `caveat`. Then the profile's picks, paged. Your own profile (read from `GET /v1/community/profile`, so it also works while private) has Edit profile and your blocked list with Unblock instead. |
| Leaderboard (`/community/leaderboard`) | Both flags. League and period pills (30 days, 90 days, all time), the API's `caveat` above everything, one line saying ranking uses the lower end of each win-rate interval, the API's `method`, then rows in the API's order: rank, handle, graded picks, won-lost-push, win rate and its interval, and the record's average price and flat-stake ROI as the API sends them (so a run of heavy favourites that wins often but only breaks even is visible). No trophies, medals, flames or "hot" wording. An empty period says only profiles with the API's minimum number of graded picks are ranked. |
| Guidelines (`/community/guidelines`) | The same guidelines on their own screen. No sign-in needed; still behind the flag. |

Text other people wrote (handles, bios, analysis, comments) is drawn with plain `Text`. Nothing is parsed as markup
and nothing is turned into a link. The app sends what was typed, trimmed, and the API decides what is allowed.

**Moderation is web-only.** Reviewing reports, hiding or removing content and suspending an author
(`/v1/admin/community/*`) are not in this app. The app only shows the results: content that disappears, a "Hidden by
moderators" note on your own pick, the moderators' note in place of your removed comment, and a notice on your own
hidden profile. That notice says the profile stays hidden when you change the handle or the bio, that the change
goes back to the moderators for review, and that only a moderator can make it visible again (the API's rule).

Every header carries a data-mode badge: "Synthetic data" while the API reports `data_mode: "synthetic"`, "Replay"
for `"replay"`, and "Data source not confirmed" (neutral, not a warning) while the mode is not known because
`GET /v1/meta` has not answered yet, failed, or answered without a data mode. An unknown mode never draws nothing
and is never treated as real data. `src/providers/meta.tsx` keeps asking until it has an answer: after 2, 5, 15, 30
and then every 60 seconds while the app is in the foreground, and at once each time the app returns to the
foreground. The badge is absent only after the API has named some other mode; the API has none today. In Settings,
the "Data source" panel says the data service cannot be reached from the first failed read until an answer
arrives, and does not go back to "Checking the data source." while a retry is on its way.

The app does no odds math. Prices, probabilities, payouts, hit rates, ranges, CLV and grading all arrive from the
API; `src/utils/format.ts` only formats, and forms send odds as typed for the API to parse. The two unit changes made
on the device are the ones the web app makes: a typed stake becomes a number, and a typed win probability in percent
becomes the fraction the API expects. The alert form adds two more of the same kind: it checks that a typed American
price is a whole number outside −100..+100 before sending it as typed, and it fills the price field with a
suggestion ten points above the current best (`suggestedThreshold`), which is a starting value for the user to edit,
not a calculation the app relies on.

## Feature flags

`src/providers/flags.tsx` reads `GET /v1/flags` when the app starts, each time it returns to the foreground and
after a sign-in. The app acts on five flags: `value_screen` (the Tools panel and the Games link row),
`tracker_analytics` (the Tracker's Analytics panel), `email_flows` ("Forgot password?" and "Send verification
email"), `community` (the Games link row, "Share a pick" on a game, the three community switches in Settings and
every community screen) and `community_leaderboard` (the Leaderboard button and its screen, which needs both). An
entry point is drawn only while its flag is on.

- **Off until known.** A flagged entry point is hidden while the flags are loading, when the call failed and
  nothing was loaded earlier, and when the API's answer does not list the flag. If a later read fails, the last
  flags loaded stay in use.
- **Everything else is unaffected.** Games, props, the tracker, calculators, parlay research, alerts,
  notifications, the assistant and the account screens existed before flags and never ask for one, so a failed
  flags call hides nothing of theirs.
- **A flag can change under the app.** If a flagged call answers 404 `feature_disabled` (a deep link, or a flag
  turned off since the last read), the screen shows "This feature isn't available right now." with no retry, and
  the flags are read again so the entry point goes away.

- **Community screens check the flag themselves.** A notification link (`/app/community/picks/{id}`,
  `/app/community/profiles/{handle}`) can arrive while `community` is off. The screen it opens then shows "This
  feature isn't available right now." and asks the API for nothing.

`premium_gating` is not read. Nothing in the app is gated by plan.

## No email is actually sent

The API writes verification and reset messages to an outbox table and sends nothing, so in this preview a link
never arrives in an inbox. The app says so wherever it asks for one: "In this preview no email is actually sent,
so the link will not arrive in your inbox." appears under "Send verification email" in Settings and on the reset
request screen, before and after sending. In development the link can be read from
`GET /v1/dev/email-outbox/latest?to=`.

`/verify-email` and `/reset-password` read a `token` parameter, so `oddvex://verify-email?token=…` and
`oddvex://reset-password?token=…` open them (the `oddvex` scheme is in `app.json`). The links in the API's emails
point at the web app (`ODDVEX_WEB_BASE_URL`), and no universal links or Android app links are configured, so today
nothing sends a person to these screens by itself. Opening them through the scheme has not been tried on a device.

## Alerts and notifications are in-app only

There is no push, no email and no background work in this app: `expo-notifications` is not installed and nothing
runs while the app is closed. The API has no background worker either. It checks a user's alert rules when the app
reads the notifications or the unread count, or calls "Check now". So an alert shows up **the next time the app is
opened or brought back to the foreground**, not at the moment its condition becomes true, and a price that touched
the threshold and moved away in between is not noticed. The screens say this where alerts are set and listed.

The unread count is read when the Games tab mounts, when it regains focus, when the app returns to the foreground,
and after anything in the app changes a notification. The weekly staking reminder is a reminder, never a limit:
the API always saves the bet, and the app never blocks or delays logging one.

## Accounts and the token

- `POST /v1/auth/login` and `/register` return a JWT (`access_token`, `expires_in`, `user`). The app calls the API
  directly with `Authorization: Bearer <token>`; there is no cookie proxy.
- The token, its expiry and the user are stored with `expo-secure-store` (Keychain on iOS, Keystore-backed storage
  on Android) under `oddvex.session`. Nothing about the account goes into AsyncStorage, which only holds the odds
  format. `src/session/store.ts` is the only file that touches SecureStore.
- In memory, `src/providers/session.tsx` holds the session and hands the token to `src/api/client.ts`. At launch it
  reads the stored session, drops it if it has expired, and confirms it with `GET /v1/me`.
- The token is only sent on the user's own endpoints (and to the assistant, when there is one). If the API answers
  401 to a request that carried the token, the session is cleared from memory and SecureStore and the log in screen
  opens. A 401 for a wrong password does not do this. Form input that was not saved yet is kept for the next log
  in by the same account (next section).
- Changing the password returns a new token, which replaces the stored one. Delete account clears it.
- **Log out ends every session of the account.** The app calls `POST /v1/auth/logout` with the token and then
  clears it from memory and SecureStore. The API has no per-device sessions: that call rejects every token issued
  to the account before it, on every device, and Settings says so under the button. The local clear happens
  whatever the API answers. Offline, timed out (the request waits up to 8 seconds) or rejected, this device is
  signed out; in those cases the other devices stay signed in until their tokens expire, and the app does not
  say that the call failed.
- A completed password reset returns no token: the saved session on this device is cleared without calling the
  logout route (the reset already ended that account's sessions) and the user logs in again.
- A suspended account: `401 account_suspended` on any call that carried the token, or `403 account_suspended` on
  log in, clears the session from memory and SecureStore. The log in screen then says "This account can't be used
  right now", that the person has been signed out on this device, that their bets and settings are kept, and that
  a copy of the data or its deletion can be asked for by writing to support@oddvex.com from the account's email
  address (`src/contact.ts`, decision D-017), with an "Email support@oddvex.com" button that opens a new email.
  A suspended account cannot sign in, so the app itself cannot export or delete its data. The message goes away
  after the next successful log in.
- 429 shows "Too many attempts. Wait a minute, then try again."

## Unsaved input when the session ends

Tokens last an hour and are not refreshed, and logging out anywhere ends every session, so the API can reject the
token while someone is in the middle of a form: on Save, or on any other request (the bell re-reads the unread
count whenever the app returns to the foreground). The screen then swaps the form for a log in prompt.

`src/session/drafts.ts` keeps what was typed through that. Form fields use `useDraft(key, initial)` in place of
`useState`. When the session provider ends a session because of a 401, every field that holds unsaved input is
kept in memory as its form leaves the screen. Log in is a modal that closes back to the screen underneath, so after
logging in with the same account the form is drawn again with the fields as they were and the line "You were signed
out, so nothing was saved. What you entered is still here." (A bet form whose last save got no clear answer says
instead that the bet may already be in the tracker; see "Saving a bet again".) Nothing is sent again automatically:
the person presses Save.

Unsaved means different from the value the field had when the form was drawn or, once the form has been saved,
from what was saved. Each form tells the module when the API has accepted it (the third value `useDraftKept`
returns, called in the success path after the form's own resets). A form that stays on screen after a save, such as
an alert, the staking reminder or a profile, is therefore not brought back by a later sign-out and is never
described as not saved. Only what is typed after the save is kept.

- Covered: Log a bet, "Track a bet on this game", "Set an alert", "Share a pick", the community profile form, a
  comment, an open report, a bet being edited or settled on the tracker, and the weekly staking reminder amount.
- Not kept, on purpose: the two fields of Change password, the typed DELETE confirmation, and an open "Delete
  this bet for good?" prompt. A password or a confirmation should be given again by the person who is now signed in.
- Discarded: on Log out, Delete account, a suspension, a completed password reset, and when a different account
  logs in. Nothing typed under one account is shown to another.
- In memory only. Nothing is written to disk, so closing the app loses it, as before.
- Leaving a form in the ordinary way (going back, switching market) still clears it, as before.
- If a save was already on its way when another request ended the session, and the API then accepts it, the copy
  kept for that form is dropped. If the form is already back on screen by then, it stops saying nothing was saved,
  but the fields it took back stay in it and no "saved" confirmation is shown.
- A kept draft waits for its form: if the person logs in again and does not open that form until later in the same
  run of the app, it comes back then, with the same line. Nothing expires it before a log out.
- The community profile form is kept per screen (the community's first screen and the profile screen can both be
  in the stack), so what was typed in one is not put into the other.
- Screens that do not swap their form out on sign-out (the assistant, the calculators, parlay research) never lost
  input and are unchanged.

## Saving a bet again

A save can reach the API and still look failed on the phone: the request waits up to 8 seconds, and an answer that
is slower or lost is reported as no answer. Log a bet and "Track a bet on this game" therefore send a
`client_request_id` with each new bet (`src/hooks/use-client-request-id.ts`, ids from `src/utils/request-id.ts`).

- The id is made when the filled-in form is first saved and is sent again while the same form, unchanged, is saved
  again after a failure. The API answers a repeated id with the bet it stored the first time (200 instead of 201),
  and the app treats both as saved. Editing the form after a failure makes a new id; a successful save clears it,
  so the next bet gets its own. Only the last save is remembered: editing, saving that, and then changing the form
  back gives a new id.
- On Log a bet the id follows the whole form. On "Track a bet on this game" it follows what the person chose (the
  game, market, side and stake), not the best price or its sportsbook: a pull to refresh can move those between two
  attempts, and the retry must still carry the same id. If the first attempt was stored, the API returns that bet at
  the price it was saved at.
- Two presses before the button turns into "Saving" (a fast double tap) send the same id, and the API answers the
  second with the bet the first stored.
- The id is a draft field like the others, so a form brought back after an unexpected sign-out keeps its id: a save
  that reached the server before the session ended is not stored twice. If a save of that form got no clear answer,
  the form that comes back says "You were signed out before OddVex could confirm the save, so this bet may already
  be in your tracker. What you entered is still here. Check the tracker before you save it again." instead of the
  usual "nothing was saved" sentence.
- When a save gets no answer, or a server error (5xx, which a proxy can send after the API has stored the bet), the
  form says "OddVex couldn't confirm the save, so this bet may already be in your tracker. Check the tracker before
  you save it again." ("Track a bet on this game" also offers "Open the tracker"). This wording is for bet saves
  only; other screens keep the shared "can't reach its data service" message.
- The bet cap (409 `bet_limit_reached`) and the API's write limit (429 `rate_limited`, which says how many seconds
  to wait) are shown in the API's words; a 429 without that code keeps the shared "Too many attempts" sentence. A
  stake under $0.01 is refused before anything is sent, because the API stores stakes in cents. The same floor
  applies when a stake is edited in the tracker.

## Help with problem gambling

`src/helpline.ts` is the only file that writes the helpline down; a test fails if the number, the text code or the
website appears in any other source file. Checked on 2026-11-19 against the National Council on Problem Gambling's
own pages:

- The National Problem Gambling Helpline is **1-800-MY-RESET (1-800-697-3738)**, in service since 2026-01-29. Call
  it, or text 800GAM (800426). It is confidential and answers 24 hours a day, every day.
- It is not an emergency service. In a crisis: call or text 988 (the Suicide and Crisis Lifeline), or call 911.
- The Council's site is https://www.ncpgambling.org, where online chat is offered. The app links to the front page
  only.
- 1-800-GAMBLER is not the national helpline (the Council on Compulsive Gambling of New Jersey runs it). The app never shows it.

The short line is "21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738)." It
appears in Settings, on the tracker and in the sportsbook sync panel, each time with a "Call 1-800-MY-RESET" button
that opens the dialer through `tel:+18006973738` (`src/components/help-link.tsx`). The weekly staking reminder
notice ends with the same number. Settings also gives the text line, the 988 sentence with a "Call 988" link, and
the link to the Council's site. The assistant's support card adds "Text 800GAM", "Text 988" and, for a crisis,
"Call 911" (`sms:` and `tel:` links from the same module). On a device that cannot place calls the link does nothing; the number is always
written out next to it. The community guidelines show the API's own `help` sentence, which this app does not word.

## What is not built

- Any purchase, upgrade or pricing UI. Plans are shown, never sold; nothing is gated by plan.
- Community moderation (web-only, see "Community"). Follower and following lists (the counts are shown), editing a
  pick (the API has no such route), filters on the feed, and a way to see who liked a pick.
- Universal links / Android app links for the email links, and a resend action on the verify screen itself.
- Line charts for analytics. The breakdowns are bar rows with their values as text.
- Data export (`GET /v1/me/export`). Download your data from the web app's settings.
- The tracker's cumulative profit chart and the by-sport / by-market / by-sportsbook / by-bet-type breakdowns.
- Line movement charts on game detail, the web's separate odds board (the Games tab stands in for it), the theme
  toggle (the app follows the system setting), and the terms, privacy and methodology pages (web only; links to
  them from the assistant are dropped).
- Automatic refresh. Data updates on pull to refresh, on a filter change, and after you change a bet or a follow.
  The "ago" labels keep counting.
- Offline cache. With no connection you get the error state. A saved session survives being offline.
- Token refresh. When the token expires you are asked to log in again; unsaved form input is kept for that (see
  "Unsaved input when the session ends").
- Push notifications, email, alert sounds, an app icon badge and background checks (see "Alerts and notifications
  are in-app only"). An unread-only filter on the notification list. Alerts on player props.
- A text-message link for 800GAM (the code is written out, not tappable), tablet layouts, web
  (`react-native-web` is not installed).
- Final app icon and splash art. Store configuration (listings, submit profiles): none exists, and nothing has
  been published to a store. The EAS project and its two build profiles exist; see "Builds".
- A search or filter on the tracker's lists. Older settled bets are reached with "Show more". Open bets come in
  one request of 1,000, the API's largest page: an account with more than that sees "Showing 1000 of N open" and
  cannot reach the rest from the app.
- Geist Sans. Interface text uses the system face. Numbers use IBM Plex Mono.

## Run it

From the repo root, once:

```bash
pnpm install
```

Start the API (see `AGENTS.md`), then:

```bash
cp apps/mobile/.env.example apps/mobile/.env.local   # then edit the address
pnpm --filter @oddvex/mobile start
```

Open it in Expo Go by scanning the QR code, or press `i` / `a` for a simulator or emulator. A development build
(`npx expo run:ios`, `npx expo run:android`) also works. `expo-secure-store` is the one native module added in
this slice; it ships in Expo Go and is registered as a config plugin in `app.json` for builds. The generated `ios/` and `android/` folders are git-ignored.

### `EXPO_PUBLIC_API_URL`

Base URL of the OddVex API. Defaults to `http://localhost:8000`. It is inlined at bundle time, so restart the bundler
after changing it.

| Where the app runs | Value |
|---|---|
| iOS simulator | `http://localhost:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| Phone with Expo Go | `http://<your computer's LAN IP>:8000`, with the API started on `--host 0.0.0.0` |

Plain `http://` is fine in Expo Go and development builds. Release builds on both platforms block cleartext traffic
by default, so a production API address must be `https://`.

## Builds

The app is linked to an EAS project (`extra.eas.projectId` in `app.json`) and `eas.json` has two build profiles.

| Profile | What it builds | API | Signing |
|---|---|---|---|
| `preview` | An Android APK for direct install (`distribution: internal`) | `https://api-preview.oddvex.com` | **The public debug key.** See below. |
| `production` | Store builds, version number raised automatically | `https://api.oddvex.com` | Real credentials kept by EAS. None are recorded as created yet; creating them is a Founder decision. |

**The preview APK is signed with a key everyone has.** The profile sets `withoutCredentials: true`, so EAS adds no
signing credentials and the build falls back to the Expo template's `debug.keystore` (password `android`), a file
published inside the `expo` npm package. The flag was added so that a build started from GitHub would not stop at
the prompt that creates a keystore. Whether such a build would create one by itself has not been established.

What that means:

- Anyone can build an APK for `com.oddvex.app` with the same signature. Android would install it over the preview
  app as an update, and it would then run as that app and could read what the app has saved, including the signed-in
  session.
- So the preview build is for the Founder's own test phone. It must never be passed around, posted where others
  can download it, or uploaded to a store. Install it only from the EAS build page it came from.
- A phone that has the preview build cannot install a build signed with a different key over it. Uninstall the
  preview app before installing any build signed with real credentials (a `production` build, or a `preview` build
  made after the flag is removed).

The `production` profile does not set the flag. Its builds are signed with real credentials that EAS keeps for the
project: an Android keystore, and on iOS a distribution certificate and provisioning profile. None are recorded
as created yet (docs/marketing/STORE_SUBMISSION_PREP.md, row B-7), so a production build cannot be signed until
they are. Creating or changing them is a decision for the Founder (PROJECT_CONSTITUTION.md, section 3). Moving the preview profile to
a private keystore means removing `withoutCredentials` and, to be safe, running one
`eas build -p android --profile preview` from a signed-in computer first, so the keystore exists before a GitHub
build needs it. EAS keeps one default Android keystore per application id, so the two profiles would then share it.

## Checks

```bash
pnpm --filter @oddvex/mobile typecheck      # tsc --noEmit
pnpm --filter @oddvex/mobile lint           # expo lint (eslint-config-expo)
pnpm --filter @oddvex/mobile test           # jest-expo + React Native Testing Library
pnpm --filter @oddvex/mobile export:check   # Metro + Hermes bundle for iOS and Android into dist/
```

`export:check` proves the JavaScript compiles and bundles. It does not build or launch a native app.

## Layout

```
src/
  app/            expo-router routes only
    _layout.tsx     providers, then a stack: the tabs, plus Log in and Create account as modals
    (tabs)/         native tabs, one stack per tab: (games) (props) (tracker) (tools) (settings)
  screens/        screen bodies the routes render
  components/     cards, forms, calculators, chart, badges, loading/empty/error states; for the community: the flag
                  gate, guidelines, profile form, pick card, share-a-pick, report control, record, and
                  community-copy.ts (its fixed sentences and the API-code-to-sentence mapping)
                  help-link.tsx holds the helpline phone links and the short line with its link
  providers/      session, feature flags, odds format (persisted), API meta (with its retry), font status
  session/        store.ts: the SecureStore-backed session. drafts.ts: unsaved form input kept across an
                  unexpected sign-out (useDraft)
  hooks/          useResource (fetch state), usePaged (cursor-paged lists), useSettledBets (the tracker's settled
                  list, paged by offset), useWatchlist, useMyProfile, useUnreadCount / useStakeReminder, useNow,
                  useTheme, shared stack options
  api/            client.ts (fetch, bearer token, error mapping, one function per endpoint), types.ts
  utils/          format.ts (display helpers ported from apps/web/src/lib/format.ts), routes.ts (web link to screen)
  test/           fixtures (fictional teams and sportsbooks), fake fetch, fake session, fake flags, screen strings
  theme.ts        every design token: colors for dark and light, spacing, radii, type sizes
  helpline.ts     the helpline facts and the sentences that give them; nothing else writes the number
```

Tests sit next to the file they test.

Routes: `/` Games, `/event/[id]`, `/assistant`, `/props`, `/player/[id]`, `/tracker`, `/log-bet`, `/tools`,
`/parlay`, `/value` (Tools stack), `/analytics` (Tracker stack), `/settings`, `/login`, `/signup`,
`/forgot-password`, `/reset-password`, `/verify-email` (the last five sit above the tabs), `/notifications` (`?tab=alerts` opens on the alert rules; it lives in
the Games tab's stack), `/community`, `/community/picks/[id]`, `/community/profiles/[handle]`, `/community/profile`,
`/community/leaderboard`, `/community/guidelines` (all in the Games tab's stack). The web links the API sends in assistant suggestions and notifications (`/app/games/{id}`
with an optional `?market=`, `/app/props/{id}`, `/app/tools`, `/app/tracker`, `/app/odds`, `/app/alerts`, `/app/community/picks/{id}`,
`/app/community/profiles/{handle}`, ...) are mapped to these by `appRoute` in `src/utils/routes.ts`. `/responsible-gambling`, which the
assistant's support replies link to, opens Settings and its responsible-gambling panel.

## Design

Tokens mirror `docs/design/DESIGN_SYSTEM.md`. Dark is the default; the light theme follows the system setting.
Components read colors through `useTheme()` and never use raw hex. Color is never the only signal: best price has the
word "Best", stale has the word "Stale" and a diamond instead of a dot, closed markets are written out, results are
badges with the word (Won, Lost, Push), chart bars carry Over / Under / Push, profit and loss carry a sign, and
Follow / Following changes its word and star as well as its selected state, unread notifications carry the word
"New", the unread count is a number, and an alert's state is written out (Active, Triggered, Paused, Expired). A pick's status is a word (Upcoming, Won, Lost, Push, Void), Like / Liked and Follow / Following change their word and their mark, and a blocked profile says so in a sentence. Analytics bars repeat every value as text, runs of wins and losses are plain text in the same color, and the edge on the value screen carries its sign. Tappable things are at least 44pt tall,
inputs have visible labels, and errors are announced as alerts and say what to do.

There are no select menus. Short choices (bet type, market, odds format, result) are wrapping pills with radio
semantics, which avoided adding a picker dependency.

## Types

`src/api/types.ts` aliases the generated schemas in `@oddvex/types` (`packages/types`, built from
`services/api/openapi.json`) with `import type`, so nothing from that package reaches the bundle and a schema change
shows up as a type error here. Regenerate with `pnpm types:generate` from the repo root. One adjustment: the
generator marks request fields that have a server-side default as required, so the request types make those
optional again (`Defaulted` in `types.ts`). The generated pick type is aliased as `CommunityPick` so it does not
shadow TypeScript's own `Pick`.

Routes are typed (`experiments.typedRoutes`). After adding a route file, regenerate `.expo/types/router.d.ts`
(git-ignored) with `npx expo customize tsconfig.json`, or `tsc` will reject links to the new route.
