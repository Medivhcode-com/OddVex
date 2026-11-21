import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Schemas } from "@oddvex/types";
import { ReportSummary } from "@/components/app/admin-report";

type Report = Schemas["AdminReportOut"];

function report(overrides: Partial<Report>): Report {
  return {
    id: "rep1",
    status: "open",
    reason: "harassment",
    details: null,
    target_type: "comment",
    target_id: "com1",
    target_exists: true,
    target_text: "The comment as it is now.",
    target_summary: null,
    target_moderation_status: "visible",
    reported_text: "The comment as it is now.",
    reported_summary: null,
    target_changed_since_report: false,
    author_edit: false,
    author_earlier_removals: 0,
    reporter: { user_id: "u2", handle: "reporter_x", status: "active" },
    author: { user_id: "u1", handle: "author_y", status: "active" },
    created_at: "2026-11-21T00:00:00Z",
    resolved_at: null,
    resolved_by: null,
    resolution_action: null,
    resolution_note: null,
    ...overrides,
  } as Report;
}

const words = (r: Report) =>
  renderToStaticMarkup(createElement(ReportSummary, { report: r }))
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;|&rsquo;|’/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();

describe("a report in the moderation queue", () => {
  it("unchanged content: the stored text once, with no 'as reported' copy", () => {
    const text = words(report({}));
    expect(text).toContain("Comment reported for harassment");
    expect(text).toContain("The comment as it is now.");
    expect(text).not.toContain("As reported");
  });

  it("deleted since the report: shows the text and summary kept with the report", () => {
    const text = words(
      report({ target_type: "pick", target_exists: false, target_text: null, target_summary: null, reported_text: "Harassing analysis text.", reported_summary: "Tides ML, Tides at Rams", target_changed_since_report: true }),
    );
    expect(text).toContain("As reported");
    expect(text).toContain("Harassing analysis text.");
    expect(text).toContain("Tides ML, Tides at Rams");
    expect(text).toContain("Target deleted");
    expect(text).toMatch(/Now The item no longer exists\./);
  });

  it("edited since the report: shows both versions", () => {
    const text = words(report({ target_text: "A softened version.", reported_text: "The original insult.", target_changed_since_report: true }));
    expect(text).toMatch(/As reported .*The original insult\./);
    expect(text).toMatch(/Now .*A softened version\./);
    expect(text).toContain("Changed since the report");
  });

  it("a report made before copies were kept says no copy exists", () => {
    const text = words(report({ target_exists: false, target_text: null, reported_text: null, reported_summary: null, target_changed_since_report: true }));
    expect(text).toContain("No copy of the content was kept with this report.");
  });

  it("an entry opened because the author edited a moderated profile carries the badge and says it stays hidden", () => {
    const text = words(
      report({
        target_type: "profile",
        target_id: "author_y",
        reason: "other",
        author_edit: true,
        reporter: { user_id: "u1", handle: "author_y", status: "active" },
        target_moderation_status: "hidden",
        target_summary: "@author_y",
        target_text: "New bio after the edit.",
        reported_text: "New bio after the edit.",
        reported_summary: "@author_y",
      } as Partial<Report>),
    );
    expect(text).toContain("Edited by its author");
    expect(text).toContain("Profile edited after moderation");
    expect(text).toMatch(/stays hidden or removed until an administrator restores it/);
    expect(text).toContain("New bio after the edit.");
    expect(text).not.toContain("reported for other");
  });

  it("shows how often moderators hid or removed the author's content before", () => {
    expect(words(report({ author_earlier_removals: 3 }))).toContain("Earlier removals of this author's content: 3");
    expect(words(report({ author_earlier_removals: 0 }))).toContain("Earlier removals of this author's content: 0");
  });
});
