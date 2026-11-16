import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { DraftBanner } from "@/components/marketing/draft-banner";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "What OddVex stores, why, and how to delete it.",
  alternates: { canonical: "/privacy" },
};

export default function Page() {
  return (
    <>
      <PageIntro title="Privacy policy" lede="What the OddVex preview stores, what it's used for and how you remove it." />
      <DraftBanner />
      <Prose>
        <h2>What we store</h2>
        <ul>
          <li><strong>Account details:</strong> your email address, display name, a hashed password, your confirmation that you are 21 or over, and whether you have confirmed your email address.</li>
          <li><strong>Bets you log:</strong> the selections, odds, stakes, sportsbook names, notes and results you enter, including bets settled from a final score.</li>
          <li><strong>Watchlist:</strong> the teams, players and games you follow.</li>
          <li><strong>Alerts and notifications:</strong> the alert rules you set, the notifications they produce inside OddVex, and your choices about which kinds of notification you see.</li>
          <li><strong>Weekly staking reminder:</strong> the weekly amount you set, if you set one.</li>
          <li><strong>Sync connections:</strong> in the preview these are mock connections. They hold no sportsbook credentials.</li>
          <li><strong>Account messages:</strong> the email-confirmation and password-reset messages addressed to you. In the preview they are stored on our server and not sent.</li>
          <li><strong>Security log:</strong> a record of sign-ins and sensitive actions, such as changing a password, settling or deleting a bet, exporting data or deleting an account. Each entry holds the time, the internal ID of the account, the IP address the request came from and a request ID.</li>
        </ul>
        <h2>What stays in your browser</h2>
        <ul>
          <li><strong>A session cookie</strong> (<code>ov_session</code>) that keeps you signed in. Scripts on the page cannot read it.</li>
          <li><strong>An odds-format cookie</strong> (<code>ov_odds</code>) that remembers American or decimal odds.</li>
          <li><strong>Browser storage</strong> for your theme and for whether live screens refresh automatically.</li>
        </ul>
        <h2>What we don&rsquo;t collect</h2>
        <p>
          We don&rsquo;t collect payment details, precise location or sportsbook passwords. The preview runs no
          advertising and no third-party analytics trackers, and it sends no push notifications or email.
        </p>
        <h2>How we use it</h2>
        <p>To run your account, compute your tracker results, check your alerts, keep the service secure and answer you when you write to us. We don&rsquo;t sell personal information.</p>
        <h2>Seeing and deleting your data</h2>
        <p>Settings, then Download my data, gives you a copy of what your account holds. You can delete individual bets, alerts, notifications and watchlist entries at any time.</p>
        <p>
          Settings, then Delete account, removes your account, bets, watchlist, alerts, notifications, notification
          choices, staking reminder, sync connections and stored account messages immediately.
        </p>
        <p>
          Security log entries are kept after an account is deleted. They include the internal account ID and the IP
          address, not your email address or name. The retention period is to be confirmed before launch.
        </p>
        <h2>Age</h2>
        <p>OddVex is for adults 21 and over and is not directed at children.</p>
        <h2>Changes</h2>
        <p>This policy will be updated before launch, including details of any service providers and your rights under applicable state privacy laws.</p>
      </Prose>
    </>
  );
}
