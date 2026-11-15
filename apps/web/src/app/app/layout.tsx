import type { Metadata } from "next";
import Link from "next/link";
import { BottomNav, SideNav } from "@/components/app/nav";
import { OddsFormatProvider, OddsFormatToggle } from "@/components/app/odds-format";
import { Logo } from "@/components/ui/logo";
import { Badge, Button, ButtonLink } from "@/components/ui/primitives";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { api } from "@/lib/api";
import { logoutAction } from "@/lib/auth-actions";
import { currentUser, oddsFormat } from "@/lib/session";
import type { Meta } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { robots: { index: false } };

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // Chrome must render even when the API is down, so the error boundary has somewhere to live.
  const [user, format, meta] = await Promise.all([
    currentUser().catch(() => null),
    oddsFormat(),
    api<Meta>("/v1/meta").catch(() => null),
  ]);

  return (
    <OddsFormatProvider initial={format}>
      <div className="lg:grid lg:grid-cols-[15rem_1fr]">
        <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface px-3 py-5 lg:flex">
          <Link href="/app" aria-label="OddVex home" className="mb-6 px-3">
            <Logo />
          </Link>
          <SideNav admin={user?.role === "admin"} />
          <p className="mt-auto px-3 text-xs leading-relaxed text-muted">
            Information only. OddVex never takes wagers. 21+. Call or text 1-800-GAMBLER for help.
          </p>
        </aside>

        <div className="min-w-0">
          <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-bg/90 px-4 backdrop-blur sm:px-6">
            <Link href="/app" aria-label="OddVex home" className="lg:hidden">
              <Logo size={24} />
            </Link>
            {meta?.data_mode === "synthetic" ? (
              <span className="hidden sm:inline">
                <Badge tone="second">Synthetic data</Badge>
              </span>
            ) : null}
            <div className="ml-auto flex items-center gap-2">
              <OddsFormatToggle />
              <div className="hidden md:block">
                <ThemeToggle />
              </div>
              {user ? (
                <form action={logoutAction} className="flex items-center gap-2">
                  <span className="hidden max-w-32 truncate text-sm text-muted md:inline">{user.display_name}</span>
                  <Button type="submit" variant="ghost" size="sm">
                    Log out
                  </Button>
                </form>
              ) : (
                <ButtonLink href="/login" variant="secondary" size="sm">
                  Log in
                </ButtonLink>
              )}
            </div>
          </header>

          {meta?.data_mode === "synthetic" ? (
            <p className="border-b border-line bg-second-soft px-4 py-1.5 text-xs text-muted sm:hidden">
              Synthetic data. Teams, players and books are fictional.
            </p>
          ) : null}

          <main id="main" className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:pb-12">
            {children}
          </main>
        </div>
      </div>
      <BottomNav />
    </OddsFormatProvider>
  );
}
