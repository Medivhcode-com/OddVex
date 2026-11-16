import type { Metadata } from "next";
import { ConfirmEmailForm, MissingLinkToken } from "@/components/app/auth-forms";
import { sessionToken } from "@/lib/api";

// `referrer: no-referrer` keeps the one-time token in the URL from leaking through a Referer header.
export const metadata: Metadata = { title: "Confirm your email address", robots: { index: false }, referrer: "no-referrer" };

/**
 * Opening the link does not confirm anything by itself: mail scanners and link previews
 * fetch URLs, and that would use up the one-time token. The visitor confirms with a button.
 */
export default async function Page({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  // A new link can only be requested for a signed-in account; the API checks the session itself.
  const signedIn = Boolean(await sessionToken());
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Confirm your email address</h1>
      <p className="mb-6 mt-1 text-muted">Confirming shows the address is yours. Nothing in OddVex is locked until you do.</p>
      {token ? <ConfirmEmailForm token={token} canResend={signedIn} /> : <MissingLinkToken />}
    </>
  );
}
