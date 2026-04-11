/**
 * selectors.js — ALL Suno UI selectors in one place.
 *
 * !! FRAGILITY WARNING !!
 * Suno is a React SPA that ships obfuscated CSS class names.
 * These selectors use aria-labels, roles, and text content wherever possible
 * to survive UI updates. If the script breaks, start here.
 *
 * HOW TO UPDATE:
 *   1. Open https://suno.com/create in a browser
 *   2. Open DevTools → Inspector
 *   3. Find the element and update the selector below
 *   4. Prefer: data-testid > aria-label > role+text > placeholder > class
 */

const SELECTORS = {
  // ── Create page ────────────────────────────────────────────────────────────

  // The main prompt input textarea on the create page
  // TODO: verify — inspect the textarea on suno.com/create
  promptTextarea: [
    'textarea[placeholder*="describe"]',
    'textarea[placeholder*="Enter a style"]',
    'textarea[data-testid="prompt-input"]',
    'textarea',                                // last resort fallback
  ],

  // The primary "Create" / "Generate" button
  // TODO: verify exact text — may be "Create", "Generate", or an icon button
  createButton: [
    'button:has-text("Create")',
    'button[data-testid="create-button"]',
    'button[aria-label="Create"]',
    'button:has-text("Generate")',
  ],

  // ── Generation progress ────────────────────────────────────────────────────

  // A song card that is still generating (has a spinner / progress indicator)
  // TODO: Suno shows a skeleton or loading state while generating
  generatingSongCard: [
    '[data-testid="song-generating"]',
    '[aria-label*="generating"]',
    '.generating',                             // TODO: verify class name
  ],

  // A completed song card (has a play button, duration shown)
  // TODO: verify — look for elements that have both a play button and a timestamp
  completedSongCard: [
    '[data-testid="song-card"]:not(.generating)',
    '[data-testid="clip-card"]',
    'div[class*="song"]:has(button[aria-label*="Play"])',
  ],

  // Play button inside a song card (confirms track is ready)
  playButton: [
    'button[aria-label*="Play"]',
    'button[data-testid="play-button"]',
    'button[aria-label="Play"]',
  ],

  // ── Download flow ──────────────────────────────────────────────────────────

  // The "..." or kebab / ellipsis menu button on a song card
  // TODO: this is typically an icon button — inspect suno.com to confirm
  songMenuButton: [
    'button[aria-label="More options"]',
    'button[aria-label*="options"]',
    'button[data-testid="song-options"]',
    'button[aria-label*="..."]',
    'button:has([data-icon="ellipsis"])',
    'button:has(svg[data-testid="ellipsis"])',
  ],

  // "Download" option inside the dropdown menu
  downloadMenuItem: [
    '[role="menuitem"]:has-text("Download")',
    'li:has-text("Download")',
    'button:has-text("Download")',
    'a:has-text("Download")',
    '[data-testid="download-button"]',
  ],

  // ── Login / session detection ──────────────────────────────────────────────

  // Element that only appears when the user IS logged in
  // (e.g. profile avatar, credits counter, sidebar nav item)
  // TODO: verify — could be a profile picture or a "Create" nav link
  loggedInIndicator: [
    '[data-testid="user-avatar"]',
    '[aria-label="Profile"]',
    'button[data-testid="credits"]',
    'nav a[href="/create"]',
  ],

  // Element visible on the login/signup page when NOT logged in
  loginPageIndicator: [
    'button:has-text("Sign In")',
    'button:has-text("Log In")',
    'button:has-text("Sign Up")',
  ],
};

/**
 * Returns the first matching selector from an array.
 * Tries each selector in order; returns the first one Playwright can find.
 *
 * Usage:
 *   const el = await findFirst(page, SELECTORS.createButton);
 */
async function findFirst(page, selectorList, options = {}) {
  const timeout = options.timeout || 10_000;
  for (const sel of selectorList) {
    try {
      const el = await page.waitForSelector(sel, { timeout: 3_000, state: 'visible' });
      if (el) return el;
    } catch {
      // try next
    }
  }
  // Last attempt with longer timeout on all selectors joined
  const joined = selectorList.join(', ');
  return await page.waitForSelector(joined, { timeout, state: 'visible' });
}

module.exports = { SELECTORS, findFirst };
