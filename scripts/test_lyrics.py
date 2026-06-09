"""
Test lyrics vidéo overlay sur reggaeton-roots-fusion-lunes-2026.

Usage:
  python scripts/test_lyrics.py [--force] [--slug <slug>]

Ce que ça fait :
  1. Lit les suno_lyrics depuis today/week_config.json
  2. Aligne via stable-ts (forced alignment texte connu → timestamps)
  3. Fallback timing proportionnel si stable-ts échoue
  4. Étend les timings sur toute la durée vidéo (MP3 en boucle)
  5. Génère output/<slug>/<slug>_WITH_LYRICS.mp4 (original intact)

Options:
  --force      Supprime le cache et réaligne
  --slug NAME  Tester sur un autre track

Prérequis :
  pip install stable-ts pillow
"""

import os
import sys
import glob
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.lyrics import (
    aligner_lyrics, lyrics_proportionnels, nettoyer_lyrics,
    sauver_timing, charger_timing, etendre_pour_boucle,
    generer_ass, appliquer_lyrics,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Args ───────────────────────────────────────────────────────────────────────
_args = sys.argv[1:]
FORCE = "--force" in _args
SLUG  = next((a for i, a in enumerate(_args) if _args[i-1] == "--slug"), None) \
        or "reggaeton-roots-fusion-lunes-2026"

INPUT_DIR  = os.path.join(BASE, "input")
OUTPUT_DIR = os.path.join(BASE, "output", SLUG)
CACHE_PATH = os.path.join(OUTPUT_DIR, "lyrics.json")
ASS_PATH   = os.path.join(OUTPUT_DIR, "lyrics.ass")


def _duree_ffprobe(path: str) -> float:
    import subprocess
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=15,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def charger_suno_lyrics(slug: str) -> str | None:
    for cfg in [
        os.path.join(BASE, "today", "week_config.json"),
        os.path.join(BASE, "today", "config.json"),
        os.path.join(BASE, "config.json"),
    ]:
        if not os.path.exists(cfg):
            continue
        data = json.load(open(cfg, encoding="utf-8"))
        for t in data.get("tracks", []):
            if t.get("slug") == slug:
                lyr = t.get("suno_lyrics", "")
                return lyr or None
    return None


def trouver_mp3(slug: str) -> str | None:
    slug_dir = os.path.join(INPUT_DIR, slug)
    if not os.path.isdir(slug_dir):
        candidats = glob.glob(os.path.join(INPUT_DIR, f"*-{slug}"))
        slug_dir  = candidats[0] if candidats else None
    if slug_dir:
        mp3s = sorted(glob.glob(os.path.join(slug_dir, "*.mp3")))
        if mp3s:
            return mp3s[0]
    return None


def trouver_video(slug: str) -> str:
    out_dir = os.path.join(BASE, "output", slug)
    slug_u  = slug.replace("-", "_")
    cands   = [
        f for f in glob.glob(os.path.join(out_dir, "*.mp4"))
        if "WITH_LYRICS" not in f and "short" not in f
        and "_intro" not in f and "_outro" not in f
        and os.path.basename(f).startswith(slug_u)
    ]
    if not cands:
        cands = [
            f for f in glob.glob(os.path.join(out_dir, "*.mp4"))
            if "WITH_LYRICS" not in f and "short" not in f
            and "_intro" not in f and "_outro" not in f
        ]
    if not cands:
        raise FileNotFoundError(f"Aucune vidéo dans {out_dir}")
    return cands[0]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n🎵 Lyrics Vidéo — {SLUG}\n")

    # ── 1. MP3
    mp3 = trouver_mp3(SLUG)
    if not mp3:
        print(f"❌ Aucun MP3 trouvé pour {SLUG}")
        sys.exit(1)
    print(f"  → MP3  : {os.path.basename(mp3)}")
    duree_mp3 = _duree_ffprobe(mp3)
    print(f"  → Durée MP3 : {duree_mp3:.1f}s")

    # ── 2. Lyrics connus
    suno_lyr = charger_suno_lyrics(SLUG)
    if suno_lyr:
        print(f"  → suno_lyrics : {len(nettoyer_lyrics(suno_lyr).split())} mots")
    else:
        print("  ⚠️  Pas de suno_lyrics dans la config")

    # ── 3. Alignment (cache ou stable-ts)
    if FORCE and os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        print("  → Cache supprimé (--force)")

    if os.path.exists(CACHE_PATH):
        lines = charger_timing(CACHE_PATH)
        print(f"  → Cache : {len(lines)} lignes")
    elif suno_lyr:
        try:
            lines = aligner_lyrics(mp3, suno_lyr, model_size="small",
                                   cache_path=CACHE_PATH)
        except Exception as e:
            print(f"  ⚠️  stable-ts échoué ({e}) → fallback proportionnel")
            lines = lyrics_proportionnels(suno_lyr, duree_mp3)
            sauver_timing(lines, CACHE_PATH)
        if not lines:
            print("  ⚠️  Alignment vide → fallback proportionnel")
            lines = lyrics_proportionnels(suno_lyr, duree_mp3)
            sauver_timing(lines, CACHE_PATH)
    else:
        print("  ❌ Aucune source de lyrics disponible.")
        sys.exit(1)

    # ── 4. Vidéo + extension
    video = trouver_video(SLUG)
    duree_video = _duree_ffprobe(video)
    print(f"  → Vidéo : {os.path.basename(video)} ({duree_video:.1f}s)")

    if duree_video > duree_mp3 * 1.05:
        lines = etendre_pour_boucle(lines, duree_mp3, duree_video)
        print(f"  → {len(lines)} entrées après extension")

    # ── 5. Infos track pour les cartes intro/CTA
    track_info = None
    suno_lyr_raw = charger_suno_lyrics(SLUG)  # already loaded above
    cfg_track = None
    for cfg in [
        os.path.join(BASE, "today", "week_config.json"),
        os.path.join(BASE, "today", "config.json"),
        os.path.join(BASE, "config.json"),
    ]:
        if not os.path.exists(cfg):
            continue
        import json as _json
        data = _json.load(open(cfg, encoding="utf-8"))
        for t in data.get("tracks", []):
            if t.get("slug") == SLUG:
                cfg_track = t
                break
        if cfg_track:
            break

    if cfg_track:
        raw_style = cfg_track.get("suno_style", "")
        # Garder les 3 premiers tags du style
        style_tags = " · ".join(s.strip() for s in raw_style.split(",")[:3])
        track_info = {
            "title":   cfg_track.get("suno_title") or cfg_track.get("title", SLUG),
            "style":   style_tags,
            "tribute": cfg_track.get("tribute") or "",
        }

    # ── 6. ASS de référence
    generer_ass(lines, ASS_PATH)

    # ── 7. Overlay
    dest = os.path.join(OUTPUT_DIR, f"{SLUG.replace('-', '_')}_WITH_LYRICS.mp4")
    tmp  = os.path.join(OUTPUT_DIR, "_lyrics_pngs")
    appliquer_lyrics(video, dest, lines, tmp_dir=tmp,
                     track_info=track_info, video_dur=duree_video)

    print(f"\n✅ Terminé !")
    print(f"   Original : {video}")
    print(f"   Lyrics   : {dest}")


if __name__ == "__main__":
    main()
