import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AuthLayout from "@/app/(auth)/layout";
import ContactPage from "@/app/(marketing)/contact/page";
import HelpPage from "@/app/(marketing)/help/page";
import MethodologyPage from "@/app/(marketing)/methodology/page";
import PricingPage, { metadata as pricingMetadata } from "@/app/(marketing)/pricing/page";
import PrivacyPage from "@/app/(marketing)/privacy/page";
import ResponsibleGamblingPage, { metadata as rgMetadata } from "@/app/(marketing)/responsible-gambling/page";
import { MarketingFooter } from "@/components/marketing/chrome";
import { StakeReminderNotice } from "@/components/app/notification-settings";
import { ResponsibleGamblingLine } from "@/components/ui/helpline";

/** The words a reader sees: markup removed, entities decoded, apostrophes straightened, whitespace collapsed. */
function text(element: ReactElement): string {
  return renderToStaticMarkup(element)
    .replace(/<script[\s\S]*?<\/script>/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/’/g, "'")
    .replace(/\s+/g, " ")
    .replace(/ ([.,;:)])/g, "$1")
    .replace(/\( /g, "(")
    .trim();
}
const html = (element: ReactElement) => renderToStaticMarkup(element);

const HELPLINE = "1-800-MY-RESET (1-800-697-3738)";
const SHORT_LINE = `21+. OddVex does not take wagers. Gambling problem? Call ${HELPLINE}.`;
/** Wording the brand voice bans outright. */
const BANNED = [/\block\b/i, /guaranteed/i, /can['’]t lose/i, /risk-free/i, /sure thing/i, /win either way/i];

describe("the short responsible-gambling line", () => {
  it("is the agreed sentence, with the number as a phone link", () => {
    const line = createElement(ResponsibleGamblingLine, {});
    expect(text(line)).toBe(SHORT_LINE);
    expect(html(line)).toContain('href="tel:+18006973738"');
  });

  it("can carry a link to the responsible-gambling page", () => {
    const line = createElement(ResponsibleGamblingLine, { more: true });
    expect(text(line)).toBe(`${SHORT_LINE} Help and limits`);
    expect(html(line)).toContain('href="/responsible-gambling"');
  });

  it("closes the login and signup screens", () => {
    const layout = html(createElement(AuthLayout, null, "form"));
    const footer = layout.slice(layout.indexOf("<footer"));
    expect(footer.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim()).toBe(SHORT_LINE);
  });

  it("is in the marketing footer as a phone link, named as the national helpline", () => {
    const footer = createElement(MarketingFooter);
    expect(text(footer)).toContain(`call ${HELPLINE}, the National Problem Gambling Helpline.`);
    expect(html(footer)).toContain('href="tel:+18006973738"');
    expect(text(footer)).not.toMatch(/call or text/i);
  });

  it("ends the staking reminder notice, without calling the help free", () => {
    const notice = createElement(StakeReminderNotice, { reminder: { exceeded: true, weekly_stake_threshold: 50, staked_this_week: 60 } as never });
    expect(text(notice)).toContain(`confidential help is available at ${HELPLINE}.`);
    expect(text(notice)).not.toMatch(/\bfree\b/i);
    expect(html(notice)).toContain('href="tel:+18006973738"');
  });
});

describe("responsible-gambling page", () => {
  const page = createElement(ResponsibleGamblingPage);
  const words = text(page);
  const helpSection = words.slice(words.indexOf("Get help now"), words.indexOf("Signs it may be a problem"));

  it("states the verified helpline facts in full sentences", () => {
    expect(helpSection).toContain("Call 1-800-MY-RESET (1-800-697-3738), the National Problem Gambling Helpline, or text 800GAM (800426). It is confidential and answers 24 hours a day, every day.");
    expect(helpSection).toContain("The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide and Crisis Lifeline) or call 911.");
    expect(helpSection).toContain("Online chat is offered on the National Council on Problem Gambling's website, ncpgambling.org.");
    expect(helpSection).toContain("1-800-MY-RESET has been the number of the National Problem Gambling Helpline since January 29, 2026.");
    expect(helpSection).toContain("Some states publish their own helpline.");
    expect(helpSection).toContain("These details were checked on November 19, 2026 against the National Council on Problem Gambling's own pages.");
  });

  it("links each number, and the Council's front page only", () => {
    const markup = html(page);
    for (const href of ["tel:+18006973738", "sms:800426", "tel:988", "tel:911", "https://www.ncpgambling.org"]) expect(markup).toContain(`href="${href}"`);
    expect(markup).not.toMatch(/ncpgambling\.org\/[a-z]/i);
  });

  it("names the old number once, as the New Jersey council's line, and never as the national helpline", () => {
    const old = new RegExp(`1-800-${"GAMB"}${"LER"}`, "g");
    expect(words.match(old)).toHaveLength(1);
    expect(words).toMatch(new RegExp(`1-800-${"GAMB"}${"LER"} is a different line, run by the Council on Compulsive Gambling of New Jersey\\.`));
    expect(words).not.toMatch(/426-?2537/);
  });

  it("drops what was not verified: that the help is free, and texting the phone number", () => {
    expect(words).not.toMatch(/(^|[^-\w])free\b/i);
    expect(words).not.toMatch(/call or text 1-800/i);
    expect(words).not.toMatch(/24\/7/);
    expect(rgMetadata.description).toBe(`Help and practical limits if betting stops being fun. Call ${HELPLINE}.`);
  });
});

describe("pricing page", () => {
  const words = text(createElement(PricingPage));

  it("says what is true: the preview is free, paid plans are planned, nothing about them is decided", () => {
    expect(words).toContain("Everything in the preview is free to use.");
    expect(words).toContain("Paid plans are planned. What they will include and what they will cost has not been decided, so this page lists no plans and no prices.");
    expect(words).toContain("its price, renewal terms and how to cancel will be shown here before you are asked to pay for anything.");
    expect(pricingMetadata.description).toBe("Everything in the OddVex preview is free to use. Paid plans are planned; what they will include and cost has not been decided.");
  });

  it("presents no plan name, price, feature split or standing promise", () => {
    for (const claim of [/premium/i, /\$\s?\d/, /stays? free/i, /remain available/i, /without paying/i, /odds history/i, /prop filters/i, /assistant limits/i, /alerts/i, /trial/i]) {
      expect(words, String(claim)).not.toMatch(claim);
    }
    const markup = html(createElement(PricingPage));
    expect(markup).not.toMatch(/<(ul|ol|table|h2)\b/);
  });
});

describe("privacy page, export and deletion", () => {
  const words = text(createElement(PrivacyPage));

  it("says what a security log entry holds, details included", () => {
    expect(words).toContain(
      "Each entry holds the time, the internal ID of the account, the action taken, the ID of the item it concerned, the IP address the request came from, a request ID and, for some actions, a short detail",
    );
    expect(words).toContain("the result of a settled bet, the team, player or game you followed");
  });

  it("describes the export by what it holds and what it leaves out", () => {
    expect(words).toContain("Settings, then Download my data, gives you one JSON file.");
    expect(words).toContain("your own security log entries");
    expect(words).toContain("It does not contain your password or its hash.");
    expect(words).toContain("the time of your last sign-in, the time your password was last changed, whether the account is active or suspended, and the email-confirmation and password-reset messages stored for you");
    expect(words).toContain("Each download is recorded in the security log.");
    expect(words).not.toContain("a copy of what your account holds");
  });

  it("says what deletion removes and the three things it leaves", () => {
    expect(words).toContain("They are gone from the live database as soon as the request completes");
    expect(words).toContain("Security log entries are kept after an account is deleted, and one more is added to record the deletion.");
    expect(words).toContain("Nothing removes these entries yet. The retention period is to be confirmed before launch.");
    expect(words).toContain("A copy made before you deleted your account still holds the account, your email address included, until that copy is removed.");
    expect(words).toContain("its community handle stays reserved, so that the suspension cannot be undone by signing up again. No email address, and no fingerprint of one, is kept for this.");
    expect(words).not.toMatch(/stored account messages immediately/);
  });

  it("covers a person who cannot sign in", () => {
    expect(words).toContain("If you cannot sign in, for example because the account is suspended or you no longer have the password, write to the address on the contact page.");
    expect(words).toContain("Staff can produce the same data file for you, or delete the account, on request.");
    expect(words).toContain("not your email address");
  });
});

describe("contact page", () => {
  const words = text(createElement(ContactPage));

  it("sends a person who cannot sign in to the contact address", () => {
    expect(words).toContain("To delete your account and data, sign in and use Settings, then Delete account.");
    expect(words).toMatch(/If you cannot sign in, write to the (address above|contact address once it is published here) and ask for a copy of your data or for the account to be deleted\. Staff can do either on request\./);
    expect(words).not.toContain("It takes effect immediately.");
  });

  it("gives the helpline as a phone link", () => {
    expect(words).toContain(`call ${HELPLINE}, the National Problem Gambling Helpline.`);
    expect(html(createElement(ContactPage))).toContain('href="tel:+18006973738"');
  });
});

describe("parlay copy on the methodology and help pages", () => {
  const methodology = text(createElement(MethodologyPage));
  const help = text(createElement(HelpPage));
  const parlays = methodology.slice(methodology.indexOf("Parlays"), methodology.indexOf("Settlement"));

  it("says what the tool shows and that it shows no chance of every leg winning", () => {
    expect(parlays).toContain("The parlay tool shows the combined price, the payout and the break-even rate.");
    expect(parlays).toContain("It does not show a chance that every leg wins.");
    expect(parlays).toContain("A fair price for a parlay, built from the no-vig prices of its legs, is planned and not built.");
    expect(help).toMatch(/Does the parlay tool show the chance that every leg wins\? \+ No\. It shows the combined price, the payout and the break-even rate/);
    expect(help).toContain("is planned and not built.");
  });

  it("promises no combined probability anywhere", () => {
    for (const words of [methodology, help]) {
      expect(words).not.toMatch(/combined probability/i);
      expect(words).not.toMatch(/assuming independence/i);
      expect(words).not.toMatch(/for some parlays/i);
    }
  });

  it("answers the deletion question for someone who cannot sign in, in the page and in the structured data", () => {
    expect(help).toContain("If you cannot sign in, write to the address on the contact page and staff can delete the account for you.");
    const markup = html(createElement(HelpPage));
    const data = JSON.parse(markup.slice(markup.indexOf(">", markup.indexOf("<script")) + 1, markup.indexOf("</script>")));
    const answers = Object.fromEntries(data.mainEntity.map((entry: { name: string; acceptedAnswer: { text: string } }) => [entry.name, entry.acceptedAnswer.text]));
    expect(answers["Does the parlay tool show the chance that every leg wins?"]).toMatch(/^No\. It shows the combined price, the payout and the break-even rate/);
    expect(answers["How do I delete my data?"]).toContain("If you cannot sign in");
  });
});

describe("copy rules", () => {
  it("keeps banned wording out of the rewritten pages", () => {
    const pages = { pricing: PricingPage, privacy: PrivacyPage, contact: ContactPage, methodology: MethodologyPage, help: HelpPage };
    for (const [name, page] of Object.entries(pages)) {
      const words = text(createElement(page));
      for (const banned of BANNED) expect(words, `${name} ${banned}`).not.toMatch(banned);
    }
    // The helpline section of the responsible-gambling page; its draft commitments name the banned claims in order to rule them out.
    const rg = text(createElement(ResponsibleGamblingPage));
    for (const banned of BANNED) expect(rg.slice(0, rg.indexOf("What OddVex commits to")), String(banned)).not.toMatch(banned);
  });
});
