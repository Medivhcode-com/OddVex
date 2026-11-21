import Link from "next/link";
import clsx from "clsx";
import { HELPLINE, RESPONSIBLE_GAMBLING_LEAD } from "@/lib/site";

/**
 * The helpline number, written both ways, as a phone link. Every fact comes from `lib/site.ts`.
 * Each spelling stays on one line; a narrow column breaks between the two, not inside a number.
 */
export function HelplineLink({ className }: { className?: string }) {
  return (
    <a href={HELPLINE.tel} className={className}>
      <span className="whitespace-nowrap">{HELPLINE.number}</span> <span className="whitespace-nowrap">({HELPLINE.digits})</span>
    </a>
  );
}

/**
 * The short responsible-gambling line: 21+, no wagers, and the helpline as a phone link.
 * `more` adds a link to the responsible-gambling page, for screens whose own chrome has none.
 */
export function ResponsibleGamblingLine({ className, more = false, ...props }: { className?: string; more?: boolean; "data-testid"?: string }) {
  return (
    <p className={clsx("text-xs leading-relaxed text-muted", className)} {...props}>
      {RESPONSIBLE_GAMBLING_LEAD} <HelplineLink className="text-ink underline" />.
      {more ? (
        <>
          {" "}
          <Link href="/responsible-gambling" className="text-ink underline">
            Help and limits
          </Link>
        </>
      ) : null}
    </p>
  );
}
