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
          <li>
            <strong>Account details:</strong> your email address, display name, a hashed password, your confirmation that you are 21 or over, whether you have confirmed
            your email address, when you last signed in and last changed your password, and the account&rsquo;s role, plan and status (active or suspended).
          </li>
          <li><strong>Bets you log:</strong> the selections, odds, stakes, sportsbook names, notes and results you enter, including bets settled from a final score.</li>
          <li><strong>Watchlist:</strong> the teams, players and games you follow.</li>
          <li><strong>Alerts and notifications:</strong> the alert rules you set, the notifications they produce inside OddVex, and your choices about which kinds of notification you see.</li>
          <li><strong>Weekly staking reminder:</strong> the weekly amount you set, if you set one.</li>
          <li><strong>Sync connections:</strong> in the preview these are mock connections. They hold no sportsbook credentials.</li>
          <li><strong>Account messages:</strong> the email-confirmation and password-reset messages addressed to you. In the preview they are stored on our server and not sent.</li>
          <li>
            <strong>Security log:</strong> a record of sign-ins and of actions on your account, such as changing a password, logging, settling or deleting a bet, following a
            team, setting an alert, exporting data or deleting an account. Each entry holds the time, the internal ID of the account, the action taken, the ID of the item it
            concerned, the IP address the request came from, a request ID and, for some actions, a short detail: for example the result of a settled bet, the team, player or
            game you followed, the kind of alert and the game or team it watches, the week in which a staking reminder was reached, or the handle you chose for a community
            profile.
          </li>
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
        <h2>Seeing your data</h2>
        <p>
          Settings, then Download my data, gives you one JSON file. It holds your account details (email address, display name, role, plan, when the account was created,
          when you confirmed your age and whether your email address is confirmed), your bets, watchlist, alert rules, notifications and notification choices, your
          staking reminder, your sync connections and import runs, your own security log entries and, if you used the community, your profile, picks, comments, follows,
          likes, blocks and the reports you made.
        </p>
        <p>
          It does not contain your password or its hash. It also leaves out some things the account record holds: the time of your last sign-in, the time your password
          was last changed, whether the account is active or suspended, and the email-confirmation and password-reset messages stored for you. Each download is recorded
          in the security log.
        </p>
        <h2>Deleting your data</h2>
        <p>You can delete individual bets, alerts, notifications and watchlist entries at any time.</p>
        <p>
          Settings, then Delete account, deletes your account and, with it, your bets, watchlist, alert rules, notifications, notification choices, staking reminder, sync
          connections and import runs, stored account messages and everything you posted in the community, graded picks included. They are gone from the live database
          as soon as the request completes, and this cannot be undone.
        </p>
        <p>Deleting an account does not remove everything:</p>
        <ul>
          <li>
            <strong>Security log entries are kept after an account is deleted</strong>, and one more is added to record the deletion. They hold what is described under
            Security log above: the internal account ID, the IP address, and the detail of each action, such as the result of a bet or the ID of a team you followed. They
            are written without your email address or display name. Nothing removes these entries yet. The retention period is to be confirmed before launch.
          </li>
          <li>
            <strong>Backups.</strong> The preview database is copied once a day, and a daily copy is normally kept for 14 days. A further copy is made before each
            release; the most recent few of those are kept, with no fixed time limit. A copy made before you deleted your account still holds the account, your email
            address included, until that copy is removed.
          </li>
          <li>
            <strong>A reserved community handle, in one case.</strong> If an account is suspended at the moment it is deleted and has a community profile, its community
            handle stays reserved, so that the suspension cannot be undone by signing up again. No email address, and no fingerprint of one, is kept for this.
          </li>
        </ul>
        <p>
          If you cannot sign in, for example because the account is suspended or you no longer have the password, write to the address on the{" "}
          <a href="/contact">contact page</a>. Staff can produce the same data file for you, or delete the account, on request. A deletion carried out by staff removes
          and keeps the same things as one you carry out yourself. Its security log entry records which staff account did it and the reason given, not your email
          address.
        </p>
        <h2>Age</h2>
        <p>OddVex is for adults 21 and over and is not directed at children.</p>
        <h2>Changes</h2>
        <p>This policy will be updated before launch, including details of any service providers and your rights under applicable state privacy laws.</p>
      </Prose>
    </>
  );
}
