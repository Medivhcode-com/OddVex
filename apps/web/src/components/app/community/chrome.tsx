import Link from "next/link";
import clsx from "clsx";
import type { ReactNode } from "react";
import type { Schemas } from "@oddvex/types";
import { Price } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { ButtonLink, EmptyState, Notice, Panel } from "@/components/ui/primitives";
import type { CommunityRecord, MyProfile } from "@/lib/community-copy";
import { formatPercent, formatSignedPercent } from "@/lib/format";

export type CommunitySection = "feed" | "leaderboard" | "profile" | "settings" | "guidelines" | "pick";

/** Page heading plus the section's own navigation. Entries that need a profile or a flag appear only then. */
export function CommunityHeader({
  title,
  description,
  current,
  me,
  leaderboard,
  actions,
}: {
  title: string;
  description?: ReactNode;
  current: CommunitySection;
  me: MyProfile | null;
  leaderboard: boolean;
  actions?: ReactNode;
}) {
  const items: { key: CommunitySection; href: string; label: string }[] = [
    { key: "feed", href: "/app/community", label: "Feed" },
    ...(leaderboard && me ? [{ key: "leaderboard" as const, href: "/app/community/leaderboard", label: "Leaderboard" }] : []),
    ...(me ? [{ key: "profile" as const, href: `/app/community/profiles/${encodeURIComponent(me.handle)}`, label: "My profile" }] : []),
    ...(me ? [{ key: "settings" as const, href: "/app/community/settings", label: "Community settings" }] : []),
    { key: "guidelines", href: "/app/community/guidelines", label: "Guidelines" },
  ];
  return (
    <>
      <PageHeader title={title} description={description} actions={actions} />
      <nav aria-label="Community sections" className="-mx-1 mb-6 flex max-w-full gap-1 overflow-x-auto px-1 py-1">
        {items.map((item) => {
          const active = item.key === current;
          return (
            <Link
              key={item.key}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-sm font-medium transition-colors",
                active ? "border-ink bg-ink text-bg" : "border-line text-muted hover:border-line-strong hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

/** The community needs an account. Nothing about other people is shown to a signed-out visitor. */
export function SignedOut({ next }: { next: string }) {
  const target = encodeURIComponent(next);
  return (
    <>
      <PageHeader title="Community" description="Research discussion around structured picks that are graded from the final score." />
      <Panel>
        <EmptyState
          title="Log in to open the community"
          action={
            <div className="flex flex-wrap justify-center gap-3">
              <ButtonLink href={`/login?next=${target}`}>Log in</ButtonLink>
              <ButtonLink href={`/signup?next=${target}`} variant="secondary">
                Create an account
              </ButtonLink>
            </div>
          }
        >
          Profiles are opt-in. Other people only ever see the handle you choose, never your email address, your name or your tracked bets.
        </EmptyState>
      </Panel>
    </>
  );
}

/** The rules exactly as `GET /v1/community/guidelines` returns them. Nothing here is hard-coded. */
export function Guidelines({ guidelines }: { guidelines: Schemas["CommunityGuidelinesOut"] }) {
  return (
    <div className="space-y-4 p-4 sm:p-5">
      <p className="max-w-prose">{guidelines.intro}</p>
      <ol className="max-w-prose space-y-3">
        {guidelines.rules.map((rule, index) => (
          <li key={rule.key} className="flex gap-3">
            <span aria-hidden="true" className="num mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border border-line-strong text-xs">
              {index + 1}
            </span>
            <div>
              <p className="font-medium">{rule.title}</p>
              <p className="text-sm text-muted">{rule.text}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="max-w-prose text-sm text-muted">{guidelines.enforcement}</p>
      <p className="max-w-prose text-sm text-muted">{guidelines.help}</p>
      <p className="text-xs text-muted">
        Guidelines version <span className="num">{guidelines.version}</span>
      </p>
    </div>
  );
}

function Figure({ label, value, hint }: { label: ReactNode; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="num mt-1 text-xl font-medium">{value}</dd>
      {hint ? <dd className="mt-0.5 text-xs text-muted">{hint}</dd> : null}
    </div>
  );
}

/** "52.4% to 71.0%", the Wilson interval the API computed. */
export function intervalText(record: CommunityRecord): string | null {
  const interval = record.win_rate_interval;
  if (!interval) return null;
  return `${formatPercent(interval.low)} to ${formatPercent(interval.high)}`;
}

/**
 * A profile's graded record. Every figure and every explanation is the API's: the web app
 * computes nothing. The return figure is labelled with the API's own `method` text.
 */
export function RecordPanel({ record }: { record: CommunityRecord }) {
  const interval = intervalText(record);
  const decided = record.wins + record.losses;
  const level = Math.round((record.win_rate_interval?.confidence_level ?? 0.95) * 100);
  return (
    <div className="space-y-4 p-4 sm:p-5">
      {record.picks === 0 ? (
        <p className="text-sm text-muted">No graded picks yet. A record appears once a game with a pick on it has finished.</p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-5 md:grid-cols-5">
          <Figure label="Graded picks" value={record.picks} hint="Sample size" />
          <Figure label="Won, lost, push" value={`${record.wins}-${record.losses}-${record.pushes}`} />
          <Figure
            label="Win rate"
            value={formatPercent(record.win_rate)}
            hint={interval ? `${level}% interval ${interval}, from ${decided} decided ${decided === 1 ? "pick" : "picks"}` : "No decided picks yet"}
          />
          <Figure label="Average price" value={record.average_price ? <Price price={record.average_price} /> : "n/a"} hint="Across graded picks, as posted" />
          <Figure label="Flat-stake ROI" value={formatSignedPercent(record.flat_stake_roi)} hint="Method below" />
        </dl>
      )}
      {record.sample_note ? <Notice tone="warn">{record.sample_note}</Notice> : null}
      <p className="max-w-prose text-sm text-muted" data-api-text="method">
        <span className="font-medium text-ink">Flat-stake ROI method.</span> {record.method}
      </p>
      <p className="max-w-prose text-sm text-muted">{record.caveat}</p>
    </div>
  );
}
