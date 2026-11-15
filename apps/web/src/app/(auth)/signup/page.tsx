import type { Metadata } from "next";
import { SignupForm } from "@/components/app/auth-forms";
import { safeNext } from "@/lib/session";

export const metadata: Metadata = { title: "Create your account", robots: { index: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const next = safeNext((await searchParams).next);
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mb-6 mt-1 text-muted">Free during the preview. No card needed.</p>
      <SignupForm next={next} />
    </>
  );
}
