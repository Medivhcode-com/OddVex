import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { DraftBanner } from "@/components/marketing/draft-banner";

export const metadata: Metadata = {
  title: "Terms of service",
  description: "The terms for using the OddVex preview.",
  alternates: { canonical: "/terms" },
};

export default function Page() {
  return (
    <>
      <PageIntro title="Terms of service" lede="The short version: OddVex is an information tool for adults, offered as-is during the preview." />
      <DraftBanner />
      <Prose>
        <h2>What OddVex is</h2>
        <p>OddVex provides sports odds information, analytics and bet-tracking tools. It is not a sportsbook. It does not accept, place or facilitate wagers and does not hold funds.</p>
        <h2>Who can use it</h2>
        <p>You must be at least 21 years old. You are responsible for knowing and following the laws on sports betting where you are.</p>
        <h2>No advice, no guarantees</h2>
        <p>Nothing on OddVex is betting, financial or legal advice. Figures can be wrong, late or incomplete. Historical statistics do not predict future results. You make your own decisions and bear your own losses.</p>
        <h2>Preview data</h2>
        <p>The preview runs on synthetic, fictional data. Do not rely on it for any real-world decision.</p>
        <h2>Alerts and reminders</h2>
        <p>Alerts are checked when you open OddVex and appear only inside it. They can be late or missed, so don&rsquo;t depend on one. The weekly staking reminder is a reminder, not a limit: it does not stop you logging bets and it has no effect at any sportsbook.</p>
        <h2>Your account</h2>
        <p>Keep your password private. Don&rsquo;t misuse the service, attempt to break its security or scrape it. We may suspend accounts that do.</p>
        <h2>Your content</h2>
        <p>The bets, notes, watchlist and alerts you enter remain yours. You can delete them and your account at any time. The privacy policy explains what is removed and what is kept.</p>
        <h2>Changes</h2>
        <p>These terms will be replaced by a counsel-reviewed version before launch. Paid plans, when offered, will come with their own clearly stated price, renewal and cancellation terms.</p>
      </Prose>
    </>
  );
}
