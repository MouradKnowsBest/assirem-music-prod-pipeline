#!/usr/bin/env python3
"""
pipeline.py - Orchestrateur principal du pipeline Assirem Music PROD

Usage :
    python pipeline.py                # Pipeline complet
    python pipeline.py --force        # Écrase tous les fichiers déjà générés
    python pipeline.py --skip-visual  # Saute image + clips Leonardo AI
    python pipeline.py --skip-video   # Saute l'assemblage FFmpeg
    python pipeline.py --skip-upload  # Saute l'upload YouTube
    python pipeline.py --debug        # Affiche les stack traces complets
"""

import os
import sys
import json
import glob
import time
import argparse
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from modules.visual  import generer_visuel
from modules.video   import generer_videos
from modules.youtube import uploader_videos

# ─── Couleurs terminal ────────────────────────────────────────────────────────
VERT  = "\033[92m"
ROUGE = "\033[91m"
JAUNE = "\033[93m"
CYAN  = "\033[96m"
GRAS  = "\033[1m"
RESET = "\033[0m"


def titre_etape(n, total, texte):
    print(f"\n{GRAS}{CYAN}{'─' * 60}{RESET}")
    print(f"{GRAS}{CYAN}  ÉTAPE {n}/{total} — {texte}{RESET}")
    print(f"{GRAS}{CYAN}{'─' * 60}{RESET}")

def succes(msg):   print(f"{VERT}{GRAS}  ✅ {msg}{RESET}")
def erreur(msg):   print(f"{ROUGE}{GRAS}  ❌ {msg}{RESET}")
def warning(msg):  print(f"{JAUNE}  ⚠️  {msg}{RESET}")
def info(msg):     print(f"  {msg}")


# ─── Config ───────────────────────────────────────────────────────────────────

def charger_config() -> dict:
    path = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"config.json introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for champ in ["mode", "title", "output_folder", "input_folder"]:
        if champ not in cfg:
            raise ValueError(f"Champ obligatoire manquant dans config.json : '{champ}'")
    if cfg["mode"] not in ("short", "medium", "long", "individual"):
        raise ValueError(f"Mode invalide : '{cfg['mode']}'")
    return cfg


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",        action="store_true")
    parser.add_argument("--skip-visual",  action="store_true")
    parser.add_argument("--skip-video",   action="store_true")
    parser.add_argument("--skip-upload",  action="store_true")
    parser.add_argument("--debug",        action="store_true")
    args = parser.parse_args()

    print(f"\n{GRAS}{'═' * 60}{RESET}")
    print(f"{GRAS}  🎵  ASSIREM MUSIC PROD — Pipeline d'automatisation  🎵{RESET}")
    print(f"{GRAS}{'═' * 60}{RESET}")

    try:
        config = charger_config()
    except Exception as e:
        erreur(f"Erreur config : {e}")
        sys.exit(1)

    print(f"  Mode     : {GRAS}{config['mode']}{RESET}")
    print(f"  Titre    : {config['title']}")
    print(f"  Clips    : {config.get('nb_clips', 6)} clips Motion × {config.get('motion_strength', 5)} force")
    print(f"  Playlist : {config.get('playlist_name', '—')}")
    if args.force:
        warning("--force activé : les fichiers existants seront écrasés.")

    total = sum([not args.skip_visual, not args.skip_video, not args.skip_upload])
    etape = 0
    debut = time.time()
    videos = []

    # ── ÉTAPE 1 : Image + Clips Motion (Leonardo AI) ──────────────────────────
    if not args.skip_visual:
        etape += 1
        titre_etape(etape, total, "Génération image + clips vidéo (Leonardo AI)")
        t0 = time.time()
        try:
            clips = generer_visuel(config, BASE_DIR, force=args.force)
            succes(f"{len(clips)} clip(s) générés en {time.time() - t0:.1f}s")
        except Exception as e:
            erreur(f"Échec génération visuelle : {e}")
            if args.debug:
                traceback.print_exc()
            sys.exit(1)
    else:
        warning("Génération visuelle ignorée (--skip-visual)")

    # ── ÉTAPE 2 : Assemblage MP4 (FFmpeg) ─────────────────────────────────────
    if not args.skip_video:
        etape += 1
        titre_etape(etape, total, "Assemblage vidéo MP4 (FFmpeg)")
        t0 = time.time()
        try:
            videos = generer_videos(config, BASE_DIR, force=args.force)
            succes(f"{len(videos)} vidéo(s) assemblée(s) en {time.time() - t0:.1f}s")
            for v in videos:
                info(f"📹 {v}")
        except Exception as e:
            erreur(f"Échec assemblage vidéo : {e}")
            if args.debug:
                traceback.print_exc()
            sys.exit(1)
    else:
        warning("Assemblage vidéo ignoré (--skip-video)")
        output_dir = os.path.join(BASE_DIR, config["output_folder"])
        videos = [f for f in glob.glob(os.path.join(output_dir, "*.mp4"))
                  if not os.path.basename(f).startswith("_")]
        if videos:
            info(f"{len(videos)} vidéo(s) trouvée(s) dans output/")
        else:
            warning("Aucune vidéo MP4 dans output/ — upload impossible.")

    # ── ÉTAPE 3 : Upload YouTube ───────────────────────────────────────────────
    if not args.skip_upload:
        if not videos:
            erreur("Aucune vidéo à uploader.")
            sys.exit(1)
        etape += 1
        titre_etape(etape, total, "Upload YouTube")
        t0 = time.time()
        try:
            uploader_videos(config, videos, BASE_DIR)
            succes(f"Upload terminé en {time.time() - t0:.1f}s")
        except Exception as e:
            erreur(f"Échec upload YouTube : {e}")
            if args.debug:
                traceback.print_exc()
            sys.exit(1)
    else:
        warning("Upload YouTube ignoré (--skip-upload)")

    # ── Résumé ─────────────────────────────────────────────────────────────────
    print(f"\n{GRAS}{'═' * 60}{RESET}")
    print(f"{VERT}{GRAS}  🎉 Pipeline terminé en {time.time() - debut:.1f}s !{RESET}")
    print(f"{GRAS}{'═' * 60}{RESET}\n")


if __name__ == "__main__":
    main()
