/**
 * suno-api.js — Direct HTTP API client for Suno (no browser needed).
 *
 * Suno uses Clerk for auth. We authenticate via cookies extracted from a
 * real browser session. The session token is a JWT valid for ~30 days.
 *
 * Endpoints used:
 *   POST https://studio-api.suno.ai/api/generate/v2/   — create tracks
 *   GET  https://studio-api.suno.ai/api/feed/?ids=...  — poll status
 *   GET  <audio_url>                                    — download MP3
 *
 * When the session expires, update SUNO_COOKIE_SESSION in .env
 * (copy fresh value from browser DevTools → Application → Cookies → suno.com)
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");
const config = require("./config");
const logger = require("./logger");

const API_BASE = "studio-api.prod.suno.com";

// ─── Load .env manually (no dotenv dep needed) ────────────────────────────────
function loadEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) {
    throw new Error(
      ".env file not found. Create suno-automation/.env with SUNO_COOKIE_CLIENT and SUNO_COOKIE_SESSION.",
    );
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

function getSessionToken() {
  const session = process.env.SUNO_COOKIE_SESSION;
  if (!session) throw new Error("Missing SUNO_COOKIE_SESSION in .env");
  return session;
}

function getCookieHeader() {
  const client = process.env.SUNO_COOKIE_CLIENT;
  const session = process.env.SUNO_COOKIE_SESSION;
  if (!client || !session) {
    throw new Error(
      "Missing SUNO_COOKIE_CLIENT or SUNO_COOKIE_SESSION in .env",
    );
  }
  return `__client=${client}; __session=${session}`;
}

// ─── Clerk JWT exchange ───────────────────────────────────────────────────────
// Suno's generate endpoint requires a fresh short-lived JWT (not the raw session
// cookie). We get it by POSTing to Clerk's token endpoint. Cached for 50s.

let _cachedJwt = null;
let _jwtExpiresAt = 0;

function getSessionId() {
  // Decode the session cookie (JWT) to extract the sid claim
  try {
    const payload = JSON.parse(
      Buffer.from(getSessionToken().split(".")[1], "base64").toString(),
    );
    if (!payload.sid) {
      logger.error(
        `Session JWT payload missing 'sid' claim. Payload: ${JSON.stringify(payload, null, 2)}`,
      );
      throw new Error("Session token missing sid claim");
    }
    logger.debug(`Session ID extracted: ${payload.sid}`);
    return payload.sid;
  } catch (err) {
    logger.error(`Failed to decode session token: ${err.message}`);
    throw new Error("Invalid SUNO_COOKIE_SESSION format (not a valid JWT)");
  }
}

async function getFreshJwt() {
  if (_cachedJwt && Date.now() < _jwtExpiresAt) {
    logger.debug("Using cached JWT");
    return _cachedJwt;
  }

  const sid = getSessionId();
  if (!sid)
    throw new Error("Could not extract session ID from SUNO_COOKIE_SESSION");

  logger.info(`🔑 Exchanging Clerk JWT for session: ${sid.slice(0, 20)}...`);

  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: "clerk.suno.com",
        path: `/v1/client/sessions/${sid}/tokens?_clerk_js_version=5.0.0`,
        method: "POST",
        headers: {
          Cookie: getCookieHeader(),
          Authorization: `Bearer ${getSessionToken()}`,
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
          Accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": 0,
          Origin: "https://suno.com",
          Referer: "https://suno.com/",
        },
      },
      (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => {
          if (res.statusCode !== 200) {
            logger.error(
              `❌ Clerk JWT exchange failed (HTTP ${res.statusCode}): ${body.slice(0, 300)}`,
            );
            reject(
              new Error(
                `Clerk token exchange failed (${res.statusCode}): ${body.slice(0, 200)}`,
              ),
            );
            return;
          }
          try {
            const data = JSON.parse(body);
            const jwt = data.jwt;
            if (!jwt) {
              logger.error(
                `❌ No jwt in Clerk response. Full body: ${body.slice(0, 300)}`,
              );
              reject(new Error("No jwt in Clerk response"));
              return;
            }
            _cachedJwt = jwt;
            _jwtExpiresAt = Date.now() + 50_000; // cache 50s (token valid ~60s)
            logger.info("✅ Fresh Clerk JWT obtained successfully");
            resolve(jwt);
          } catch (err) {
            logger.error(
              `❌ Failed to parse Clerk response: ${err.message}. Body: ${body.slice(0, 300)}`,
            );
            reject(err);
          }
        });
      },
    );
    req.on("error", (err) => {
      logger.error(`❌ Clerk request error: ${err.message}`);
      reject(err);
    });
    req.end();
  });
}

async function getAuthHeaders() {
  const jwt = await getFreshJwt();
  return {
    Cookie: getCookieHeader(),
    Authorization: `Bearer ${jwt}`,
    "User-Agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    Accept: "application/json",
    Origin: "https://suno.com",
    Referer: "https://suno.com/",
  };
}

// ─── HTTP helpers ─────────────────────────────────────────────────────────────

async function request(apiPath, options = {}, body = null) {
  const url = `https://${API_BASE}${apiPath}`;
  const authHeaders = await getAuthHeaders();
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);

    const reqOptions = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: options.method || "GET",
      headers: {
        ...authHeaders,
        ...(options.headers || {}),
      },
    };

    if (body) {
      const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
      reqOptions.headers["Content-Type"] = "application/json";
      reqOptions.headers["Content-Length"] = Buffer.byteLength(bodyStr);
    }

    const req = https.request(reqOptions, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const raw = Buffer.concat(chunks).toString("utf-8");
        resolve({ status: res.statusCode, headers: res.headers, body: raw });
      });
    });

    req.on("error", reject);
    if (body) req.write(typeof body === "string" ? body : JSON.stringify(body));
    req.end();
  });
}

async function requestJson(apiPath, options = {}, body = null) {
  const res = await request(apiPath, options, body);
  if (res.status >= 400) {
    throw new Error(
      `HTTP ${res.status} from ${API_BASE}${apiPath}: ${res.body.slice(0, 200)}`,
    );
  }
  try {
    return JSON.parse(res.body);
  } catch {
    throw new Error(
      `Non-JSON response from ${API_BASE}${apiPath}: ${res.body.slice(0, 200)}`,
    );
  }
}

// ─── Download binary file ────────────────────────────────────────────────────

async function downloadFile(url, destPath) {
  const authHeaders = await getAuthHeaders();
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath);
    const parsed = new URL(url);
    const lib = parsed.protocol === "https:" ? https : http;

    const options = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: "GET",
      headers: authHeaders,
    };

    function doRequest(reqUrl) {
      const p = new URL(reqUrl);
      const opts = {
        ...options,
        hostname: p.hostname,
        path: p.pathname + p.search,
      };
      const libToUse = p.protocol === "https:" ? https : http;

      libToUse
        .get(opts, (res) => {
          // Follow redirects
          if (
            res.statusCode >= 300 &&
            res.statusCode < 400 &&
            res.headers.location
          ) {
            res.resume();
            doRequest(res.headers.location);
            return;
          }
          if (res.statusCode >= 400) {
            file.close();
            fs.unlink(destPath, () => {});
            reject(new Error(`Download failed with HTTP ${res.statusCode}`));
            return;
          }
          res.pipe(file);
          file.on("finish", () => file.close(resolve));
          file.on("error", (err) => {
            fs.unlink(destPath, () => {});
            reject(err);
          });
        })
        .on("error", (err) => {
          fs.unlink(destPath, () => {});
          reject(err);
        });
    }

    doRequest(url);
  });
}

// ─── Suno API calls ───────────────────────────────────────────────────────────

/**
 * Checks that the session cookies are valid by calling the user info endpoint.
 * Throws if not authenticated.
 */
async function checkAuth() {
  logger.info("Checking Suno API auth...");
  try {
    const data = await requestJson("/api/user/me/");
    const name = data?.display_name || data?.handle || "(unknown)";
    const billing = await requestJson("/api/billing/info/");
    const credits = billing?.credits ?? "?";
    logger.success(`Authenticated as: ${name} — credits: ${credits}`);
    return true;
  } catch (err) {
    throw new Error(
      `Suno auth failed: ${err.message}\nUpdate SUNO_COOKIE_SESSION in .env with a fresh cookie from your browser.`,
    );
  }
}

/**
 * Submits a generation request to Suno.
 * Returns an array of clip IDs that are being generated.
 *
 * @param {string} style  - genre/instrument/mood descriptors → Suno "tags" field
 * @param {string} lyrics - song lyrics or "[Instrumental]" → Suno "prompt" field
 * @returns {string[]} array of clip IDs
 */
async function generateTracks(style, lyrics = "") {
  logger.info(`Requesting generation: style="${style.slice(0, 70)}..."`);

  const isInstrumental = !lyrics || lyrics.trim() === "[Instrumental]";

  // Suno now requires a Cloudflare Turnstile token. For now, we hardcode one from browser.
  // TODO: Implement proper Turnstile solving or switch back to Playwright
  const turnstileToken = process.env.SUNO_TURNSTILE_TOKEN || "";
  if (!turnstileToken) {
    logger.warn(
      "⚠️  SUNO_TURNSTILE_TOKEN not set in .env — generation will likely fail.",
    );
    logger.warn(
      "   Extract token from browser DevTools (Payload of /api/generate/v2-web) and add to .env",
    );
  }

  const payload = {
    token: turnstileToken,
    generation_type: "TEXT",
    mv: "chirp-fenix", // Suno's latest model (April 2026)
    prompt: isInstrumental ? "" : lyrics,
    gpt_description_prompt: style, // Renamed from "tags"
    make_instrumental: isInstrumental,
    user_uploaded_images_b64: null,
    metadata: {
      web_client_pathname: "/create",
      is_max_mode: false,
      is_mumble: false,
      create_mode: "simple",
      user_tier: "3eaebef3-ef46-446a-931c-3d50cd1514f1",
      create_session_token: require("crypto").randomUUID(),
      disable_volume_normalization: false,
      lyrics_model: "default",
    },
    override_fields: [],
    cover_clip_id: null,
    cover_start_s: null,
    cover_end_s: null,
    persona_id: null,
    artist_clip_id: null,
    artist_start_s: null,
    artist_end_s: null,
    continue_clip_id: null,
    continued_aligned_prompt: null,
    continue_at: null,
    transaction_uuid: require("crypto").randomUUID(),
  };

  logger.debug(`📤 Payload: ${JSON.stringify(payload, null, 2)}`);

  try {
    const data = await requestJson(
      "/api/generate/v2-web/", // Changed from v2/ to v2-web/
      { method: "POST" },
      payload,
    );

    // Response shape: { clips: [{ id, status, ... }, ...] }
    const clips = data?.clips || data;
    if (!Array.isArray(clips) || clips.length === 0) {
      throw new Error(
        `Unexpected generate response: ${JSON.stringify(data).slice(0, 300)}`,
      );
    }

    const ids = clips.map((c) => c.id);
    logger.info(`Generation started — clip IDs: ${ids.join(", ")}`);
    return ids;
  } catch (err) {
    logger.error(`❌ Generate request failed: ${err.message}`);
    throw err;
  }
}

/**
 * Polls the feed API until all clips are complete (or timeout).
 * Returns the completed clip objects with audio_url populated.
 *
 * @param {string[]} ids
 * @returns {object[]} completed clip objects
 */
async function waitForClips(ids) {
  logger.info(`Polling generation status for ${ids.length} clip(s)...`);
  const deadline = Date.now() + config.generationTimeout;
  let dots = 0;

  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, config.pollInterval));

    const data = await requestJson(`/api/feed/?ids=${ids.join(",")}`);

    const clips = Array.isArray(data) ? data : data.clips || [];

    const done = clips.filter((c) => c.status === "complete" && c.audio_url);
    const failed = clips.filter(
      (c) => c.status === "error" || c.status === "failed",
    );
    const pending = clips.filter(
      (c) => !["complete", "error", "failed"].includes(c.status),
    );

    if (failed.length > 0) {
      throw new Error(
        `Suno reported generation failure for clip(s): ${failed.map((c) => c.id).join(", ")}`,
      );
    }

    if (dots % 3 === 0) {
      logger.debug(`Status: ${done.length} done, ${pending.length} pending...`);
      process.stdout.write(
        `\r  ⏳ Generating... ${done.length}/${ids.length} ready  `,
      );
    }
    dots++;

    if (done.length >= ids.length) {
      console.log(); // newline
      logger.success(`All ${done.length} clip(s) ready!`);
      return done;
    }
  }

  console.log();
  throw new Error(
    `Generation timed out after ${config.generationTimeout / 1000}s`,
  );
}

/**
 * Downloads a single clip's audio file.
 *
 * @param {object} clip      - clip object from feed API (has .audio_url, .title)
 * @param {object} prompt    - prompt object from prompts.json (has .id, .slug, .title)
 * @param {number} trackIndex - 1-based index within this prompt
 * @returns {string} saved file path
 */
async function downloadClip(clip, prompt, trackIndex) {
  const { getTargetDir, sanitizeFilename } = require("./downloader");

  const dir = getTargetDir(prompt);
  const ext = "mp3";
  const slug = sanitizeFilename(prompt.title || prompt.id);
  const filename = `${prompt.id}_${slug}_${trackIndex}.${ext}`;
  const destPath = path.join(dir, filename);

  if (config.skipExisting && fs.existsSync(destPath)) {
    logger.warn(`Already exists, skipping: ${filename}`);
    return destPath;
  }

  logger.info(`Downloading: ${filename} (${clip.title || clip.id})`);
  await downloadFile(clip.audio_url, destPath);

  const sizeMb = (fs.statSync(destPath).size / 1024 / 1024).toFixed(1);
  logger.success(
    `Saved: ${path.relative(process.cwd(), destPath)} (${sizeMb} MB)`,
  );
  return destPath;
}

// ─── Full prompt pipeline (no browser) ───────────────────────────────────────

/**
 * Processes a single prompt end-to-end via the API.
 * Returns array of saved file paths.
 */
async function processPromptApi(prompt) {
  const { loadState } = require("./state");

  let lastErr;
  for (let attempt = 1; attempt <= config.maxRetries; attempt++) {
    try {
      // 1. Generate
      const ids = await generateTracks(prompt.style, prompt.lyrics);

      // 2. Wait for completion
      const clips = await waitForClips(ids);

      // 3. Download each clip
      const files = [];
      for (let i = 0; i < Math.min(clips.length, config.tracksPerPrompt); i++) {
        const filePath = await downloadClip(clips[i], prompt, i + 1);
        if (filePath) files.push(filePath);
      }

      if (files.length === 0) throw new Error("No files downloaded.");
      return files;
    } catch (err) {
      lastErr = err;
      if (attempt < config.maxRetries) {
        logger.warn(
          `Attempt ${attempt}/${config.maxRetries} failed: ${err.message}. Retrying in ${config.retryDelay / 1000}s...`,
        );
        await new Promise((r) => setTimeout(r, config.retryDelay));
      }
    }
  }

  throw new Error(
    `All ${config.maxRetries} attempts failed. Last: ${lastErr.message}`,
  );
}

module.exports = {
  checkAuth,
  generateTracks,
  waitForClips,
  downloadClip,
  processPromptApi,
};
