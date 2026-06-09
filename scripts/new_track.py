"""
Helper script to set up a new track manually (no Leonardo API).

Usage:
  python scripts/new_track.py <slug>

What it does:
  1. Creates input/<slug>/           → drop your MP3 here
  2. Creates output/<slug>/scenes/   → drop your photos here (any format)
  3. Runs: python scripts/new_track.py <slug> --prep-photos
           to rename & convert photos → scene_001.png, scene_002.png ...

Then run the pipeline:
  python pipeline.py --slug <slug> --skip-visual --ken-burns --pingpong

Examples:
  python scripts/new_track.py reggae-sunset-vibes-2026
  python scripts/new_track.py reggae-sunset-vibes-2026 --prep-photos
"""

import os
import sys
import shutil
import glob
from pathlib import Path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup(slug: str):
    input_dir  = os.path.join(BASE, "input", slug)
    scenes_dir = os.path.join(BASE, "output", slug, "scenes")
    clips_kb   = os.path.join(BASE, "output", slug, "clips_kb")

    os.makedirs(input_dir,  exist_ok=True)
    os.makedirs(scenes_dir, exist_ok=True)
    os.makedirs(clips_kb,   exist_ok=True)

    print(f"✅ Folders created for '{slug}':")
    print(f"   → Drop your MP3(s) in:  input/{slug}/")
    print(f"   → Drop your photos in:  output/{slug}/scenes/")
    print(f"")
    print(f"Once photos are in place, run:")
    print(f"   python scripts/new_track.py {slug} --prep-photos")
    print(f"")
    print(f"Then build the video:")
    print(f"   python pipeline.py --slug {slug} --skip-visual --ken-burns --pingpong --skip-upload")


def prep_photos(slug: str):
    scenes_dir = os.path.join(BASE, "output", slug, "scenes")

    if not os.path.isdir(scenes_dir):
        print(f"ERROR: {scenes_dir} does not exist. Run setup first.")
        sys.exit(1)

    # Collect all image files that are not already named scene_NNN.png
    EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".heic", ".heif")
    all_images = sorted([
        f for f in glob.glob(os.path.join(scenes_dir, "*"))
        if Path(f).suffix.lower() in EXTS
        and not os.path.basename(f).startswith("scene_")
    ])

    if not all_images:
        # Check if scene_*.png already exist
        existing = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
        if existing:
            print(f"✅ {len(existing)} scene image(s) already ready:")
            for f in existing:
                print(f"   {os.path.basename(f)}")
        else:
            print(f"⚠️  No photos found in {scenes_dir}")
            print(f"   Drop your photos there (jpg/png/webp) then re-run with --prep-photos")
        return

    print(f"Found {len(all_images)} photo(s) to prepare...")

    try:
        from PIL import Image
    except ImportError:
        print("Installing Pillow...")
        os.system(f"{sys.executable} -m pip install pillow -q")
        from PIL import Image

    converted = []
    for i, src in enumerate(all_images, 1):
        dst = os.path.join(scenes_dir, f"scene_{i:03d}.png")
        ext = Path(src).suffix.lower()

        if ext == ".png" and src != dst:
            # Just rename if already PNG
            shutil.move(src, dst)
            print(f"   {os.path.basename(src)} → scene_{i:03d}.png")
        else:
            # Convert to PNG and resize to 1536×864 if needed
            img = Image.open(src).convert("RGB")
            w, h = img.size
            target_w, target_h = 1536, 864

            # Crop to 16:9 if not already
            if abs(w / h - 16 / 9) > 0.05:
                target_ratio = 16 / 9
                if w / h > target_ratio:
                    new_w = int(h * target_ratio)
                    offset = (w - new_w) // 2
                    img = img.crop((offset, 0, offset + new_w, h))
                else:
                    new_h = int(w / target_ratio)
                    offset = (h - new_h) // 2
                    img = img.crop((0, offset, w, offset + new_h))

            img = img.resize((target_w, target_h), Image.LANCZOS)
            img.save(dst, "PNG")
            if src != dst:
                os.remove(src)
            print(f"   {os.path.basename(src)} → scene_{i:03d}.png (resized to 1536×864)")

        converted.append(dst)

    print(f"\n✅ {len(converted)} photo(s) ready as scene_*.png")
    print(f"\nNow build the video:")
    print(f"   python pipeline.py --slug {slug} --skip-visual --ken-burns --pingpong --skip-upload")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    prep = "--prep-photos" in args
    slug = " ".join(a for a in args if not a.startswith("--")).strip()

    if not slug:
        print("ERROR: no slug provided.")
        sys.exit(1)

    if prep:
        prep_photos(slug)
    else:
        setup(slug)


if __name__ == "__main__":
    main()
