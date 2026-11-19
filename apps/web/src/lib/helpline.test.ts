import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { HELPLINE, RESPONSIBLE_GAMBLING_LEAD, RESPONSIBLE_GAMBLING_LINE, SITE } from "./site";

const KEYPAD: Record<string, string> = { ABC: "2", DEF: "3", GHI: "4", JKL: "5", MNO: "6", PQRS: "7", TUV: "8", WXYZ: "9" };
/** The digits a phone dials for a number written with letters. */
const dial = (text: string) =>
  text
    .toUpperCase()
    .replace(/[A-Z]/g, (letter) => Object.entries(KEYPAD).find(([letters]) => letters.includes(letter))?.[1] ?? letter)
    .replace(/\D/g, "");

const WEB = path.resolve(__dirname, "../..");
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const file = path.join(dir, name);
    if (statSync(file).isDirectory()) return sources(file);
    return /\.(ts|tsx|css|md|mdx|json)$/.test(name) ? [file] : [];
  });
}
const rel = (file: string) => path.relative(WEB, file).split(path.sep).join("/");

describe("helpline facts (checked 2026-11-19 against the National Council on Problem Gambling's own pages)", () => {
  it("names the National Problem Gambling Helpline and spells its number three ways", () => {
    expect(HELPLINE.name).toBe("National Problem Gambling Helpline");
    expect(HELPLINE.number).toBe("1-800-MY-RESET");
    expect(HELPLINE.digits).toBe("1-800-697-3738");
    expect(HELPLINE.display).toBe("1-800-MY-RESET (1-800-697-3738)");
    expect(HELPLINE.tel).toBe("tel:+18006973738");
    expect(dial(HELPLINE.number)).toBe(dial(HELPLINE.digits));
    expect(HELPLINE.tel).toBe(`tel:+${dial(HELPLINE.digits)}`);
  });

  it("gives the text line in letters, in digits and as a link", () => {
    expect(HELPLINE.textTo).toBe("800GAM");
    expect(HELPLINE.textDigits).toBe("800426");
    expect(dial(HELPLINE.textTo)).toBe(HELPLINE.textDigits);
    expect(HELPLINE.sms).toBe("sms:800426");
  });

  it("gives the crisis lines, which the helpline is not", () => {
    expect(HELPLINE.crisisName).toBe("Suicide and Crisis Lifeline");
    expect(HELPLINE.crisisNumber).toBe("988");
    expect(HELPLINE.crisisTel).toBe("tel:988");
    expect(HELPLINE.crisisSms).toBe("sms:988");
    expect(HELPLINE.emergencyNumber).toBe("911");
    expect(HELPLINE.emergencyTel).toBe("tel:911");
  });

  it("records when the number came into service and when the facts were checked", () => {
    expect(HELPLINE.inServiceSince).toBe("2026-01-29");
    expect(HELPLINE.inServiceSinceText).toBe("January 29, 2026");
    expect(HELPLINE.verifiedOn).toBe("2026-11-19");
    expect(HELPLINE.verifiedOnText).toBe("November 19, 2026");
    const long = (iso: string) => new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
    expect(HELPLINE.inServiceSinceText).toBe(long(HELPLINE.inServiceSince));
    expect(HELPLINE.verifiedOnText).toBe(long(HELPLINE.verifiedOn));
  });

  it("links to the front page of the Council, not to a deeper address", () => {
    expect(HELPLINE.council).toBe("National Council on Problem Gambling");
    expect(HELPLINE.site).toBe("https://www.ncpgambling.org");
    expect(HELPLINE.siteLabel).toBe("ncpgambling.org");
  });

  it("words the short line as agreed", () => {
    expect(RESPONSIBLE_GAMBLING_LINE).toBe("21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738).");
    expect(RESPONSIBLE_GAMBLING_LINE).toBe(`${RESPONSIBLE_GAMBLING_LEAD} ${HELPLINE.display}.`);
  });

  it("keeps the helpline out of the general site constants", () => {
    expect(SITE).not.toHaveProperty("helpline");
  });
});

describe("the helpline in the rest of the web app", () => {
  const app = sources(path.join(WEB, "src")).filter((file) => !/\.test\.tsx?$/.test(file));
  const all = [...sources(path.join(WEB, "src")), ...sources(path.join(WEB, "e2e"))];

  it("is written in one module only: pages and components read the constants", () => {
    expect(app.length).toBeGreaterThan(100);
    const written = app.filter((file) => /MY-?RESET|697-?3738|8006973738|800GAM|800426|ncpgambling/i.test(readFileSync(file, "utf8"))).map(rel);
    expect(written).toEqual(["src/lib/site.ts"]);
  });

  it("writes no phone or text link by hand", () => {
    const linked = app.filter((file) => /["'`](tel|sms):/.test(readFileSync(file, "utf8"))).map(rel);
    expect(linked).toEqual(["src/lib/site.ts"]);
  });

  it("names the New Jersey line once, in the sentence that says whose line it is", () => {
    // The old number, as a word and in digits. The word is written in halves so that a search of
    // the source for it finds only the one sentence on the responsible-gambling page.
    const old = new RegExp(`${"GAMB"}${"LER"}|426-?2537`, "i");
    const hits = all.flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .filter((line) => old.test(line))
        .map((line) => ({ file: rel(file), newJersey: /Council on Compulsive Gambling of New Jersey/.test(line), national: /national/i.test(line) })),
    );
    expect(hits).toEqual([{ file: "src/app/(marketing)/responsible-gambling/page.tsx", newJersey: true, national: false }]);
  });
});
