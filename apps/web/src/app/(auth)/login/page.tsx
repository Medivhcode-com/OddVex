import type { Metadata } from "next";
import { LoginForm } from "@/components/app/auth-forms";
import { safeNext } from "@/lib/session";

export const metadata: Metadata = { title: "Log in", robots: { index: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const next = safeNext((await searchParams).next);
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
      <p className="mb-6 mt-1 text-muted">Pick up where you left off.</p>
      <LoginForm next={next} />
    </>
  );
}
