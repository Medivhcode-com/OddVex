import { createContext, use } from 'react';

/** True once IBM Plex Mono has loaded. False means numbers fall back to the platform monospace face. */
export const MonoFontContext = createContext(false);

export function useMonoFontLoaded(): boolean {
  return use(MonoFontContext);
}
