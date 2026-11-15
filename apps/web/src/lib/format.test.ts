import { describe, expect, it } from "vitest";
import { formatAge, formatAmerican, formatDecimal, formatLine, formatMoney, formatPercent, formatPrice, titleCase } from "./format";

describe("formatAmerican", () => {
  it("signs positive prices and uses a true minus for negatives", () => {
    expect(formatAmerican(142)).toBe("+142");
    expect(formatAmerican(-165)).toBe("−165");
    expect(formatAmerican(100)).toBe("+100");
  });
  it("rounds fractional American prices", () => {
    expect(formatAmerican(141.6)).toBe("+142");
  });
});

describe("formatPrice", () => {
  const price = { american: -110, decimal: 1.9090909 };
  it("follows the chosen format", () => {
    expect(formatPrice(price, "american")).toBe("−110");
    expect(formatPrice(price, "decimal")).toBe("1.91");
    expect(formatDecimal(2.5)).toBe("2.50");
  });
});

describe("formatLine", () => {
  it("formats totals unsigned and spreads signed", () => {
    expect(formatLine(221.5)).toBe("221.5");
    expect(formatLine(-3.5, { signed: true })).toBe("−3.5");
    expect(formatLine(7, { signed: true })).toBe("+7");
    expect(formatLine(0, { signed: true })).toBe("PK");
  });
  it("returns an empty string when there is no line", () => {
    expect(formatLine(null)).toBe("");
    expect(formatLine(undefined)).toBe("");
  });
});

describe("formatPercent", () => {
  it("formats probabilities", () => {
    expect(formatPercent(0.4132)).toBe("41.3%");
    expect(formatPercent(0.5, 0)).toBe("50%");
  });
  it("does not invent a number for missing values", () => {
    expect(formatPercent(null)).toBe("n/a");
    expect(formatPercent(Number.NaN)).toBe("n/a");
  });
});

describe("formatMoney", () => {
  it("formats amounts, with an explicit sign on request", () => {
    expect(formatMoney(1250)).toBe("$1,250.00");
    expect(formatMoney(-20.5)).toBe("−$20.50");
    expect(formatMoney(42, { signed: true })).toBe("+$42.00");
    expect(formatMoney(0, { signed: true })).toBe("$0.00");
  });
});

describe("formatAge", () => {
  const now = new Date("2026-11-15T12:00:00Z");
  it("picks a readable unit", () => {
    expect(formatAge("2026-11-15T11:59:18Z", now)).toBe("42s ago");
    expect(formatAge("2026-11-15T11:51:00Z", now)).toBe("9 min ago");
    expect(formatAge("2026-11-15T09:00:00Z", now)).toBe("3h ago");
    expect(formatAge("2026-11-10T12:00:00Z", now)).toBe("5d ago");
  });
  it("never reports a negative age for clock skew", () => {
    expect(formatAge("2026-11-15T12:00:05Z", now)).toBe("0s ago");
  });
});

describe("titleCase", () => {
  it("turns keys into labels", () => {
    expect(titleCase("passing_yards")).toBe("Passing Yards");
  });
});
