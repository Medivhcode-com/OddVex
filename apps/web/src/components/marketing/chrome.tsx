import Link from "next/link";
import { Logo } from "@/components/ui/logo";
import { HelplineLink } from "@/components/ui/helpline";
import { ButtonLink } from "@/components/ui/primitives";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { HELPLINE, MARKETING_NAV, SITE } from "@/lib/site";

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="OddVex home" className="shrink-0">
          <Logo />
        </Link>
        <nav aria-label="Product" className="hidden flex-1 items-center gap-1 md:flex">
          {MARKETING_NAV.map((item) => (
            <Link key={item.href} href={item.href} className="rounded-cell px-3 py-2 text-sm text-muted hover:bg-raised hover:text-ink">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>
          <ButtonLink href="/login" variant="ghost" size="sm" className="hidden sm:inline-flex">
            Log in
          </ButtonLink>
          <ButtonLink href="/app" size="sm">
            Open the app
          </ButtonLink>
        </div>
      </div>
      <nav aria-label="Product (mobile)" className="flex gap-1 overflow-x-auto border-t border-line px-3 py-1.5 md:hidden">
        {MARKETING_NAV.map((item) => (
          <Link key={item.href} href={item.href} className="shrink-0 rounded-cell px-3 py-2 text-sm text-muted hover:text-ink">
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

const FOOTER = [
  {
    title: "Product",
    links: [
      ["Features", "/features"],
      ["Odds comparison", "/odds-comparison"],
      ["Player props", "/player-props"],
      ["Bet tracking", "/bet-tracking"],
      ["OddVex AI", "/ai"],
      ["Pricing", "/pricing"],
      ["Get the app", "/download"],
    ],
  },
  {
    title: "Company",
    links: [
      ["About", "/about"],
      ["Blog", "/blog"],
      ["Contact", "/contact"],
      ["Help center", "/help"],
    ],
  },
  {
    title: "Trust",
    links: [
      ["Data and methodology", "/methodology"],
      ["Responsible gambling", "/responsible-gambling"],
      ["Privacy policy", "/privacy"],
      ["Terms of service", "/terms"],
    ],
  },
] as const;

export function MarketingFooter() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-sm text-muted">{SITE.tagline}</p>
          <div className="mt-4 sm:hidden">
            <ThemeToggle />
          </div>
        </div>
        {FOOTER.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2 className="text-sm font-semibold">{group.title}</h2>
            <ul className="mt-3 space-y-2">
              {group.links.map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="text-sm text-muted hover:text-ink">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="mx-auto max-w-6xl space-y-2 px-4 py-6 text-sm text-muted sm:px-6">
          <p>
            OddVex is a research and analytics product for adults 21 and over. It does not accept, place or facilitate
            wagers. Nothing here is a prediction or a guarantee of any outcome. If gambling is causing you or someone
            you know harm, call <HelplineLink className="text-ink underline" />, the {HELPLINE.name}.
          </p>
          <p>
            © {new Date().getFullYear()} {SITE.company}. OddVex is a {SITE.company} product.
          </p>
        </div>
      </div>
    </footer>
  );
}

export function PageIntro({ title, lede, children }: { title: string; lede: string; children?: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-10 pt-14 sm:px-6 sm:pt-20">
      <h1 className="max-w-3xl text-title font-semibold">{title}</h1>
      <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">{lede}</p>
      {children ? <div className="mt-7 flex flex-wrap gap-3">{children}</div> : null}
    </div>
  );
}

export function Prose({ children }: { children: React.ReactNode }) {
  return <div className="prose-ov mx-auto max-w-6xl px-4 sm:px-6">{children}</div>;
}
