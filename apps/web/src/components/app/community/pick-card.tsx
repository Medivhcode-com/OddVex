"use client";

import Link from "next/link";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Price } from "@/components/app/odds-format";
import { Badge, Button, buttonClass, Notice } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { communityError, countLabel, pickStatus, type Pick } from "@/lib/community-copy";
import { formatDateTime, formatPercent } from "@/lib/format";

const profileHref = (handle: string) => `/app/community/profiles/${encodeURIComponent(handle)}`;
const pickHref = (id: string) => `/app/community/picks/${encodeURIComponent(id)}`;

/** A like is a toggle: `aria-pressed` carries the state, the word and the count carry it visibly. */
export function LikeButton({ pickId, liked, count }: { pickId: string; liked: boolean; count: number }) {
  const [state, setState] = useState({ liked, count });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const out = await clientApi<Schemas["LikeStateOut"]>(`/v1/community/picks/${encodeURIComponent(pickId)}/like`, state.liked ? { method: "DELETE" } : { method: "PUT", body: {} });
      setState({ liked: out.liked_by_me, count: out.like_count });
    } catch (caught) {
      setError(caught instanceof ClientApiError ? communityError(caught) : "The like was not saved. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button type="button" variant="secondary" aria-pressed={state.liked} disabled={busy} onClick={toggle} className={state.liked ? "border-accent" : undefined}>
        <svg width="16" height="16" viewBox="0 0 20 20" fill={state.liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
          <path d="M10 16.5 3.6 10.4a3.9 3.9 0 0 1 5.5-5.5l.9.9.9-.9a3.9 3.9 0 0 1 5.5 5.5z" />
        </svg>
        {state.liked ? "Liked" : "Like"}
        <span className="num text-muted">{state.count}</span>
        <span className="sr-only">{state.count === 1 ? "like" : "likes"}</span>
      </Button>
      {error ? (
        <p role="alert" className="basis-full text-sm text-error">
          {error}
        </p>
      ) : null}
    </>
  );
}

/**
 * One pick. Everything a person wrote (`analysis`, the handle) is rendered as text by React,
 * never as markup. The price is the one the API recorded when the pick was posted.
 */
export function PickCard({ pick, heading = "h3", full = false }: { pick: Pick; heading?: "h2" | "h3"; full?: boolean }) {
  const Heading = heading;
  const status = pickStatus(pick);
  const moderated = pick.moderation_status !== "visible";
  const titleId = `pick-${pick.id}`;
  return (
    <article aria-labelledby={titleId} className="space-y-3 px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-sm text-muted">
            <Link href={profileHref(pick.author.handle)} className="inline-flex min-h-6 items-center font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
              @{pick.author.handle}
            </Link>{" "}
            posted <time dateTime={pick.posted_at}>{formatDateTime(pick.posted_at)}</time>
          </p>
          <Heading id={titleId} className="mt-1 break-words font-semibold">
            {pick.selection}
          </Heading>
          <p className="mt-0.5 break-words text-sm text-muted">
            <Link href={`/app/games/${encodeURIComponent(pick.event_id)}`} className="underline underline-offset-4 hover:text-ink">
              {pick.event_label}
            </Link>
            , {pick.league.toUpperCase()}, starts <time dateTime={pick.event_start_time}>{formatDateTime(pick.event_start_time)}</time>
          </p>
        </div>
        <p className="flex flex-wrap items-center gap-1.5">
          <Badge tone={status.tone}>{status.label}</Badge>
          <Badge>Verified</Badge>
        </p>
      </div>

      <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <div>
          <dt className="text-xs text-muted">Price when posted</dt>
          <dd>
            <Price price={pick.price} className="font-medium" /> at {pick.sportsbook.name}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Implied probability</dt>
          <dd className="num">{formatPercent(pick.price.implied_probability)}</dd>
        </div>
        {pick.final_score ? (
          <div>
            <dt className="text-xs text-muted">Final score, away then home</dt>
            <dd className="num">
              {pick.final_score.away} to {pick.final_score.home}
            </dd>
          </div>
        ) : null}
      </dl>

      {moderated ? (
        <Notice tone="warn" title={pick.moderation_note ?? "Removed by moderators."}>
          Only you can see this pick now. It still counts in your record.
        </Notice>
      ) : pick.analysis ? (
        <p className="max-w-prose whitespace-pre-line break-words text-[0.9375rem] leading-relaxed">{pick.analysis}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <LikeButton pickId={pick.id} liked={pick.liked_by_me} count={pick.like_count} />
        {full ? (
          <a href="#comments" className={buttonClass("ghost")}>
            <span className="num">{pick.comment_count}</span> {pick.comment_count === 1 ? "comment" : "comments"}
          </a>
        ) : (
          <Link href={`${pickHref(pick.id)}#comments`} className={buttonClass("ghost")}>
            <span className="num">{pick.comment_count}</span> {pick.comment_count === 1 ? "comment" : "comments"}
            <span className="sr-only"> on {pick.selection}</span>
          </Link>
        )}
        {full ? null : (
          <Link href={pickHref(pick.id)} className={buttonClass("ghost")}>
            Open pick<span className="sr-only">: {pick.selection}</span>
          </Link>
        )}
      </div>
    </article>
  );
}

/** A page of picks with cursor paging: "Load more" appends the next page from the API. */
export function PickList({ initial, next, path, emptyTitle, emptyBody, label }: { initial: Pick[]; next: string | null; path: string; emptyTitle: string; emptyBody?: string; label: string }) {
  const [items, setItems] = useState(initial);
  const [cursor, setCursor] = useState(next);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function more() {
    if (!cursor) return;
    setBusy(true);
    setError(null);
    try {
      const page = await clientApi<Schemas["PickPageOut"]>(`${path}${path.includes("?") ? "&" : "?"}before=${encodeURIComponent(cursor)}`);
      setItems((current) => [...current, ...page.items.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setCursor(page.next_before ?? null);
    } catch (caught) {
      setError(caught instanceof ClientApiError ? communityError(caught) : "More picks could not be loaded. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="px-5 py-10 text-center">
        <p className="font-medium">{emptyTitle}</p>
        {emptyBody ? <p className="mx-auto mt-1 max-w-md text-sm text-muted">{emptyBody}</p> : null}
      </div>
    );
  }
  return (
    <div>
      <ul aria-label={label} className="divide-y divide-line">
        {items.map((pick) => (
          <li key={pick.id}>
            <PickCard pick={pick} />
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5">
        <p className="text-sm text-muted" role="status">
          Showing {countLabel(items.length, "pick", "picks")}, newest first.{cursor ? "" : " That is all of them."}
        </p>
        {cursor ? (
          <Button type="button" variant="secondary" disabled={busy} onClick={more}>
            {busy ? "Loading" : "Load more"}
          </Button>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="border-t border-line px-4 py-2 text-sm text-error sm:px-5">
          {error}
        </p>
      ) : null}
    </div>
  );
}
