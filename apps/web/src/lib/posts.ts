export type Post = {
  slug: string;
  title: string;
  description: string;
  published: string;
  minutes: number;
  sections: { heading: string; paragraphs: string[] }[];
};

export const POSTS: Post[] = [
  {
    slug: "what-odds-actually-say",
    title: "What odds actually say: implied probability in two minutes",
    description: "Every price is a probability wearing a costume. Here is how to read American odds as a percentage.",
    published: "2026-11-10",
    minutes: 3,
    sections: [
      {
        heading: "A price is a probability",
        paragraphs: [
          "American odds tell you how much you win relative to $100. At +150 you win $150 on a $100 stake. At −150 you stake $150 to win $100. Underneath, each price says how often the bet has to win for you to break even.",
          "For a plus price, divide 100 by the price plus 100. So +150 is 100 / 250, or 40%. For a minus price, divide the price by the price plus 100, ignoring the sign. So −150 is 150 / 250, or 60%.",
        ],
      },
      {
        heading: "Why the two sides add up to more than 100%",
        paragraphs: [
          "Take a spread priced at −110 on both sides. Each side implies 52.38%, and together they imply 104.76%. Nothing happens 104.76% of the time. The extra 4.76% is the sportsbook's margin, usually called the vig or the overround.",
          "That is why implied probability is the break-even rate for you, and not the book's honest estimate of the outcome. To get closer to the estimate you have to remove the margin, which is what no-vig probability does.",
        ],
      },
      {
        heading: "What to do with it",
        paragraphs: [
          "Reading prices as percentages makes books comparable. +136 implies 42.4% and +142 implies 41.3%. The second asks you to be right less often for the same payout structure, which is all a better price means.",
        ],
      },
    ],
  },
  {
    slug: "removing-the-vig",
    title: "Removing the vig: how to find the market's own estimate",
    description: "No-vig probability strips out the sportsbook's margin. Here is the arithmetic and where it can mislead.",
    published: "2026-11-12",
    minutes: 4,
    sections: [
      {
        heading: "The proportional method",
        paragraphs: [
          "Convert each side to its implied probability, add them up, and divide each by the total. With a favorite at −158 and an underdog at +136, the implied probabilities are 61.24% and 42.37%, which total 103.61%. Dividing through gives 59.1% and 40.9%.",
          "Those two numbers add up to 100%, and they are that book's margin-free view of the game. The 3.61% you removed is the book's hold on that market.",
        ],
      },
      {
        heading: "Why averaging across books helps",
        paragraphs: [
          "One book's no-vig number reflects that book's customers and risk as much as the game. Averaging several books' no-vig probabilities gives a steadier consensus. OddVex leaves stale and suspended prices out of that average, because an old price describes an old market.",
        ],
      },
      {
        heading: "Where it can mislead",
        paragraphs: [
          "The proportional method assumes the margin is spread evenly across outcomes. Books often shade longshots more heavily, so on lopsided markets the true split can sit a little further toward the favorite than the proportional answer suggests.",
          "A consensus is also just an estimate. It is the best public summary of what the market thinks, and the market is sometimes wrong. It is a reference point, not an answer key.",
        ],
      },
    ],
  },
  {
    slug: "seven-of-ten-is-not-seventy-percent",
    title: "Seven of ten is not seventy percent",
    description: "Why a player's recent hit rate tells you less than it seems to, and how a confidence range fixes the picture.",
    published: "2026-11-14",
    minutes: 4,
    sections: [
      {
        heading: "Small samples are noisy",
        paragraphs: [
          "A player has gone over a points line in seven of the last ten games. It is tempting to call that a 70% chance tonight. But a player whose true rate is exactly 50% will produce a seven-of-ten stretch, or better, about one time in six by luck alone.",
        ],
      },
      {
        heading: "Put a range on it",
        paragraphs: [
          "A confidence interval turns a hit rate into an honest statement about how much the sample can support. For seven of ten, the 95% Wilson interval runs from roughly 40% to 89%. For fourteen of twenty it narrows to roughly 48% to 85%. Same percentage, more evidence, tighter range.",
          "OddVex shows that range beside every hit rate, along with the sample size, so a hot ten-game stretch looks like what it is.",
        ],
      },
      {
        heading: "The line moved too",
        paragraphs: [
          "Sportsbooks see the same game logs. When a player runs hot, the line rises and the price on the over gets worse. A hit rate measured against tonight's line is more useful than one measured against old lines, and it still describes the past. Treat it as context for a decision, never as the probability.",
        ],
      },
    ],
  },
];

export function getPost(slug: string) {
  return POSTS.find((post) => post.slug === slug);
}
