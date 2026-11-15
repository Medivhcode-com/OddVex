import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";

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
          <li>To delete your account and data, use Settings in the app. It takes effect immediately.</li>
        </ul>
        <p>
          OddVex can&rsquo;t help with a bet placed at a sportsbook. Contact that sportsbook directly. If gambling is
          causing harm, call or text <a href="tel:18004262537">1-800-GAMBLER</a>.
        </p>
      </Prose>
    </>
  );
}
