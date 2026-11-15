"use client";

import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

/**
 * Re-fetches the page's server data on an interval while the tab is visible.
 * The user can pause it, and it never runs for people who prefer reduced motion
 * unless they turn it on, because content changing by itself can be disorienting.
 */
const KEY = "ov-autorefresh";
const EVENT = "ov-autorefresh-change";

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function readPreference(): boolean {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(KEY);
  } catch {}
  if (stored !== null) return stored === "on";
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function AutoRefresh({ seconds = 30 }: { seconds?: number }) {
  const router = useRouter();
  const on = useSyncExternalStore(subscribe, readPreference, () => false);

  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, seconds * 1000);
    return () => clearInterval(id);
  }, [on, seconds, router]);

  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={() => {
        try {
          localStorage.setItem(KEY, on ? "off" : "on");
        } catch {}
        window.dispatchEvent(new Event(EVENT));
      }}
      className="inline-flex min-h-9 items-center gap-2 rounded-full border border-line px-3 text-xs font-medium text-muted hover:border-line-strong hover:text-ink"
    >
      <span aria-hidden="true" className={on ? "size-1.5 rounded-full bg-accent" : "size-1.5 rounded-full border border-muted"} />
      {on ? `Refreshing every ${seconds}s` : "Auto-refresh off"}
    </button>
  );
}
