import { useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, quantClv, quantConvert, quantEv, quantNoVig } from '@/api/client';
import type { ClvResult, ConvertResult, EntryOddsFormat, EvResult, NoVigResult } from '@/api/types';
import { Choice, Field } from '@/components/form';
import { Button, Notice, Panel, PanelHeading, Stat, StatGrid, Working } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, space } from '@/theme';
import { cleanOdds, formatAmerican, formatMoney, formatPercent, formatSignedPercent } from '@/utils/format';

const FORMATS: readonly { value: EntryOddsFormat; label: string }[] = [
  { value: 'american', label: 'American' },
  { value: 'decimal', label: 'Decimal' },
  { value: 'fractional', label: 'Fractional' },
];

/**
 * Runs one calculation on the API and holds its result or error. The app never works a number out itself:
 * what is typed goes to `/v1/quant/*` and what comes back is displayed.
 */
function useCalc<Body, Result>(request: (body: Body) => Promise<Result>) {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(body: Body) {
    setBusy(true);
    setError(null);
    try {
      setResult(await request(body));
    } catch (caught) {
      setResult(null);
      setError(describeError(caught, 'The calculation failed. Check the values and try again.'));
    } finally {
      setBusy(false);
    }
  }
  return { result, error, busy, run };
}

function Calc({ title, description, error, children }: { title: string; description: string; error: string | null; children: ReactNode }) {
  return (
    <Panel>
      <View style={styles.calc}>
        <PanelHeading title={title} description={description} />
        {children}
        {error ? <Notice tone="error" text={error} /> : null}
      </View>
    </Panel>
  );
}

function OddsFormatChoice({ name, value, onChange }: { name: string; value: EntryOddsFormat; onChange: (format: EntryOddsFormat) => void }) {
  return <Choice label={`${name} odds format`} options={FORMATS} value={value} onChange={onChange} />;
}

function Results({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View accessibilityLabel={label} accessibilityLiveRegion="polite" style={styles.results}>
      {children}
    </View>
  );
}

export function ConvertCalculator() {
  const [odds, setOdds] = useState('-110');
  const [format, setFormat] = useState<EntryOddsFormat>('american');
  const calc = useCalc<Parameters<typeof quantConvert>[0], ConvertResult>(quantConvert);
  const price = calc.result?.price;
  return (
    <Calc title="Odds converter" description="Turn a price into every format and the probability it implies." error={calc.error}>
      <Field label="Odds to convert" mono keyboardType="numbers-and-punctuation" value={odds} onChangeText={setOdds} />
      <OddsFormatChoice name="Converter" value={format} onChange={setFormat} />
      <Button label="Convert" disabled={calc.busy} onPress={() => calc.run({ odds: cleanOdds(odds), odds_format: format })} />
      {calc.result && price ? (
        <Results label="Converted price">
          <StatGrid>
            <Stat label="American" value={formatAmerican(price.american)} />
            <Stat label="Decimal" value={price.decimal.toFixed(3)} />
            <Stat label="Fractional" value={price.fractional} />
            <Stat label="Implied probability" value={formatPercent(price.implied_probability, 2)} />
          </StatGrid>
          <Working steps={calc.result.steps} />
        </Results>
      ) : null}
    </Calc>
  );
}

export function NoVigCalculator() {
  const theme = useTheme();
  const [sides, setSides] = useState(['-110', '-110']);
  const [format, setFormat] = useState<EntryOddsFormat>('american');
  const calc = useCalc<Parameters<typeof quantNoVig>[0], NoVigResult>(quantNoVig);
  return (
    <Calc title="No-vig calculator" description="Enter every side of one market to remove the sportsbook's margin." error={calc.error}>
      {sides.map((side, index) => (
        <Field
          key={index}
          label={`Side ${index + 1}`}
          mono
          keyboardType="numbers-and-punctuation"
          value={side}
          onChangeText={(text) => setSides((current) => current.map((value, i) => (i === index ? text : value)))}
        />
      ))}
      <OddsFormatChoice name="No-vig" value={format} onChange={setFormat} />
      <View style={styles.actions}>
        <Button label="Remove the vig" disabled={calc.busy} onPress={() => calc.run({ odds: sides.map(cleanOdds), odds_format: format })} />
        <Button
          label={sides.length === 2 ? 'Add a third side' : 'Use two sides'}
          variant="secondary"
          onPress={() => setSides((current) => (current.length === 2 ? [...current, ''] : current.slice(0, 2)))}
        />
      </View>
      {calc.result ? (
        <Results label="No-vig result">
          {calc.result.outcomes.map((outcome, index) => (
            <View
              key={index}
              accessible
              accessibilityLabel={`${outcome.label}: price ${formatAmerican(outcome.price.american)}, implied ${formatPercent(outcome.implied_probability, 2)}, no-vig ${formatPercent(outcome.no_vig_probability, 2)}, fair price ${formatAmerican(outcome.fair_price.american)}`}
              style={[styles.outcome, { borderTopColor: theme.border }]}>
              <View style={styles.outcomeHead}>
                <Txt weight="semibold">{outcome.label}</Txt>
                <Num>{formatAmerican(outcome.price.american)}</Num>
              </View>
              <View style={styles.triple}>
                <Mini label="Implied" value={formatPercent(outcome.implied_probability, 2)} />
                <Mini label="No-vig" value={formatPercent(outcome.no_vig_probability, 2)} strong />
                <Mini label="Fair price" value={formatAmerican(outcome.fair_price.american)} />
              </View>
            </View>
          ))}
          <StatGrid>
            <Stat label="Overround" value={formatPercent(calc.result.overround, 2)} hint="Implied probabilities minus 100%" />
            <Stat label="Hold" value={formatPercent(calc.result.hold, 2)} hint="The book's theoretical margin" />
          </StatGrid>
          <Working steps={calc.result.steps} />
        </Results>
      ) : null}
    </Calc>
  );
}

function Mini({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.mini}>
      <Txt variant="caption" tone="muted">
        {label}
      </Txt>
      <Num size={fontSize.secondary} tone={strong ? 'text' : 'muted'} weight={strong ? 'semibold' : 'regular'}>
        {value}
      </Num>
    </View>
  );
}

const signTone = (value: number) => (value > 0 ? 'accent' : value < 0 ? 'error' : undefined);

export function EvCalculator() {
  const [odds, setOdds] = useState('+150');
  const [format, setFormat] = useState<EntryOddsFormat>('american');
  const [probability, setProbability] = useState('45');
  const [stake, setStake] = useState('100');
  const [localError, setLocalError] = useState<string | null>(null);
  const calc = useCalc<Parameters<typeof quantEv>[0], EvResult>(quantEv);

  const submit = () => {
    const percent = Number(probability);
    if (!(percent > 0 && percent < 100)) return setLocalError('Enter a win probability between 0 and 100.');
    setLocalError(null);
    // The percentage typed becomes the fraction the API expects; that is a unit change, not betting math.
    return calc.run({ odds: cleanOdds(odds), odds_format: format, win_probability: percent / 100, stake: Number(stake) || 1 });
  };

  const result = localError ? null : calc.result;
  return (
    <Calc title="Expected value" description="What a bet is worth on average, if your win probability is right." error={localError ?? calc.error}>
      <Field label="Odds for expected value" mono keyboardType="numbers-and-punctuation" value={odds} onChangeText={setOdds} />
      <OddsFormatChoice name="Expected value" value={format} onChange={setFormat} />
      <Field label="Your win probability (%)" mono keyboardType="decimal-pad" value={probability} onChangeText={setProbability} />
      <Field label="Expected value stake ($)" mono keyboardType="decimal-pad" value={stake} onChangeText={setStake} />
      <Button label="Calculate expected value" disabled={calc.busy} onPress={submit} />
      {result ? (
        <Results label="Expected value result">
          <StatGrid>
            <Stat label="Expected value" value={formatSignedPercent(result.ev_per_unit, 2)} tone={signTone(result.ev_per_unit)} hint="Per dollar staked" />
            <Stat label="Expected profit" value={formatMoney(result.expected_profit, { signed: true })} hint={`On a ${formatMoney(result.stake)} stake`} />
            <Stat label="Break-even" value={formatPercent(result.breakeven_probability, 2)} hint="Win rate needed at this price" />
            <Stat label="Edge" value={formatSignedPercent(result.edge, 2)} hint="Your probability minus break-even" />
          </StatGrid>
          <Notice title="Only as good as the probability you entered" text={result.caveat} />
          <Working steps={result.steps} />
        </Results>
      ) : null}
    </Calc>
  );
}

export function ClvCalculator() {
  const [odds, setOdds] = useState('+150');
  const [closing, setClosing] = useState('+135');
  const [opposite, setOpposite] = useState('');
  const [format, setFormat] = useState<EntryOddsFormat>('american');
  const calc = useCalc<Parameters<typeof quantClv>[0], ClvResult>(quantClv);
  const result = calc.result;
  return (
    <Calc title="Closing line value" description="Compare the price you took with where the market closed." error={calc.error}>
      <Field label="Price you took" mono keyboardType="numbers-and-punctuation" value={odds} onChangeText={setOdds} />
      <Field label="Closing price" mono keyboardType="numbers-and-punctuation" value={closing} onChangeText={setClosing} />
      <Field
        label="Closing price, other side"
        mono
        keyboardType="numbers-and-punctuation"
        placeholder="Optional"
        value={opposite}
        onChangeText={setOpposite}
      />
      <OddsFormatChoice name="Closing line value" value={format} onChange={setFormat} />
      <Button
        label="Calculate closing line value"
        disabled={calc.busy}
        onPress={() =>
          calc.run({
            odds: cleanOdds(odds),
            closing_odds: cleanOdds(closing),
            closing_opposite_odds: opposite.trim() ? cleanOdds(opposite) : null,
            odds_format: format,
          })
        }
      />
      {result ? (
        <Results label="Closing line value result">
          <StatGrid>
            <Stat
              label="Closing line value"
              value={formatSignedPercent(result.clv, 2)}
              tone={signTone(result.clv)}
              hint={result.beat_close ? 'You beat the close' : 'The close was as good or better'}
            />
            <Stat
              label="Closing no-vig probability"
              value={formatPercent(result.closing_no_vig_probability, 2)}
              hint="Needs the other side's closing price"
            />
            <Stat
              label="Probability gained"
              value={formatSignedPercent(result.no_vig_probability_delta, 2)}
              hint="Closing no-vig minus your break-even"
            />
          </StatGrid>
          <Working steps={result.steps} />
        </Results>
      ) : null}
    </Calc>
  );
}

const styles = StyleSheet.create({
  calc: { gap: space[3] },
  results: { gap: space[3], paddingTop: space[1] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
  outcome: { gap: space[2], paddingTop: space[3], borderTopWidth: StyleSheet.hairlineWidth },
  outcomeHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: space[3] },
  triple: { flexDirection: 'row', gap: space[4] },
  mini: { gap: 2 },
});
