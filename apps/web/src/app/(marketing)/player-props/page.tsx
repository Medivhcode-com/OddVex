import type { Metadata } from "next";
import { FeaturePage } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Player prop analyzer",
  description: "Research player props with game logs, splits and hit rates that show their sample size and confidence range.",
  alternates: { canonical: "/player-props" },
};

export default function Page() {
  return (
    <FeaturePage
      copy={{
        title: "Research a player prop without guessing",
        lede: "Put a player's recent games against the posted line. See how often they cleared it, in which situations, and how much weight that record can bear.",
        cta: { href: "/app/props", label: "Open the prop board" },
        points: [
          { title: "Game logs against the line", body: "Each game is drawn as a bar against tonight's line, marked over, under or push, so the pattern is visible before you read a number." },
          { title: "Windows and splits", body: "Last 5, 10 or 20 games or the full season. Home, away, or only games against tonight's opponent." },
          { title: "Hit rates with a range", body: "A hit rate is shown with its sample size and a 95% Wilson interval. Seven overs in ten games is consistent with a true rate anywhere from roughly 40% to 89%." },
          { title: "Line shopping for props", body: "The same prop is often posted at different lines and prices. OddVex lists each book's line with over and under prices and marks the best of each." },
          { title: "A board for tonight", body: "Scan every posted prop by league and market with the consensus line, best prices and recent hit rate in one row." },
          { title: "Context when it's licensed", body: "Injury and lineup context will appear once a licensed source is connected. Until then the app does not show or imply any." },
        ],
        limits: [
          "A hit rate describes past games. It is not a probability for the next one.",
          "Small samples swing widely. Read the interval, not only the percentage.",
          "The preview uses synthetic, fictional players and game logs.",
        ],
      }}
    />
  );
}
