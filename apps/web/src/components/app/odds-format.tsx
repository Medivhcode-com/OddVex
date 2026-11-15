"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import clsx from "clsx";
import { formatPrice, type OddsFormat } from "@/lib/format";

const COOKIE = "ov_odds";
const OddsFormatContext = createContext<{ format: OddsFormat; setFormat: (f: OddsFormat) => void }>({
  format: "american",
  setFormat: () => {},
});

export function OddsFormatProvider({ initial, children }: { initial: OddsFormat; children: ReactNode }) {
  const [format, setState] = useState<OddsFormat>(initial);
  const setFormat = (next: OddsFormat) => {
    setState(next);
    document.cookie = `${COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
  };
  return <OddsFormatContext.Provider value={{ format, setFormat }}>{children}</OddsFormatContext.Provider>;
}

export function useOddsFormat() {
  return useContext(OddsFormatContext);
}

/** Renders a price in the user's chosen format. */
export function Price({ price, className }: { price: { american: number; decimal: number }; className?: string }) {
  const { format } = useOddsFormat();
  return <span className={clsx("num", className)}>{formatPrice(price, format)}</span>;
}

export function OddsFormatToggle() {
  const { format, setFormat } = useOddsFormat();
  return (
    <div role="group" aria-label="Odds format" className="flex rounded-full border border-line p-0.5 text-xs">
      {(["american", "decimal"] as const).map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={format === option}
          onClick={() => setFormat(option)}
          className={clsx(
            "min-h-8 rounded-full px-3 font-medium capitalize",
            format === option ? "bg-ink text-bg" : "text-muted hover:text-ink",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
