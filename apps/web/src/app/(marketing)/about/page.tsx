import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "About",
  description: "Why OddVex exists and the principles behind it.",
  alternates: { canonical: "/about" },
};

export default function Page() {
  return (
    <>
      <PageIntro
        title="Sports betting information should be checkable"
        lede={`OddVex is built by ${SITE.company} for people who would rather see the numbers than be told what to think about them.`}
      />
      <Prose>
        <h2>Why we&rsquo;re building it</h2>
        <p>
          Betting markets are prices, and prices can be compared, converted and tracked. Yet most products in this space
          lead with picks and confidence. We think the more useful thing is plain: what every book is offering, what
          those prices imply, how old they are, and how your own record holds up.
        </p>
        <h2>How we work</h2>
        <ul>
          <li><strong>Show the working.</strong> Every figure traces to a documented formula.</li>
          <li><strong>Label uncertainty.</strong> Samples have sizes. Estimates have ranges. Old data says it&rsquo;s old.</li>
          <li><strong>No promises about outcomes.</strong> We don&rsquo;t sell locks and we don&rsquo;t publish accuracy claims we can&rsquo;t support.</li>
          <li><strong>Information only.</strong> OddVex doesn&rsquo;t take bets or move money.</li>
        </ul>
        <h2>Where things stand</h2>
        <p>
          OddVex is in preview. It currently runs on synthetic data with fictional teams, players and sportsbooks while
          licensed data is arranged. The product is intended for adults 21 and over in the United States.
        </p>
      </Prose>
    </>
  );
}
