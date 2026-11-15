# OddVex mobile

The iOS and Android app. Expo SDK 58, React Native 0.88, React 19.3, TypeScript, expo-router.

OddVex is a sports-betting intelligence product. This app compares prices; it never takes or places wagers.

**Status: first slice, not yet run on a device or simulator.** Everything below was checked by type checker, linter,
unit and component tests, a JS bundle export for both platforms, and a smoke test of the API client and the list and
odds components against a locally running API. Nobody has looked at these screens on a phone yet. Treat layout,
native tab bar appearance, fonts, safe areas, Dynamic Type and screen reader behavior as unverified until someone does.

## What is built

| Screen | What it does |
|---|---|
| Games (tab) | Events grouped Live / Upcoming / Final, league filter chips, pull to refresh. Each card shows the status in words, both teams, the score if there is one, and the best moneyline per side with the sportsbook's name (plus the draw for three-way markets). Loading skeleton, empty state, and an error state with a retry. |
| Game detail | Market switcher (moneyline, spread, total). One row per sportsbook with each outcome's price, freshness ("42s ago" or "Stale, 9 min ago"), and hold. The best price gets an accent bar, a tint and the word "Best". Suspended and not-offered markets are spelled out. No-vig consensus row. Pull to refresh. |
| Settings (tab) | Odds format (American or decimal, saved on the device with AsyncStorage), the data source notice driven by `GET /v1/meta`, the responsible-gambling line, app and data service versions. |

A "Synthetic data" badge sits in every header while the API reports `data_mode: "synthetic"`.

The app does no odds math. Prices arrive with `american`, `decimal` and `implied_probability`; `is_best`, `is_stale`,
`consensus` and `holds` are computed by the API. `src/utils/format.ts` only formats.

## What is not built

- Accounts, sign-in, bet tracking, player props, the assistant, line history, notifications.
- Automatic refresh. Prices update when you pull to refresh or switch market. The "ago" labels keep counting.
- Offline cache. With no connection you get the error state.
- A tappable phone link on the responsible-gambling line. It is plain, selectable text.
- Tablet layouts and web. `react-native-web` is not installed.
- Final app icon and splash art. `assets/images` holds the Expo template placeholders.
- EAS project, build profiles, store configuration. None exist; nothing has been published.
- Geist Sans. Interface text uses the system face (San Francisco, Roboto). Numbers use IBM Plex Mono.

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
(`npx expo run:ios`, `npx expo run:android`) also works and is what you want once native modules beyond Expo Go's
are added. The generated `ios/` and `android/` folders are git-ignored.

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
  app/            expo-router routes only: native tabs, one stack per tab
  screens/        screen bodies the routes render
  components/     game card, odds row, badges, choice controls, loading/empty/error states
  providers/      odds format (persisted), API meta, font status
  hooks/          useResource (fetch state), useNow, useTheme, shared stack options
  api/            client.ts (fetch + error mapping), types.ts (response shapes)
  utils/          format.ts (display helpers ported from apps/web/src/lib/format.ts)
  test/           fixtures (fictional teams and sportsbooks)
  theme.ts        every design token: colors for dark and light, spacing, radii, type sizes
```

Tests sit next to the file they test.

## Design

Tokens mirror `docs/design/DESIGN_SYSTEM.md`. Dark is the default; the light theme follows the system setting.
Components read colors through `useTheme()` and never use raw hex. Color is never the only signal: best price has the
word "Best", stale has the word "Stale" and a diamond instead of a dot, closed markets are written out.

## Types

`src/api/types.ts` is a hand copy of the shapes in `apps/web/src/lib/types.ts`, checked by hand against
`services/api/openapi.json`. Unlike the web app there is no compile-time contract test against `@oddvex/types` yet.
When the API schema changes, update this file too.
