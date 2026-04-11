/**
 * browser.js — Launches a Playwright browser with a persistent user profile.
 *
 * Why persistent context instead of storageState?
 *   Suno uses Google / Discord OAuth and sets HttpOnly cookies that cannot be
 *   captured by storageState. A persistent user data directory preserves the
 *   full browser profile (cookies, localStorage, IndexedDB) across runs.
 *   This is the most reliable approach for Suno specifically.
 */

const { chromium } = require('playwright');
// We use the real installed Chrome (channel: 'chrome') instead of Playwright's
// bundled Chromium because Google OAuth blocks sign-in on automated Chromium builds.
const path = require('path');
const fs = require('fs');
const config = require('./config');
const logger = require('./logger');

/**
 * Launches the browser and returns { browser, context, page }.
 * Re-uses the profile in config.userDataDir if it exists.
 */
async function launchBrowser(options = {}) {
  const headless = options.headless !== undefined ? options.headless : config.headless;

  // Ensure the profile dir exists
  fs.mkdirSync(config.userDataDir, { recursive: true });
  logger.debug(`Browser profile: ${config.userDataDir}`);

  const context = await chromium.launchPersistentContext(config.userDataDir, {
    channel: 'chrome',   // use real Chrome — required for Google OAuth
    headless,
    // Viewport large enough for Suno's layout
    viewport: { width: 1440, height: 900 },
    // Accept downloads so we can save tracks
    acceptDownloads: true,
    // Mimic a real browser
    userAgent: [
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
      'AppleWebKit/537.36 (KHTML, like Gecko)',
      'Chrome/124.0.0.0 Safari/537.36',
    ].join(' '),
    // Slow down by a few ms in headful mode to look more human
    slowMo: headless ? 0 : 80,
  });

  context.setDefaultNavigationTimeout(config.navigationTimeout);
  context.setDefaultTimeout(config.navigationTimeout);

  const page = context.pages()[0] || (await context.newPage());

  return { context, page };
}

/**
 * Closes the browser context gracefully.
 */
async function closeBrowser(context) {
  try {
    await context.close();
  } catch {
    // ignore
  }
}

module.exports = { launchBrowser, closeBrowser };
