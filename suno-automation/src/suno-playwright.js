/**
 * suno-playwright.js — Suno automation via Playwright (headless browser)
 *
 * Uses a real browser to bypass Cloudflare Turnstile anti-bot protection.
 * Injects cookies from .env, navigates to /create, submits generation requests,
 * and downloads MP3s.
 */

const playwright = require("playwright");
const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");
const logger = require("./logger");
const config = require("./config");

const SUNO_BASE = "https://suno.com";

// Load cookies from .env
function loadEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) {
    throw new Error(".env file not found");
  }
  for (const line of fs.readFileSync(envPath, "utf-8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}

loadEnv();

function getCookies() {
  const client = process.env.SUNO_COOKIE_CLIENT;
  const session = process.env.SUNO_COOKIE_SESSION;
  if (!client || !session) {
    throw new Error(
      "Missing SUNO_COOKIE_CLIENT or SUNO_COOKIE_SESSION in .env",
    );
  }
  return [
    { name: "__client", value: client, domain: ".suno.com", path: "/" },
    { name: "__session", value: session, domain: ".suno.com", path: "/" },
  ];
}

/**
 * Generates tracks using Playwright browser automation.
 *
 * @param {object} prompt - { id, slug, title, style, lyrics }
 * @param {string} outputDir - where to save MP3s
 * @returns {string[]} array of downloaded file paths
 */
async function generateWithBrowser(prompt, outputDir) {
  logger.info(`[${prompt.id}] Launching browser...`);

  const browser = await playwright.chromium.launch({
    headless: true,
    args: ["--disable-blink-features=AutomationControlled"],
  });

  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  await context.addCookies(getCookies());
  const page = await context.newPage();

  try {
    logger.info(`[${prompt.id}] Navigating to Suno Create...`);
    await page.goto(`${SUNO_BASE}/create`, {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    // Wait for create form to load
    await page.waitForSelector(
      '[data-testid="create-form"], textarea, input[type="text"]',
      { timeout: 10000 },
    );

    logger.info(`[${prompt.id}] Filling generation form...`);

    // Switch to Custom mode if needed (to reveal lyrics textarea)
    const customModeButton = page.locator(
      'button:has-text("Custom"), button:has-text("Advanced"), [role="tab"]:has-text("Custom")',
    );
    if ((await customModeButton.count()) > 0) {
      logger.info(`[${prompt.id}] Switching to Custom mode...`);
      await customModeButton.first().click();
      await page.waitForTimeout(1000); // Wait for UI transition
    }

    // Find the style/description input
    const descriptionInput = page
      .locator(
        'textarea[data-testid="gpt-description-prompt"], textarea[placeholder*="Describe"], input[placeholder*="style"]',
      )
      .first();
    if ((await descriptionInput.count()) > 0) {
      await descriptionInput.fill(prompt.style);
      logger.info(`[${prompt.id}] Filled style/description`);
    } else {
      logger.warn(
        `[${prompt.id}] Could not find style input — page structure may have changed`,
      );
    }

    // Find lyrics input if not instrumental
    if (
      prompt.lyrics &&
      prompt.lyrics.trim() &&
      prompt.lyrics.trim() !== "[Instrumental]"
    ) {
      const lyricsTextarea = page
        .locator(
          'textarea[data-testid="lyrics-textarea"], textarea[placeholder*="Lyrics"]',
        )
        .first();

      // Force visible if needed
      await lyricsTextarea.waitFor({ state: "attached", timeout: 5000 });

      // Use JS to fill since it might be visibility-hidden
      await lyricsTextarea.evaluate((el, text) => {
        el.value = text;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      }, prompt.lyrics);

      logger.info(
        `[${prompt.id}] Filled lyrics (${prompt.lyrics.split("\\n").length} lines)`,
      );
    } else {
      logger.info(`[${prompt.id}] Instrumental mode — skipping lyrics`);
    }

    // Click Create button
    logger.info(`[${prompt.id}] Submitting generation request...`);
    const createButton = await page
      .locator('button:has-text("Create"), button[type="submit"]')
      .first();
    await createButton.click();

    // Wait for generation to start (check for progress indicators or new clips)
    logger.info(`[${prompt.id}] Waiting for generation to complete...`);
    await page.waitForTimeout(5000); // Initial wait for submission

    // Poll for completed tracks (look for download buttons or audio elements)
    const maxWait = config.generationTimeout || 300000; // 5 min default
    const startTime = Date.now();
    let clipIds = [];

    while (Date.now() - startTime < maxWait) {
      // Try to find completed clips with download links
      const downloadButtons = await page
        .locator('button[aria-label*="Download"], a[download], audio[src]')
        .all();

      if (downloadButtons.length >= 2) {
        logger.info(
          `[${prompt.id}] Found ${downloadButtons.length} completed clips`,
        );

        // Extract clip URLs
        for (let i = 0; i < Math.min(downloadButtons.length, 2); i++) {
          const btn = downloadButtons[i];
          let audioUrl = null;

          // Try to get download URL from button
          const href = await btn.getAttribute("href");
          if (href && href.startsWith("http")) {
            audioUrl = href;
          } else {
            // Try to find associated audio element
            const audio = await page.locator("audio[src]").nth(i);
            if ((await audio.count()) > 0) {
              audioUrl = await audio.getAttribute("src");
            }
          }

          if (audioUrl) {
            clipIds.push({ index: i + 1, url: audioUrl });
          }
        }

        if (clipIds.length >= 2) break;
      }

      await page.waitForTimeout(3000);
    }

    if (clipIds.length === 0) {
      throw new Error(
        `No clips generated after ${(Date.now() - startTime) / 1000}s`,
      );
    }

    logger.info(`[${prompt.id}] Downloading ${clipIds.length} clip(s)...`);

    // Download each clip
    const files = [];
    for (const clip of clipIds) {
      const filename = `${prompt.slug}_${clip.index}.mp3`;
      const filepath = path.join(outputDir, filename);

      await downloadFile(clip.url, filepath);
      logger.success(`[${prompt.id}] Downloaded: ${filename}`);
      files.push(filepath);
    }

    return files;
  } catch (err) {
    logger.error(`[${prompt.id}] Browser automation failed: ${err.message}`);

    // Take screenshot for debugging
    const screenshotPath = path.join(
      __dirname,
      "..",
      "screenshots",
      `error-${prompt.slug}-${Date.now()}.png`,
    );
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({ path: screenshotPath, fullPage: true });
    logger.info(`[${prompt.id}] Screenshot saved: ${screenshotPath}`);

    throw err;
  } finally {
    await browser.close();
  }
}

/**
 * Download a file from URL to disk
 */
function downloadFile(url, filepath) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https") ? https : http;
    const file = fs.createWriteStream(filepath);

    client
      .get(url, (res) => {
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          return;
        }
        res.pipe(file);
        file.on("finish", () => {
          file.close();
          resolve();
        });
      })
      .on("error", (err) => {
        fs.unlinkSync(filepath);
        reject(err);
      });
  });
}

module.exports = { generateWithBrowser };
