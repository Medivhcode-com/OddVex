"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { TextArea } from "@/components/app/community/text-area";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { BIO_MAX, communityError, HANDLE_MAX, HANDLE_MIN, handleProblem, profileSavedText, RULES_REMINDER, type MyProfile } from "@/lib/community-copy";

const HANDLE_CODES = new Set(["invalid_handle", "handle_taken", "handle_reserved"]);

function isHandleError(error: ClientApiError): boolean {
  if (HANDLE_CODES.has(error.code)) return true;
  const field = error.details && typeof error.details === "object" ? (error.details as { field?: unknown }).field : undefined;
  return field === "handle";
}

/**
 * Creates the community profile (onboarding) or edits it (settings). The handle is checked
 * while typing against the same rule the API enforces; the API has the last word.
 */
export function ProfileForm({ initial, mode }: { initial?: Pick<MyProfile, "handle" | "bio" | "is_public">; mode: "create" | "edit" }) {
  const router = useRouter();
  const [handle, setHandle] = useState(initial?.handle ?? "");
  const [bio, setBio] = useState(initial?.bio ?? "");
  const [isPublic, setIsPublic] = useState(initial?.is_public ?? false);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [handleError, setHandleError] = useState<string | null>(null);
  const [bioError, setBioError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedText, setSavedText] = useState<string | null>(null);
  // The handle and bio as last saved, to tell whether a save changed them (only then does the API queue a review).
  const [last, setLast] = useState(initial ? { handle: initial.handle, bio: initial.bio ?? null } : undefined);

  const local = touched || handle.length > 0 ? handleProblem(handle) : null;
  const shownHandleError = handleError ?? local;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    setSavedText(null);
    setError(null);
    setBioError(null);
    if (handleProblem(handle)) return;
    if (bio.length > BIO_MAX) return setBioError(`Keep the bio to ${BIO_MAX} characters or fewer.`);
    setBusy(true);
    try {
      const sent = { handle, bio: bio.trim() || null };
      const profile = await clientApi<MyProfile>("/v1/community/profile", { method: "PUT", body: { ...sent, is_public: isPublic } });
      // A profile moderators hid or removed stays that way when edited; a changed handle or bio goes to review.
      setSavedText(profileSavedText(last, sent, profile?.moderation_status));
      setLast(profile ? { handle: profile.handle, bio: profile.bio ?? null } : { handle: sent.handle.trim().toLowerCase(), bio: sent.bio });
      router.refresh();
    } catch (caught) {
      if (caught instanceof ClientApiError) {
        const text = communityError(caught, "The profile was not saved. Try again.");
        if (isHandleError(caught)) setHandleError(text);
        else if (caught.code === "links_not_allowed" || caught.code === "content_not_allowed") setBioError(text);
        else setError(text);
      } else {
        setError("The profile was not saved. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5 p-4 sm:p-5">
      <Field
        id="profile-handle"
        label="Handle"
        className="max-w-xs"
        value={handle}
        onChange={(event) => {
          setHandle(event.target.value);
          setHandleError(null);
        }}
        onBlur={() => setTouched(true)}
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={64}
        hint={`${HANDLE_MIN} to ${HANDLE_MAX} characters: lowercase letters, numbers and underscores. This is the only name other people see.`}
        error={shownHandleError ?? undefined}
      />
      <TextArea id="profile-bio" label="Bio (optional)" max={BIO_MAX} value={bio} onChange={(event) => { setBio(event.target.value); setBioError(null); }} hint={RULES_REMINDER} error={bioError} rows={3} className="max-w-xl" />
      <div>
        <label className="flex min-h-11 cursor-pointer items-center gap-3">
          <input type="checkbox" checked={isPublic} onChange={(event) => setIsPublic(event.target.checked)} aria-describedby="profile-public-hint" className="size-5 accent-[var(--ov-accent)]" />
          <span className="font-medium">Make my profile public</span>
        </label>
        <div id="profile-public-hint" className="mt-1 max-w-prose space-y-1.5 text-sm text-muted">
          <p>Public: other signed-in people can see your handle, your bio, your picks and the graded record of those picks. They never see your email address, your name, the bets in your tracker or your plan.</p>
          <p>Private: nobody can find your profile. You can browse, like and report, but you can&rsquo;t post picks, comment or follow anyone until you make it public.</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving" : mode === "create" ? "Create profile" : "Save profile"}
        </Button>
      </div>
      <div aria-live="polite">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {savedText && mode === "edit" ? <Notice tone="accent">{savedText}</Notice> : null}
      </div>
    </form>
  );
}
