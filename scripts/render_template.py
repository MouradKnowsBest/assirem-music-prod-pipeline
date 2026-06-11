#!/usr/bin/env python3
"""Render an Assirem Music track using the HTML template → CDP screencast → ffmpeg MP4.

Capture method: Chrome DevTools Protocol Page.screencastFrame
  - frames captured directly from the GPU compositor at render time
  - JPEG quality 92, 1920×1080, up to 30fps
  - zero re-encoding artifacts vs record_video_dir (VP8 @ 600kbps)
"""

import argparse
import base64
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright not installed — run: pip install playwright && playwright install chromium")

REPO = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO / "input"
OUTPUT_DIR = REPO / "output"
TEMPLATE       = REPO / "assets" / "template.html"
TEMPLATE_SHORT = REPO / "assets" / "template_short.html"

CAPTURE_FPS   = 30   # target fps sent to CDP (browser may deliver fewer)
EVERY_N_FRAME = 1    # everyNthFrame=1 → all frames; 2 → half
JPEG_QUALITY  = 92   # CDP screencast JPEG quality


# ── helpers ──────────────────────────────────────────────────────────────────

def find_input_folder(slug: str) -> Path:
    exact = INPUT_DIR / slug
    if exact.is_dir():
        return exact
    for d in sorted(INPUT_DIR.iterdir()):
        if d.is_dir() and d.name.endswith(f"-{slug}"):
            return d
    raise FileNotFoundError(f"No input folder found for slug '{slug}'")


def get_duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True,
    )
    return float(out.strip())


def prepare_audio(folder: Path, tmp_dir: Path) -> Path:
    """Return a single MP3: either the only file, or all files concatenated."""
    mp3s = sorted(folder.glob("*.mp3"), key=lambda p: p.name)
    if not mp3s:
        raise FileNotFoundError(f"No MP3 in {folder}")
    if len(mp3s) == 1:
        print(f"  MP3      : {mp3s[0].name}")
        return mp3s[0]

    # Concatenate all MP3s in alphabetical order
    concat_list = tmp_dir / "_concat.txt"
    merged = tmp_dir / "_merged.mp3"
    # Use filter_complex concat — handles any filename (apostrophes, spaces, accents)
    inputs = []
    for p in mp3s:
        inputs += ["-i", str(p)]
    n = len(mp3s)
    filter_chain = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    subprocess.run(
        ["ffmpeg", "-y", *inputs,
         "-filter_complex", filter_chain, "-map", "[out]",
         "-acodec", "libmp3lame", "-q:a", "2", str(merged)],
        check=True, capture_output=True,
    )
    names = " + ".join(p.name for p in mp3s)
    print(f"  MP3      : {names}  (merged)")
    return merged


def find_output_folder(slug: str) -> Path:
    exact = OUTPUT_DIR / slug
    if exact.is_dir():
        return exact
    # Handle {nn}-{slug} prefix (mirrors input folder convention)
    for d in sorted(OUTPUT_DIR.iterdir()):
        if d.is_dir() and d.name.endswith(f"-{slug}"):
            return d
    raise FileNotFoundError(f"No output folder found for slug '{slug}'")


def find_scenes(slug: str) -> list:
    folder = find_output_folder(slug)
    scenes_dir = folder / "scenes"
    if not scenes_dir.is_dir():
        raise FileNotFoundError(f"Scenes dir not found: {scenes_dir}")
    imgs = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        imgs += scenes_dir.glob(ext)
    imgs = sorted(set(imgs))
    if not imgs:
        raise FileNotFoundError(
            f"No images found in {scenes_dir}\n"
            f"  → Put your Leonardo images there (any name, .png/.jpg/.webp)"
        )
    return [f"file://{img.resolve()}" for img in imgs]


def load_track_meta(slug: str, config: Path) -> dict:
    if not config or not config.exists():
        return {}
    data = json.loads(config.read_text())
    for t in data.get("tracks", []):
        if t.get("slug") == slug:
            return t
    return {}


# ── main render ──────────────────────────────────────────────────────────────

def render(slug: str, config: Path, out_path: Path | None = None, headless: bool = True, short: bool = False) -> Path:
    input_folder = find_input_folder(slug)

    template = TEMPLATE_SHORT if short else TEMPLATE
    if not template.exists():
        raise FileNotFoundError(f"Template not found: {template}")

    if out_path is None:
        base = find_output_folder(slug)
        if short:
            out_path = base / "shorts" / f"{slug.replace('-', '_')}_short.mp4"
        else:
            out_path = base / f"{slug.replace('-', '_')}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    viewport_w, viewport_h = (1080, 1920) if short else (1920, 1080)

    tmp = out_path.parent / ".tmp_render"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    frames_dir = tmp / "frames"
    frames_dir.mkdir()

    mp3 = prepare_audio(input_folder, tmp)
    duration = get_duration(mp3)
    scenes = find_scenes(slug)
    meta = load_track_meta(slug, config)

    clean_slug = slug.removesuffix(".json")
    suno_title = meta.get("suno_title", clean_slug.replace("-", " ").title())
    short_title = suno_title.split(" — ")[0].strip() if " — " in suno_title else suno_title
    slide_dur_ms = max(3000, int(duration * 1000 / len(scenes)))

    print(f"\n[render_template] {slug}{'  [SHORT 9:16]' if short else ''}")
    print(f"  Duration : {duration:.1f}s")
    print(f"  Scenes   : {len(scenes)} × {slide_dur_ms}ms")
    print(f"  Output   : {out_path}")
    print(f"  Viewport : {viewport_w}×{viewport_h}")
    print(f"  Mode     : {'headless' if headless else 'headed'}")
    print(f"  Capture  : CDP screencast JPEG {JPEG_QUALITY}q @ up to {CAPTURE_FPS}fps")

    # ── Screencast state (shared with CDP event thread) ───────────────────
    captured: list[tuple[float, bytes]] = []   # (timestamp_s, jpeg_bytes)
    lock = threading.Lock()
    cdp_client: dict = {}   # mutable box so the closure can reference it

    def on_frame(params):
        ts = params.get("metadata", {}).get("timestamp", time.time())
        jpeg = base64.b64decode(params["data"])
        with lock:
            captured.append((ts, jpeg))
        try:
            cdp_client["ref"].send(
                "Page.screencastFrameAck", {"sessionId": params["sessionId"]}
            )
        except Exception:
            pass

    # ── Playwright session ────────────────────────────────────────────────
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
                "--allow-file-access-from-files",
                "--force-device-scale-factor=1",
            ],
        )
        ctx = browser.new_context(
            viewport={"width": viewport_w, "height": viewport_h},
            device_scale_factor=1,
        )
        page = ctx.new_page()

        # Attach CDP session BEFORE navigation
        client = ctx.new_cdp_session(page)
        cdp_client["ref"] = client
        client.on("Page.screencastFrame", on_frame)

        page.goto(f"file://{template.resolve()}", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        page.evaluate(
            "cfg => window.AssiremMontage.configure(cfg)",
            {
                "photos":     scenes,
                "audioSrc":   f"file://{mp3.resolve()}",
                "title":      short_title,
                "artist":     "Assirem Music PROD",
                "brand":      "Assirem Music",
                "brandSub":   "Music PROD",
                "slideDurMs": slide_dur_ms,
            },
        )
        page.evaluate("() => window.AssiremMontage.start()")

        # Wait for the first real frame to be painted before starting capture
        page.wait_for_timeout(400)
        client.send("Page.startScreencast", {
            "format":       "jpeg",
            "quality":      JPEG_QUALITY,
            "maxWidth":     viewport_w,
            "maxHeight":    viewport_h,
            "everyNthFrame": EVERY_N_FRAME,
        })

        print(f"  Recording… ({duration:.0f}s)")
        if headless:
            # In headless mode audio doesn't play — just wait the exact duration.
            # Polling via page.evaluate() while CDP streams 30fps freezes Chromium
            # (each evaluate round-trip stalls behind the frame queue → 10× slowdown).
            page.wait_for_timeout(int(duration * 1000) + 300)
            with lock:
                n = len(captured)
            print(f"  Done — {n} frames captured.")
        else:
            # Headed mode: audio plays → poll for the ended signal
            deadline = time.time() + duration + 25
            while time.time() < deadline:
                done = page.evaluate("() => Boolean(window.__assiremDone)")
                if done:
                    with lock:
                        n = len(captured)
                    print(f"  Audio ended — {n} frames captured.")
                    break
                page.wait_for_timeout(500)
            else:
                with lock:
                    n = len(captured)
                print(f"  WARNING: timed out. {n} frames captured.")

        page.wait_for_timeout(400)   # let last frames drain
        client.send("Page.stopScreencast")
        page.wait_for_timeout(200)
        ctx.close()
        browser.close()

    # ── Save frames to disk ───────────────────────────────────────────────
    with lock:
        snapshot = list(captured)

    if not snapshot:
        sys.exit("ERROR: no frames captured via CDP screencast")

    print(f"  Saving {len(snapshot)} frames to disk…")
    for i, (_, jpeg) in enumerate(snapshot):
        (frames_dir / f"frame_{i:06d}.jpg").write_bytes(jpeg)

    # fps that makes video duration == audio duration
    fps_for_ffmpeg = len(snapshot) / duration
    print(f"  Assembling at {fps_for_ffmpeg:.3f}fps ({len(snapshot)} frames / {duration:.1f}s)")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", f"{fps_for_ffmpeg:.6f}",
            "-i", str(frames_dir / "frame_%06d.jpg"),
            "-i", str(mp3),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(out_path),
        ],
        check=True,
    )

    shutil.rmtree(tmp, ignore_errors=True)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"  Done → {out_path}  ({size_mb:.1f} MB)\n")
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Render HTML template to MP4 (CDP screencast)")
    ap.add_argument("--slug",     required=True,                            help="Track slug")
    ap.add_argument("--config",   default=None,                             help="Week config JSON (auto-detected if omitted)")
    ap.add_argument("--output",   default=None,                             help="Override output MP4 path")
    ap.add_argument("--short",    action="store_true",
                    help="Render YouTube Short (portrait 1080×1920, template_short.html)")
    ap.add_argument("--no-headless", action="store_true", dest="no_headless",
                    help="Run Chromium headed (debug only — default is headless)")
    args = ap.parse_args()

    render(
        args.slug,
        Path(args.config) if args.config else None,
        Path(args.output) if args.output else None,
        headless=not args.no_headless,
        short=args.short,
    )


if __name__ == "__main__":
    main()
