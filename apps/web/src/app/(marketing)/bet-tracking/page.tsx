import type { Metadata } from "next";
import { FeaturePage } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Bet tracking",
  description: "Track straight bets, parlays and futures. See profit, ROI and closing line value by sport, market and sportsbook.",
  alternates: { canonical: "/bet-tracking" },
};

export default function Page() {
  return (
    <FeaturePage
      copy={{
        title: "An honest record of every bet",
        lede: "Log a bet in a few seconds, settle it when it's over, and let OddVex do the arithmetic. Then see where your results really come from.",
        cta: { href: "/app/tracker", label: "Open the tracker" },
        points: [
          { title: "Any bet type", body: "Straight bets, parlays, same-game parlays and futures, with one or many legs. Enter odds as American, decimal or fractional." },
          { title: "Every outcome", body: "Won, lost, push, void, half won, half lost and cash-out. Payouts are computed for you and can be checked on the methodology page." },
          { title: "Profit and ROI", body: "Total staked, net profit, return on investment and record, with open exposure kept separate from settled results." },
          { title: "Breakdowns that explain results", body: "Performance by sport, market, bet type and sportsbook, and a cumulative profit chart over time." },
          { title: "Closing line value", body: "Record the closing price and OddVex reports whether you beat it. Over many bets that says more about your process than the win column does." },
          { title: "Sportsbook sync", body: "A sync layer is built and tested against a mock provider. Connecting real accounts needs an authorized vendor and is not live." },
        ],
        limits: [
          "Results you enter yourself are self-reported. OddVex labels them that way.",
          "Past results do not predict future results.",
          "You can export or delete your data, and delete your account, at any time from Settings.",
        ],
      }}
    />
  );
}
