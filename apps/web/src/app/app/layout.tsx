import type { Metadata } from "next";
import Link from "next/link";
import { BottomNav, SideNav } from "@/components/app/nav";
import { OddsFormatProvider, OddsFormatToggle } from "@/components/app/odds-format";
import { Logo, LogoMark } from "@/components/ui/logo";
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
  const unread = user
    ? await api<{ unread_count: number }>("/v1/notifications/unread-count", { auth: true })
        .then((out) => out.unread_count)
        .catch(() => 0)
    : 0;

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
            <Link href="/app" aria-label="OddVex home" className="shrink-0 lg:hidden">
              <LogoMark size={28} />
            </Link>
            {meta?.data_mode === "synthetic" ? (
              <span className="hidden sm:inline">
                <Badge tone="second">Synthetic data</Badge>
              </span>
            ) : null}
            <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">
              <OddsFormatToggle />
              <div className="hidden md:block">
                <ThemeToggle />
              </div>
              {user ? (
                <Link
                  href="/app/alerts"
                  className="relative inline-flex min-h-9 items-center gap-1.5 rounded-cell px-2.5 text-sm text-muted hover:bg-raised hover:text-ink"
                >
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M10 3a4.5 4.5 0 0 0-4.5 4.5c0 4-1.5 5-1.5 5h12s-1.5-1-1.5-5A4.5 4.5 0 0 0 10 3zM8.5 15.5a1.6 1.6 0 0 0 3 0" />
                  </svg>
                  <span className="sr-only">Notifications</span>
                  {unread > 0 ? (
                    <span className="num rounded-full bg-accent px-1.5 text-xs font-semibold leading-5 text-accent-ink">
                      {unread > 99 ? "99+" : unread}
                      <span className="sr-only"> unread</span>
                    </span>
                  ) : null}
                </Link>
              ) : null}
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
