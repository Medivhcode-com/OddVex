import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { DraftBanner } from "@/components/marketing/draft-banner";

export const metadata: Metadata = {
  title: "Responsible gambling",
  description: "Help and practical limits if betting stops being fun. Call or text 1-800-GAMBLER.",
  alternates: { canonical: "/responsible-gambling" },
};

export default function Page() {
  return (
    <>
      <PageIntro
        title="Responsible gambling"
        lede="Betting should be entertainment you can afford. If it stops being that, help is free and confidential."
      />
      <Prose>
        <h2>Get help now</h2>
        <ul>
          <li>Call or text <a href="tel:18004262537"><strong>1-800-GAMBLER</strong></a> (1-800-426-2537), the National Problem Gambling Helpline. It is free, confidential and open 24/7.</li>
          <li>If you are in crisis or thinking about harming yourself, call or text <a href="tel:988"><strong>988</strong></a>.</li>
        </ul>
        <h2>Signs it may be a problem</h2>
        <ul>
          <li>Betting more than you planned, or to win back losses.</li>
          <li>Hiding how much you bet from people close to you.</li>
          <li>Borrowing, or using money meant for bills.</li>
          <li>Feeling anxious or irritable when you try to stop.</li>
        </ul>
        <h2>Practical limits</h2>
        <ul>
          <li>Decide what you can afford to lose before you start, and stop there.</li>
          <li>Use the deposit, loss and time limits your sportsbook provides.</li>
          <li>Sportsbooks and state regulators offer self-exclusion programs. Your state gaming regulator&rsquo;s website explains how to enroll.</li>
        </ul>
        <h2>What OddVex commits to</h2>
      </Prose>
      {/* Only the commitments are draft text. The helpline information above is not hedged. */}
      <DraftBanner className="mt-4">
        These commitments describe how the preview works today. They have not yet been reviewed by legal counsel and
        will be replaced by a final version before public launch.
      </DraftBanner>
      <Prose>
        <ul>
          <li>OddVex is for adults 21 and over and is not directed at anyone younger.</li>
          <li>We don&rsquo;t promise wins, call anything a lock or describe any bet as risk-free.</li>
          <li>The tracker shows your losses as plainly as your wins.</li>
          <li>You can set a weekly staking reminder in Settings. It is a reminder, not a limit: OddVex cannot stop a bet at a sportsbook.</li>
          <li>Better information does not remove risk. Most bettors lose money over time.</li>
        </ul>
      </Prose>
    </>
  );
}
