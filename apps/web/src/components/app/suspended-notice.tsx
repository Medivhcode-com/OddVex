import Link from "next/link";
import { Notice } from "@/components/ui/primitives";
import { CONTACT_EMAIL } from "@/lib/site";

/**
 * Shown after a login attempt on a suspended account, and when a suspended session was just
 * ended. A suspended person cannot sign in to Settings, so the notice says where to write for
 * a copy of the data or for deletion: staff can do either (`POST /v1/admin/users/{id}/export`
 * and `/delete`). Without a contact address it points to the contact page.
 */
export function SuspendedNotice({ role, email = CONTACT_EMAIL }: { role: "alert" | "status"; email?: string }) {
  return (
    <Notice tone="warn" role={role} title="This account is suspended">
      You can&rsquo;t log in to it right now. Its data is kept. To ask for a copy of your data, or for the account and its data to be deleted,{" "}
      {email ? (
        <>
          write to <a href={`mailto:${email}`}>{email}</a>. Staff can do either for you.
        </>
      ) : (
        <>
          use the <Link href="/contact">contact page</Link>. Staff can do either for you.
        </>
      )}
    </Notice>
  );
}
