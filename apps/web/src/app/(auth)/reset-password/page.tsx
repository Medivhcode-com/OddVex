import type { Metadata } from "next";
import { MissingLinkToken, ResetPasswordForm } from "@/components/app/auth-forms";

// `referrer: no-referrer` keeps the one-time token in the URL from leaking through a Referer header.
export const metadata: Metadata = { title: "Set a new password", robots: { index: false }, referrer: "no-referrer" };

export default async function Page({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Set a new password</h1>
      <p className="mb-6 mt-1 text-muted">Choose a password you don&rsquo;t use anywhere else.</p>
      {token ? <ResetPasswordForm token={token} /> : <MissingLinkToken reset />}
    </>
  );
}
