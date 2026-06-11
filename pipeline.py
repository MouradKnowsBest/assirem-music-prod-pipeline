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
import shutil
import argparse
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from modules.video   import generer_videos
from modules.youtube import uploader_videos, UploadLimitExceeded, get_upload_count_today
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


def _resolve_output_dir(slug: str) -> str:
    """
    Retourne le dossier output d'un slug.
    Compatibilité: accepte output/<slug> et output/<nn>-<slug>.
    """
    output_root = os.path.join(BASE_DIR, "output")
    exact = os.path.join(output_root, slug)
    if os.path.isdir(exact):
        return exact

    try:
        candidats = []
        for name in os.listdir(output_root):
            path = os.path.join(output_root, name)
            if os.path.isdir(path) and name.endswith(f"-{slug}"):
                candidats.append(path)
        if candidats:
            return sorted(candidats)[0]
    except FileNotFoundError:
        pass

    # Fallback pour les étapes qui vont créer le dossier ensuite
    return exact


def _sync_input_images(slug: str, track: dict) -> int:
    """
    Copie les images (png/jpg/jpeg/webp) trouvées dans le dossier input/<slug>/
    vers output/<slug>/scenes/ en les renommant scene_001.ext, scene_002.ext, …
    Ne fait rien si des scènes existent déjà (pour ne pas écraser les visuels IA).
    Retourne le nombre d'images copiées.
    """
    input_root = os.path.join(BASE_DIR, track.get("input_folder", "input"))
    input_slug_dir = os.path.join(input_root, slug)
    if not os.path.isdir(input_slug_dir):
        candidats = glob.glob(os.path.join(input_root, f"*-{slug}"))
        if candidats:
            input_slug_dir = sorted(candidats)[0]

    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        images += sorted(glob.glob(os.path.join(input_slug_dir, ext)))
    if not images:
        return 0

    scenes_dir = os.path.join(_resolve_output_dir(slug), "scenes")
    os.makedirs(scenes_dir, exist_ok=True)

    # Ne pas écraser si des scènes IA existent déjà
    existing = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        existing += glob.glob(os.path.join(scenes_dir, "scene_*" + ext[1:]))
    if existing:
        return 0

    copied = 0
    for i, src in enumerate(images, 1):
        ext = os.path.splitext(src)[1].lower()
        dest = os.path.join(scenes_dir, f"scene_{i:03d}{ext}")
        shutil.copy2(src, dest)
        info(f"  🖼  Image input → scenes : {os.path.basename(src)} → scene_{i:03d}{ext}")
        copied += 1
    return copied


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


def charger_schedule(base_dir: str) -> dict:
    """
    Lit today/upload_schedule.json et retourne {slug: publish_at_iso} pour
    chaque slot dont le slug est non-null.
    Lève FileNotFoundError si le fichier est absent.
    """
    path = os.path.join(base_dir, "today", "upload_schedule.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Schedule introuvable : {path}\n"
            "Crée today/upload_schedule.json avant d'utiliser --respect-schedule."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mapping = {}
    for slot in data.get("slots", []):
        slug = slot.get("slug")
        publish_at = slot.get("publish_at")
        if slug and publish_at:
            mapping[slug] = publish_at
    return mapping


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

    # Priorité de recherche :
    #   1. today/week_config.json   (config hebdo généré par scripts/generate_week_config.py)
    #   2. today/config.json        (config quotidien — ex: agent Claude planifié)
    #   3. config.json              (legacy, racine)
    week_path   = os.path.join(BASE_DIR, "today", "week_config.json")
    today_path  = os.path.join(BASE_DIR, "today", "config.json")
    legacy_path = os.path.join(BASE_DIR, "config.json")

    for label, path in (("today/week_config.json", week_path),
                        ("today/config.json",      today_path)):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tracks        = data.get("tracks", [])
            priority_slug = data.get("priority_slug", tracks[0]["slug"] if tracks else "")
            date          = data.get("date", "?")
            print(f"  → Config : {label} ({date}, {len(tracks)} track(s))")
            return tracks, priority_slug, label

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

    # Validation de la configuration de distribution (seulement si explicitement configurée)
    if track.get("distribution"):
        try:
            dist_config = valider_distribution(track)
            print(f"\n  📤 Distribution : {', '.join(dist_config.platforms_enabled())}")
        except ValueError as e:
            warning(f"Configuration de distribution : {e}")

    # Affiche le suno_prompt en reminder si présent
    if track.get("suno_prompt"):
        print(f"\n  💡 Suno prompt : {track['suno_prompt'][:100]}...")

    # ── Mode shorts-only : on charge directement le short existant ───────────
    if getattr(args, "shorts_only", False):
        output_dir = _resolve_output_dir(slug)
        shorts = glob.glob(os.path.join(output_dir, "shorts", "*.mp4"))
        if not shorts:
            erreur(f"Aucun short trouvé dans {output_dir}/shorts/ — génère d'abord la vidéo.")
            return []
        info(f"Short trouvé : {os.path.basename(shorts[0])}")
        if not args.skip_upload:
            etape += 1
            titre_etape(etape, total_etapes, f"Upload YouTube Short — {slug}")
            t0 = time.time()
            try:
                uploader_videos(
                    track, shorts, BASE_DIR,
                    skip_playlists=getattr(args, "no_playlists", False),
                    force_playlist=getattr(args, "default_playlist", None),
                )  # pas de thumbnail pour les Shorts
                succes(f"Upload short terminé en {time.time()-t0:.1f}s")
            except UploadLimitExceeded as e:
                erreur(f"Échec upload [{slug}] : {e}")
                raise
            except Exception as e:
                erreur(f"Échec upload [{slug}] : {e}")
                if args.debug: traceback.print_exc()
        else:
            warning(f"Upload ignoré (--skip-upload)")
        return shorts

    # ── Étape visuelle ────────────────────────────────────────────────────────
    engine = getattr(args, "visual_engine", "leonardo")
    if not args.skip_visual and engine != "template":
        if engine == "wavespeed":
            from modules.wavespeed import generer_visuel
            engine_label = "WaveSpeed AI"
        elif engine == "kling":
            from modules.kling import generer_visuel
            engine_label = "Kling AI"
        else:
            from modules.visual import generer_visuel
            engine_label = "Leonardo AI"
        etape += 1
        titre_etape(etape, total_etapes, f"Génération cinématique ({engine_label}) — {slug}")
        t0 = time.time()
        try:
            ken_burns = getattr(args, "ken_burns", False)
            generer_visuel(track, BASE_DIR, force=args.force, skip_motion=ken_burns)
            succes(f"Visuels générés en {time.time()-t0:.1f}s")
        except Exception as e:
            erreur(f"Échec visuel [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return []
    elif engine == "template":
        warning(f"Visuel ignoré (--visual-engine template — rendu HTML Playwright)")
    else:
        warning(f"Visuel ignoré (--skip-visual)")

    # Auto-sync images depuis input/ → output/scenes/
    # Toujours exécuté : le moteur template en a besoin pour son slideshow
    n = _sync_input_images(slug, track)
    if n:
        succes(f"{n} image(s) copiée(s) depuis input/ vers scenes/")

    # ── Étape vidéo ───────────────────────────────────────────────────────────
    if engine == "template" and not args.skip_video:
        etape += 1
        titre_etape(etape, total_etapes, f"Rendu HTML template (Playwright + FFmpeg) — {slug}")
        t0 = time.time()
        try:
            import subprocess as _sp
            _cfg = getattr(args, "config", None)
            if not _cfg:
                for _p in (os.path.join(BASE_DIR, "today", "week_config.json"),
                           os.path.join(BASE_DIR, "today", "config.json"),
                           os.path.join(BASE_DIR, "config.json")):
                    if os.path.exists(_p):
                        _cfg = _p
                        break
            config_arg = _cfg or os.path.join(BASE_DIR, "config.json")
            result = _sp.run(
                ["python3", os.path.join(BASE_DIR, "scripts", "render_template.py"),
                 "--slug", slug, "--config", config_arg],
                check=True,
            )
            out_mp4 = os.path.join(_resolve_output_dir(slug), f"{slug.replace('-', '_')}.mp4")
            videos = [out_mp4] if os.path.exists(out_mp4) else []
            succes(f"Template rendu en {time.time()-t0:.1f}s")
            for v in videos: info(f"📹 {v}")
        except Exception as e:
            erreur(f"Échec rendu template [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return []
    elif not args.skip_video:
        etape += 1
        titre_etape(etape, total_etapes, f"Assemblage MP4 (FFmpeg) — {slug}")
        t0 = time.time()
        try:
            videos = generer_videos(track, BASE_DIR, force=args.force,
                                    ken_burns=getattr(args, "ken_burns", False) or getattr(args, "static", False),
                                    ping_pong=getattr(args, "pingpong", False),
                                    static=getattr(args, "static", False),
                                    zoom_only=getattr(args, "zoom_only", False))
            succes(f"{len(videos)} vidéo(s) en {time.time()-t0:.1f}s")
            for v in videos: info(f"📹 {v}")
        except Exception as e:
            erreur(f"Échec assemblage [{slug}] : {e}")
            if args.debug: traceback.print_exc()
            return []
    else:
        warning(f"Assemblage ignoré (--skip-video)")
        output_dir = _resolve_output_dir(slug)
        videos = [f for f in glob.glob(os.path.join(output_dir, "*.mp4"))
                  if not os.path.basename(f).startswith("_")]
        shorts = glob.glob(os.path.join(output_dir, "shorts", "*.mp4"))
        videos = videos + shorts
        if videos: info(f"{len(videos)} vidéo(s) existante(s) dans {output_dir}/ (dont {len(shorts)} short(s))")
        else: warning(f"Aucune vidéo dans {output_dir}/ — upload impossible.")

    # ── Étape thumbnail ───────────────────────────────────────────────────────
    if not getattr(args, "skip_thumbnail", False):
        etape += 1
        thumb_path = track.get("thumbnail_path")
        if thumb_path and os.path.exists(thumb_path):
            titre_etape(etape, total_etapes, f"Thumbnail — {slug}")
            info(f"Thumbnail existant réutilisé : {os.path.basename(thumb_path)}")
        elif track.get("tier"):
            titre_etape(etape, total_etapes, f"Génération thumbnail (Leonardo) — {slug}")
            t0 = time.time()
            try:
                from modules.thumbnail import build_thumbnail
                output_dir = os.path.join(BASE_DIR, "output", slug)
                thumb_path = str(build_thumbnail(
                    track_title=track.get("title", slug),
                    duration_label=track.get("duration_label", "1 HOUR"),
                    usage=track.get("usage", "focus"),
                    tier=track["tier"],
                    output_dir=output_dir,
                ))
                track["thumbnail_path"] = thumb_path
                succes(f"Thumbnail généré en {time.time()-t0:.1f}s")
            except Exception as e:
                warning(f"Thumbnail échoué [{slug}] (upload sans thumbnail) : {e}")
                thumb_path = None
                if args.debug: traceback.print_exc()
        else:
            titre_etape(etape, total_etapes, f"Thumbnail — {slug}")
            scenes_dir = os.path.join(_resolve_output_dir(slug), "scenes")
            _scene_thumb = None
            for _ext in (".png", ".jpg", ".jpeg", ".webp"):
                _candidate = os.path.join(scenes_dir, f"scene_001{_ext}")
                if os.path.exists(_candidate):
                    _scene_thumb = _candidate
                    break
            if _scene_thumb:
                thumb_path = _scene_thumb
                track["thumbnail_path"] = _scene_thumb
                info(f"Thumbnail : {os.path.basename(_scene_thumb)}")
            else:
                warning(f"Thumbnail ignoré (champ 'tier' absent et aucun scene_001.* pour {slug})")
    else:
        warning("Thumbnail ignoré (--skip-thumbnail)")

    # ── Étape upload ──────────────────────────────────────────────────────────
    if not args.skip_upload:
        if not videos:
            erreur(f"Aucune vidéo à uploader pour [{slug}].")
            return []
        etape += 1
        titre_etape(etape, total_etapes, f"Upload YouTube — {slug}")
        if getattr(args, "publish_now", False):
            track = dict(track)
            track.pop("scheduled_at", None)
            track.pop("publish_at", None)
            warning("--publish-now : scheduled_at ignoré → upload public immédiat")
        t0 = time.time()
        try:
            uploader_videos(
                track, videos, BASE_DIR,
                thumbnail_path=track.get("thumbnail_path"),
                skip_playlists=getattr(args, "no_playlists", False),
                force_playlist=getattr(args, "default_playlist", None),
            )
            succes(f"Upload terminé en {time.time()-t0:.1f}s")
            
            # Distribution multi-plateforme (seulement si configurée)
            if track.get("distribution"):
                try:
                    dist_config = valider_distribution(track)
                    if dist_config.has_any():
                        distribuer_track(track, BASE_DIR, skip_upload=False)
                except (ValueError, Exception) as e:
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
    parser.add_argument("--config",       type=str,  default=None,
                        help="Chemin vers un fichier config (défaut : today/week_config.json → today/config.json → config.json)")
    parser.add_argument("--slug",         type=str,  nargs="+", help="Lance un track spécifique par slug (guillemets optionnels, espaces OK)")
    parser.add_argument("--all",          action="store_true", help="Lance tous les tracks")
    parser.add_argument("--list",         action="store_true", help="Liste les tracks disponibles")
    parser.add_argument("--force",        action="store_true", help="Écrase les fichiers existants")
    parser.add_argument("--skip-visual",    action="store_true")
    parser.add_argument("--skip-video",     action="store_true")
    parser.add_argument("--skip-thumbnail", action="store_true",
                        help="Saute la génération du thumbnail (nécessite 'tier' dans la config du track)")
    parser.add_argument("--skip-upload",    action="store_true")
    parser.add_argument("--publish-now",    action="store_true",
                        help="Upload en public immédiat (ignore scheduled_at)")
    parser.add_argument("--no-playlists",   action="store_true",
                        help="Upload sans ajouter à aucune playlist (escape hatch quand les playlists sont KO)")
    parser.add_argument("--default-playlist", type=str, default=None,
                        help="Force une playlist unique pour TOUS les tracks (override config). "
                             "Ex: --default-playlist '🎵 Assirem Music PROD — All Tracks'")
    parser.add_argument("--shorts-only",    action="store_true", help="Upload uniquement le short existant (skip visual + video)")
    parser.add_argument("--respect-schedule", action="store_true",
                        help="Lit today/upload_schedule.json et upload chaque track en mode 'scheduled publish' à la date prévue")
    parser.add_argument("--debug",          action="store_true")
    parser.add_argument("--visual-engine",  type=str, default="leonardo",
                        choices=["leonardo", "wavespeed", "kling", "template"],
                        help="Moteur de génération visuelle (défaut: leonardo). 'template' = HTML montage via Playwright (pas de tokens IA)")
    parser.add_argument("--ken-burns",       action="store_true",
                        help="Images uniquement + animation Ken Burns FFmpeg (pas de clips IA — économise 90%% des crédits)")
    parser.add_argument("--pingpong",        action="store_true",
                        help="Ken Burns ping-pong : chaque image fait aller+retour (3 images → 6 clips, 50%% moins de tokens)")
    parser.add_argument("--static",          action="store_true",
                        help="Photos statiques sans zoompan : musique + photos fixes (plus simple, plus rapide)")
    parser.add_argument("--zoom-only",       action="store_true",
                        help="Ken Burns zoom uniquement (zoom_in/zoom_out) — pas de pan gauche/droite/diagonal")
    parser.add_argument("--limit",          type=int, default=0,
                        help="Limite le nombre de tracks à traiter (ex: --limit 10 = les 10 premiers par priorité)")
    parser.add_argument("--from",           type=int, default=0, dest="from_track",
                        help="Track de départ (1-based, ex: --from 11 --to 20)")
    parser.add_argument("--to",             type=int, default=0, dest="to_track",
                        help="Track de fin inclus (1-based, ex: --from 11 --to 20)")
    parser.add_argument("--workers",        type=int, default=1,
                        help="Nombre de tracks en parallèle pour visual+video (défaut: 1). "
                             "Recommandé: 3-5. Upload reste toujours séquentiel (quota YouTube).")
    args = parser.parse_args()

    print(f"\n{GRAS}{'═'*60}{RESET}")
    print(f"{GRAS}  🎵  ASSIREM MUSIC PROD — Pipeline multi-tracks  🎵{RESET}")
    print(f"{GRAS}{'═'*60}{RESET}")

    # Chargement config
    try:
        tracks, priority_slug, source = charger_tracks(args.config)
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
        slug_list = args.slug if isinstance(args.slug, list) else [args.slug]
        selection = [t for t in tracks if t["slug"] in slug_list]
        if not selection:
            # fallback : essaie de joindre comme slug unique avec espaces
            slug_str = " ".join(slug_list)
            selection = [t for t in tracks if t["slug"] == slug_str]
        if not selection:
            erreur(f"Slug(s) '{slug_list}' introuvable(s). Slugs disponibles : {[t['slug'] for t in tracks]}")
            sys.exit(1)
    elif args.all:
        selection = sorted(tracks, key=lambda x: x.get("priority", 99))
        if args.from_track or args.to_track:
            start = (args.from_track - 1) if args.from_track else 0
            end   = args.to_track if args.to_track else len(selection)
            selection = selection[start:end]
        elif args.limit:
            selection = selection[:args.limit]
    else:
        # Défaut : track prioritaire seulement
        selection = [t for t in tracks if t["slug"] == priority_slug]
        if not selection:
            selection = [tracks[0]]

    # ── --respect-schedule : injecte publish_at par track ──────────────────────
    if args.respect_schedule:
        # Build schedule map from upload_schedule.json (if exists)
        schedule_map = {}
        try:
            schedule_map = charger_schedule(BASE_DIR)
        except FileNotFoundError:
            pass  # will fall back to scheduled_at in track config

        # Fallback: use scheduled_at from track config for tracks not in schedule_map
        for t in selection:
            if t["slug"] not in schedule_map and t.get("scheduled_at"):
                schedule_map[t["slug"]] = t["scheduled_at"]

        if not schedule_map:
            erreur("Aucun schedule trouvé (ni upload_schedule.json ni scheduled_at dans les tracks).")
            sys.exit(1)

        # Filtre les tracks au schedule + injecte publish_at
        avant = [t["slug"] for t in selection]
        selection = [t for t in selection if t["slug"] in schedule_map]
        for t in selection:
            t["publish_at"] = schedule_map[t["slug"]]
        ignores = [s for s in avant if s not in schedule_map]
        info(f"📅 Schedule actif : {len(selection)} track(s) programmé(s)")
        if ignores:
            warning(f"Ignorés (pas dans le schedule) : {ignores}")
        if not selection:
            erreur("Aucun track sélectionné ne figure dans le schedule.")
            sys.exit(1)

    if args.force: warning("--force activé : fichiers existants écrasés.")

    # ── Calcul du nombre total d'étapes ───────────────────────────────────────
    if getattr(args, "shorts_only", False):
        etapes_par_track = 1 if not args.skip_upload else 0
    else:
        etapes_par_track = sum([
            not args.skip_visual,
            not args.skip_video,
            not getattr(args, "skip_thumbnail", False),
            not args.skip_upload,
        ])
    total_etapes = etapes_par_track * len(selection)

    print(f"  Tracks sélectionnés : {[t['slug'] for t in selection]}")
    print(f"  Étapes totales      : {total_etapes} ({etapes_par_track} × {len(selection)} track(s))")

    # ── Boucle sur les tracks ─────────────────────────────────────────────────
    debut_global = time.time()
    resultats    = {}
    upload_bloque = False
    slugs_en_attente = []

    nb_uploads, slugs_uploades = get_upload_count_today(BASE_DIR)
    if nb_uploads > 0:
        print(f"\n  📊 Uploads YouTube aujourd'hui : {nb_uploads} vidéo(s) ({', '.join(slugs_uploades)})")

    workers = getattr(args, "workers", 1)
    need_generate = not args.skip_visual or not args.skip_video
    use_parallel = workers > 1 and need_generate and not args.skip_upload

    if use_parallel:
        # ── Phase 1 : génération parallèle (visual + video, sans upload) ─────
        print(f"\n{GRAS}{CYAN}  ⚡ Mode parallèle — {workers} workers (génération uniquement){RESET}")
        args_gen = argparse.Namespace(**vars(args))
        args_gen.skip_upload = True

        videos_par_slug = {}

        def _generer(track_et_index):
            track, i = track_et_index
            slug = track["slug"]
            titre_track(slug, i, len(selection), priority=(slug == priority_slug))
            try:
                vids = run_track(track, args_gen, 0, 1)
                return slug, vids, None
            except Exception as e:
                return slug, [], e

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_generer, (track, i)): track["slug"]
                for i, track in enumerate(selection, 1)
            }
            for future in as_completed(futures):
                slug, vids, err = future.result()
                videos_par_slug[slug] = vids
                if err:
                    erreur(f"Échec génération [{slug}] : {err}")
                    if args.debug:
                        traceback.print_exc()
                else:
                    succes(f"Génération terminée : {slug} ({len(vids)} vidéo(s))")

        # ── Phase 2 : upload séquentiel ───────────────────────────────────────
        print(f"\n{GRAS}{CYAN}  📤 Phase upload séquentielle ({len(selection)} tracks){RESET}")
        args_up = argparse.Namespace(**vars(args))
        args_up.skip_visual = True
        args_up.skip_video  = True

        for i, track in enumerate(selection, 1):
            slug = track["slug"]
            if not videos_par_slug.get(slug):
                warning(f"Pas de vidéo générée pour [{slug}] — upload ignoré.")
                resultats[slug] = []
                continue

            titre_track(slug, i, len(selection), priority=(slug == priority_slug))
            if upload_bloque:
                warning(f"Upload ignoré (limite YouTube atteinte)")
                info(f"python3 pipeline.py --slug {slug} --skip-visual --skip-video")
                slugs_en_attente.append(slug)
                resultats[slug] = videos_par_slug[slug]
                continue
            try:
                vids = run_track(track, args_up, 0, 1)
                resultats[slug] = vids
            except UploadLimitExceeded:
                upload_bloque = True
                resultats[slug] = videos_par_slug[slug]
                slugs_en_attente.append(slug)
            except Exception as e:
                erreur(f"Échec upload [{slug}] : {e}")
                if args.debug:
                    traceback.print_exc()
                resultats[slug] = videos_par_slug[slug]

    else:
        # ── Mode séquentiel classique ─────────────────────────────────────────
        if workers > 1:
            warning(f"--workers ignoré (skip-visual+skip-video actifs ou skip-upload — mode séquentiel).")

        for i, track in enumerate(selection, 1):
            slug       = track["slug"]
            is_priority = slug == priority_slug
            titre_track(slug, i, len(selection), priority=is_priority)

            etape_offset = (i - 1) * etapes_par_track

            if upload_bloque and not args.skip_upload:
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
                    output_dir = _resolve_output_dir(slug)
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
