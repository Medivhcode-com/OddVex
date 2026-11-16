/**
 * Runs before first paint so a stored light preference never flashes dark.
 * It is the one inline script the app writes itself; the Content-Security-Policy allows it by
 * its SHA-256 hash (see `src/proxy.ts`), so any change here changes the hash automatically.
 */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("ov-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
