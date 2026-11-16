"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { APP_NAV, type AppNavItem } from "@/lib/site";

const ICONS: Record<string, string> = {
  home: "M3 9.5 10 3l7 6.5V17h-4.5v-5h-5v5H3z",
  games: "M3 5h14v10H3zM10 5v10M3 10h3M14 10h3",
  odds: "M3 5h14M3 10h14M3 15h14M7 3v14M13 3v14",
  props: "M4 16V9M8 16V4M12 16v-5M16 16V7",
  value: "M3 6h8M3 14h8M14 4v12M11.5 6.5 14 4l2.5 2.5M11.5 13.5 14 16l2.5-2.5",
  tracker: "M3 14l4-4 3 3 7-8M13 5h4v4",
  tools: "M5 3h10v14H5zM8 6h4M8 10h.01M12 10h.01M8 13h.01M12 13h.01",
  parlay: "M5 5h4v4H5zM11 11h4v4h-4zM9 7h2a2 2 0 0 1 2 2v2",
  ai: "M10 3l1.8 4.2L16 9l-4.2 1.8L10 15l-1.8-4.2L4 9l4.2-1.8z",
  alerts: "M10 3a4.5 4.5 0 0 0-4.5 4.5c0 4-1.5 5-1.5 5h12s-1.5-1-1.5-5A4.5 4.5 0 0 0 10 3zM8.5 15.5a1.6 1.6 0 0 0 3 0",
  more: "M4 10h.01M10 10h.01M16 10h.01",
  settings: "M10 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM10 2v2M10 16v2M2 10h2M16 10h2",
};

function Icon({ name }: { name: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

function isActive(pathname: string, href: string) {
  return href === "/app" ? pathname === "/app" : pathname === href || pathname.startsWith(`${href}/`);
}

type Flags = Record<string, boolean>;

/** Entries behind a feature flag are left out unless that flag is explicitly on. */
function visible(items: readonly AppNavItem[], flags: Flags): AppNavItem[] {
  return items.filter((item) => !item.flag || flags[item.flag] === true);
}

export function SideNav({ admin = false, flags = {} }: { admin?: boolean; flags?: Flags }) {
  const pathname = usePathname();
  return (
    <nav aria-label="App" className="flex flex-col gap-0.5">
      {[...visible(APP_NAV, flags), { href: "/app/settings", label: "Settings", icon: "settings" }, ...(admin ? [{ href: "/app/admin", label: "Admin", icon: "tools" }] : [])].map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={clsx(
              "flex min-h-10 items-center gap-3 rounded-cell px-3 text-sm font-medium",
              active ? "bg-raised text-ink shadow-[inset_2px_0_0_var(--ov-accent)]" : "text-muted hover:bg-raised hover:text-ink",
            )}
          >
            <Icon name={item.icon} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

const PRIMARY = ["/app", "/app/odds", "/app/props", "/app/tracker"];

/** Bottom bar for one-handed use. Four destinations plus a sheet with the rest. */
export function BottomNav({ admin = false, flags = {} }: { admin?: boolean; flags?: Flags }) {
  const pathname = usePathname();
  const items = visible(APP_NAV, flags);
  const primary = items.filter((item) => PRIMARY.includes(item.href));
  const rest = [...items.filter((item) => !PRIMARY.includes(item.href)), { href: "/app/settings", label: "Settings", icon: "settings" }, ...(admin ? [{ href: "/app/admin", label: "Admin", icon: "tools" }] : [])];
  const restActive = rest.some((item) => isActive(pathname, item.href));
  const tab = "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-medium";
  return (
    <nav aria-label="App" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden">
      {primary.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={clsx(tab, active ? "text-ink" : "text-muted")}>
            <span className={clsx("rounded-full px-3 py-0.5", active && "bg-accent-soft text-accent")}>
              <Icon name={item.icon} />
            </span>
            {item.label}
          </Link>
        );
      })}
      <details className="group relative flex-1" key={pathname}>
        <summary className={clsx(tab, "cursor-pointer list-none", restActive ? "text-ink" : "text-muted")}>
          <span className={clsx("rounded-full px-3 py-0.5", restActive && "bg-accent-soft text-accent")}>
            <Icon name="more" />
          </span>
          More
        </summary>
        <div className="absolute bottom-full right-2 mb-2 w-56 rounded-panel border border-line-strong bg-surface p-1.5 shadow-xl shadow-black/30">
          {rest.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className="flex min-h-11 items-center gap-3 rounded-cell px-3 text-sm font-medium text-muted hover:bg-raised hover:text-ink aria-[current=page]:text-ink"
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </div>
      </details>
    </nav>
  );
}
