/**
 * Robust Playwright browser management for PDF rendering.
 *
 * - Lazy-launches Chromium on first use
 * - Auto-reconnects on disconnection / crash
 * - Retries on transient failures
 * - Graceful shutdown on SIGTERM/SIGINT
 */
import { chromium, type Browser, type Page } from "playwright";

let browser: Browser | null = null;
let launching = false;
const MAX_RETRIES = 2;

async function ensureBrowser(): Promise<Browser> {
  if (browser?.isConnected()) return browser;

  if (launching) {
    // Another call is already launching — wait and retry
    await new Promise((r) => setTimeout(r, 500));
    return ensureBrowser();
  }

  launching = true;
  try {
    if (browser) {
      try {
        await browser.close();
      } catch {
        /* ignore */
      }
    }
    browser = await chromium.launch({ headless: true });
    browser.on("disconnected", () => {
      browser = null;
    });
    console.log("[browser-pool] Chromium launched");
    return browser;
  } finally {
    launching = false;
  }
}

/**
 * Execute a function with a fresh browser page.
 * Handles page lifecycle and retries on browser crash.
 */
export async function withPage<T>(
  fn: (page: Page) => Promise<T>
): Promise<T> {
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const b = await ensureBrowser();
    const page = await b.newPage({ viewport: { width: 960, height: 540 } });
    try {
      return await fn(page);
    } catch (err) {
      if (attempt < MAX_RETRIES && !b.isConnected()) {
        console.warn(
          `[browser-pool] Browser disconnected, retrying (attempt ${attempt + 1}/${MAX_RETRIES})`
        );
        continue;
      }
      throw err;
    } finally {
      try {
        await page.close();
      } catch {
        /* ignore */
      }
    }
  }
  throw new Error("browser-pool: max retries exceeded");
}

/** Shutdown the browser (call on process exit). */
export async function shutdown(): Promise<void> {
  if (browser) {
    console.log("[browser-pool] Shutting down Chromium");
    try {
      await browser.close();
    } catch {
      /* ignore */
    }
    browser = null;
  }
}
