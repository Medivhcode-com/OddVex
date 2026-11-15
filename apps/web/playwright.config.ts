import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = 3210;
const API_PORT = 8210;
const systemChromium = process.env.PLAYWRIGHT_CHROMIUM_PATH;

/**
 * End-to-end tests run the real API (synthetic provider, throwaway SQLite database)
 * and the production build of the web app. Run `pnpm build` first.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.02, animations: "disabled" } },
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "off",
    launchOptions: {
      executablePath: systemChromium || undefined,
      args: ["--no-proxy-server"],
    },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grepInvert: /@desktop-only/ },
  ],
  webServer: [
    {
      command: `bash ./e2e/start-api.sh ${API_PORT}`,
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "bash ./e2e/start-web.sh",
      url: `http://localhost:${WEB_PORT}`,
      env: { PORT: String(WEB_PORT), HOSTNAME: "localhost", ODDVEX_API_URL: `http://localhost:${API_PORT}`, ODDVEX_INSECURE_COOKIES: "true" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
