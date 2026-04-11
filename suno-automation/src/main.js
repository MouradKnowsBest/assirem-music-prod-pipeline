/**
 * main.js — `npm run generate`
 *
 * API-based orchestrator: no browser, no Playwright.
 * Uses Suno's internal HTTP API with session cookies from .env
 *
 * Reads prompts from ../config.json (tracks[].suno_prompt + slug).
 * After all tracks are generated, auto-launches python pipeline.py --all.
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const config = require("./config");
const logger = require("./logger");
const { checkAuth } = require("./suno-api");
const { generateWithBrowser } = require("./suno-playwright");
const { loadState, markDone, markFailed, isDone } = require("./state");
const { outputFilesExist } = require("./downloader");

const PIPELINE_ROOT = path.resolve(__dirname, "..", "..");
const PIPELINE_CONFIG = path.join(PIPELINE_ROOT, "config.json");

/**
 * Strips BPM values from a Suno style prompt so they don't leak into lyrics.
 * Only removes "NNN BPM" / "NNN bpm" patterns — leaves other numbers intact
 * (e.g. "808 bass", "2-step" are fine).
 */
function sanitizeSunoPrompt(prompt) {
  return prompt
    .replace(/\d+\s*bpm/gi, "")
    .replace(/,\s*,/g, ",")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/**
 * Reads tracks from ../config.json and converts them to the prompt format.
 * Also ensures input/{slug}/ directories exist.
 */
function loadPrompts() {
  // Support override via PROMPTS_FILE env var (legacy prompts.json)
  if (process.env.PROMPTS_FILE && fs.existsSync(process.env.PROMPTS_FILE)) {
    const prompts = JSON.parse(
      fs.readFileSync(process.env.PROMPTS_FILE, "utf-8"),
    );
    logger.info(
      `Loaded ${prompts.length} prompts from ${process.env.PROMPTS_FILE}`,
    );
    return prompts;
  }

  if (!fs.existsSync(PIPELINE_CONFIG)) {
    throw new Error(`config.json not found at: ${PIPELINE_CONFIG}`);
  }

  const data = JSON.parse(fs.readFileSync(PIPELINE_CONFIG, "utf-8"));
  const tracks = data.tracks || [];
  if (tracks.length === 0) throw new Error("No tracks found in config.json");

  // Convert pipeline track format → prompt format
  const prompts = tracks
    .sort((a, b) => (a.priority || 99) - (b.priority || 99))
    .map((t, i) => {
      if (!t.slug) throw new Error(`Track at index ${i} missing "slug"`);
      if (!t.suno_style && !t.suno_prompt)
        throw new Error(
          `Track "${t.slug}" missing "suno_style" or "suno_prompt"`,
        );

      // Ensure input/{slug}/ exists
      const dir = path.join(PIPELINE_ROOT, "input", t.slug);
      fs.mkdirSync(dir, { recursive: true });

      return {
        id: String(t.priority || i + 1).padStart(3, "0"),
        slug: t.slug,
        title: t.title || t.slug,
        style: sanitizeSunoPrompt(t.suno_style || t.suno_prompt),
        lyrics: t.lyrics || "",
      };
    });

  logger.info(`Loaded ${prompts.length} tracks from config.json`);
  return prompts;
}

function printSummary(results) {
  logger.header("Generation Summary");
  let ok = 0,
    skipped = 0,
    failed = 0;
  for (const { prompt, status, files, error } of results) {
    const label = `[${prompt.id}] ${(prompt.title || "").slice(0, 30)}`.padEnd(
      38,
    );
    if (status === "success") {
      logger.success(`${label} → ${files.length} file(s) saved`);
      ok++;
    } else if (status === "skipped") {
      logger.warn(`${label} → skipped (already done)`);
      skipped++;
    } else {
      logger.error(`${label} → FAILED: ${error}`);
      failed++;
    }
  }
  logger.sep();
  logger.info(
    `${ok} success · ${skipped} skipped · ${failed} failed · ${results.length} total`,
  );
  if (failed > 0)
    logger.warn("Re-run `npm run generate` to retry failed prompts.");
}

async function main() {
  logger.header("Suno API — Music Generation Pipeline");
  logger.info(`Prompts : ${config.promptsFile}`);
  logger.info(`Output  : ${config.outputDir}`);
  logger.sep();

  let prompts;
  try {
    prompts = loadPrompts();
  } catch (err) {
    logger.error(err.message);
    process.exit(1);
  }

  // Check auth before doing anything
  try {
    await checkAuth();
  } catch (err) {
    logger.error(err.message);
    process.exit(1);
  }
  logger.sep();

  // Support both: FORCE=true npm run generate AND npm run generate FORCE=true
  const force =
    process.env.FORCE === "true" || process.argv.includes("FORCE=true");
  const state = loadState();

  const toProcess = force
    ? prompts // FORCE=true → reprocess everything regardless of state
    : prompts.filter(
        (p) =>
          !isDone(state, p.id) && !(config.skipExisting && outputFilesExist(p)),
      );

  const alreadyDone = force
    ? []
    : prompts.filter(
        (p) =>
          isDone(state, p.id) || (config.skipExisting && outputFilesExist(p)),
      );

  logger.info(`To process : ${toProcess.length} / ${prompts.length}`);
  if (alreadyDone.length > 0)
    logger.info(`Already done: ${alreadyDone.length} (skipping)`);

  if (toProcess.length === 0) {
    logger.success("Nothing to do. Use FORCE=true to reprocess everything.");
    process.exit(0);
  }

  logger.sep();
  const results = [
    ...alreadyDone.map((p) => ({ prompt: p, status: "skipped" })),
  ];

  for (let i = 0; i < toProcess.length; i++) {
    const prompt = toProcess[i];
    logger.step(
      `[${i + 1}/${toProcess.length}] "${prompt.title || prompt.id}" — slug: ${prompt.slug || "?"}`,
    );
    logger.info(`Style : "${prompt.style.slice(0, 80)}..."`);

    const outputDir = path.join(PIPELINE_ROOT, "input", prompt.slug);
    fs.mkdirSync(outputDir, { recursive: true });

    try {
      const files = await generateWithBrowser(prompt, outputDir);
      markDone(state, prompt.id, files);
      results.push({ prompt, status: "success", files });
    } catch (err) {
      markFailed(state, prompt.id, err.message);
      results.push({ prompt, status: "failed", error: err.message });
      logger.error(`Failed: ${err.message}`);
    }

    if (i < toProcess.length - 1) {
      logger.info(
        `Waiting ${config.delayBetweenPrompts / 1000}s before next prompt...`,
      );
      await new Promise((r) => setTimeout(r, config.delayBetweenPrompts));
    }
    logger.sep();
  }

  printSummary(results);

  const hasFailed = results.some((r) => r.status === "failed");

  // ── Auto-launch the pipeline if at least one track succeeded ─────────────
  const hasSuccess = results.some((r) => r.status === "success");
  if (hasSuccess && process.env.SKIP_PIPELINE !== "true") {
    logger.header("Launching pipeline.py --all");
    logger.info(`Working dir: ${PIPELINE_ROOT}`);
    try {
      execSync("python3 pipeline.py --all", {
        cwd: PIPELINE_ROOT,
        stdio: "inherit", // streams output directly to this terminal
      });
      logger.success("Pipeline completed.");
    } catch (err) {
      logger.error(
        `Pipeline exited with error (code ${err.status}). Check output above.`,
      );
    }
  } else if (!hasSuccess) {
    logger.warn("No tracks succeeded — skipping pipeline launch.");
  } else {
    logger.warn("SKIP_PIPELINE=true — pipeline not launched.");
  }

  process.exit(hasFailed ? 1 : 0);
}

main().catch((err) => {
  logger.error(`Crash: ${err.message}`);
  process.exit(1);
});
