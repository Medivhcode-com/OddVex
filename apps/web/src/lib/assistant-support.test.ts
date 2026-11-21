import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AssistantReplyView } from "@/components/app/assistant-chat";
import { supportParts } from "@/lib/assistant-support";
import type { AssistantReply } from "@/lib/types";

const DISCLAIMER = "OddVex gives information and math, not betting advice or predictions. All sports data shown is synthetic sample data.";
const HELPLINE_SENTENCE = "The National Problem Gambling Helpline is confidential and answers 24 hours a day, every day: call 1-800-MY-RESET (1-800-697-3738) or text 800GAM (800426).";
const CRISIS_SENTENCE = "The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide and Crisis Lifeline) or call 911.";

/** The three support replies as the API writes them (assistant/safeguards.py), shortened where the wording does not matter here. */
const ANSWERS = {
  crisis: [
    "I'm sorry you are going through this. You don't have to face it alone, and help is available right now.",
    "Call or text 988 (the Suicide and Crisis Lifeline). If you are in immediate danger, call 911.",
    `If gambling is part of what is weighing on you, there is a helpline for that too. ${HELPLINE_SENTENCE}`,
  ].join("\n\n"),
  distress: ["Thank you for telling me. I'm leaving prices and other betting data out of this reply.", HELPLINE_SENTENCE, CRISIS_SENTENCE].join("\n\n"),
  underage: ["OddVex is for adults 21 and over, so I can't give odds, prices or any other betting information here.", HELPLINE_SENTENCE, CRISIS_SENTENCE].join("\n\n"),
} as const;

function support(kind: keyof typeof ANSWERS): AssistantReply {
  return {
    intent: "support",
    answer: ANSWERS[kind],
    data: null,
    sources: [],
    suggestions: [{ label: "Help and support resources", href: "/responsible-gambling" }],
    disclaimer: DISCLAIMER,
    support: { case: kind },
  } as AssistantReply;
}

const render = (reply: AssistantReply) => renderToStaticMarkup(createElement(AssistantReplyView, { reply }));
const hrefs = (html: string) => [...html.matchAll(/href="([^"]+)"/g)].map((match) => match[1]);

describe("supportParts", () => {
  it("turns every helpline, crisis and emergency number into a link, as it appears", () => {
    const parts = supportParts(CRISIS_SENTENCE + " " + HELPLINE_SENTENCE);
    expect(parts.filter((part) => part.href).map((part) => [part.text, part.href])).toEqual([
      ["988", "tel:988"],
      ["911", "tel:911"],
      ["1-800-MY-RESET", "tel:+18006973738"],
      ["1-800-697-3738", "tel:+18006973738"],
      ["800GAM", "sms:800426"],
      ["800426", "sms:800426"],
    ]);
    expect(parts.map((part) => part.text).join("")).toBe(CRISIS_SENTENCE + " " + HELPLINE_SENTENCE);
  });

  it("leaves other numbers alone", () => {
    expect(supportParts("adults 21 and over, 24 hours a day, 19885 and 9110").every((part) => !part.href)).toBe(true);
  });
});

describe("a support reply in the assistant", () => {
  it("two support cards of the same case in one chat each name their own heading", () => {
    const html = renderToStaticMarkup(createElement("div", null, createElement(AssistantReplyView, { reply: support("crisis") }), createElement(AssistantReplyView, { reply: support("crisis") })));
    const labels = [...html.matchAll(/aria-labelledby="([^"]+)"/g)].map((match) => match[1]);
    expect(labels).toHaveLength(2);
    expect(new Set(labels).size).toBe(2);
    for (const label of labels) expect(html).toContain(`id="${label}"`);
  });

  for (const kind of ["crisis", "distress", "underage"] as const) {
    it(`${kind}: a support card with tappable numbers and no data panel`, () => {
      const html = render(support(kind));
      expect(html).toContain('data-support-case="' + kind + '"');
      expect(html).not.toContain("Sources:");
      expect(html).not.toContain("No data was used for this answer");
      expect(html).not.toContain(DISCLAIMER);
      const links = hrefs(html);
      expect(links).toContain("tel:988");
      expect(links).toContain("tel:+18006973738");
      expect(links).toContain("sms:800426");
      expect(links).toContain("/responsible-gambling");
      if (kind === "crisis") expect(links).toContain("tel:911");
    });
  }

  it("the crisis card leads with the crisis line, not with betting", () => {
    const html = render(support("crisis"));
    expect(html).toMatch(/Help is available/);
    expect(html.indexOf("tel:988")).toBeLessThan(html.indexOf("tel:+18006973738"));
  });

  it("an ordinary answer keeps its sources panel and disclaimer", () => {
    const html = render({
      intent: "compare_odds",
      answer: "Best moneyline price for the Harbor City Tides: +209 at Northline.",
      data: { price: 209 },
      sources: [{ label: "Odds board", data_mode: "synthetic", as_of: "2026-11-21T00:00:00Z" }],
      suggestions: [],
      disclaimer: DISCLAIMER,
      support: null,
    } as AssistantReply);
    expect(html).toContain("Sources:");
    expect(html).toContain(DISCLAIMER);
    expect(html).not.toContain("data-support-case");
  });
});
