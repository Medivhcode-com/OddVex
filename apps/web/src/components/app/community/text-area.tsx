"use client";

import clsx from "clsx";
import type { ComponentProps } from "react";

/**
 * A labelled plain-text box with a live character count. The count is always visible; it is
 * announced only when the text is over the limit, so typing is not narrated letter by letter.
 */
export function TextArea({
  id,
  label,
  hint,
  error,
  max,
  value,
  className,
  ...props
}: Omit<ComponentProps<"textarea">, "value"> & { id: string; label: string; hint?: string; error?: string | null; max: number; value: string }) {
  const over = value.length > max;
  const describedBy = [hint ? `${id}-hint` : null, `${id}-count`, error ? `${id}-error` : null].filter(Boolean).join(" ");
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        rows={4}
        aria-invalid={error || over ? true : undefined}
        aria-describedby={describedBy}
        className={clsx("block min-h-24 w-full rounded-cell border border-line-strong bg-bg px-3 py-2 text-[0.9375rem] text-ink placeholder:text-muted/70 focus:border-second", (error || over) && "border-error")}
        {...props}
      />
      <div className="mt-1 flex flex-wrap items-start justify-between gap-x-4 gap-y-1 text-sm">
        {hint ? (
          <p id={`${id}-hint`} className="text-muted">
            {hint}
          </p>
        ) : (
          <span />
        )}
        <p id={`${id}-count`} className={clsx("num shrink-0", over ? "text-error" : "text-muted")} aria-live={over ? "polite" : "off"}>
          {value.length} of {max} characters{over ? ", over the limit" : ""}
        </p>
      </div>
      {error ? (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
