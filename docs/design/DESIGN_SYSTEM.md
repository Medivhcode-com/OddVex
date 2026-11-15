# OddVex design system

Source of truth for tokens: `apps/web/src/app/globals.css`. Components: `apps/web/src/components/ui`. Live showcase:
`/design` in the web app (also the target of the visual regression test).

## Idea

A trading terminal's discipline with a consumer app's legibility. The interface is quiet so the numbers can be loud.
The one signature device is the **best-price notch**: a mint inset bar and tint on the best open price in a row,
always paired with the word "Best". The same notch marks the active item in navigation.

## Color

Semantic tokens only. Components never use raw hex.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#090D16` | `#F4F6FA` | Page |
| `surface` | `#121A29` | `#FFFFFF` | Panels, tables |
| `raised` | `#1B2638` | `#EBEFF5` | Hover, selected, skeletons |
| `line` / `line-strong` | `#2A3648` / `#3B4A61` | `#D3DAE5` / `#AAB5C5` | Borders, input outlines |
| `ink` | `#F5F8FC` | `#0D1422` | Primary text |
| `muted` | `#98A7BA` | `#515F75` | Secondary text |
| `accent` | `#43E6B1` | `#06694B` | Best price, primary action, positive result |
| `second` | `#748BFF` | `#3F52D0` | Focus ring, reference lines, information |
| `warn` | `#F5B84B` | `#8F5A00` | Stale data, cautions |
| `error` | `#F16B77` | `#BD2F40` | Errors, losses |

Light mode is tuned separately: accents are darkened so text-on-surface contrast stays at or above 4.5:1.

**Color is never the only signal.** Best price has a label. Stale has a label and a diamond instead of a dot.
Over/under bars carry text. Chart series differ by dash pattern. Profit and loss carry a sign.

## Type

- **Geist Sans** for interface and display. Display sizes are set tight (−0.035em) at weight 600.
- **IBM Plex Mono** (`.num`) for anything compared digit by digit: prices, lines, money, percentages. Always tabular.
- Sentence case everywhere. No all-caps labels.
- Scale: display `clamp(2.5rem…4.75rem)`, title `clamp(1.75rem…2.5rem)`, page heading 1.5rem, panel heading
  0.9375rem, body 1rem, secondary 0.875rem, caption 0.75rem. Prose is capped at 68 characters.

## Shape, depth, spacing

- Radii: `cell` 6px for controls and data cells, `panel` 12px for containers, full for pills and filters.
- Depth comes from borders and surface steps, not shadows. The only shadow is on floating menus.
- 4px spacing grid. Panels pad 16px on phones and 20px from `sm`.
- Touch targets are at least 44px tall for primary controls and 36px for dense filters.

## Motion

- One orchestrated moment: the hero board settles in on first load (`.ov-resolve`).
- Otherwise motion only answers an action: colour transitions on hover and press, 150ms.
- `prefers-reduced-motion` removes all of it.

## Components

| Component | File | Notes |
|---|---|---|
| Button, ButtonLink | `ui/primitives.tsx` | primary, secondary, ghost, danger; sm, md, lg |
| Panel, PanelHeader | `ui/primitives.tsx` | The standard container |
| Badge | `ui/primitives.tsx` | neutral, accent, second, warn, error |
| Stat | `ui/primitives.tsx` | Label over a mono value with an optional hint |
| Notice | `ui/primitives.tsx` | Inline message with an icon glyph per tone |
| Field, SelectField | `ui/primitives.tsx` | Labelled inputs with hint and error wiring |
| Segmented | `ui/primitives.tsx` | URL-driven filter pills |
| Skeleton, EmptyState | `ui/primitives.tsx` | Loading and empty states |
| Sparkline, LineHistoryChart, GameLogBars, ProfitChart, Meter | `ui/charts.tsx` | Server-rendered SVG with text summaries |
| Price, OddsFormatToggle | `app/odds-format.tsx` | Renders a price in the chosen format |
| Freshness | `app/freshness.tsx` | Ticking "Updated 42s ago", stale variant |
| SideNav, BottomNav | `app/nav.tsx` | Sidebar from `lg`, bottom bar below |

## States every data screen handles

Loading (skeleton, `role="status"`), empty (what to do next), stale (labelled, excluded from best), suspended or
unavailable (said in words), and failure (what happened, a retry, and a reassurance about the user's own data).

## Accessibility baseline

WCAG 2.2 AA target. Visible focus ring on every interactive element, skip link, landmarks and labelled navigation,
tables with captions and scoped headers, charts with `role="img"` and a text summary, form errors tied to fields with
`aria-describedby`, and no information carried by colour alone. Automated checks cover a subset. A manual screen
reader pass is still required before launch.
