import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { DraftBanner } from "@/components/marketing/draft-banner";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "What OddVex collects, why, and how to delete it.",
  alternates: { canonical: "/privacy" },
};

export default function Page() {
  return (
    <>
      <PageIntro title="Privacy policy" lede="What the OddVex preview collects, what it's used for and how you remove it." />
      <DraftBanner />
      <Prose>
        <h2>What we collect</h2>
        <ul>
          <li><strong>Account details:</strong> your email address, display name, a hashed password and your confirmation that you are 21 or over.</li>
          <li><strong>Bets you log:</strong> the selections, odds, stakes, sportsbook names and results you enter.</li>
          <li><strong>Sync connections:</strong> in the preview these are mock connections and hold no sportsbook credentials.</li>
          <li><strong>Security logs:</strong> sign-ins and sensitive actions such as deleting a bet, with a timestamp.</li>
        </ul>
        <h2>What we don&rsquo;t collect</h2>
        <p>
          We don&rsquo;t collect payment details, precise location or sportsbook passwords. The preview sets one
          cookie that keeps you signed in and stores your theme and odds-format choices in your browser. It runs no
          advertising or third-party analytics trackers.
        </p>
        <h2>How we use it</h2>
        <p>To run your account, compute your tracker results, keep the service secure and answer you when you write to us. We don&rsquo;t sell personal information.</p>
        <h2>Deleting your data</h2>
        <p>
          Settings, then Delete account, removes your account, bets and sync connections immediately. You can also
          delete individual bets at any time.
        </p>
        <h2>Age</h2>
        <p>OddVex is for adults 21 and over and is not directed at children.</p>
        <h2>Changes</h2>
        <p>This policy will be updated before launch, including details of any service providers and your rights under applicable state privacy laws.</p>
      </Prose>
    </>
  );
}
