import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { DraftBanner } from "@/components/marketing/draft-banner";
import { HELPLINE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Responsible gambling",
  description: `Help and practical limits if betting stops being fun. Call ${HELPLINE.display}.`,
  alternates: { canonical: "/responsible-gambling" },
};

export default function Page() {
  return (
    <>
      <PageIntro
        title="Responsible gambling"
        lede="Betting should be entertainment you can afford. If it stops being that, confidential help is available at any hour."
      />
      <Prose>
        <h2>Get help now</h2>
        {/* Every helpline fact below comes from HELPLINE in lib/site.ts, which records where and when it was checked. */}
        <ul>
          <li>
            Call <a href={HELPLINE.tel}><strong>{HELPLINE.number}</strong></a> ({HELPLINE.digits}), the {HELPLINE.name}, or text{" "}
            <a href={HELPLINE.sms}><strong>{HELPLINE.textTo}</strong></a> ({HELPLINE.textDigits}). It is confidential and answers 24 hours a day, every day.
          </li>
          <li>
            The helpline is not an emergency service. In a crisis, call or text <a href={HELPLINE.crisisTel}><strong>{HELPLINE.crisisNumber}</strong></a> (the{" "}
            {HELPLINE.crisisName}) or call <a href={HELPLINE.emergencyTel}><strong>{HELPLINE.emergencyNumber}</strong></a>.
          </li>
          <li>
            Online chat is offered on the {HELPLINE.council}&rsquo;s website, <a href={HELPLINE.site}>{HELPLINE.siteLabel}</a>.
          </li>
        </ul>
        <p>
          {HELPLINE.number} has been the number of the {HELPLINE.name} since {HELPLINE.inServiceSinceText}. 1-800-GAMBLER is a different line, run by the Council on Compulsive Gambling of New Jersey.
          Some states publish their own helpline. If yours does, you can call that one instead.
        </p>
        <p>These details were checked on {HELPLINE.verifiedOnText} against the {HELPLINE.council}&rsquo;s own pages.</p>
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
      {/* Only the commitments are draft text. The helpline facts above were checked on the date the page gives. */}
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
