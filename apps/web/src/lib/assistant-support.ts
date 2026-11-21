import { HELPLINE } from "@/lib/site";

/**
 * The assistant's support replies (`support` set on the answer: crisis, distress or underage)
 * give phone and text numbers in the answer text. These helpers make each number a link, so
 * it can be tapped on a phone. The numbers and their links come from `HELPLINE` in
 * `lib/site.ts`; the API writes the same facts from its own `helpline.py`.
 */
export type SupportPart = { text: string; href?: string };

const LINKS: Record<string, string> = {
  [HELPLINE.number]: HELPLINE.tel,
  [HELPLINE.digits]: HELPLINE.tel,
  [HELPLINE.textTo]: HELPLINE.sms,
  [HELPLINE.textDigits]: HELPLINE.sms,
  [HELPLINE.crisisNumber]: HELPLINE.crisisTel,
  [HELPLINE.emergencyNumber]: HELPLINE.emergencyTel,
};

const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Longest first, and never inside a longer run of digits, letters or dashes ("19885" is not 988). */
const NUMBER = new RegExp(
  `(?<![A-Za-z0-9-])(${Object.keys(LINKS)
    .sort((a, b) => b.length - a.length)
    .map(escape)
    .join("|")})(?![A-Za-z0-9-])`,
  "g",
);

/** `text` cut into plain runs and numbers, each number with its phone or text link. */
export function supportParts(text: string): SupportPart[] {
  const parts: SupportPart[] = [];
  let last = 0;
  for (const match of text.matchAll(NUMBER)) {
    const start = match.index ?? 0;
    if (start > last) parts.push({ text: text.slice(last, start) });
    parts.push({ text: match[0], href: LINKS[match[0]] });
    last = start + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}

/** A short, calm heading for each support case. */
export const SUPPORT_TITLE: Record<"crisis" | "distress" | "underage", string> = {
  crisis: "Help is available now",
  distress: "Help with gambling",
  underage: "OddVex is for adults 21 and over",
};
