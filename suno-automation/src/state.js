/**
 * state.js — Manages processed.json for idempotency.
 *
 * Design: we store a flat object { [promptId]: { status, files, timestamp } }
 * A prompt is considered "done" if status === "success".
 * This lets us resume interrupted runs without regenerating anything.
 */

const fs = require('fs');
const config = require('./config');
const logger = require('./logger');

/**
 * Loads the processed state from disk. Returns {} if file doesn't exist.
 */
function loadState() {
  if (!fs.existsSync(config.processedFile)) return {};
  try {
    return JSON.parse(fs.readFileSync(config.processedFile, 'utf-8'));
  } catch (err) {
    logger.warn(`Could not parse processed.json: ${err.message} — starting fresh.`);
    return {};
  }
}

/**
 * Saves the full state object to disk.
 */
function saveState(state) {
  fs.writeFileSync(config.processedFile, JSON.stringify(state, null, 2), 'utf-8');
}

/**
 * Marks a prompt as successfully processed.
 * @param {object} state - the current state object (mutated in place)
 * @param {string} id - the prompt id
 * @param {string[]} files - list of downloaded file paths
 */
function markDone(state, id, files) {
  state[id] = {
    status: 'success',
    files,
    timestamp: new Date().toISOString(),
  };
  saveState(state);
}

/**
 * Marks a prompt as failed.
 */
function markFailed(state, id, reason) {
  state[id] = {
    status: 'failed',
    reason,
    timestamp: new Date().toISOString(),
  };
  saveState(state);
}

/**
 * Returns true if the prompt was already successfully processed.
 */
function isDone(state, id) {
  return state[id]?.status === 'success';
}

module.exports = { loadState, saveState, markDone, markFailed, isDone };
