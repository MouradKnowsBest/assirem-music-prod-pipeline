# Suno Automation

Playwright script that automates Suno to generate music from prompts and download the tracks directly into the pipeline's `input/{slug}/` folders.

## Architecture

```
suno-automation/
├── prompts.json          ← your prompts (mapped to pipeline slugs)
├── processed.json        ← auto-generated, tracks what's done (do not edit)
├── .browser-profile/     ← auto-generated, saves your Suno session
├── screenshots/          ← failure screenshots (auto-generated)
└── src/
    ├── config.js         ← ALL configuration (timeouts, paths, flags)
    ├── selectors.js      ← ALL Suno UI selectors (edit here if UI breaks)
    ├── logger.js         ← colored terminal output
    ├── browser.js        ← persistent browser context setup
    ├── suno.js           ← core automation (navigate, fill, generate, download)
    ├── downloader.js     ← file saving with clean filenames
    ├── state.js          ← processed.json read/write (idempotency)
    ├── login.js          ← `npm run login`
    └── main.js           ← `npm run generate`
```

## Install

```bash
cd suno-automation
npm install
npx playwright install chromium
```

## Usage

### Step 1 — Login once

```bash
npm run login
```

A browser window opens. Log in with Google or Discord. The session is saved to `.browser-profile/` automatically. You will **not** need to do this again unless Suno logs you out.

### Step 2 — Generate tracks

```bash
npm run generate
```

Processes all prompts in `prompts.json` in sequence, downloads the tracks into `../input/{slug}/`, and marks each as done in `processed.json`.

**Resume-safe**: if the script is interrupted, re-running it will skip already-completed prompts.

### Force re-download everything

```bash
npm run generate:force
# or: FORCE=true npm run generate
```

### Run headless (no visible browser)

```bash
npm run generate:headless
# or: HEADLESS=true npm run generate
```

## prompts.json format

```json
[
  {
    "id": "001",
    "slug": "lofi",
    "title": "My Track Title",
    "prompt": "Lofi hip hop, 80 BPM, piano and vinyl crackle..."
  }
]
```

- `id`: unique identifier used in filenames and processed.json
- `slug`: maps to `../input/{slug}/` in the pipeline (must match pipeline config)
- `title`: human-readable name (used in filenames)
- `prompt`: the text sent to Suno's Create field

## Output filenames

```
../input/lofi/001_lofi-hip-hop-late-night-study_1.mp3
../input/lofi/001_lofi-hip-hop-late-night-study_2.mp3
```

## Environment variables

| Variable             | Default             | Description                            |
|----------------------|---------------------|----------------------------------------|
| `HEADLESS`           | `false`             | Run without visible browser            |
| `FORCE`              | `false`             | Reprocess already-done prompts         |
| `PROMPTS_FILE`       | `./prompts.json`    | Path to input prompts file             |
| `OUTPUT_DIR`         | `../input`          | Root output directory                  |
| `TRACKS_PER_PROMPT`  | `2`                 | How many tracks to download per prompt |
| `GENERATION_TIMEOUT` | `240000`            | Max ms to wait for generation (4 min)  |
| `MAX_RETRIES`        | `3`                 | Retries per prompt on failure          |
| `DELAY_BETWEEN`      | `5000`              | Ms pause between prompts               |
| `DEBUG`              | unset               | Set to any value for verbose logs      |
| `HTML_DUMP`          | `false`             | Save HTML on failure for debugging     |

## If the script breaks

Suno is a React SPA — their UI can change without notice. When it breaks:

1. Open `src/selectors.js`
2. Update the selectors for the broken step
4. All selectors are grouped by function with clear TODO comments

Most likely breakage points (see also: Potential Fragility section below):
- Prompt textarea selector
- Create button selector
- Song menu "..." button selector
- "Download" menu item selector

## Potential fragility points

1. **`SELECTORS.promptTextarea`** — Suno may change the textarea's placeholder or add a mode toggle before it's accessible. Most likely to break after UI redesigns.

2. **`SELECTORS.createButton`** — The button text or test ID may change. Also may become temporarily disabled due to rate limiting or credits.

3. **`SELECTORS.songMenuButton`** — The "..." kebab menu on each song card. Suno redesigns cards frequently. This is the #1 most fragile selector.

4. **`SELECTORS.downloadMenuItem`** — The "Download" option in the dropdown. May be renamed, moved behind a submenu, or require a subscription tier.

5. **API feed interception** — `suno.js` intercepts `/api/feed` responses to detect generation completion. If Suno changes this endpoint or encrypts responses, the fallback DOM polling takes over. Both may need updating.

6. **Session expiry** — Suno sessions expire. If `npm run generate` says "not logged in", run `npm run login` again.

7. **Rate limiting** — Suno may throttle rapid generation. Increase `DELAY_BETWEEN` if you hit 429 errors.

8. **Credits** — If your Suno account runs out of credits, the Create button will be disabled. The script detects this and throws a clear error.

## Future improvements

- **Cloud sync**: output to a watched Dropbox/S3 folder instead of local disk
- **Folder watcher**: auto-trigger the pipeline when new MP3s appear in input/
- **FFmpeg post-processing**: normalize audio levels, add fade in/out
- **Metadata sidecar**: export a `{id}.json` alongside each MP3 with prompt metadata
- **Parallel generation**: open multiple Suno tabs simultaneously (risky for rate limits)
- **CSV input**: `prompts.csv` support in addition to JSON
- **Discord/Slack notifications**: alert when a run completes or fails
