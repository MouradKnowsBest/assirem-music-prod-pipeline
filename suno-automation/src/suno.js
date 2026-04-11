/**
 * suno.js — Core Suno automation logic.
 *
 * This module handles:
 *   1. Checking login status
 *   2. Navigating to the Create page
 *   3. Filling the prompt
 *   4. Triggering generation
 *   5. Waiting for generation to complete (via API response interception + UI polling)
 *   6. Downloading the generated tracks
 *
 * !! SELECTOR FRAGILITY !!
 * All selectors are imported from selectors.js. Edit there if Suno's UI changes.
 */

const fs = require('fs');
const path = require('path');
const config = require('./config');
const logger = require('./logger');
const { SELECTORS, findFirst } = require('./selectors');
const { saveDownload } = require('./downloader');

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Saves a screenshot to the screenshots directory with a timestamp + label.
 */
async function screenshot(page, label) {
  if (!config.screenshotOnFailure) return;
  fs.mkdirSync(config.screenshotsDir, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = path.join(config.screenshotsDir, `${ts}_${label}.png`);
  try {
    await page.screenshot({ path: filename, fullPage: true });
    logger.info(`Screenshot saved: ${filename}`);
  } catch {
    // ignore screenshot failures
  }
}

/**
 * Saves the page HTML for debugging.
 */
async function dumpHtml(page, label) {
  if (!config.htmlDumpOnFailure) return;
  fs.mkdirSync(config.screenshotsDir, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = path.join(config.screenshotsDir, `${ts}_${label}.html`);
  try {
    const html = await page.content();
    fs.writeFileSync(filename, html, 'utf-8');
    logger.info(`HTML dump saved: ${filename}`);
  } catch {
    // ignore
  }
}

/**
 * Retries an async function up to maxRetries times.
 */
async function withRetry(fn, label, maxRetries = config.maxRetries) {
  let lastErr;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt < maxRetries) {
        logger.warn(`[${label}] Attempt ${attempt}/${maxRetries} failed: ${err.message}. Retrying in ${config.retryDelay / 1000}s...`);
        await new Promise(r => setTimeout(r, config.retryDelay));
      }
    }
  }
  throw new Error(`[${label}] All ${maxRetries} attempts failed. Last error: ${lastErr.message}`);
}

// ─── Login Check ─────────────────────────────────────────────────────────────

/**
 * Returns true if the user appears to be logged in.
 * Checks for known logged-in indicators from selectors.js.
 */
async function isLoggedIn(page) {
  try {
    await page.goto(config.sunoUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2_000);

    for (const sel of SELECTORS.loggedInIndicator) {
      const el = await page.$(sel);
      if (el) {
        logger.debug(`Logged in indicator found: ${sel}`);
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

// ─── Navigate to Create ───────────────────────────────────────────────────────

/**
 * Navigates to the Create page and waits for it to be ready.
 */
async function navigateToCreate(page) {
  logger.info('Navigating to Suno Create page...');
  await page.goto(config.createUrl, { waitUntil: 'networkidle', timeout: config.navigationTimeout });
  // Give React time to hydrate
  await page.waitForTimeout(1_500);
  logger.debug('Create page loaded.');
}

// ─── Fill Prompt ─────────────────────────────────────────────────────────────

/**
 * Finds the prompt textarea and types the prompt text.
 * Clears existing content first.
 *
 * TODO: If Suno adds a "Custom Mode" toggle that needs to be clicked first,
 *       add that step before filling the textarea.
 */
async function fillPrompt(page, promptText) {
  logger.info('Filling prompt...');

  const textarea = await findFirst(page, SELECTORS.promptTextarea, { timeout: 15_000 });
  if (!textarea) throw new Error('Prompt textarea not found on page.');

  // Click to focus, then clear existing content
  await textarea.click();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');

  // Type with a small delay to simulate human input
  await textarea.fill(promptText);
  await page.waitForTimeout(500);

  logger.debug(`Prompt filled: "${promptText.slice(0, 60)}..."`);
}

// ─── Click Create ─────────────────────────────────────────────────────────────

/**
 * Clicks the Create/Generate button.
 * Returns the timestamp just before clicking (used to identify newly created songs).
 */
async function clickCreate(page) {
  logger.info('Clicking Create button...');

  const btn = await findFirst(page, SELECTORS.createButton, { timeout: 10_000 });
  if (!btn) throw new Error('Create button not found.');

  // Check it's not disabled
  const disabled = await btn.getAttribute('disabled');
  if (disabled !== null) throw new Error('Create button is disabled (rate limit or not logged in?).');

  const clickedAt = Date.now();
  await btn.click();
  logger.debug('Create button clicked.');
  return clickedAt;
}

// ─── Wait for Generation ──────────────────────────────────────────────────────

/**
 * Waits for Suno to finish generating tracks.
 *
 * Strategy (two-pronged for resilience):
 *   1. PRIMARY: Intercept Suno's internal feed API responses and watch for
 *      status === "complete" on the new tracks. This is fast and reliable
 *      when Suno's API structure is stable.
 *   2. FALLBACK: Poll the DOM for completed song cards (play button visible,
 *      no loading spinner). Used if the API response format changes.
 *
 * Returns an array of song objects from the feed API (or empty array on fallback).
 */
async function waitForGeneration(page, clickedAt) {
  logger.info('Waiting for generation to complete...');
  const deadline = Date.now() + config.generationTimeout;

  // Strategy 1: intercept /api/feed/ responses
  const completedSongs = [];
  let apiStrategySucceeded = false;

  const responseHandler = async (response) => {
    // TODO: Suno's feed endpoint may change — update this URL pattern if needed
    if (!response.url().includes('/api/feed') && !response.url().includes('/api/generate')) return;
    try {
      const json = await response.json().catch(() => null);
      if (!json) return;

      // Suno's feed returns: { clips: [...] } or an array of clip objects
      const clips = Array.isArray(json) ? json : (json.clips || json.data || []);
      for (const clip of clips) {
        // Only pick up clips created after we clicked Create
        const createdAt = new Date(clip.created_at || 0).getTime();
        if (createdAt < clickedAt - 5000) continue;  // 5s margin

        if (clip.status === 'complete' && clip.audio_url) {
          if (!completedSongs.find(s => s.id === clip.id)) {
            completedSongs.push(clip);
            logger.info(`Track ready via API: "${clip.title || clip.id}" (${completedSongs.length}/${config.tracksPerPrompt})`);
          }
        }
      }

      if (completedSongs.length >= config.tracksPerPrompt) {
        apiStrategySucceeded = true;
      }
    } catch {
      // API response parse failure — fall through to DOM strategy
    }
  };

  page.on('response', responseHandler);

  // Poll until done or timeout
  while (Date.now() < deadline) {
    if (apiStrategySucceeded) {
      logger.success(`Generation complete (API strategy): ${completedSongs.length} track(s)`);
      page.off('response', responseHandler);
      return completedSongs;
    }

    // Strategy 2: DOM polling fallback
    // Count completed song cards (those with visible play buttons)
    try {
      const cards = await page.$$(SELECTORS.completedSongCard.join(', '));
      const playButtons = await page.$$(SELECTORS.playButton.join(', '));
      if (playButtons.length >= config.tracksPerPrompt) {
        logger.success(`Generation complete (DOM strategy): ${playButtons.length} track(s) visible.`);
        page.off('response', responseHandler);
        return [];  // Return empty — downloader will use DOM-based approach
      }
      logger.debug(`Polling... play buttons found: ${playButtons.length}/${config.tracksPerPrompt}`);
    } catch {
      // DOM not ready yet
    }

    await new Promise(r => setTimeout(r, config.pollInterval));
  }

  page.off('response', responseHandler);
  throw new Error(`Generation timed out after ${config.generationTimeout / 1000}s`);
}

// ─── Download Tracks ──────────────────────────────────────────────────────────

/**
 * Downloads generated tracks.
 *
 * If we have API clip data with audio_url, we use direct URL download (fastest).
 * Otherwise we fall back to UI-based download via the "..." menu.
 *
 * @param {import('playwright').Page} page
 * @param {import('playwright').BrowserContext} context
 * @param {object} prompt - the prompt object from prompts.json
 * @param {object[]} apiClips - clips returned by waitForGeneration (may be empty)
 * @returns {string[]} list of saved file paths
 */
async function downloadTracks(page, context, prompt, apiClips) {
  const savedFiles = [];

  if (apiClips.length > 0) {
    // ── Fast path: direct URL download from API data ────────────────────────
    logger.info('Using direct URL download (fast path)...');
    for (let i = 0; i < Math.min(apiClips.length, config.tracksPerPrompt); i++) {
      const clip = apiClips[i];
      const trackIndex = i + 1;

      try {
        logger.info(`Downloading track ${trackIndex}/${config.tracksPerPrompt}: ${clip.title || clip.id}`);
        const filePath = await downloadViaUrl(context, clip.audio_url, prompt, trackIndex);
        if (filePath) savedFiles.push(filePath);
      } catch (err) {
        logger.warn(`Direct URL download failed for track ${trackIndex}: ${err.message}. Trying UI fallback...`);
        const filePath = await downloadViaUi(page, context, prompt, trackIndex);
        if (filePath) savedFiles.push(filePath);
      }
    }
  } else {
    // ── UI fallback: click the "..." menu and Download option ────────────────
    logger.info('Using UI-based download (fallback)...');
    for (let trackIndex = 1; trackIndex <= config.tracksPerPrompt; trackIndex++) {
      const filePath = await downloadViaUi(page, context, prompt, trackIndex);
      if (filePath) savedFiles.push(filePath);
    }
  }

  return savedFiles;
}

/**
 * Downloads a track directly from its audio URL.
 * Opens a new page to trigger the download via Playwright's download API.
 */
async function downloadViaUrl(context, audioUrl, prompt, trackIndex) {
  logger.debug(`Downloading from URL: ${audioUrl}`);

  const downloadPage = await context.newPage();
  try {
    const [download] = await Promise.all([
      downloadPage.waitForEvent('download', { timeout: config.downloadTimeout }),
      downloadPage.goto(audioUrl),
    ]);
    return await saveDownload(download, prompt, trackIndex);
  } finally {
    await downloadPage.close().catch(() => {});
  }
}

/**
 * Downloads a track using the Suno UI:
 *   1. Find the nth song card
 *   2. Click its "..." menu button
 *   3. Click "Download" in the dropdown
 *   4. Handle the Playwright download event
 *
 * TODO: This is the most likely function to break when Suno updates its UI.
 *       If it breaks, inspect the "..." button and "Download" menu item selectors
 *       in selectors.js and update them.
 */
async function downloadViaUi(page, context, prompt, trackIndex) {
  logger.info(`UI download — track ${trackIndex}...`);

  // Find all song menu buttons (one per generated track)
  const menuButtons = await page.$$(SELECTORS.songMenuButton.join(', '));
  if (menuButtons.length < trackIndex) {
    throw new Error(`Expected ${trackIndex} menu button(s), found ${menuButtons.length}. UI layout may have changed.`);
  }

  const menuBtn = menuButtons[trackIndex - 1];
  await menuBtn.scrollIntoViewIfNeeded();
  await menuBtn.click();
  await page.waitForTimeout(600);  // wait for dropdown to open

  // Find "Download" in the open dropdown
  const downloadItem = await findFirst(page, SELECTORS.downloadMenuItem, { timeout: 8_000 });
  if (!downloadItem) throw new Error('"Download" option not found in dropdown menu.');

  // Intercept the download event
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: config.downloadTimeout }),
    downloadItem.click(),
  ]);

  return await saveDownload(download, prompt, trackIndex);
}

// ─── Full prompt pipeline ─────────────────────────────────────────────────────

/**
 * Processes a single prompt: navigate → fill → create → wait → download.
 * Returns array of saved file paths.
 *
 * @param {import('playwright').Page} page
 * @param {import('playwright').BrowserContext} context
 * @param {object} prompt  - { id, title, prompt, slug? }
 */
async function processPrompt(page, context, prompt) {
  return withRetry(async () => {
    try {
      await navigateToCreate(page);
      await fillPrompt(page, prompt.prompt);
      const clickedAt = await clickCreate(page);
      const apiClips = await waitForGeneration(page, clickedAt);
      const files = await downloadTracks(page, context, prompt, apiClips);

      if (files.length === 0) throw new Error('No files were downloaded.');
      return files;
    } catch (err) {
      await screenshot(page, `failure_${prompt.id}`);
      await dumpHtml(page, `failure_${prompt.id}`);
      throw err;
    }
  }, `processPrompt[${prompt.id}]`);
}

module.exports = {
  isLoggedIn,
  processPrompt,
  screenshot,
};
