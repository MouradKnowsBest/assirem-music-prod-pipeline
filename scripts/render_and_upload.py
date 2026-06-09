#!/usr/bin/env python3
"""
Batch render + upload — headless, sequential.

Usage:
  # Auto-detect all output/{n}-{slug}/scenes/ folders that have images:
  python3 scripts/render_and_upload.py --auto

  # Specific slugs:
  python3 scripts/render_and_upload.py --slugs lofi-reggae-island-sunset-chill-2026 peru-andes-quechua-pacha-mama-2026

Options:
  --config    Week JSON config (default: today/week_2026-W22.json)
  --no-upload Skip YouTube upload (render only)
  --publish-now  Upload as public immediately (ignore scheduled_at)
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO   = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "output"
SCRIPT = REPO / "scripts" / "render_template.py"


def has_scenes(slug: str) -> bool:
    """True if the scenes folder has at least one image."""
    for d in OUTPUT.iterdir():
        if d.is_dir() and (d.name == slug or d.name.endswith(f"-{slug}")):
            scenes = d / "scenes"
            if scenes.is_dir():
                imgs = list(scenes.glob("*.jpg")) + list(scenes.glob("*.png")) + list(scenes.glob("*.webp"))
                return len(imgs) > 0
    return False


def already_rendered(slug: str) -> bool:
    """True if the final MP4 already exists."""
    for d in OUTPUT.iterdir():
        if d.is_dir() and (d.name == slug or d.name.endswith(f"-{slug}")):
            mp4 = d / f"{slug.replace('-', '_')}.mp4"
            return mp4.exists()
    return False


def auto_detect_slugs(config: Path) -> list:
    """Return slugs that have images but no MP4 yet, in config order."""
    import json
    if not config.exists():
        print(f"[batch] Config not found: {config}")
        return []
    tracks = json.loads(config.read_text()).get("tracks", [])
    result = []
    for t in tracks:
        slug = t["slug"]
        if has_scenes(slug) and not already_rendered(slug):
            result.append(slug)
    return result


def run(cmd: list, label: str) -> bool:
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    ret = subprocess.run(cmd)
    return ret.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Batch render + upload (headless)")
    ap.add_argument("--auto",        action="store_true",  help="Auto-detect slugs with images")
    ap.add_argument("--slugs",       nargs="+",            help="Explicit slug list")
    ap.add_argument("--config",      default="today/week_2026-W22.json")
    ap.add_argument("--no-upload",   action="store_true",  help="Render only, skip upload")
    ap.add_argument("--publish-now", action="store_true",  help="Upload public immediately")
    args = ap.parse_args()

    config = Path(args.config)

    if args.auto:
        slugs = auto_detect_slugs(config)
        if not slugs:
            print("[batch] No slugs found with images ready. Add images to output/{slug}/scenes/ first.")
            sys.exit(0)
        print(f"[batch] Auto-detected {len(slugs)} slug(s) ready:")
        for s in slugs:
            print(f"  • {s}")
    elif args.slugs:
        slugs = args.slugs
    else:
        ap.print_help()
        sys.exit(1)

    ok, failed = [], []

    for slug in slugs:
        print(f"\n{'═'*60}")
        print(f"  PROCESSING: {slug}")
        print(f"{'═'*60}")

        # ── Render ────────────────────────────────────────────────
        render_ok = run(
            [sys.executable, str(SCRIPT),
             "--slug", slug,
             "--config", str(config),
             "--headless"],
            f"Render: {slug}",
        )
        if not render_ok:
            print(f"  ❌ Render failed for {slug}, skipping upload.")
            failed.append(slug)
            continue

        # ── Upload ────────────────────────────────────────────────
        if not args.no_upload:
            upload_cmd = [
                sys.executable, str(REPO / "pipeline.py"),
                "--slug", slug,
                "--config", str(config),
                "--skip-visual", "--skip-video",
            ]
            if args.publish_now:
                upload_cmd.append("--publish-now")

            upload_ok = run(upload_cmd, f"Upload: {slug}")
            if not upload_ok:
                print(f"  ❌ Upload failed for {slug}")
                failed.append(slug)
                continue

        ok.append(slug)

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  BATCH DONE — {len(ok)} ok, {len(failed)} failed")
    for s in ok:
        print(f"  ✅ {s}")
    for s in failed:
        print(f"  ❌ {s}")


if __name__ == "__main__":
    main()
