import type { Metadata } from "next";
import Link from "next/link";
import { ClvCalculator, ConvertCalculator, EvCalculator, NoVigCalculator } from "@/components/app/calculators";
import { PageHeader } from "@/components/app/page-header";

export const metadata: Metadata = { title: "Calculators" };

const LINKS = [
  ["#convert", "Odds converter"],
  ["#no-vig", "No-vig"],
  ["#ev", "Expected value"],
  ["#clv", "Closing line value"],
];

export default function ToolsPage() {
  return (
    <>
      <PageHeader
        title="Calculators"
        description={
          <>
            Each one shows its working. The formulas are on the <Link href="/methodology" className="text-ink underline">methodology page</Link>. Enter odds as American (−110), decimal (1.91) or fractional (10/11).
          </>
        }
      />
      <nav aria-label="Calculators" className="mb-5 flex flex-wrap gap-2">
        {LINKS.map(([href, label]) => (
          <a key={href} href={href} className="inline-flex min-h-9 items-center rounded-full border border-line px-3.5 text-sm font-medium text-muted hover:border-line-strong hover:text-ink">
            {label}
          </a>
        ))}
        <Link href="/app/parlay" className="inline-flex min-h-9 items-center rounded-full border border-line px-3.5 text-sm font-medium text-muted hover:border-line-strong hover:text-ink">
          Parlay
        </Link>
      </nav>
      <div className="space-y-5 [&>section]:scroll-mt-20">
        <ConvertCalculator />
        <NoVigCalculator />
        <EvCalculator />
        <ClvCalculator />
      </div>
    </>
  );
}
