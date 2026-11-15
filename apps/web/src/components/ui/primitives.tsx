import Link from "next/link";
import clsx from "clsx";
import type { ComponentProps, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-cell font-medium whitespace-nowrap transition-colors duration-150 disabled:opacity-50 disabled:pointer-events-none";
const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-ink hover:brightness-110",
  secondary: "border border-line-strong bg-surface text-ink hover:bg-raised",
  ghost: "text-muted hover:text-ink hover:bg-raised",
  danger: "border border-error text-error hover:bg-error-soft",
};
const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-5 text-base",
};

export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string) {
  return clsx(buttonBase, buttonVariants[variant], buttonSizes[size], className);
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

export function Panel({
  as: Tag = "section",
  className,
  children,
  ...props
}: { as?: "section" | "div" | "article" | "aside"; className?: string; children: ReactNode } & Record<string, unknown>) {
  return (
    <Tag className={clsx("rounded-panel border border-line bg-surface", className)} {...props}>
      {children}
    </Tag>
  );
}

export function PanelHeader({
  title,
  description,
  action,
  id,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  id?: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-3 sm:px-5">
      <div className="min-w-0">
        <h2 id={id} className="text-[0.9375rem] font-semibold tracking-tight">
          {title}
        </h2>
        {description ? <p className="mt-0.5 text-sm text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

type Tone = "neutral" | "accent" | "second" | "warn" | "error";
const toneClass: Record<Tone, string> = {
  neutral: "border-line text-muted",
  accent: "border-transparent bg-accent-soft text-accent",
  second: "border-transparent bg-second-soft text-second",
  warn: "border-transparent bg-warn-soft text-warn",
  error: "border-transparent bg-error-soft text-error",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium leading-5",
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "accent" | "error";
}) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted">{label}</dt>
      <dd
        className={clsx(
          "num mt-1 truncate text-2xl font-medium",
          tone === "accent" && "text-accent",
          tone === "error" && "text-error",
        )}
      >
        {value}
      </dd>
      {hint ? <dd className="mt-0.5 text-xs text-muted">{hint}</dd> : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={clsx("ov-skeleton", className)} />;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="px-5 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children ? <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Notice({
  tone = "second",
  title,
  children,
  role,
}: {
  tone?: "second" | "warn" | "error" | "accent";
  title?: string;
  children: ReactNode;
  role?: "alert" | "status" | "note";
}) {
  const marks = { second: "i", warn: "!", error: "×", accent: "✓" } as const;
  return (
    <div
      role={role ?? (tone === "error" ? "alert" : "note")}
      className={clsx("flex gap-3 rounded-cell border px-3 py-2.5 text-sm", {
        "border-second/40 bg-second-soft": tone === "second",
        "border-warn/40 bg-warn-soft": tone === "warn",
        "border-error/40 bg-error-soft": tone === "error",
        "border-accent/40 bg-accent-soft": tone === "accent",
      })}
    >
      <span
        aria-hidden="true"
        className={clsx("num mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-xs font-semibold", {
          "bg-second text-bg": tone === "second",
          "bg-warn text-bg": tone === "warn",
          "bg-error text-bg": tone === "error",
          "bg-accent text-accent-ink": tone === "accent",
        })}
      >
        {marks[tone]}
      </span>
      <div className="min-w-0">
        {title ? <p className="font-medium">{title}</p> : null}
        <div className="text-muted [&_a]:text-ink [&_a]:underline">{children}</div>
      </div>
    </div>
  );
}

const fieldClass =
  "min-h-11 w-full rounded-cell border border-line-strong bg-bg px-3 text-[0.9375rem] text-ink placeholder:text-muted/70 focus:border-second";

export function Field({
  label,
  hint,
  error,
  id,
  className,
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        className={clsx(fieldClass, props.inputMode === "decimal" || props.type === "number" ? "num" : null, error && "border-error")}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-sm text-error">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-sm text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function SelectField({
  label,
  id,
  className,
  children,
  ...props
}: ComponentProps<"select"> & { label: string; id: string }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <select id={id} className={fieldClass} {...props}>
        {children}
      </select>
    </div>
  );
}

/** Link-based segmented filter. State lives in the URL so it survives reloads and is shareable. */
export function Segmented({
  label,
  options,
  current,
}: {
  label: string;
  options: { href: string; label: string; value: string }[];
  current: string;
}) {
  return (
    <nav aria-label={label} className="-mx-1 flex max-w-full gap-1 overflow-x-auto px-1 py-1">
      {options.map((option) => {
        const active = option.value === current;
        return (
          <Link
            key={option.value}
            href={option.href}
            aria-current={active ? "page" : undefined}
            scroll={false}
            className={clsx(
              "inline-flex min-h-9 shrink-0 items-center rounded-full border px-3.5 text-sm font-medium transition-colors",
              active ? "border-ink bg-ink text-bg" : "border-line text-muted hover:border-line-strong hover:text-ink",
            )}
          >
            {option.label}
          </Link>
        );
      })}
    </nav>
  );
}
