import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/chrome";
import { ButtonLink, Notice } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Get the app",
  description: "OddVex for iOS and Android is in development. The web app works on any phone today.",
  alternates: { canonical: "/download" },
};

export default function Page() {
  return (
    <>
      <PageIntro
        title="The web app works on your phone today"
        lede="OddVex for iOS and Android is in development and is not in the App Store or Google Play yet. Until it is, the web app is built for one-handed use on a phone."
      >
        <ButtonLink href="/app" size="lg">
          Open the web app
        </ButtonLink>
      </PageIntro>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Notice title="No store listings exist yet">
          If you see an app called OddVex in a store before this page links to it, it isn&rsquo;t ours.
        </Notice>
      </div>
    </>
  );
}
