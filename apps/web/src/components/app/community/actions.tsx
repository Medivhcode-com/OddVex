"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useActionState, useId, useState } from "react";
import type { Schemas } from "@oddvex/types";
import { TextArea } from "@/components/app/community/text-area";
import { Button, Notice, SelectField } from "@/components/ui/primitives";
import { adminDeleteCommentAction, type AdminActionState } from "@/lib/admin-actions";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { COMMENT_MAX, communityError, countLabel, DELETE_LOCK_NOTE, REPORT_DETAILS_MAX, REPORT_REASONS, RULES_REMINDER, type Comment, type ReportReason, type ReportTarget } from "@/lib/community-copy";
import { formatDateTime } from "@/lib/format";

const profileHref = (handle: string) => `/app/community/profiles/${encodeURIComponent(handle)}`;

function describe(caught: unknown, fallback: string): string {
  return caught instanceof ClientApiError ? communityError(caught, fallback) : fallback;
}

/** "Report" opens a short form. The confirmation is neutral and says the other person is not told. */
export function ReportButton({ targetType, targetId, what }: { targetType: ReportTarget; targetId: string; what: string }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>("spam");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (details.length > REPORT_DETAILS_MAX) return setError(`Keep the details to ${REPORT_DETAILS_MAX} characters or fewer.`);
    setBusy(true);
    setError(null);
    try {
      await clientApi<Schemas["ReportOut"]>("/v1/community/reports", { body: { target_type: targetType, target_id: targetId, reason, details: details.trim() || null } });
      setSent(true);
      setOpen(false);
      setDetails("");
    } catch (caught) {
      setError(describe(caught, "The report was not sent. Try again."));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="basis-full">
        <Notice tone="second" role="status">
          Report received. A moderator will review it against the community guidelines. The person you reported is not told.
        </Notice>
      </div>
    );
  }
  if (!open) {
    return (
      <Button type="button" variant="ghost" onClick={() => setOpen(true)}>
        Report<span className="sr-only"> {what}</span>
      </Button>
    );
  }
  return (
    <form onSubmit={submit} noValidate aria-label={`Report ${what}`} className="basis-full space-y-3 rounded-cell border border-line-strong p-3">
      <SelectField id={`${id}-reason`} label="Reason" value={reason} onChange={(event) => setReason(event.target.value as ReportReason)} className="max-w-xs">
        {REPORT_REASONS.map((entry) => (
          <option key={entry.value} value={entry.value}>
            {entry.label}
          </option>
        ))}
      </SelectField>
      <TextArea id={`${id}-details`} label="Details (optional)" max={REPORT_DETAILS_MAX} value={details} onChange={(event) => setDetails(event.target.value)} hint="Only moderators see this." error={error} rows={3} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="secondary" disabled={busy}>
          {busy ? "Sending" : "Send report"}
        </Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function FollowButton({ handle, following }: { handle: string; following: boolean }) {
  const router = useRouter();
  const [state, setState] = useState(following);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const path = `/v1/community/follows/${encodeURIComponent(handle)}`;
      if (state) await clientApi(path, { method: "DELETE" });
      else await clientApi<Schemas["FollowStateOut"]>(path, { method: "POST", body: {} });
      setState(!state);
      router.refresh();
    } catch (caught) {
      setError(describe(caught, "That was not saved. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button type="button" variant={state ? "secondary" : "primary"} aria-pressed={state} disabled={busy} onClick={toggle}>
        {state ? "Following" : "Follow"}
        <span className="sr-only"> @{handle}</span>
      </Button>
      {error ? (
        <p role="alert" className="basis-full text-sm text-error">
          {error}
        </p>
      ) : null}
    </>
  );
}

/** Blocking asks first and says what it does in both directions. Unblocking is a single step. */
export function BlockButton({ handle, blocked }: { handle: string; blocked: boolean }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(block: boolean) {
    setBusy(true);
    setError(null);
    try {
      await clientApi(`/v1/community/blocks/${encodeURIComponent(handle)}`, block ? { method: "PUT", body: {} } : { method: "DELETE" });
      setConfirming(false);
      router.refresh();
    } catch (caught) {
      setError(describe(caught, "That was not saved. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {blocked ? (
        <Button type="button" variant="secondary" disabled={busy} onClick={() => run(false)}>
          Unblock<span className="sr-only"> @{handle}</span>
        </Button>
      ) : confirming ? (
        <div role="group" aria-label={`Confirm blocking @${handle}`} className="basis-full space-y-3 rounded-cell border border-line-strong p-3">
          <p className="max-w-prose text-sm">
            Block @{handle}? You will no longer see their profile, picks or comments, and they will no longer see yours. If either of you follows the other, that follow is
            removed. They are not told.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="danger" disabled={busy} onClick={() => run(true)}>
              {busy ? "Blocking" : "Block profile"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
          Block<span className="sr-only"> @{handle}</span>
        </Button>
      )}
      {error ? (
        <p role="alert" className="basis-full text-sm text-error">
          {error}
        </p>
      ) : null}
    </>
  );
}

/** Only offered while the game is upcoming. The API refuses afterwards; the reason is shown either way. */
export function DeletePickButton({ pickId, locked }: { pickId: string; locked: boolean }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (locked) return <p className="basis-full text-sm text-muted">{DELETE_LOCK_NOTE}</p>;

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await clientApi(`/v1/community/picks/${encodeURIComponent(pickId)}`, { method: "DELETE" });
      router.push("/app/community?deleted=1");
      router.refresh();
    } catch (caught) {
      setError(describe(caught, "The pick was not deleted. Try again."));
      setBusy(false);
    }
  }

  return (
    <>
      {confirming ? (
        <div role="group" aria-label="Confirm deleting this pick" className="basis-full space-y-3 rounded-cell border border-line-strong p-3">
          <p className="max-w-prose text-sm">Delete this pick? Its comments and likes go with it. You can only do this before the game starts.</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="danger" disabled={busy} onClick={remove}>
              {busy ? "Deleting" : "Delete pick"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => setConfirming(false)}>
              Keep
            </Button>
          </div>
        </div>
      ) : (
        <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
          Delete pick
        </Button>
      )}
      {error ? (
        <p role="alert" className="basis-full text-sm text-error">
          {error}
        </p>
      ) : null}
    </>
  );
}

/** A moderator removing someone else's comment: a server action, like every other admin change. */
function ModeratorDelete({ comment, onDeleted }: { comment: Comment; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminDeleteCommentAction(previous, form);
    if (next.ok) onDeleted();
    return next;
  }, {} as AdminActionState);
  if (!confirming) {
    return (
      <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
        Delete as moderator<span className="sr-only">: comment by @{comment.author.handle}</span>
      </Button>
    );
  }
  return (
    <form action={action} aria-label={`Confirm deleting the comment by @${comment.author.handle}`} className="basis-full space-y-3 rounded-cell border border-line-strong p-3">
      <input type="hidden" name="comment_id" value={comment.id} />
      <input type="hidden" name="pick_id" value={comment.pick_id} />
      <p className="text-sm">Delete this comment as a moderator? It is removed for everyone and the action is written to the audit log.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="danger" disabled={pending}>
          {pending ? "Deleting" : "Delete comment"}
        </Button>
        <Button type="button" variant="ghost" disabled={pending} onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
    </form>
  );
}

function CommentItem({ comment, moderator, onDeleted }: { comment: Comment; moderator: boolean; onDeleted: (id: string) => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const moderated = comment.moderation_status !== "visible";

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await clientApi(`/v1/community/comments/${encodeURIComponent(comment.id)}`, { method: "DELETE" });
      onDeleted(comment.id);
    } catch (caught) {
      setError(describe(caught, "The comment was not deleted. Try again."));
      setBusy(false);
    }
  }

  return (
    <li className="space-y-2 px-4 py-3.5 sm:px-5">
      <p className="text-sm text-muted">
        <Link href={profileHref(comment.author.handle)} className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
          @{comment.author.handle}
        </Link>{" "}
        commented <time dateTime={comment.created_at}>{formatDateTime(comment.created_at)}</time>
      </p>
      {moderated ? (
        <p className="text-sm text-warn">{comment.moderation_note ?? "Removed by moderators."} Only you can see this comment now.</p>
      ) : (
        <p className="max-w-prose whitespace-pre-line break-words text-[0.9375rem] leading-relaxed">{comment.body}</p>
      )}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
        {comment.is_mine ? (
          confirming ? (
            <>
              <span className="text-sm text-muted">Delete this comment?</span>
              <Button type="button" variant="danger" disabled={busy} onClick={remove}>
                {busy ? "Deleting" : "Delete comment"}
              </Button>
              <Button type="button" variant="ghost" disabled={busy} onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
              Delete<span className="sr-only"> your comment</span>
            </Button>
          )
        ) : (
          <>
            <ReportButton targetType="comment" targetId={comment.id} what={`comment by @${comment.author.handle}`} />
            {moderator ? <ModeratorDelete comment={comment} onDeleted={() => onDeleted(comment.id)} /> : null}
          </>
        )}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      ) : null}
    </li>
  );
}

/**
 * The comments of one pick, newest first, with "Load more" and the form to add one. Comment
 * text is plain text: React escapes it, and only line breaks are kept.
 */
export function Comments({
  pickId,
  initial,
  next,
  total,
  canPost,
  cannotPostReason,
  moderator,
}: {
  pickId: string;
  initial: Comment[];
  next: string | null;
  total: number;
  canPost: boolean;
  cannotPostReason: string;
  moderator: boolean;
}) {
  const [items, setItems] = useState(initial);
  const [cursor, setCursor] = useState(next);
  const [count, setCount] = useState(total);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState<"post" | "more" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);
  const base = `/v1/community/picks/${encodeURIComponent(pickId)}/comments`;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPosted(false);
    if (!body.trim()) return setError("Write a comment first.");
    if (body.length > COMMENT_MAX) return setError(`Keep the comment to ${COMMENT_MAX} characters or fewer.`);
    setBusy("post");
    setError(null);
    try {
      const created = await clientApi<Comment>(base, { body: { body } });
      setItems((current) => [created, ...current]);
      setCount((current) => current + 1);
      setBody("");
      setPosted(true);
    } catch (caught) {
      setError(describe(caught, "The comment was not posted. Try again."));
    } finally {
      setBusy(null);
    }
  }

  async function more() {
    if (!cursor) return;
    setBusy("more");
    setListError(null);
    try {
      const page = await clientApi<Schemas["CommentPageOut"]>(`${base}?limit=20&before=${encodeURIComponent(cursor)}`);
      setItems((current) => [...current, ...page.items.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setCursor(page.next_before ?? null);
    } catch (caught) {
      setListError(describe(caught, "More comments could not be loaded. Try again."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      {canPost ? (
        <form onSubmit={submit} noValidate className="space-y-3 border-b border-line p-4 sm:p-5">
          <TextArea id="comment-body" label="Add a comment" max={COMMENT_MAX} value={body} onChange={(event) => setBody(event.target.value)} hint={RULES_REMINDER} error={error} rows={3} />
          <Button type="submit" disabled={busy !== null}>
            {busy === "post" ? "Posting" : "Post comment"}
          </Button>
          <div aria-live="polite">{posted ? <Notice tone="accent">Comment posted.</Notice> : null}</div>
        </form>
      ) : (
        <p className="border-b border-line px-4 py-3 text-sm text-muted sm:px-5">{cannotPostReason}</p>
      )}
      {items.length === 0 ? (
        <div className="px-5 py-10 text-center">
          <p className="font-medium">No comments yet</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted">Comments are for discussing the research behind a pick.</p>
        </div>
      ) : (
        <ul aria-label="Comments, newest first" className="divide-y divide-line">
          {items.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              moderator={moderator}
              onDeleted={(id) => {
                setItems((current) => current.filter((item) => item.id !== id));
                setCount((current) => Math.max(0, current - 1));
              }}
            />
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5">
        <p className="text-sm text-muted" role="status">
          {countLabel(count, "comment", "comments")}
        </p>
        {cursor ? (
          <Button type="button" variant="secondary" disabled={busy !== null} onClick={more}>
            {busy === "more" ? "Loading" : "Load more comments"}
          </Button>
        ) : null}
      </div>
      {listError ? (
        <p role="alert" className="border-t border-line px-4 py-2 text-sm text-error sm:px-5">
          {listError}
        </p>
      ) : null}
    </div>
  );
}

export function UnblockButton({ handle }: { handle: string }) {
  return <BlockButton handle={handle} blocked />;
}
