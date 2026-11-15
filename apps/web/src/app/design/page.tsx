import type { Metadata } from "next";
import { Logo } from "@/components/ui/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Badge, Button, EmptyState, Field, Notice, Panel, PanelHeader, SelectField, Skeleton, Stat } from "@/components/ui/primitives";
import { GameLogBars, LineHistoryChart, Meter, ProfitChart, Sparkline } from "@/components/ui/charts";

export const metadata: Metadata = { title: "Design system", robots: { index: false } };

const SWATCHES = ["bg", "surface", "raised", "line", "line-strong", "ink", "muted", "accent", "second", "warn", "error"];
const T0 = Date.UTC(2026, 10, 1);
const HOUR = 3600000;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line py-8">
      <h2 className="mb-5 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function DesignPage() {
  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex items-center justify-between">
        <Logo />
        <ThemeToggle />
      </div>
      <h1 className="text-title font-semibold">Design system</h1>
      <p className="mt-2 max-w-2xl text-muted">Every shared component in its main states. Tokens are documented in docs/design/DESIGN_SYSTEM.md.</p>

      <div className="mt-8">
        <Section title="Color">
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
            {SWATCHES.map((name) => (
              <li key={name}>
                <div className="h-14 rounded-cell border border-line-strong" style={{ background: `var(--color-${name})` }} />
                <p className="num mt-1.5 text-xs text-muted">{name}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Type">
          <p className="text-display font-semibold">Every line.</p>
          <p className="mt-3 text-title font-semibold">A smarter perspective</p>
          <p className="mt-3 max-w-prose text-muted">Body copy is set in Geist Sans at 16px with a comfortable measure. Secondary text uses the muted tone.</p>
          <p className="num mt-3 text-xl">+142 −165 2.42 41.3% $1,250.00</p>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Log a bet</Button>
            <Button variant="secondary">Compare odds</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete bet</Button>
            <Button disabled>Saving</Button>
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
          </div>
        </Section>

        <Section title="Badges and notices">
          <div className="flex flex-wrap gap-2">
            <Badge>Final</Badge>
            <Badge tone="accent">Live</Badge>
            <Badge tone="second">Synthetic data</Badge>
            <Badge tone="warn">Stale</Badge>
            <Badge tone="error">Lost</Badge>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Notice title="Hit rate is a record, not a forecast">Seven of ten describes the past ten games.</Notice>
            <Notice tone="warn" title="These legs are correlated">A combined probability is not shown.</Notice>
            <Notice tone="error" title="The bet was not saved">Stake must be greater than zero.</Notice>
            <Notice tone="accent" title="Bet settled">Profit of +$42.00 recorded.</Notice>
          </div>
        </Section>

        <Section title="Form fields">
          <div className="grid max-w-2xl gap-4 sm:grid-cols-2">
            <Field id="ds-stake" label="Stake" inputMode="decimal" defaultValue="25.00" hint="In dollars." />
            <Field id="ds-odds" label="Odds" inputMode="decimal" defaultValue="-50" error="American odds can't be between −100 and +100." />
            <SelectField id="ds-format" label="Odds format" defaultValue="american">
              <option value="american">American</option>
              <option value="decimal">Decimal</option>
              <option value="fractional">Fractional</option>
            </SelectField>
          </div>
        </Section>

        <Section title="Panels, stats and states">
          <div className="grid gap-4 md:grid-cols-2">
            <Panel>
              <PanelHeader title="Performance" description="Settled bets, last 60 days" />
              <dl className="grid grid-cols-3 gap-4 p-5">
                <Stat label="Profit" value="+$182.40" tone="accent" />
                <Stat label="ROI" value="6.1%" />
                <Stat label="Record" value="21-17-2" hint="W-L-P" />
              </dl>
            </Panel>
            <Panel>
              <PanelHeader title="Pending bets" />
              <EmptyState title="No open bets" action={<Button size="sm">Log a bet</Button>}>
                Bets you log appear here until you settle them.
              </EmptyState>
            </Panel>
            <Panel className="p-5">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="mt-3 h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-2/3" />
            </Panel>
            <Panel className="space-y-4 p-5">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted">Line, last 48h</span>
                <Sparkline values={[128, 128, 132, 130, 136, 140, 142]} summary="Line rising from +128 to +142" tone="accent" />
              </div>
              <div>
                <p className="mb-1.5 text-sm text-muted">Hit rate 70%</p>
                <Meter value={0.7} label="Hit rate" />
              </div>
            </Panel>
          </div>
        </Section>

        <Section title="Charts">
          <div className="grid gap-4">
            <Panel className="p-4">
              <LineHistoryChart
                summary="Sample line history for three books"
                formatValue={(v) => (v > 0 ? `+${Math.round(v)}` : `${Math.round(v)}`)}
                formatTime={(t) => `${Math.round((T0 + 48 * HOUR - t) / HOUR)}h ago`}
                series={[
                  { name: "Cardinal (best)", emphasis: true, points: [0, 10, 22, 36, 44].map((h, i) => ({ t: T0 + h * HOUR, v: [128, 132, 136, 140, 142][i] })) },
                  { name: "Northline", points: [0, 14, 30, 46].map((h, i) => ({ t: T0 + h * HOUR, v: [126, 130, 134, 136][i] })) },
                  { name: "Beacon", points: [0, 20, 40].map((h, i) => ({ t: T0 + h * HOUR, v: [130, 134, 138][i] })) },
                ]}
              />
            </Panel>
            <Panel className="p-4">
              <GameLogBars
                line={22.5}
                summary="Sample game log: 6 of 10 games over 22.5 points"
                games={[19, 27, 24, 31, 18, 23, 22, 29, 26, 17].map((value, i) => ({ label: `G${i + 1}`, value, detail: `Game ${i + 1}: ${value}` }))}
              />
            </Panel>
            <Panel className="p-4">
              <ProfitChart
                summary="Sample cumulative profit ending at plus 182 dollars"
                points={[0, -20, 15, 40, 10, 85, 60, 120, 150, 182].map((v, i) => ({ t: T0 + i * 24 * HOUR * 6, v }))}
              />
            </Panel>
          </div>
        </Section>
      </div>
    </main>
  );
}
