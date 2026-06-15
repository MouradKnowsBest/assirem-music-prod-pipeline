#!/usr/bin/env python3
"""
render_lyrics.py — Render a track with synchronized lyrics display.

Reads lyrics automatically from the MP3 ID3 USLT tag and distributes them
evenly across the track duration. Uses template_lyrics.html (same cinematic
gold/dark aesthetic, 5-line teleprompter display).

Usage:
  python scripts/render_lyrics.py --input "/path/to/folder"
  python scripts/render_lyrics.py --input "/path/to/folder" --output "out.mp4"
  python scripts/render_lyrics.py --input "/path/to/folder" --lyrics "lyrics.txt"
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

REPO          = Path(__file__).resolve().parent.parent
TEMPLATE      = REPO / "assets" / "template_lyrics.html"
CAPTURE_FPS   = 30
EVERY_N_FRAME = 1
JPEG_QUALITY  = 92


# ── Audio helpers ─────────────────────────────────────────────────────────────

def find_mp3(folder: Path) -> Path:
    mp3s = sorted(folder.glob("*.mp3"))
    if not mp3s:
        raise FileNotFoundError(f"No MP3 found in {folder}")
    if len(mp3s) > 1:
        print(f"  Warning: multiple MP3s found, using first: {mp3s[0].name}")
    return mp3s[0]


def get_duration(mp3: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)],
        text=True,
    )
    return float(out.strip())


def read_lyrics_from_id3(mp3: Path) -> str:
    """Extract USLT (unsynchronized lyrics) from MP3 ID3 tags."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(mp3)
        for key, val in tags.items():
            if key.startswith("USLT"):
                return val.text.strip()
        return ""
    except ImportError:
        print("  Warning: mutagen not installed (pip install mutagen) — no lyrics from ID3")
        return ""
    except Exception as e:
        print(f"  Warning: could not read ID3 lyrics: {e}")
        return ""


def find_images(folder: Path) -> list[str]:
    imgs = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        imgs += sorted(folder.glob(ext))
    return [f"file://{img.resolve()}" for img in imgs]


def get_title_from_folder(folder: Path) -> str:
    return folder.name


# ── Render ────────────────────────────────────────────────────────────────────

def render(
    input_folder: Path,
    output: Path,
    lyrics_override: str | None = None,
    headless: bool = True,
) -> Path:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE}")

    mp3      = find_mp3(input_folder)
    duration = get_duration(mp3)
    images   = find_images(input_folder)
    lyrics   = lyrics_override if lyrics_override is not None else read_lyrics_from_id3(mp3)

    if not images:
        raise FileNotFoundError(
            f"No images found in {input_folder}\n"
            "  → Add .png/.jpg/.webp images alongside the MP3"
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    title        = get_title_from_folder(input_folder)
    slide_dur_ms = max(5000, int(duration * 1000 / len(images)))

    print(f"\n[render_lyrics] {input_folder.name}")
    print(f"  MP3      : {mp3.name}")
    print(f"  Duration : {duration:.1f}s")
    print(f"  Images   : {len(images)}")
    print(f"  Lyrics   : {'yes (' + str(len(lyrics.splitlines())) + ' lines)' if lyrics else 'none'}")
    print(f"  Output   : {output}")
    print(f"  Mode     : {'headless' if headless else 'headed'}")

    # ── CDP screencast state ──────────────────────────────────────────────
    captured: list[tuple[float, bytes]] = []
    lock = threading.Lock()
    cdp_box: dict = {}

    def on_frame(params):
        ts   = params.get("metadata", {}).get("timestamp", time.time())
        jpeg = base64.b64decode(params["data"])
        with lock:
            captured.append((ts, jpeg))
        try:
            cdp_box["ref"].send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:
            pass

    # ── Playwright session ────────────────────────────────────────────────
    tmp        = output.parent / ".tmp_lyrics_render"
    frames_dir = tmp / "frames"
    if tmp.exists():
        shutil.rmtree(tmp)
    frames_dir.mkdir(parents=True)

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
        ctx  = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page = ctx.new_page()

        client = ctx.new_cdp_session(page)
        cdp_box["ref"] = client
        client.on("Page.screencastFrame", on_frame)

        page.goto(f"file://{TEMPLATE.resolve()}", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        page.evaluate(
            "cfg => window.AssiremMontage.configure(cfg)",
            {
                "photos":     images,
                "audioSrc":   f"file://{mp3.resolve()}",
                "title":      title,
                "artist":     "Assirem Music PROD",
                "brand":      "Assirem Music",
                "brandSub":   "Music PROD",
                "slideDurMs": slide_dur_ms,
                "duration":   duration,
                "lyrics":     lyrics,
            },
        )
        page.evaluate("() => window.AssiremMontage.start()")
        page.wait_for_timeout(400)

        client.send("Page.startScreencast", {
            "format":        "jpeg",
            "quality":       JPEG_QUALITY,
            "maxWidth":      1920,
            "maxHeight":     1080,
            "everyNthFrame": EVERY_N_FRAME,
        })

        print(f"  Recording… ({duration:.0f}s)")
        if headless:
            page.wait_for_timeout(int(duration * 1000) + 500)
            with lock:
                n = len(captured)
            print(f"  Done — {n} frames captured.")
        else:
            deadline = time.time() + duration + 30
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
                print(f"  Warning: timed out — {n} frames captured.")

        page.wait_for_timeout(400)
        client.send("Page.stopScreencast")
        page.wait_for_timeout(200)
        ctx.close()
        browser.close()

    # ── Save frames ───────────────────────────────────────────────────────
    with lock:
        snapshot = list(captured)

    if not snapshot:
        sys.exit("ERROR: no frames captured")

    print(f"  Saving {len(snapshot)} frames…")
    for i, (_, jpeg) in enumerate(snapshot):
        (frames_dir / f"frame_{i:06d}.jpg").write_bytes(jpeg)

    fps = len(snapshot) / duration
    print(f"  Assembling at {fps:.3f}fps ({len(snapshot)} frames / {duration:.1f}s)")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", f"{fps:.6f}",
            "-i", str(frames_dir / "frame_%06d.jpg"),
            "-i", str(mp3),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(output),
        ],
        check=True,
    )

    shutil.rmtree(tmp, ignore_errors=True)
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"  Done → {output}  ({size_mb:.1f} MB)\n")
    return output


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Render track with lyrics display (template_lyrics.html)")
    ap.add_argument("--input",      required=True,
                    help="Folder containing MP3 + image(s)")
    ap.add_argument("--output",     default=None,
                    help="Output MP4 path (default: <input-folder>/<slug>.mp4)")
    ap.add_argument("--lyrics",     default=None,
                    help="Plain-text lyrics file (overrides ID3 USLT tag)")
    ap.add_argument("--no-headless", action="store_true", dest="no_headless",
                    help="Run Chromium headed (debug)")
    args = ap.parse_args()

    input_folder = Path(args.input).resolve()
    if not input_folder.is_dir():
        sys.exit(f"Input folder not found: {input_folder}")

    if args.output:
        output = Path(args.output).resolve()
    else:
        slug   = input_folder.name.lower().replace(" ", "_").replace("-", "_")
        output = input_folder / f"{slug}_lyrics.mp4"

    lyrics_override = None
    if args.lyrics:
        lp = Path(args.lyrics)
        if not lp.exists():
            sys.exit(f"Lyrics file not found: {lp}")
        lyrics_override = lp.read_text(encoding="utf-8")

    render(
        input_folder=input_folder,
        output=output,
        lyrics_override=lyrics_override,
        headless=not args.no_headless,
    )


if __name__ == "__main__":
    main()
