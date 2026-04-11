/**
 * login.js — `npm run login`
 *
 * Opens Suno in a visible browser window and waits for you to log in manually.
 * Once logged in, closes the browser — the session is saved automatically
 * in the persistent profile directory (.browser-profile/).
 *
 * You only need to run this ONCE. After that, `npm run generate` reuses
 * the saved session automatically.
 *
 * If your session expires (Suno logs you out), just run `npm run login` again.
 */

const { launchBrowser, closeBrowser } = require('./browser');
const { SELECTORS } = require('./selectors');
const logger = require('./logger');
const config = require('./config');

/**
 * Checks if logged in by inspecting the CURRENT page only — no navigation.
 * Safe to call while the user is in the middle of the OAuth flow.
 */
async function isLoggedInNow(page) {
  for (const sel of SELECTORS.loggedInIndicator) {
    try {
      const el = await page.$(sel);
      if (el) return true;
    } catch {
      // selector not found, try next
    }
  }
  return false;
}

async function main() {
  logger.header('Suno Login — Manual Session Setup');
  logger.info(`Browser profile will be saved to: ${config.userDataDir}`);

  const { context, page } = await launchBrowser({ headless: false });

  logger.info('Opening Suno...');
  // Navigate once — then NEVER navigate again during login
  await page.goto(config.sunoUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2_000);

  // Check if already logged in (without navigating)
  if (await isLoggedInNow(page)) {
    logger.success('You are already logged in!');
    logger.info('Session is valid. You can close this window and run: npm run generate');
  } else {
    logger.info('──────────────────────────────────────────────');
    logger.info('👉  Log in to Suno in the browser window.');
    logger.info('    Use Google or Discord — take your time.');
    logger.info('    This script will wait up to 5 minutes.');
    logger.info('    DO NOT close the browser manually.');
    logger.info('──────────────────────────────────────────────');

    // Poll the current page — no page.goto() here
    const deadline = Date.now() + 5 * 60_000;
    let loggedIn = false;
    let lastDot = Date.now();

    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3_000));

      // Print a dot every 15s so the terminal doesn't look frozen
      if (Date.now() - lastDot > 15_000) {
        process.stdout.write('.');
        lastDot = Date.now();
      }

      if (await isLoggedInNow(page)) {
        loggedIn = true;
        break;
      }
    }

    console.log(); // newline after dots

    if (loggedIn) {
      logger.success('Login detected! Session saved to .browser-profile/');
    } else {
      logger.warn('Timed out (5 min). Re-run `npm run login` and log in faster.');
    }
  }

  // Wait to ensure cookies are fully flushed to disk before closing
  logger.info('Saving session to disk...');
  await page.waitForTimeout(3_000);
  await closeBrowser(context);
  logger.success('Done. Run: npm run generate');
}

main().catch(err => {
  console.error('Login error:', err);
  process.exit(1);
});
