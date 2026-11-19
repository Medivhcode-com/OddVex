import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { HelplineLink } from "@/components/ui/helpline";
import { HELPLINE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: "How to reach the OddVex team.",
  alternates: { canonical: "/contact" },
};

const email = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

export default function Page() {
  return (
    <>
      <PageIntro title="Contact OddVex" lede="Questions, corrections and data-rights requests all go to the same place." />
      <Prose>
        {email ? (
          <p>
            Email us at <a href={`mailto:${email}`}>{email}</a>. We read everything.
          </p>
        ) : (
          <p>A contact address is being set up and will be published here before launch.</p>
        )}
        <h2>Before you write</h2>
        <ul>
          <li>For how a number is calculated, see <a href="/methodology">data and methodology</a>.</li>
          <li>For account and tracker questions, see the <a href="/help">help center</a>.</li>
          <li>
            To delete your account and data, sign in and use Settings, then Delete account. The <a href="/privacy">privacy policy</a> says what is removed and what is kept.
          </li>
          <li>
            If you cannot sign in, {email ? "write to the address above" : "write to the contact address once it is published here"} and ask for a copy of your data or for the account to be
            deleted. Staff can do either on request.
          </li>
        </ul>
        <p>
          OddVex can&rsquo;t help with a bet placed at a sportsbook. Contact that sportsbook directly. If gambling is
          causing harm, call <HelplineLink />, the {HELPLINE.name}.
        </p>
      </Prose>
    </>
  );
}
