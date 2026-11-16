import type { Metadata } from "next";
import { LoginForm } from "@/components/app/auth-forms";
import { safeNext } from "@/lib/session";

export const metadata: Metadata = { title: "Log in", robots: { index: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string; reset?: string; suspended?: string; signedout?: string }> }) {
  const params = await searchParams;
  const next = safeNext(params.next);
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
      <p className="mb-6 mt-1 text-muted">Pick up where you left off.</p>
      <LoginForm next={next} notice={params.reset === "done" ? "Password changed. Log in with the new password." : params.signedout === "all" ? "You are logged out on every device." : undefined} suspended={params.suspended === "1"} />
    </>
  );
}
