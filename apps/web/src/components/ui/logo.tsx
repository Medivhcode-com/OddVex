/**
 * The mark is a price line that dips and turns up through a "V": a line moving, then a read on it.
 */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--ov-raised)" />
      <path d="M6 11h5l5 11 5-11h5" stroke="var(--ov-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="22" r="2.2" fill="var(--ov-second)" />
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} />
      <span className="text-[1.0625rem] font-semibold tracking-tight">OddVex</span>
    </span>
  );
}
