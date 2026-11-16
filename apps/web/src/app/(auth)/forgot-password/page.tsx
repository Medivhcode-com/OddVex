import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/app/auth-forms";

export const metadata: Metadata = { title: "Reset your password", robots: { index: false } };
// The form posts to the API through a server action, so this page is rendered per request.
export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>
      <p className="mb-6 mt-1 text-muted">Enter the email address on your account and we&rsquo;ll prepare a link to set a new password.</p>
      <ForgotPasswordForm />
    </>
  );
}
