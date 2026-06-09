#!/usr/bin/env python3
"""
build_stock_config.py — Construit today/config.json depuis le dossier stock/

Lit tous les <slug>.json dans stock/<slug>/ et les assemble en un fichier
today/config.json au format multi-tracks du pipeline.

Usage :
  python scripts/build_stock_config.py ./stock
  python scripts/build_stock_config.py ./stock --output today/config.json
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path


def build_config(stock_dir: str, output_path: str) -> dict:
    stock = Path(stock_dir)
    if not stock.is_dir():
        print(f"❌ Dossier stock introuvable : {stock_dir}", file=sys.stderr)
        sys.exit(1)

    tracks = []
    for slug_dir in sorted(stock.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        json_path = slug_dir / f"{slug}.json"

        if not json_path.exists():
            print(f"  ⚠️  {slug} — pas de JSON, ignoré (lance d'abord auto_json.py)")
            continue

        # Vérifie qu'il y a un fichier audio
        audio_files = (
            list(slug_dir.glob("*.mp3"))
            + list(slug_dir.glob("*.wav"))
            + list(slug_dir.glob("*.m4a"))
        )
        if not audio_files:
            print(f"  ⚠️  {slug} — pas d'audio, ignoré")
            continue

        with open(json_path, encoding="utf-8") as f:
            track = json.load(f)

        # Force le slug à correspondre au dossier
        track["slug"] = slug

        # input_folder laissé à "input" (défaut pipeline) —
        # le workflow CI copie MP3 + images dans input/<slug>/ avant d'appeler pipeline.py
        track.pop("input_folder", None)

        tracks.append(track)
        print(f"  ✅ {slug} — ajouté ({len(audio_files)} audio, scènes: {len(track.get('scenes', []))})")

    if not tracks:
        print("  (aucun track prêt dans le stock)")
        config = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": "Assirem Stock — aucun track",
            "tracks": [],
            "priority_slug": "",
        }
    else:
        config = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": "Assirem Stock — Pipeline automatique",
            "tracks": tracks,
            "priority_slug": tracks[0]["slug"],
        }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n  📄 {len(tracks)} track(s) → {output_path}")
    return config


def main():
    parser = argparse.ArgumentParser(description="Build today/config.json from stock/")
    parser.add_argument("stock_dir", help="Dossier stock (ex: ./stock)")
    parser.add_argument("--output", default="today/config.json", help="Chemin de sortie (défaut: today/config.json)")
    args = parser.parse_args()
    build_config(args.stock_dir, args.output)


if __name__ == "__main__":
    main()
