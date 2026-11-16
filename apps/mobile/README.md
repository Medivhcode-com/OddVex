# OddVex mobile

The iOS and Android app. Expo SDK 58, React Native 0.88, React 19.3, TypeScript, expo-router.

OddVex is a sports-betting intelligence product. This app compares prices; it never takes or places wagers.

**Status: feature parity with the web app's signed-in loop, not yet run on a device or simulator.** Everything
below was checked by the type checker, the linter, unit and component tests, a JS bundle export for both platforms,
and a scripted run of the real API client against a locally running API. Nobody has looked at these screens on a
phone, in a simulator or in Expo Go. Treat layout, the native tab bar, modals, keyboard avoidance, safe areas,
Dynamic Type, screen reader behavior and SecureStore on real hardware as unverified until someone does. That
includes everything added for alerts and notifications: the bell in the Games header (drawn from plain views, with
no icon library) and its badge, the header's layout next to the "Synthetic data" badge, and refresh on focus.

## What is built

Five tabs: Games, Props, Tracker, Tools, Settings. Research screens work signed out; the tracker, the watchlist,
alerts and notifications need an account.

| Screen | What it does |
|---|---|
| Games (tab) | Events grouped Live / Upcoming / Final, league filter chips, pull to refresh. Best moneyline per side with the sportsbook's name. An "Ask OddVex AI" card. When logged in, "Your watchlist": live and upcoming games for what you follow (`GET /v1/watchlist/events`) and the players you follow. A bell in the header opens Notifications and shows the unread count as a number ("Notifications, 3 unread"); the badge is not drawn at zero. |
| Game detail | Market switcher, one row per sportsbook with price, freshness, hold, the word "Best" on the best price, no-vig consensus. Follow / Following toggles for the game and both teams. On a game that is not over, "Track a bet on this game" logs a structured leg (game, market, side, line, best price, sportsbook) so the tracker can settle it from the final score; signed out, it asks you to log in. Below it, "Set an alert" (also only while the game is not over): "Price reaches" (a side of the market selected in the switcher, with its line for spread and total, and an American price to reach, filled in a little above the current best), "Line moves" (spread and total; points, 1 by default), "Before the game starts" (15 or 30 minutes, 1 or 2 hours; upcoming games only) and "When the game ends", plus "Alert me before {team}'s games" for either team (60 minutes before each game). The API's 422 message is shown as sent. Opens on the market a link names (`/event/{id}?market=spread`). |
| Notifications | Reached from the bell and from Settings; one screen with two segments. **Notifications**: newest first, pull to refresh, "Load more" (`next_before`), the API's `title` and `body` unchanged, the word "New" on unread ones, "Mark all as read", a Delete button on each. Tapping one marks it read and opens the screen its web link maps to; a link with no screen here only marks it read. **Alerts**: your rules grouped Active / Triggered / Paused / Expired with the API's `summary`; Pause, Resume, "Set again" for a triggered rule, Delete after an inline confirmation, "Open game", and "Check now" (`POST /v1/alerts/evaluate`, reported as "Checked 4 alerts. 1 fired."). Signed out, it asks you to log in. |
| OddVex AI | Chat reached from the Games tab and from Settings. Example questions seeded from current games and props, `POST /v1/assistant/query`, suggestion chips that open the matching screen in this app, and the sources line and disclaimer under every answer. |
| Props (tab) | Prop board with league and stat filters: consensus line, best over and under with the book, last-10 over rate with its sample size. |
| Prop analyzer | Stat, window (5 / 10 / 20 / season) and split (all / home / away / vs opponent) selectors. Over rate with "x of n games" and the API's 95% Wilson range, averages, a game-log bar chart against the line (plain views, each bar labelled Over, Under or Push), per-book offers with Best / Stale / Suspended / Not offered in words, the API's caveat under "A record, not a forecast", the game log list, and a Follow toggle for the player. |
| Tracker (tab) | Signed out: an invitation to log in. Signed in: profit, ROI, record, average closing line value, open bets and exposure (`GET /v1/bets/summary`); open and settled bets with "Tied to a game", "Settled from final score" and "Synced" badges; settle (won, lost, push, void, half won, half lost, cashed out with the amount), settle a parlay leg by leg, edit stake / sportsbook / notes / closing odds, delete after confirmation; "Settle from final scores"; mock sportsbook sync (connect, sync now, disconnect and delete). When your weekly staking reminder has been reached, a notice at the top says so, says it is a reminder and not a limit, and gives 1-800-GAMBLER. Nothing is blocked. |
| Log a bet | Straight, parlay, same-game parlay or future; add and remove legs; American, decimal or fractional odds; league, sportsbook, stake, optional closing odds. OddVex records the bet. It does not place it. |
| Tools (tab) | Odds converter, no-vig (two or three sides), expected value, closing line value. Each posts to `/v1/quant/*`, shows the API's result and caveat, and has a "Show the working" toggle listing the API's steps. |
| Parlay research | Pick moneyline legs from current games or add a custom leg, set a stake, `POST /v1/quant/parlay`. Shows combined odds, payout and break-even. When the API reports correlated legs it shows the warning, the API's note, and "Not shown" for combined probability. |
| Settings (tab) | Account (name, email, log out; or log in / create account), odds format, data source notice, responsible-gambling line, a switch per kind of notification (`PUT /v1/me/notification-preferences` with only the kind that changed), the weekly staking reminder (amount, Save, Turn off, "You have staked $X this week"), change password, delete account with a typed DELETE confirmation, versions. |
| Log in, Create account | Modals above the tabs, so they open from any screen and close back to it. Create account needs a name, an email, a password of at least 10 characters and the "I am 21 or older…" switch. |

A "Synthetic data" badge sits in every header while the API reports `data_mode: "synthetic"`.

The app does no odds math. Prices, probabilities, payouts, hit rates, ranges, CLV and grading all arrive from the
API; `src/utils/format.ts` only formats, and forms send odds as typed for the API to parse. The two unit changes made
on the device are the ones the web app makes: a typed stake becomes a number, and a typed win probability in percent
becomes the fraction the API expects. The alert form adds two more of the same kind: it checks that a typed American
price is a whole number outside −100..+100 before sending it as typed, and it fills the price field with a
suggestion ten points above the current best (`suggestedThreshold`), which is a starting value for the user to edit,
not a calculation the app relies on.

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
- 429 shows "Too many attempts. Wait a minute, then try again."

## What is not built

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
  providers/      session, odds format (persisted), API meta, font status
  session/        store.ts: the SecureStore-backed session
  hooks/          useResource (fetch state), useWatchlist, useUnreadCount / useStakeReminder, useNow, useTheme,
                  shared stack options
  api/            client.ts (fetch, bearer token, error mapping, one function per endpoint), types.ts
  utils/          format.ts (display helpers ported from apps/web/src/lib/format.ts), routes.ts (web link to screen)
  test/           fixtures (fictional teams and sportsbooks), fake fetch, fake session
  theme.ts        every design token: colors for dark and light, spacing, radii, type sizes
```

Tests sit next to the file they test.

Routes: `/` Games, `/event/[id]`, `/assistant`, `/props`, `/player/[id]`, `/tracker`, `/log-bet`, `/tools`,
`/parlay`, `/settings`, `/login`, `/signup`, `/notifications` (`?tab=alerts` opens on the alert rules; it lives in
the Games tab's stack). The web links the API sends in assistant suggestions and notifications (`/app/games/{id}`
with an optional `?market=`, `/app/props/{id}`, `/app/tools`, `/app/tracker`, `/app/odds`, `/app/alerts`, ...) are
mapped to these by `appRoute` in `src/utils/routes.ts`.

## Design

Tokens mirror `docs/design/DESIGN_SYSTEM.md`. Dark is the default; the light theme follows the system setting.
Components read colors through `useTheme()` and never use raw hex. Color is never the only signal: best price has the
word "Best", stale has the word "Stale" and a diamond instead of a dot, closed markets are written out, results are
badges with the word (Won, Lost, Push), chart bars carry Over / Under / Push, profit and loss carry a sign, and
Follow / Following changes its word and star as well as its selected state, unread notifications carry the word
"New", the unread count is a number, and an alert's state is written out (Active, Triggered, Paused, Expired). Tappable things are at least 44pt tall,
inputs have visible labels, and errors are announced as alerts and say what to do.

There are no select menus. Short choices (bet type, market, odds format, result) are wrapping pills with radio
semantics, which avoided adding a picker dependency.

## Types

`src/api/types.ts` aliases the generated schemas in `@oddvex/types` (`packages/types`, built from
`services/api/openapi.json`) with `import type`, so nothing from that package reaches the bundle and a schema change
shows up as a type error here. Regenerate with `pnpm types:generate` from the repo root. One adjustment: the
generator marks request fields that have a server-side default as required, so the request types make those
optional again (`Defaulted` in `types.ts`).
