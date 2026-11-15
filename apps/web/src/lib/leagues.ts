import { api } from "@/lib/api";
import type { League } from "@/lib/types";

export const MARKETS = [
  { value: "moneyline", label: "Moneyline" },
  { value: "spread", label: "Spread" },
  { value: "total", label: "Total" },
] as const;

export async function getLeagues(): Promise<League[]> {
  return api<League[]>("/v1/leagues");
}

export function leagueLabel(leagues: League[], key: string): string {
  return leagues.find((league) => league.key === key)?.name ?? key.toUpperCase();
}

export function pick<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}
