/**
 * config.js — Central configuration for the Suno automation
 * All paths and timeouts in one place.
 */

const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PIPELINE_ROOT = path.resolve(ROOT, '..');

const config = {
  // ── URLs ──────────────────────────────────────────────────────────────────
  sunoUrl: 'https://suno.com',
  createUrl: 'https://suno.com/create',

  // ── Input / Output ────────────────────────────────────────────────────────
  // Prompts source: by default reads ../config.json (pipeline format).
  // Set PROMPTS_FILE=./prompts.json to use the standalone prompts file instead.
  promptsFile: process.env.PROMPTS_FILE || null,

  // outputDir: where to save MP3s.
  // By default, maps directly into the pipeline's input/{slug}/ directories.
  // Override with OUTPUT_DIR env var if needed.
  outputDir: process.env.OUTPUT_DIR || path.join(PIPELINE_ROOT, 'input'),

  // processed.json: tracks which prompt IDs have already been completed
  processedFile: process.env.PROCESSED_FILE || path.join(ROOT, 'processed.json'),

  // ── Browser ───────────────────────────────────────────────────────────────
  // Persistent context: keeps session across runs (no re-login needed)
  userDataDir: process.env.USER_DATA_DIR || path.join(ROOT, '.browser-profile'),
  headless: process.env.HEADLESS === 'true',

  // ── Timeouts (ms) ─────────────────────────────────────────────────────────
  navigationTimeout: 30_000,
  // Suno can take 1–3 minutes to generate a track
  generationTimeout: parseInt(process.env.GENERATION_TIMEOUT || '240000', 10),
  downloadTimeout: 60_000,
  // Poll interval when checking generation status
  pollInterval: 4_000,

  // ── Retry ─────────────────────────────────────────────────────────────────
  maxRetries: parseInt(process.env.MAX_RETRIES || '3', 10),
  retryDelay: 6_000,

  // ── Delays ────────────────────────────────────────────────────────────────
  // Pause between prompts to avoid rate limiting
  delayBetweenPrompts: parseInt(process.env.DELAY_BETWEEN || '5000', 10),

  // ── Debug ─────────────────────────────────────────────────────────────────
  screenshotsDir: path.join(ROOT, 'screenshots'),
  screenshotOnFailure: process.env.NO_SCREENSHOTS !== 'true',
  htmlDumpOnFailure: process.env.HTML_DUMP === 'true',

  // ── Behaviour ─────────────────────────────────────────────────────────────
  // If true, skip prompts whose output files already exist
  skipExisting: process.env.FORCE !== 'true',
  // How many tracks per prompt to download (Suno generates 2 by default)
  tracksPerPrompt: parseInt(process.env.TRACKS_PER_PROMPT || '2', 10),
};

module.exports = config;
