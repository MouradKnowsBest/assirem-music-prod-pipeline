/**
 * logger.js — Colored terminal logger with timestamps.
 */

const RESET  = '\x1b[0m';
const BOLD   = '\x1b[1m';
const GREEN  = '\x1b[32m';
const RED    = '\x1b[31m';
const YELLOW = '\x1b[33m';
const CYAN   = '\x1b[36m';
const GRAY   = '\x1b[90m';
const MAGENTA = '\x1b[35m';

function timestamp() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function fmt(color, symbol, msg) {
  return `${GRAY}[${timestamp()}]${RESET} ${color}${BOLD}${symbol}${RESET} ${msg}`;
}

const logger = {
  info:    (msg) => console.log(fmt(CYAN,    '→', msg)),
  success: (msg) => console.log(fmt(GREEN,   '✅', msg)),
  warn:    (msg) => console.log(fmt(YELLOW,  '⚠ ', msg)),
  error:   (msg) => console.log(fmt(RED,     '❌', msg)),
  step:    (msg) => console.log(fmt(MAGENTA, '▶ ', `${BOLD}${msg}${RESET}`)),
  debug:   (msg) => {
    if (process.env.DEBUG) console.log(fmt(GRAY, '·', msg));
  },
  sep: () => console.log(`${GRAY}${'─'.repeat(60)}${RESET}`),
  header: (msg) => {
    console.log(`\n${BOLD}${'═'.repeat(60)}${RESET}`);
    console.log(`${BOLD}  ${msg}${RESET}`);
    console.log(`${BOLD}${'═'.repeat(60)}${RESET}`);
  },
};

module.exports = logger;
