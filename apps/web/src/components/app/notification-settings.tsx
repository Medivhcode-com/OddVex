"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatMoney } from "@/lib/format";

type Prefs = Schemas["InAppPreferencesOut"];
const LABELS: [keyof Prefs, string][] = [
  ["price_alert", "Price alerts"],
  ["line_move", "Line moves"],
  ["game_start", "Game start"],
  ["game_final", "Final scores"],
  ["bet_settled", "Settled bets"],
  ["sync_finished", "Sync results"],
  ["stake_reminder", "Weekly staking reminder"],
];
/** Shown only while the `community` feature flag is on: with it off, nothing can create these. */
const COMMUNITY_LABELS: [keyof Prefs, string][] = [
  ["new_follower", "New followers"],
  ["pick_comment", "Comments on your picks"],
  ["pick_graded", "Graded picks"],
];

export function NotificationPreferences({ initial, community = false }: { initial: Prefs; community?: boolean }) {
  const [prefs, setPrefs] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  async function toggle(key: keyof Prefs) {
    const next = !prefs[key];
    setPrefs((current) => ({ ...current, [key]: next }));
    setError(null);
    try {
      await clientApi("/v1/me/notification-preferences", { method: "PUT", body: { in_app: { [key]: next } } });
    } catch (caught) {
      setPrefs((current) => ({ ...current, [key]: !next }));
      setError(caught instanceof ClientApiError ? caught.message : "That setting was not saved. Try again.");
    }
  }

  return (
    <div className="space-y-3 p-4 sm:p-5">
      <ul className="divide-y divide-line">
        {(community ? [...LABELS, ...COMMUNITY_LABELS] : LABELS).map(([key, label]) => (
          <li key={key}>
            <label className="flex min-h-11 cursor-pointer items-center justify-between gap-4 py-1.5">
              <span>{label}</span>
              <input type="checkbox" role="switch" checked={prefs[key] ?? false} onChange={() => toggle(key)} className="size-5 accent-[var(--ov-accent)]" />
            </label>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted">Notifications appear inside OddVex only. Nothing is sent by push or email.</p>
      {error ? <Notice tone="error">{error}</Notice> : null}
    </div>
  );
}

export function StakeReminderNotice({ reminder }: { reminder: Schemas["StakeReminderOut"] }) {
  if (!reminder.exceeded || reminder.weekly_stake_threshold === null || reminder.weekly_stake_threshold === undefined) return null;
  return (
    <Notice tone="warn" title="You've reached your weekly staking reminder">
      You have staked {formatMoney(reminder.staked_this_week)} this week, against the {formatMoney(reminder.weekly_stake_threshold)} reminder you set. If betting is
      feeling like more than you planned, free and confidential help is available at <a href="tel:18004262537">1-800-GAMBLER</a>.
    </Notice>
  );
}

export function StakeReminderForm({ reminder }: { reminder: Schemas["StakeReminderOut"] }) {
  const router = useRouter();
  const current = reminder.weekly_stake_threshold ?? null;
  const [amount, setAmount] = useState(current === null ? "" : String(current));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "accent" | "error"; text: string } | null>(null);

  async function save(value: number | null) {
    setBusy(true);
    setMessage(null);
    try {
      await clientApi("/v1/me/stake-reminder", { method: "PUT", body: { weekly_stake_threshold: value } });
      if (value === null) setAmount("");
      setMessage({ tone: "accent", text: value === null ? "Reminder turned off." : `Reminder set at ${formatMoney(value)} a week.` });
      router.refresh();
    } catch (caught) {
      setMessage({ tone: "error", text: caught instanceof ClientApiError ? caught.message : "The reminder was not saved. Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 p-4 sm:p-5">
      <p className="text-sm leading-relaxed text-muted">
        Pick a weekly amount. If the stakes you log in a week reach it, OddVex tells you once. It is a reminder, not a limit: OddVex will not stop you logging bets, and
        it has no connection to your sportsbook accounts.
      </p>
      <p className="text-sm">
        You have staked <span className="num font-medium">{formatMoney(reminder.staked_this_week)}</span> this week.
      </p>
      <StakeReminderNotice reminder={reminder} />
      <form
        className="flex flex-wrap items-end gap-3"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          const value = Number(amount);
          if (!amount.trim() || !Number.isFinite(value) || value <= 0) return setMessage({ tone: "error", text: "Enter an amount greater than zero." });
          void save(value);
        }}
      >
        <Field id="stake-reminder" label="Weekly amount ($)" inputMode="decimal" className="w-44" placeholder="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Button type="submit" variant="secondary" disabled={busy}>
          Save reminder
        </Button>
        {current !== null ? (
          <Button type="button" variant="ghost" disabled={busy} onClick={() => save(null)}>
            Turn off
          </Button>
        ) : null}
      </form>
      <div aria-live="polite">{message ? <Notice tone={message.tone}>{message.text}</Notice> : null}</div>
    </div>
  );
}
