"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Badge, Button, EmptyState } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAge } from "@/lib/format";

type Notification = Schemas["NotificationOut"];
type Rule = Schemas["AlertRuleOut"];

const KIND_LABEL: Record<Notification["kind"], string> = {
  price_alert: "Price alert",
  line_move: "Line move",
  game_start: "Game start",
  game_final: "Final score",
  bet_settled: "Settled bet",
  sync_finished: "Sync",
  stake_reminder: "Staking reminder",
};

function useAction() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "That didn't work. Try again.");
    } finally {
      setBusy(null);
    }
  }
  return { busy, error, run };
}

/** Notifications are shown exactly as the API wrote them. The copy rules live with the engine. */
export function NotificationList({ items, unread }: { items: Notification[]; unread: number }) {
  const { busy, error, run } = useAction();
  if (items.length === 0) {
    return (
      <EmptyState title="No notifications yet">
        Open a game and choose Set an alert. When a price, line or game you asked about changes, it shows up here.
      </EmptyState>
    );
  }
  return (
    <div>
      {unread > 0 ? (
        <div className="flex justify-end border-b border-line px-4 py-2 sm:px-5">
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => run("all", () => clientApi("/v1/notifications/read-all", { method: "POST", body: {} }))}>
            Mark all as read
          </Button>
        </div>
      ) : null}
      <ul>
        {items.map((item) => {
          const isUnread = !item.read_at;
          return (
            <li key={item.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-t border-line px-4 py-3.5 first:border-t-0 sm:px-5">
              <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
                <p className="flex flex-wrap items-center gap-2">
                  <span className={isUnread ? "font-semibold" : "font-medium"}>{item.title}</span>
                  {isUnread ? <Badge tone="accent">New</Badge> : null}
                  <Badge>{KIND_LABEL[item.kind]}</Badge>
                </p>
                <p className="mt-1 max-w-prose text-sm text-muted">{item.body}</p>
                <p className="mt-1 text-xs text-muted">
                  <time dateTime={item.created_at} suppressHydrationWarning>
                    {formatAge(item.created_at)}
                  </time>
                </p>
              </div>
              <div className="flex w-full flex-wrap items-center justify-end gap-1 sm:w-auto sm:shrink-0">
                {item.href ? (
                  <Link
                    href={item.href}
                    onClick={() => {
                      if (isUnread) void clientApi(`/v1/notifications/${item.id}/read`, { method: "POST", body: {} }).catch(() => {});
                    }}
                    className="inline-flex min-h-9 items-center rounded-cell border border-line-strong px-3 text-sm font-medium hover:bg-raised"
                  >
                    Open<span className="sr-only">: {item.title}</span>
                  </Link>
                ) : null}
                {isUnread ? (
                  <Button size="sm" variant="ghost" disabled={busy !== null} aria-label={`Mark as read: ${item.title}`} onClick={() => run(item.id, () => clientApi(`/v1/notifications/${item.id}/read`, { method: "POST", body: {} }))}>
                    Mark as read
                  </Button>
                ) : null}
                <Button size="sm" variant="ghost" disabled={busy !== null} aria-label={`Delete notification: ${item.title}`} onClick={() => run(item.id, () => clientApi(`/v1/notifications/${item.id}`, { method: "DELETE" }))}>
                  Delete
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      {error ? (
        <p role="alert" className="border-t border-line px-4 py-2 text-sm text-error sm:px-5">
          {error}
        </p>
      ) : null}
    </div>
  );
}

const STATE_LABEL: Record<Rule["state"], string> = { active: "Active", triggered: "Triggered", paused: "Paused", expired: "Expired" };
const STATE_TONE: Record<Rule["state"], "accent" | "second" | "neutral" | "warn"> = { active: "accent", triggered: "second", paused: "warn", expired: "neutral" };

export function AlertRuleList({ rules }: { rules: Rule[] }) {
  const { busy, error, run } = useAction();
  const [checked, setChecked] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  if (rules.length === 0) {
    return <EmptyState title="No alerts set">Open a game and choose Set an alert to watch a price, a line, the start or the final score.</EmptyState>;
  }
  const patch = (rule: Rule, state: "active" | "paused") => run(rule.id, () => clientApi(`/v1/alerts/${rule.id}`, { method: "PATCH", body: { state } }));

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2 sm:px-5">
        <p className="text-xs text-muted" role="status">
          {checked ?? "Alerts are checked when you open OddVex. Nothing is sent by push or email."}
        </p>
        <Button
          size="sm"
          variant="secondary"
          disabled={busy !== null}
          onClick={() =>
            run("check", async () => {
              const out = await clientApi<Schemas["AlertEvaluationOut"]>("/v1/alerts/evaluate", { method: "POST", body: {} });
              setChecked(`Checked ${out.evaluated} ${out.evaluated === 1 ? "alert" : "alerts"}. ${out.fired} fired${out.expired ? `, ${out.expired} expired` : ""}.`);
            })
          }
        >
          {busy === "check" ? "Checking" : "Check now"}
        </Button>
      </div>
      <ul>
        {rules.map((rule) => (
          <li key={rule.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line px-4 py-3.5 first:border-t-0 sm:px-5">
            <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
              <p className="font-medium">{rule.summary}</p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
                <Badge tone={STATE_TONE[rule.state]}>{STATE_LABEL[rule.state]}</Badge>
                {rule.event_id && rule.available ? (
                  <Link href={`/app/games/${rule.event_id}`} className="underline underline-offset-4 hover:text-ink">
                    {rule.label}
                  </Link>
                ) : (
                  <span>{rule.label}</span>
                )}
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center justify-end gap-1 sm:w-auto sm:shrink-0">
              {confirming === rule.id ? (
                <>
                  <span className="text-sm text-muted">Delete this alert?</span>
                  <Button size="sm" variant="danger" disabled={busy !== null} onClick={() => run(rule.id, () => clientApi(`/v1/alerts/${rule.id}`, { method: "DELETE" }))}>
                    Delete alert
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>
                    Keep
                  </Button>
                </>
              ) : (
                <>
                  {rule.state === "active" ? (
                    <Button size="sm" variant="ghost" disabled={busy !== null} aria-label={`Pause: ${rule.summary}`} onClick={() => patch(rule, "paused")}>
                      Pause
                    </Button>
                  ) : null}
                  {rule.state === "paused" ? (
                    <Button size="sm" variant="ghost" disabled={busy !== null} aria-label={`Resume: ${rule.summary}`} onClick={() => patch(rule, "active")}>
                      Resume
                    </Button>
                  ) : null}
                  {rule.state === "triggered" && rule.available ? (
                    <Button size="sm" variant="ghost" disabled={busy !== null} aria-label={`Set again: ${rule.summary}`} onClick={() => patch(rule, "active")}>
                      Set again
                    </Button>
                  ) : null}
                  <Button size="sm" variant="ghost" aria-label={`Delete: ${rule.summary}`} onClick={() => setConfirming(rule.id)}>
                    Delete
                  </Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
      {error ? (
        <p role="alert" className="border-t border-line px-4 py-2 text-sm text-error sm:px-5">
          {error}
        </p>
      ) : null}
    </div>
  );
}
