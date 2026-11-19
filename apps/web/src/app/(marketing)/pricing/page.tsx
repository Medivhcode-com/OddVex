import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";
import { ButtonLink } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Everything in the OddVex preview is free to use. Paid plans are planned; what they will include and cost has not been decided.",
  alternates: { canonical: "/pricing" },
};

/**
 * No plan names, prices or features-by-plan here: none has been decided. The page says only
 * what is true today, and what will be shown before anyone is asked to pay.
 */
export default function Page() {
  return (
    <>
      <PageIntro title="Free while OddVex is in preview" lede="Everything in the preview is free to use. There is nothing to buy, and we don't ask for a card.">
        <ButtonLink href="/signup" size="lg">
          Create an account
        </ButtonLink>
      </PageIntro>
      <Prose>
        <p>
          Paid plans are planned. What they will include and what they will cost has not been decided, so this page lists no plans and no prices.
        </p>
        <p>When a paid plan is offered, its price, renewal terms and how to cancel will be shown here before you are asked to pay for anything.</p>
      </Prose>
    </>
  );
}
