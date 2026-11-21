import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ContactPage from "@/app/(marketing)/contact/page";
import { SuspendedNotice } from "@/components/app/suspended-notice";

const words = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&#x27;|&rsquo;|’/g, "'").replace(/\s+/g, " ").trim();

describe("the suspended-account notice on the sign-in screen", () => {
  it("says how to ask for a copy of the data or for deletion: write to the contact address", () => {
    const html = renderToStaticMarkup(createElement(SuspendedNotice, { role: "alert", email: "support@example.test" }));
    expect(words(html)).toContain("This account is suspended");
    expect(words(html)).toMatch(/To ask for a copy of your data, or for the account and its data to be deleted, write to support@example\.test/);
    expect(html).toContain('href="mailto:support@example.test"');
  });

  it("points to the contact page while no address is set", () => {
    const html = renderToStaticMarkup(createElement(SuspendedNotice, { role: "status", email: "" }));
    expect(words(html)).toMatch(/To ask for a copy of your data, or for the account and its data to be deleted, use the contact page/);
    expect(html).toContain('href="/contact"');
    expect(html).not.toContain("mailto:");
  });
});

describe("the contact page", () => {
  it("tells people who cannot sign in how to get a copy of their data or have the account deleted", () => {
    const text = words(renderToStaticMarkup(createElement(ContactPage)));
    expect(text).toMatch(/If you cannot sign in, .*ask for a copy of your data or for the account to be deleted/);
  });
});
