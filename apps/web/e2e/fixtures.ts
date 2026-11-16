import { expect, test as base, type Page as PlaywrightPage } from "@playwright/test";

/**
 * Every test in the suite fails if the browser reports a Content-Security-Policy violation,
 * so the theme toggle, odds toggle, calculators, charts and downloads are all exercised
 * under the real policy. A test that provokes a violation on purpose empties the list.
 */
/** Records every Content-Security-Policy violation the browser reports on `page` into `violations`. */
export function watchCsp(page: PlaywrightPage, violations: string[]) {
  page.on("console", (message) => {
    if (/content[- ]security[- ]policy/i.test(message.text())) violations.push(`${page.url()}: ${message.text()}`);
  });
}

export const test = base.extend<{ cspViolations: string[] }>({
  cspViolations: [
    async ({ page }, use) => {
      const violations: string[] = [];
      watchCsp(page, violations);
      await use(violations);
      expect(violations, "Content-Security-Policy violations reported by the browser").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
export type { Page } from "@playwright/test";
