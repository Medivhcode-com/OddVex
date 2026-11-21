"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { formatAge } from "@/lib/format";

/**
 * "Updated 42s ago", ticking on the client. Stale data gets a text label and a different shape,
 * so the state does not depend on color.
 */
export function Freshness({ at, stale = false, prefix = "Updated", className }: { at: string; stale?: boolean; prefix?: string; className?: string }) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 15000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className={clsx("inline-flex items-center gap-1.5 text-xs", stale ? "text-warn" : "text-muted", className)}>
      <span aria-hidden="true" className={clsx("size-1.5", stale ? "rotate-45 bg-warn" : "rounded-full bg-accent")} />
      <time dateTime={at} suppressHydrationWarning>
        {stale ? "Stale, " : `${prefix} `}
        {now ? formatAge(at, now) : "just now"}
      </time>
    </span>
  );
}

/**
 * For a quote the API sent without a time. The API counts such a quote as stale (`is_stale`),
 * so the stale label and shape are shown without an age.
 */
export function UndatedFreshness({ stale, className }: { stale: boolean; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 text-xs", stale ? "text-warn" : "text-muted", className)}>
      <span aria-hidden="true" className={clsx("size-1.5", stale ? "rotate-45 bg-warn" : "rounded-full bg-line-strong")} />
      <span>{stale ? "Stale, no update time" : "No update time"}</span>
    </span>
  );
}
