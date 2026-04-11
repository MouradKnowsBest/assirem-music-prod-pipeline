"""
Module video.py — Assemblage vidéo cinématique par track

Workflow medium/long :
  A) Concat MP3 depuis input/<slug>/ (ou input/ en fallback) → audio N min
  B) Ralentit les clips de scène ×6 (~5s → ~30s) → clips_slow/
  C) Boucle les clips ralentis EN ORDRE (narratif) → vidéo loop
  D) Mixe vidéo + audio → output/<slug>/<slug>.mp4
"""

import os
import re
import sys
import glob
import subprocess
import threading
import time

DUREES = {
    "short":  30 * 60,
    "medium": 30 * 60,
    "long":   2 * 60 * 60,
}
FACTEUR_RALENTI = 6


# ─── Utilitaires ─────────────────────────────────────────────────────────────

def _slug_safe(texte: str) -> str:
    texte = texte.lower()
    texte = re.sub(r"[^\w\s-]", "", texte)
    texte = re.sub(r"[\s_-]+", "_", texte)
    return texte.strip("_")[:80]


def _duree(chemin: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        chemin,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def _escape_concat(chemin: str) -> str:
    """Échappe les apostrophes pour le format concat FFmpeg (Don't → Don'\''t)."""
    return chemin.replace("'", "'\\''"  )


def _lister_mp3(input_dir: str, slug: str) -> list:
    """Cherche les MP3 dans input/<slug>/ puis input/ en fallback."""
    # Priorité 1 : input/<slug>/
    slug_dir = os.path.join(input_dir, slug)
    fichiers = sorted(glob.glob(os.path.join(slug_dir, "*.mp3")))
    if fichiers:
        print(f"  → MP3 trouvés dans input/{slug}/")
        return fichiers
    # Fallback : input/
    fichiers = sorted(glob.glob(os.path.join(input_dir, "*.mp3")))
    if fichiers:
        print(f"  → MP3 trouvés dans input/ (fallback)")
        return fichiers
    raise FileNotFoundError(
        f"Aucun MP3 trouvé dans input/{slug}/ ni dans input/\n"
        f"Placez vos fichiers .mp3 dans input/{slug}/"
    )


def _lister_clips(clips_dir: str) -> list:
    clips = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))
    if not clips:
        raise FileNotFoundError(
            f"Aucun clip trouvé dans {clips_dir}\n"
            "Lancez d'abord l'étape visuelle."
        )
    return clips


# ─── Barre de progression ─────────────────────────────────────────────────────

def _barre(label: str, stop: threading.Event, duree_estimee: float = None) -> threading.Thread:
    def _run():
        debut = time.time()
        syms  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        i = 0
        while not stop.is_set():
            elapsed = time.time() - debut
            mm, ss  = int(elapsed // 60), int(elapsed % 60)
            sp = syms[i % len(syms)]
            if duree_estimee and duree_estimee > 0:
                pct = min(int(elapsed / duree_estimee * 100), 99)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                sys.stdout.write(f"\r  {sp} {label} [{bar}] {pct}% — {mm:02d}:{ss:02d}")
            else:
                sys.stdout.write(f"\r  {sp} {label} — {mm:02d}:{ss:02d}")
            sys.stdout.flush()
            i += 1; time.sleep(0.1)
        elapsed = time.time() - debut
        mm, ss  = int(elapsed // 60), int(elapsed % 60)
        sys.stdout.write(f"\r  ✅ {label} — {mm:02d}:{ss:02d}                              \n")
        sys.stdout.flush()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _run_ffmpeg(cmd: list, label: str, duree_estimee: float = None) -> None:
    stop = threading.Event()
    _barre(label, stop, duree_estimee)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stop.set(); time.sleep(0.15)
    if proc.returncode != 0:
        raise RuntimeError(f"Erreur FFmpeg [{label}] :\n{proc.stderr[-2000:]}")


# ─── Audio ────────────────────────────────────────────────────────────────────

def _concatener_audio(mp3s: list, duree_cible: float, output_dir: str) -> tuple:
    """Retourne (chemin_audio, duree_reelle)."""
    durees = [_duree(f) for f in mp3s]
    total  = sum(d for d in durees if d > 0)
    if total == 0:
        raise RuntimeError("Impossible de lire la durée des MP3.")

    liste = list(mp3s)
    cumul_total = total
    while cumul_total < duree_cible:
        liste.extend(mp3s)
        cumul_total += total

    fichiers_finaux, cumul = [], 0.0
    durees_ext = durees * ((len(liste) // len(mp3s)) + 2)
    for chemin, dur in zip(liste, durees_ext):
        if cumul >= duree_cible: break
        fichiers_finaux.append(chemin)
        cumul += dur

    duree_reelle = min(cumul, duree_cible)
    liste_path   = os.path.join(output_dir, "_concat_list.txt")
    audio_out    = os.path.join(output_dir, "_audio_concat.mp3")

    with open(liste_path, "w", encoding="utf-8") as f:
        for c in fichiers_finaux:
            f.write(f"file '{_escape_concat(os.path.abspath(c))}'\n")

    nb = len(fichiers_finaux); mins = int(duree_cible // 60)
    _run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", liste_path, "-t", str(duree_cible),
        "-acodec", "libmp3lame", "-q:a", "2", audio_out,
    ], f"Concat audio ({nb} fichiers → {mins} min)", duree_estimee=duree_cible * 0.015)

    if os.path.exists(liste_path): os.remove(liste_path)

    duree_verif = _duree(audio_out)
    if duree_verif < duree_cible * 0.9:
        raise RuntimeError(
            f"Audio trop court : {duree_verif:.0f}s au lieu de {duree_cible:.0f}s.\n"
            "Vérifiez que les MP3 ne sont pas corrompus."
        )
    print(f"  → Audio : {duree_verif/60:.1f} min ✓")
    return audio_out, duree_reelle


# ─── Clips : ralentissement ×6 ───────────────────────────────────────────────

def _ralentir_clip(src: str, dest: str, facteur: int = FACTEUR_RALENTI) -> None:
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", src,
        "-vf", f"setpts={facteur}*PTS",
        "-r", "30", "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an", dest,
    ], f"Ralenti ×{facteur} — {os.path.basename(src)}", duree_estimee=15)


def _preparer_clips_ralentis(clips: list, output_dir: str, force: bool = False) -> list:
    """Ralentit les clips dans l'ordre des scènes. Retourne clips_slow[] en ordre."""
    slow_dir = os.path.join(output_dir, "clips_slow")
    os.makedirs(slow_dir, exist_ok=True)
    ralentis = []
    for i, clip in enumerate(clips, 1):
        dest = os.path.join(slow_dir, os.path.basename(clip))
        if os.path.exists(dest) and not force:
            duree_s = _duree(dest)
            print(f"  → Clip ralenti {i}/{len(clips)} déjà présent ({duree_s:.1f}s)")
        else:
            print(f"  → Ralentissement scène {i}/{len(clips)}...")
            _ralentir_clip(clip, dest)
            print(f"     → {os.path.basename(dest)} ({_duree(dest):.1f}s)")
        ralentis.append(dest)
    return ralentis


# ─── Boucle vidéo ─────────────────────────────────────────────────────────────

def _boucler_clips(clips: list, duree_cible: float, output_dir: str) -> str:
    """Concatène les clips EN ORDRE en boucle jusqu'à duree_cible."""
    durees = [_duree(c) for c in clips]
    total  = sum(durees)
    if total == 0:
        raise RuntimeError("Impossible de lire la durée des clips ralentis.")

    liste = list(clips)
    cumul_total = total
    while cumul_total < duree_cible:
        liste.extend(clips)
        cumul_total += total

    clips_finaux, cumul = [], 0.0
    durees_ext = durees * ((len(liste) // len(clips)) + 2)
    for c, d in zip(liste, durees_ext):
        if cumul >= duree_cible: break
        clips_finaux.append(c)
        cumul += d

    liste_path = os.path.join(output_dir, "_clips_list.txt")
    video_loop = os.path.join(output_dir, "_video_loop.mp4")

    with open(liste_path, "w", encoding="utf-8") as f:
        for c in clips_finaux:
            f.write(f"file '{_escape_concat(os.path.abspath(c))}'\n")

    nb = len(clips_finaux); mins = int(duree_cible // 60)
    _run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", liste_path, "-t", str(duree_cible),
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an", video_loop,
    ], f"Boucle vidéo ({nb} clips → {mins} min)", duree_estimee=duree_cible * 0.02)

    if os.path.exists(liste_path): os.remove(liste_path)
    return video_loop


def _mixer(video: str, audio: str, sortie: str, duree: float) -> None:
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", video, "-i", audio,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", str(duree), "-movflags", "+faststart", sortie,
    ], "Mixage vidéo + audio", duree_estimee=30)


def _assembler_simple(image: str, audio: str, sortie: str) -> None:
    duree = _duree(audio)
    _run_ffmpeg([
        "ffmpeg", "-y", "-loop", "1", "-i", image, "-i", audio,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-t", str(duree),
        "-movflags", "+faststart", sortie,
    ], "Assemblage vidéo", duree_estimee=duree * 0.3)


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def generer_videos(track: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère le MP4 final pour un track.
    Retourne [chemin_mp4].
    """
    slug       = track["slug"]
    mode       = track.get("mode", "medium")
    titre      = track.get("title", slug)
    input_dir  = os.path.join(base_dir, track.get("input_folder", "input"))
    output_dir = os.path.join(base_dir, "output", slug)
    clips_dir  = os.path.join(output_dir, "clips")
    os.makedirs(output_dir, exist_ok=True)

    mp3s = _lister_mp3(input_dir, slug)
    print(f"  → {len(mp3s)} MP3 trouvé(s)")

    # ── INDIVIDUAL ─────────────────────────────────────────────────────────
    if mode == "individual":
        image = os.path.join(output_dir, "scenes", "scene_001.png")
        if not os.path.exists(image):
            raise FileNotFoundError(f"Image scène 1 introuvable : {image}")
        videos = []
        for i, mp3 in enumerate(mp3s, 1):
            nom    = os.path.splitext(os.path.basename(mp3))[0]
            sortie = os.path.join(output_dir, f"{_slug_safe(nom)}.mp4")
            if os.path.exists(sortie) and not force:
                print(f"  → [{i}] Déjà existant, ignoré.")
                videos.append(sortie); continue
            print(f"  → [{i}/{len(mp3s)}] {os.path.basename(mp3)}")
            _assembler_simple(image, mp3, sortie)
            print(f"     📹 {os.path.basename(sortie)} ({os.path.getsize(sortie)/1024/1024:.1f} Mo)")
            videos.append(sortie)
        return videos

    # ── SHORT ───────────────────────────────────────────────────────────────
    if mode == "short":
        image  = os.path.join(output_dir, "scenes", "scene_001.png")
        sortie = os.path.join(output_dir, f"{_slug_safe(slug)}.mp4")
        if os.path.exists(sortie) and not force:
            return [sortie]
        _assembler_simple(image, mp3s[0], sortie)
        print(f"     📹 {os.path.basename(sortie)} ({os.path.getsize(sortie)/1024/1024:.1f} Mo)")
        return [sortie]

    # ── MEDIUM / LONG ────────────────────────────────────────────────────────
    duree_cible = DUREES.get(mode, DUREES["medium"])
    sortie      = os.path.join(output_dir, f"{_slug_safe(slug)}.mp4")

    if os.path.exists(sortie) and not force:
        print(f"  → Déjà existant, ignoré : {os.path.basename(sortie)}")
        return [sortie]

    print("\n  ── A) Audio")
    audio_concat, duree_reelle = _concatener_audio(mp3s, duree_cible, output_dir)

    print("\n  ── B) Ralentissement clips ×6")
    clips = _lister_clips(clips_dir)
    print(f"  → {len(clips)} clip(s) cinématiques trouvés (scènes en ordre)")
    clips_lents = _preparer_clips_ralentis(clips, output_dir, force=force)

    print("\n  ── C) Boucle vidéo narrative")
    video_loop = _boucler_clips(clips_lents, duree_reelle, output_dir)

    print(f"\n  ── D) Mixage final → {os.path.basename(sortie)}")
    _mixer(video_loop, audio_concat, sortie, duree_reelle)

    for tmp in [audio_concat, video_loop]:
        if os.path.exists(tmp): os.remove(tmp)

    taille = os.path.getsize(sortie) / (1024 * 1024)
    print(f"\n     📹 {os.path.basename(sortie)} ({taille:.1f} Mo)")
    return [sortie]
