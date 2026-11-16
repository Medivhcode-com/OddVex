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

## What is built

Five tabs: Games, Props, Tracker, Tools, Settings. Research screens work signed out; the tracker, its analytics,
the watchlist, alerts and notifications need an account. Three features sit behind the API's feature flags (see
"Feature flags").

| Screen | What it does |
|---|---|
| Games (tab) | Events grouped Live / Upcoming / Final, league filter chips, pull to refresh. Best moneyline per side with the sportsbook's name. An "Ask OddVex AI" card. When logged in, "Your watchlist": live and upcoming games for what you follow (`GET /v1/watchlist/events`) and the players you follow. A bell in the header opens Notifications and shows the unread count as a number ("Notifications, 3 unread"); the badge is not drawn at zero. |
| Value screen | Flag `value_screen`. Reached from a panel at the top of the Tools tab and from a link row on Games. `GET /v1/value` with league, market and smallest-edge filters (the three fixed sizes are sent as the fractions the API takes). The API's `caveat` ("A price above the consensus is not proof of an edge…") and `method` sit above the rows. Each row: the game, the outcome with its line, the best price with its sportsbook and age, "Consensus of N other books: 47.3%", "Break-even at this price", and "Edge vs consensus" as a signed percentage. Tapping a row opens that game on that market. An empty screen says that on many slates nothing qualifies. Loading, error with retry, pull to refresh. The screen never calls the number anything but "Edge vs consensus"; a test fails if "guarantee", "lock", "free money", "risk-free", "+EV", "pick" or "profit" appears in any string on it. |
| Game detail | Market switcher, one row per sportsbook with price, freshness, hold, the word "Best" on the best price, no-vig consensus. Follow / Following toggles for the game and both teams. On a game that is not over, "Track a bet on this game" logs a structured leg (game, market, side, line, best price, sportsbook) so the tracker can settle it from the final score; signed out, it asks you to log in. Below it, "Set an alert" (also only while the game is not over): "Price reaches" (a side of the market selected in the switcher, with its line for spread and total, and an American price to reach, filled in a little above the current best), "Line moves" (spread and total; points, 1 by default), "Before the game starts" (15 or 30 minutes, 1 or 2 hours; upcoming games only) and "When the game ends", plus "Alert me before {team}'s games" for either team (60 minutes before each game). The API's 422 message is shown as sent. Opens on the market a link names (`/event/{id}?market=spread`). |
| Notifications | Reached from the bell and from Settings; one screen with two segments. **Notifications**: newest first, pull to refresh, "Load more" (`next_before`), the API's `title` and `body` unchanged, the word "New" on unread ones, "Mark all as read", a Delete button on each. Tapping one marks it read and opens the screen its web link maps to; a link with no screen here only marks it read. **Alerts**: your rules grouped Active / Triggered / Paused / Expired with the API's `summary`; Pause, Resume, "Set again" for a triggered rule, Delete after an inline confirmation, "Open game", and "Check now" (`POST /v1/alerts/evaluate`, reported as "Checked 4 alerts. 1 fired."). Signed out, it asks you to log in. |
| OddVex AI | Chat reached from the Games tab and from Settings. Example questions seeded from current games and props, `POST /v1/assistant/query`, suggestion chips that open the matching screen in this app, and the sources line and disclaimer under every answer. |
| Props (tab) | Prop board with league and stat filters: consensus line, best over and under with the book, last-10 over rate with its sample size. |
| Prop analyzer | Stat, window (5 / 10 / 20 / season) and split (all / home / away / vs opponent) selectors. Over rate with "x of n games" and the API's 95% Wilson range, averages, a game-log bar chart against the line (plain views, each bar labelled Over, Under or Push), per-book offers with Best / Stale / Suspended / Not offered in words, the API's caveat under "A record, not a forecast", the game log list, and a Follow toggle for the player. |
| Tracker (tab) | Signed out: an invitation to log in. Signed in: profit, ROI, record, average closing line value, open bets and exposure (`GET /v1/bets/summary`); open and settled bets with "Tied to a game", "Settled from final score" and "Synced" badges; settle (won, lost, push, void, half won, half lost, cashed out with the amount), settle a parlay leg by leg, edit stake / sportsbook / notes / closing odds, delete after confirmation; "Settle from final scores"; mock sportsbook sync (connect, sync now, disconnect and delete). When your weekly staking reminder has been reached, a notice at the top says so, says it is a reminder and not a limit, and gives 1-800-GAMBLER. Nothing is blocked. |
| Analytics | Flag `tracker_analytics`. "Open analytics" on the Tracker tab when signed in. `GET /v1/bets/analytics`: results by odds band, weekday and month as labelled bars drawn from plain views, each with its values written out ("7 bets · $175.00 staked · profit −$12.50 · ROI −7.1% · win rate 42.9%"); average stake and average odds; runs ("2 losses in a row", longest run of wins and of losses) in plain text with no color, plus the API's `streak_note` when it sends one (the field is not in the schema yet; `types.ts` declares it optional); closing line value (average, share above the close, buckets); stake sizes; the API's `sample_note` as a "Small sample" caution when present, and its `note` at the foot. Empty state when nothing is settled. The bar lengths are the only arithmetic: a row's count against the largest count in its list. |
| Log a bet | Straight, parlay, same-game parlay or future; add and remove legs; American, decimal or fractional odds; league, sportsbook, stake, optional closing odds. OddVex records the bet. It does not place it. |
| Tools (tab) | Odds converter, no-vig (two or three sides), expected value, closing line value. Each posts to `/v1/quant/*`, shows the API's result and caveat, and has a "Show the working" toggle listing the API's steps. |
| Parlay research | Pick moneyline legs from current games or add a custom leg, set a stake, `POST /v1/quant/parlay`. Shows combined odds, payout and break-even. When the API reports correlated legs it shows the warning, the API's note, and "Not shown" for combined probability. |
| Settings (tab) | Account (name, email, "Email verified" or "Email not verified", the plan when the API sends one, "Preview: every feature is included" while `GET /v1/me/entitlements` reports `preview`, log out; or log in / create account). While the address is not verified and `email_flows` is on, "Send verification email" (`POST /v1/auth/verify-email/request`) shows the API's confirmation and the preview statement below. There is no purchase or upgrade UI anywhere. Then odds format, data source notice, responsible-gambling line, a switch per kind of notification (`PUT /v1/me/notification-preferences` with only the kind that changed), the weekly staking reminder (amount, Save, Turn off, "You have staked $X this week"), change password, delete account with a typed DELETE confirmation, versions. |
| Log in, Create account | Modals above the tabs, so they open from any screen and close back to it. Create account needs a name, an email, a password of at least 10 characters and the "I am 21 or older…" switch. With `email_flows` on, Log in has "Forgot password?". After a suspension it shows "This account can't be used right now" (see "Accounts and the token"). |
| Reset your password (`/forgot-password`) | Takes an email, `POST /v1/auth/password-reset/request`, and always answers "If an account exists for that address, a reset link has been sent." whether or not the address has an account, with the preview statement. 429 shows "Too many attempts. Wait a minute, then try again." |
| Set a new password (`/reset-password?token=`) | New password (at least 10 characters) and a confirmation field, `POST /v1/auth/password-reset/confirm`, then the saved session on the device is cleared and Log in opens with "Password changed. Log in with your new password." A used or expired link says so and offers a new one; a link with no token says it is incomplete. |
| Confirm your email address (`/verify-email?token=`) | A "Confirm email address" button calls `POST /v1/auth/verify-email/confirm` and shows "Email address confirmed." or "This link has expired or was already used." Like the web page, opening the link spends nothing: the token works once, so it is used only when the button is pressed. Works signed out; signed in, the user is read again so Settings shows "Email verified". |

A "Synthetic data" badge sits in every header while the API reports `data_mode: "synthetic"`.

The app does no odds math. Prices, probabilities, payouts, hit rates, ranges, CLV and grading all arrive from the
API; `src/utils/format.ts` only formats, and forms send odds as typed for the API to parse. The two unit changes made
on the device are the ones the web app makes: a typed stake becomes a number, and a typed win probability in percent
becomes the fraction the API expects. The alert form adds two more of the same kind: it checks that a typed American
price is a whole number outside −100..+100 before sending it as typed, and it fills the price field with a
suggestion ten points above the current best (`suggestedThreshold`), which is a starting value for the user to edit,
not a calculation the app relies on.

## Feature flags

`src/providers/flags.tsx` reads `GET /v1/flags` when the app starts, each time it returns to the foreground and
after a sign-in. The app acts on three flags: `value_screen` (the Tools panel and the Games link row),
`tracker_analytics` (the Tracker's Analytics panel) and `email_flows` ("Forgot password?" and "Send verification
email"). An entry point is drawn only while its flag is on.

- **Off until known.** A flagged entry point is hidden while the flags are loading, when the call failed and
  nothing was loaded earlier, and when the API's answer does not list the flag. If a later read fails, the last
  flags loaded stay in use.
- **Everything else is unaffected.** Games, props, the tracker, calculators, parlay research, alerts,
  notifications, the assistant and the account screens existed before flags and never ask for one, so a failed
  flags call hides nothing of theirs.
- **A flag can change under the app.** If a flagged call answers 404 `feature_disabled` (a deep link, or a flag
  turned off since the last read), the screen shows "This feature isn't available right now." with no retry, and
  the flags are read again so the entry point goes away.

`premium_gating` and `community` are not read. Nothing in the app is gated by plan.

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
  opens. A 401 for a wrong password does not do this.
- Changing the password returns a new token, which replaces the stored one. Log out and delete account clear it.
  A completed password reset returns no token: the saved session is cleared and the user logs in again.
- A suspended account: `401 account_suspended` on any call that carried the token, or `403 account_suspended` on
  log in, clears the session from memory and SecureStore. The log in screen then says "This account can't be used
  right now", that the person has been signed out on this device, that their bets and settings are kept, and that
  a copy of the data or its deletion can be asked for from OddVex support (text only; the repo defines no support
  address yet, so none is shown). The message goes away after the next successful log in.
- 429 shows "Too many attempts. Wait a minute, then try again."

## What is not built

- Any purchase, upgrade or pricing UI. Plans are shown, never sold; nothing is gated by plan.
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
- Token refresh. When the token expires you are asked to log in again.
- Push notifications, email, alert sounds, an app icon badge and background checks (see "Alerts and notifications
  are in-app only"). An unread-only filter on the notification list. Alerts on player props.
- A tappable phone link on the responsible-gambling line, tablet layouts, web
  (`react-native-web` is not installed).
- Final app icon and splash art. EAS project, build profiles, store configuration: none exist; nothing has been
  published.
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
  components/     cards, forms, calculators, chart, badges, loading/empty/error states
  providers/      session, feature flags, odds format (persisted), API meta, font status
  session/        store.ts: the SecureStore-backed session
  hooks/          useResource (fetch state), useWatchlist, useUnreadCount / useStakeReminder, useNow, useTheme,
                  shared stack options
  api/            client.ts (fetch, bearer token, error mapping, one function per endpoint), types.ts
  utils/          format.ts (display helpers ported from apps/web/src/lib/format.ts), routes.ts (web link to screen)
  test/           fixtures (fictional teams and sportsbooks), fake fetch, fake session, fake flags, screen strings
  theme.ts        every design token: colors for dark and light, spacing, radii, type sizes
```

Tests sit next to the file they test.

Routes: `/` Games, `/event/[id]`, `/assistant`, `/props`, `/player/[id]`, `/tracker`, `/log-bet`, `/tools`,
`/parlay`, `/value` (Tools stack), `/analytics` (Tracker stack), `/settings`, `/login`, `/signup`,
`/forgot-password`, `/reset-password`, `/verify-email` (the last five sit above the tabs), `/notifications` (`?tab=alerts` opens on the alert rules; it lives in
the Games tab's stack). The web links the API sends in assistant suggestions and notifications (`/app/games/{id}`
with an optional `?market=`, `/app/props/{id}`, `/app/tools`, `/app/tracker`, `/app/odds`, `/app/alerts`, ...) are
mapped to these by `appRoute` in `src/utils/routes.ts`.

## Design

Tokens mirror `docs/design/DESIGN_SYSTEM.md`. Dark is the default; the light theme follows the system setting.
Components read colors through `useTheme()` and never use raw hex. Color is never the only signal: best price has the
word "Best", stale has the word "Stale" and a diamond instead of a dot, closed markets are written out, results are
badges with the word (Won, Lost, Push), chart bars carry Over / Under / Push, profit and loss carry a sign, and
Follow / Following changes its word and star as well as its selected state, unread notifications carry the word
"New", the unread count is a number, and an alert's state is written out (Active, Triggered, Paused, Expired). Analytics bars repeat every value as text, runs of wins and losses are plain text in the same color, and the edge on the value screen carries its sign. Tappable things are at least 44pt tall,
inputs have visible labels, and errors are announced as alerts and say what to do.

There are no select menus. Short choices (bet type, market, odds format, result) are wrapping pills with radio
semantics, which avoided adding a picker dependency.

## Types

`src/api/types.ts` aliases the generated schemas in `@oddvex/types` (`packages/types`, built from
`services/api/openapi.json`) with `import type`, so nothing from that package reaches the bundle and a schema change
shows up as a type error here. Regenerate with `pnpm types:generate` from the repo root. One adjustment: the
generator marks request fields that have a server-side default as required, so the request types make those
optional again (`Defaulted` in `types.ts`). One addition: `BetAnalytics` declares an optional `streak_note`, which
the API does not publish yet; remove it once the generated type has the field.

Routes are typed (`experiments.typedRoutes`). After adding a route file, regenerate `.expo/types/router.d.ts`
(git-ignored) with `npx expo customize tsconfig.json`, or `tsc` will reject links to the new route.
