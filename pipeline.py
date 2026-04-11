#!/usr/bin/env python3
"""
pipeline.py — Orchestrateur Assirem Music PROD

Lecture du config :
  1. today/config.json  (format multi-tracks généré par la tâche planifiée)
  2. config.json        (format legacy single-track, fallback)

Usage :
  python3 pipeline.py                    # lance le track prioritaire
  python3 pipeline.py --slug lofi        # lance un track spécifique
  python3 pipeline.py --all              # lance tous les tracks
  python3 pipeline.py --list             # liste les tracks disponibles
  python3 pipeline.py --force            # écrase les fichiers existants
  python3 pipeline.py --skip-visual      # saute Leonardo AI
  python3 pipeline.py --skip-video       # saute FFmpeg
  python3 pipeline.py --skip-upload      # saute YouTube
  python3 pipeline.py --debug            # stack traces complets
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

from modules.video   import generer_videos
from modules.youtube import uploader_videos, UploadLimitExceeded, get_upload_count_today
from modules.distribution import valider_distribution, distribuer_track
from modules.distribution import valider_distribution, distribuer_track

# ─── Couleurs ────────────────────────────────────────────────────────────────
VERT  = "\033[92m"; ROUGE = "\033[91m"; JAUNE = "\033[93m"
CYAN  = "\033[96m"; GRAS  = "\033[1m";  RESET = "\033[0m"
MAGENTA = "\033[95m"

def _sep(char="─", n=60): return char * n
def titre_etape(n, total, texte):
    print(f"\n{GRAS}{CYAN}{_sep()}{RESET}")
    print(f"{GRAS}{CYAN}  ÉTAPE {n}/{total} — {texte}{RESET}")
    print(f"{GRAS}{CYAN}{_sep()}{RESET}")
def titre_track(slug, i, total, priority=False):
    badge = f" {JAUNE}★ PRIORITAIRE{RESET}" if priority else ""
    print(f"\n{GRAS}{MAGENTA}{_sep('═')}{RESET}")
    print(f"{GRAS}{MAGENTA}  TRACK {i}/{total} — {slug.upper()}{badge}{RESET}")
    print(f"{GRAS}{MAGENTA}{_sep('═')}{RESET}")
def succes(msg):  print(f"{VERT}{GRAS}  ✅ {msg}{RESET}")
def erreur(msg):  print(f"{ROUGE}{GRAS}  ❌ {msg}{RESET}")
def warning(msg): print(f"{JAUNE}  ⚠️  {msg}{RESET}")
def info(msg):    print(f"  {msg}")


# ─── Chargement config ────────────────────────────────────────────────────────

def _normaliser_track_legacy(cfg: dict) -> dict:
    """Convertit l'ancien format config.json en format track unifié."""
    return {
        "slug": "main",
        "priority": 1,
        "suno_prompt": "",
        "mode":          cfg.get("mode", "medium"),
        "title":         cfg.get("title", "Assirem Music"),
        "description":   cfg.get("description", ""),
        "tags":          cfg.get("tags", []),
        "playlist_name": cfg.get("playlist_name", "Assirem Music"),
        "leonardo_model":cfg.get("leonardo_model", "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"),
        "input_folder":  cfg.get("input_folder", "input"),
        "scenes": [
            {
                "prompt": cfg.get("visual_prompt", "abstract music background"),
                "motion_strength": cfg.get("motion_strength", 5),
            }
        ] * cfg.get("nb_clips", 6),
    }


def charger_tracks(config_path: str = None) -> tuple:
    """
    Retourne (tracks: list, priority_slug: str, source: str).
    Si config_path est fourni, lit ce fichier directement.
    Sinon, lit today/config.json si présent, sinon config.json (legacy).
    """
    if config_path is not None:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config introuvable : {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "tracks" in data:
            tracks        = data["tracks"]
            priority_slug = data.get("priority_slug", tracks[0]["slug"] if tracks else "")
            return tracks, priority_slug, "config"
        else:
            track = _normaliser_track_legacy(data)
            return [track], "main", "legacy"

    today_path  = os.path.join(BASE_DIR, "today", "config.json")
    legacy_path = os.path.join(BASE_DIR, "config.json")

    if os.path.exists(today_path):
        with open(today_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tracks        = data.get("tracks", [])
        priority_slug = data.get("priority_slug", tracks[0]["slug"] if tracks else "")
        date          = data.get("date", "?")
        print(f"  → Config : today/config.json ({date}, {len(tracks)} track(s))")
        return tracks, priority_slug, "today"

    if os.path.exists(legacy_path):
        with open(legacy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "tracks" in data:
            # Nouveau format mais dans config.json
            tracks        = data["tracks"]
            priority_slug = data.get("priority_slug", tracks[0]["slug"] if tracks else "")
            return tracks, priority_slug, "config"
        else:
            # Legacy single-track
            track = _normaliser_track_legacy(data)
            print(f"  → Config : config.json (legacy single-track → slug 'main')")
            return [track], "main", "legacy"

    raise FileNotFoundError(
        "Aucun fichier de config trouvé.\n"
        "Attendu : today/config.json ou config.json"
    )


# ─── Pipeline par track ───────────────────────────────────────────────────────

def run_track(track: dict, args, etape_offset: int, total_etapes: int) -> list:
    """
    Exécute le pipeline complet pour un track.
    Retourne la liste des MP4 produits.
    """
    slug    = track["slug"]
    videos  = []
    etape   = etape_offset

    # Validation de la configuration de distribution
    try:
        dist_config = valider_distribution(track)
        print(f"\n  📤 Distribution : {', '.join(dist_config.platforms_enabled())}")
    except ValueError as e:
        warning(f"Configuration de distribution : {e}")
        # On continue quand même si la distribution n'est pas configurée

    # Affiche le suno_prompt en reminder si présent
    if track.get("suno_prompt"):
        print(f"\n  💡 Suno prompt : {track['suno_prompt'][:100]}...")

    # ── Étape visuelle ────────────────────────────────────────────────────────
    if not args.skip_visual:
        engine = getattr(args, "visual_engine", "leonardo")
        if engine == "wavespeed":
            from modules.wavespeed import generer_visuel
            engine_label = "WaveSpeed AI"
        else:
            from modules.visual import generer_visuel
            engine_label = "Leonardo AI"
        etape += 1
        titre_etape(etape, total_etapes, f"Génération cinématique ({engine_label}) — {slug}")
        t0 = time.time()
        try:
            generer_visuel(track, BASE_DIR, force=args.force)
            succes(f"Visuels générés en {time.time()-t0:.1f}s")
        except Exception as e:
            erreur(f"Échec visuel [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return []
    else:
        warning(f"Visuel ignoré (--skip-visual)")

    # ── Étape vidéo ───────────────────────────────────────────────────────────
    if not args.skip_video:
        etape += 1
        titre_etape(etape, total_etapes, f"Assemblage MP4 (FFmpeg) — {slug}")
        t0 = time.time()
        try:
            videos = generer_videos(track, BASE_DIR, force=args.force)
            succes(f"{len(videos)} vidéo(s) en {time.time()-t0:.1f}s")
            for v in videos: info(f"📹 {v}")
        except Exception as e:
            erreur(f"Échec assemblage [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return []
    else:
        warning(f"Assemblage ignoré (--skip-video)")
        output_dir = os.path.join(BASE_DIR, "output", slug)
        videos = [f for f in glob.glob(os.path.join(output_dir, "*.mp4"))
                  if not os.path.basename(f).startswith("_")]
        if videos: info(f"{len(videos)} vidéo(s) existante(s) dans output/{slug}/")
        else: warning(f"Aucune vidéo dans output/{slug}/ — upload impossible.")

    # ── Étape upload ──────────────────────────────────────────────────────────
    if not args.skip_upload:
        if not videos:
            erreur(f"Aucune vidéo à uploader pour [{slug}].")
            return []
        etape += 1
        titre_etape(etape, total_etapes, f"Upload YouTube — {slug}")
        t0 = time.time()
        try:
            uploader_videos(track, videos, BASE_DIR)
            succes(f"Upload terminé en {time.time()-t0:.1f}s")
            
            # Distribution multi-plateforme
            try:
                dist_config = valider_distribution(track)
                if dist_config.has_any():
                    distribuer_track(track, BASE_DIR, skip_upload=False)
            except ValueError:
                pass  # Pas de distribution configurée
            except Exception as e:
                warning(f"Distribution partielle : {e}")
                if args.debug: traceback.print_exc()
                
        except UploadLimitExceeded as e:
            erreur(f"Échec upload [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            raise  # remonter pour stopper les uploads restants
        except Exception as e:
            erreur(f"Échec upload [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return videos  # vidéos générées même si upload échoue
    else:
        warning(f"Upload ignoré (--skip-upload)")

    return videos


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Assirem Music PROD — multi-tracks"
    )
    parser.add_argument("--slug",         type=str,  help="Lance un track spécifique par slug")
    parser.add_argument("--all",          action="store_true", help="Lance tous les tracks")
    parser.add_argument("--list",         action="store_true", help="Liste les tracks disponibles")
    parser.add_argument("--force",        action="store_true", help="Écrase les fichiers existants")
    parser.add_argument("--skip-visual",    action="store_true")
    parser.add_argument("--skip-video",     action="store_true")
    parser.add_argument("--skip-upload",    action="store_true")
    parser.add_argument("--debug",          action="store_true")
    parser.add_argument("--visual-engine",  type=str, default="leonardo",
                        choices=["leonardo", "wavespeed"],
                        help="Moteur de génération visuelle (défaut: leonardo)")
    args = parser.parse_args()

    print(f"\n{GRAS}{'═'*60}{RESET}")
    print(f"{GRAS}  🎵  ASSIREM MUSIC PROD — Pipeline multi-tracks  🎵{RESET}")
    print(f"{GRAS}{'═'*60}{RESET}")

    # Chargement config
    try:
        tracks, priority_slug, source = charger_tracks()
    except Exception as e:
        erreur(f"Erreur config : {e}")
        sys.exit(1)

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        print(f"\n  Tracks disponibles ({len(tracks)}) :\n")
        for t in sorted(tracks, key=lambda x: x.get("priority", 99)):
            badge = " ★" if t["slug"] == priority_slug else ""
            nb_scenes = len(t.get("scenes", []))
            print(f"  {'→' if t['slug']==priority_slug else ' '} [{t['slug']}]{badge}")
            print(f"      Titre    : {t.get('title','?')[:60]}")
            print(f"      Mode     : {t.get('mode','?')} | Scènes : {nb_scenes}")
            print(f"      Suno     : {t.get('suno_prompt','—')[:70]}...")
            print()
        sys.exit(0)

    # ── Sélection des tracks à traiter ────────────────────────────────────────
    if args.slug:
        selection = [t for t in tracks if t["slug"] == args.slug]
        if not selection:
            erreur(f"Slug '{args.slug}' introuvable. Slugs disponibles : {[t['slug'] for t in tracks]}")
            sys.exit(1)
    elif args.all:
        selection = sorted(tracks, key=lambda x: x.get("priority", 99))
    else:
        # Défaut : track prioritaire seulement
        selection = [t for t in tracks if t["slug"] == priority_slug]
        if not selection:
            selection = [tracks[0]]

    if args.force: warning("--force activé : fichiers existants écrasés.")

    # ── Calcul du nombre total d'étapes ───────────────────────────────────────
    etapes_par_track = sum([
        not args.skip_visual,
        not args.skip_video,
        not args.skip_upload,
    ])
    total_etapes = etapes_par_track * len(selection)

    print(f"  Tracks sélectionnés : {[t['slug'] for t in selection]}")
    print(f"  Étapes totales      : {total_etapes} ({etapes_par_track} × {len(selection)} track(s))")

    # ── Boucle sur les tracks ─────────────────────────────────────────────────
    debut_global = time.time()
    resultats    = {}
    upload_bloque = False  # True si YouTube a refusé (limite atteinte)
    slugs_en_attente = []  # tracks dont l'upload reste à faire

    # Afficher le compteur d'uploads du jour
    nb_uploads, slugs_uploades = get_upload_count_today(BASE_DIR)
    if nb_uploads > 0:
        print(f"\n  📊 Uploads YouTube aujourd'hui : {nb_uploads} vidéo(s) ({', '.join(slugs_uploades)})")

    for i, track in enumerate(selection, 1):
        slug       = track["slug"]
        is_priority = slug == priority_slug
        titre_track(slug, i, len(selection), priority=is_priority)

        etape_offset = (i - 1) * etapes_par_track

        if upload_bloque and not args.skip_upload:
            # On continue visual/video mais on saute l'upload
            warning(f"Upload ignoré (limite YouTube atteinte) — à relancer demain avec :")
            info(f"python3 pipeline.py --slug {slug} --skip-visual --skip-video")
            args_temp = argparse.Namespace(**vars(args))
            args_temp.skip_upload = True
            videos = run_track(track, args_temp, etape_offset, total_etapes)
            slugs_en_attente.append(slug)
        else:
            try:
                videos = run_track(track, args, etape_offset, total_etapes)
            except UploadLimitExceeded:
                upload_bloque = True
                videos = []
                # Récupérer les vidéos existantes pour le résultat
                output_dir = os.path.join(BASE_DIR, "output", slug)
                videos = [f for f in glob.glob(os.path.join(output_dir, "*.mp4"))
                          if not os.path.basename(f).startswith("_")]
                slugs_en_attente.append(slug)

        resultats[slug] = videos

    # ── Résumé global ─────────────────────────────────────────────────────────
    duree = time.time() - debut_global
    print(f"\n{GRAS}{'═'*60}{RESET}")
    print(f"{GRAS}  🎉 Pipeline terminé en {duree:.1f}s{RESET}")
    print(f"{GRAS}{'═'*60}{RESET}")
    for slug, vids in resultats.items():
        statut = f"{VERT}✅ {len(vids)} vidéo(s){RESET}" if vids else f"{ROUGE}❌ échec{RESET}"
        if slug in slugs_en_attente:
            statut += f" {JAUNE}(upload en attente){RESET}"
        print(f"  {slug:20s} → {statut}")

    if slugs_en_attente:
        print(f"\n{JAUNE}{GRAS}  ⚠️  {len(slugs_en_attente)} track(s) en attente d'upload (limite YouTube atteinte){RESET}")
        print(f"{JAUNE}  → Relancez demain avec :{RESET}")
        for s in slugs_en_attente:
            print(f"{JAUNE}     python3 pipeline.py --slug {s} --skip-visual --skip-video{RESET}")
    print()


if __name__ == "__main__":
    main()
