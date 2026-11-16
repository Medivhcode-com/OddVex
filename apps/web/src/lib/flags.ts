import "server-only";
import { cache } from "react";
import { notFound } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { api } from "@/lib/api";

export type Flags = Record<string, boolean>;

/** One `GET /v1/flags` per render, shared by the layout and the page. */
const load = cache(async (): Promise<{ flags: Flags; error: unknown }> => {
  try {
    return { flags: (await api<Schemas["FlagsOut"]>("/v1/flags")).flags ?? {}, error: null };
  } catch (error) {
    return { flags: {}, error };
  }
});

/** The feature flags, for chrome and entry points. If they can't be read, every flag counts as off. */
export async function getFlags(): Promise<Flags> {
  return (await load()).flags;
}

/** Only an explicit `true` is on: an unknown or missing flag is off. */
export function flagOn(flags: Flags, key: string): boolean {
  return flags[key] === true;
}

/**
 * For a page behind a flag: the standard not-found page while the flag is off. If the flags
 * could not be read at all the error is rethrown, so the visitor sees the "can't reach the
 * data service" screen instead of a misleading 404.
 */
export async function requireFlag(...keys: string[]): Promise<Flags> {
  const { flags, error } = await load();
  if (error) throw error;
  if (!keys.every((key) => flagOn(flags, key))) notFound();
  return flags;
}
