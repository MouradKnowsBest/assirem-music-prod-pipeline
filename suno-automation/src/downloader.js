/**
 * downloader.js — Handles saving downloaded files with clean filenames.
 */

const fs = require('fs');
const path = require('path');
const config = require('./config');
const logger = require('./logger');

/**
 * Sanitizes a string into a safe filename component.
 * e.g. "Night Code Loop #2!" → "night-code-loop-2"
 */
function sanitizeFilename(str) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

/**
 * Builds the target directory for a prompt's downloads.
 * Maps: slug "lofi" → <outputDir>/lofi/
 * Falls back to <outputDir>/<sanitizedTitle>/ if no slug.
 */
function getTargetDir(prompt) {
  const slug = prompt.slug || sanitizeFilename(prompt.title || prompt.id);
  const dir = path.join(config.outputDir, slug);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Builds the target filename for a track.
 * Pattern: <id>_<slug>_<trackIndex>.mp3
 * e.g.  001_lofi_1.mp3 / 001_lofi_2.mp3
 */
function buildFilename(prompt, trackIndex, ext = 'mp3') {
  const slug = sanitizeFilename(prompt.title || prompt.id);
  return `${prompt.id}_${slug}_${trackIndex}.${ext}`;
}

/**
 * Saves a Playwright Download object to the right place.
 * Returns the saved file path, or null on error.
 *
 * @param {import('playwright').Download} download
 * @param {object} prompt
 * @param {number} trackIndex  (1-based)
 */
async function saveDownload(download, prompt, trackIndex) {
  const dir = getTargetDir(prompt);

  // Try to infer extension from the suggested filename
  const suggested = download.suggestedFilename();
  const ext = path.extname(suggested).replace('.', '') || 'mp3';

  const filename = buildFilename(prompt, trackIndex, ext);
  const destPath = path.join(dir, filename);

  // Skip if already exists and not force mode
  if (config.skipExisting && fs.existsSync(destPath)) {
    logger.warn(`File already exists, skipping: ${filename}`);
    return destPath;
  }

  try {
    await download.saveAs(destPath);
    const sizeMb = (fs.statSync(destPath).size / 1024 / 1024).toFixed(1);
    logger.success(`Saved: ${path.relative(process.cwd(), destPath)} (${sizeMb} MB)`);
    return destPath;
  } catch (err) {
    logger.error(`Failed to save download: ${err.message}`);
    // Save failure report from download if available
    const failReason = await download.failure();
    if (failReason) logger.error(`Download failure reason: ${failReason}`);
    return null;
  }
}

/**
 * Checks if expected output files already exist for a prompt.
 * Used to skip re-downloading in resume mode.
 */
function outputFilesExist(prompt) {
  const dir = getTargetDir(prompt);
  for (let i = 1; i <= config.tracksPerPrompt; i++) {
    const mp3Path = path.join(dir, buildFilename(prompt, i, 'mp3'));
    const wavPath = path.join(dir, buildFilename(prompt, i, 'wav'));
    if (!fs.existsSync(mp3Path) && !fs.existsSync(wavPath)) return false;
  }
  return true;
}

module.exports = { saveDownload, outputFilesExist, getTargetDir, sanitizeFilename };
