import type { Schemas } from "@oddvex/types";
import { Badge } from "@/components/ui/primitives";
import { reasonLabel } from "@/lib/community-copy";
import { titleCase } from "@/lib/format";

type Report = Schemas["AdminReportOut"];

export const TARGET_LABEL: Record<string, string> = { pick: "Pick", comment: "Comment", profile: "Profile" };

function Quote({ text }: { text: string }) {
  return <blockquote className="mt-1 max-w-prose whitespace-pre-line break-words rounded-cell border border-line bg-bg px-3 py-2 text-sm">{text}</blockquote>;
}

/** The content as it was when the report was made, kept with the report by the API. */
function AsReported({ report }: { report: Report }) {
  return (
    <div>
      <p className="text-xs text-muted">As reported</p>
      {report.reported_summary ? <p className="mt-1 break-words text-sm text-muted">{report.reported_summary}</p> : null}
      {report.reported_text ? <Quote text={report.reported_text} /> : null}
      {!report.reported_text && !report.reported_summary ? <p className="mt-1 text-sm text-muted">No copy of the content was kept with this report.</p> : null}
    </div>
  );
}

/**
 * The top of one entry in the moderation queue: what was reported, its state, and the text.
 *
 * When the content was deleted or changed after the report (`target_exists` false or
 * `target_changed_since_report` true), the copy the API kept with the report is shown next to
 * the content as it is now, so a moderator can still judge what was reported. An entry the API
 * opened because the author edited a moderated profile (`author_edit`) is labelled as such.
 * Every text is shown as plain text, exactly as stored.
 */
export function ReportSummary({ report }: { report: Report }) {
  const target = TARGET_LABEL[report.target_type] ?? titleCase(report.target_type);
  const changed = !report.target_exists || report.target_changed_since_report;
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <h3 className="font-medium">{report.author_edit ? "Profile edited after moderation" : `${target} reported for ${reasonLabel(report.reason).toLowerCase()}`}</h3>
        <p className="flex flex-wrap items-center gap-1.5">
          <Badge tone={report.status === "open" ? "warn" : "neutral"}>{report.status === "open" ? "Open" : "Resolved"}</Badge>
          <Badge>Target: {target}</Badge>
          {report.author_edit ? <Badge tone="second">Edited by its author</Badge> : null}
          {report.target_exists ? null : <Badge>Target deleted</Badge>}
          {report.target_exists && report.target_changed_since_report ? <Badge>Changed since the report</Badge> : null}
          {report.target_moderation_status && report.target_moderation_status !== "visible" ? <Badge tone="second">Now {report.target_moderation_status}</Badge> : null}
        </p>
      </div>
      {report.author_edit ? (
        <p className="max-w-prose text-sm">
          The author edited this profile after moderators hid or removed it. It stays hidden or removed until an administrator restores it. The text below is the edited version.
        </p>
      ) : null}
      {changed ? <AsReported report={report} /> : null}
      <div>
        <p className="text-xs text-muted">{changed ? "Now" : "Reported content"}</p>
        {report.target_summary ? <p className="mt-1 break-words text-sm text-muted">{report.target_summary}</p> : null}
        {report.target_text ? (
          <Quote text={report.target_text} />
        ) : (
          <p className="mt-1 text-sm text-muted">{report.target_exists ? "This item has no text." : "The item no longer exists."}</p>
        )}
      </div>
      <p className="text-sm text-muted">Earlier removals of this author&rsquo;s content: <span className="num text-ink">{report.author_earlier_removals ?? 0}</span></p>
    </>
  );
}
