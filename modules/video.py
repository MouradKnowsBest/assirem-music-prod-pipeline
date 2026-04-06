"""
Module video.py - Assemblage clips vidéo Motion + audio → MP4 final via FFmpeg

Workflow medium/long :
  1. Concatène les MP3 → audio 30 min
  2. Ralentit les clips Motion ×6 (~5s → ~30s) via FFmpeg frame interpolation
  3. Loope les clips ralentis pour couvrir la durée cible
  4. Mixe vidéo + audio → MP4 final
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

FACTEUR_RALENTI = 6  # clips ~5s × 6 = ~30s par clip


# ─── Utilitaires ─────────────────────────────────────────────────────────────

def _escape_concat(chemin: str) -> str:
    """
    Échappe un chemin pour le format concat de FFmpeg.
    Les apostrophes (ex: Don't) cassent le parsing si non échappées.
    Règle FFmpeg : ' → '\''
    """
    return chemin.replace("'", "'\\''")

def _slug(texte: str) -> str:
    texte = texte.lower()
    texte = re.sub(r"[^\w\s-]", "", texte)
    texte = re.sub(r"[\s_-]+", "_", texte)
    return texte.strip("_")[:80]


def _duree(chemin: str) -> float:
    """Durée en secondes via ffprobe."""
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


def _lister_mp3(dossier: str) -> list:
    fichiers = sorted(glob.glob(os.path.join(dossier, "*.mp3")))
    if not fichiers:
        raise FileNotFoundError(
            f"Aucun fichier MP3 trouvé dans : {dossier}\n"
            "Placez vos fichiers .mp3 dans le dossier input/ avant de lancer le pipeline."
        )
    return fichiers


def _lister_clips(clips_dir: str) -> list:
    clips = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))
    if not clips:
        raise FileNotFoundError(
            f"Aucun clip vidéo trouvé dans : {clips_dir}\n"
            "Lancez d'abord l'étape visuelle pour générer les clips."
        )
    return clips


# ─── Barre de progression ─────────────────────────────────────────────────────

def _barre(label: str, stop_event: threading.Event, duree_estimee: float = None) -> threading.Thread:
    def _run():
        debut = time.time()
        syms  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        i = 0
        while not stop_event.is_set():
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
            i += 1
            time.sleep(0.1)
        elapsed = time.time() - debut
        mm, ss  = int(elapsed // 60), int(elapsed % 60)
        sys.stdout.write(f"\r  ✅ {label} — {mm:02d}:{ss:02d}                              \n")
        sys.stdout.flush()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _run_ffmpeg(cmd: list, label: str, duree_estimee: float = None) -> None:
    """Lance une commande FFmpeg avec barre de progression. Lève si erreur."""
    stop = threading.Event()
    _barre(label, stop, duree_estimee)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stop.set()
    time.sleep(0.15)
    if proc.returncode != 0:
        raise RuntimeError(f"Erreur FFmpeg ({label}) :\n{proc.stderr[-2000:]}")


# ─── Audio : concaténation & vérification ────────────────────────────────────

def _concatener_audio(mp3s: list, duree_cible: float, output_dir: str) -> tuple:
    """
    Concatène les MP3 en boucle jusqu'à atteindre duree_cible.
    Retourne (chemin_audio, duree_reelle).
    """
    durees = [_duree(f) for f in mp3s]
    total  = sum(d for d in durees if d > 0)
    if total == 0:
        raise RuntimeError("Impossible de lire la durée des MP3. Vérifiez les fichiers dans input/")

    # Construire la liste loopée
    liste = list(mp3s)
    cumul_total = total
    while cumul_total < duree_cible:
        liste.extend(mp3s)
        cumul_total += total

    # Tronquer à la durée cible
    fichiers_finaux, cumul = [], 0.0
    durees_ext = (durees * ((len(liste) // len(mp3s)) + 2))
    for chemin, dur in zip(liste, durees_ext):
        if cumul >= duree_cible:
            break
        fichiers_finaux.append(chemin)
        cumul += dur

    duree_reelle = min(cumul, duree_cible)

    # Fichier de liste concat
    liste_path = os.path.join(output_dir, "_concat_list.txt")
    audio_out  = os.path.join(output_dir, "_audio_concat.mp3")

    with open(liste_path, "w", encoding="utf-8") as f:
        for chemin in fichiers_finaux:
            chemin_abs = os.path.abspath(chemin)
            f.write(f"file '{_escape_concat(chemin_abs)}'\n")

    nb = len(fichiers_finaux)
    mins = int(duree_cible // 60)
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", liste_path,
        "-t", str(duree_cible),
        "-acodec", "libmp3lame", "-q:a", "2",
        audio_out,
    ], f"Concat audio ({nb} fichiers → {mins} min)", duree_estimee=duree_cible * 0.015)

    if os.path.exists(liste_path):
        os.remove(liste_path)

    # Vérification durée audio produit
    duree_verif = _duree(audio_out)
    if duree_verif < duree_cible * 0.9:
        raise RuntimeError(
            f"L'audio concaténé est trop court : {duree_verif:.0f}s au lieu de {duree_cible:.0f}s.\n"
            f"Vérifiez que les MP3 dans input/ ne sont pas corrompus."
        )

    print(f"  → Audio : {duree_verif/60:.1f} min ✓")
    return audio_out, duree_reelle


# ─── Clips : ralentissement ×6 ───────────────────────────────────────────────

def _ralentir_clip(chemin_in: str, chemin_out: str, facteur: int = FACTEUR_RALENTI) -> None:
    """
    Ralentit un clip vidéo par un facteur donné (ex: ×6 : 5s → 30s).
    Utilise setpts pour étirer les frames + fps cible 30 pour la fluidité.
    """
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-i", chemin_in,
        "-vf", f"setpts={facteur}*PTS",
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        chemin_out,
    ], f"Ralentissement ×{facteur} — {os.path.basename(chemin_in)}", duree_estimee=15)


def _preparer_clips_ralentis(clips: list, output_dir: str, force: bool = False) -> list:
    """
    Applique le ralentissement ×6 sur chaque clip.
    Retourne la liste des clips ralentis.
    """
    slow_dir = os.path.join(output_dir, "clips_slow")
    os.makedirs(slow_dir, exist_ok=True)

    clips_ralentis = []
    for i, clip in enumerate(clips, 1):
        nom      = os.path.basename(clip)
        sortie   = os.path.join(slow_dir, nom)

        if os.path.exists(sortie) and not force:
            duree_s = _duree(sortie)
            print(f"  → Clip ralenti {i}/{len(clips)} déjà présent ({duree_s:.1f}s), ignoré")
            clips_ralentis.append(sortie)
            continue

        print(f"  → Ralentissement clip {i}/{len(clips)} ({os.path.basename(clip)})...")
        _ralentir_clip(clip, sortie)
        duree_s = _duree(sortie)
        print(f"     → {os.path.basename(sortie)} ({duree_s:.1f}s)")
        clips_ralentis.append(sortie)

    return clips_ralentis


# ─── Vidéo : boucle clips + mixage ───────────────────────────────────────────

def _boucler_clips(clips: list, duree_cible: float, output_dir: str) -> str:
    """
    Concatène les clips en boucle jusqu'à couvrir duree_cible.
    Retourne le chemin de la vidéo loop (sans audio).
    """
    durees = [_duree(c) for c in clips]
    total  = sum(durees)
    if total == 0:
        raise RuntimeError("Impossible de lire la durée des clips ralentis.")

    # Construire la liste loopée
    liste = list(clips)
    cumul_total = total
    while cumul_total < duree_cible:
        liste.extend(clips)
        cumul_total += total

    # Tronquer
    clips_finaux, cumul = [], 0.0
    durees_ext = (durees * ((len(liste) // len(clips)) + 2))
    for chemin, dur in zip(liste, durees_ext):
        if cumul >= duree_cible:
            break
        clips_finaux.append(chemin)
        cumul += dur

    liste_path = os.path.join(output_dir, "_clips_list.txt")
    video_loop = os.path.join(output_dir, "_video_loop.mp4")

    with open(liste_path, "w", encoding="utf-8") as f:
        for c in clips_finaux:
            f.write(f"file '{_escape_concat(os.path.abspath(c))}'\n")

    nb   = len(clips_finaux)
    mins = int(duree_cible // 60)
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", liste_path,
        "-t", str(duree_cible),
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        video_loop,
    ], f"Boucle vidéo ({nb} clips → {mins} min)", duree_estimee=duree_cible * 0.02)

    if os.path.exists(liste_path):
        os.remove(liste_path)

    return video_loop


def _mixer(video: str, audio: str, sortie: str, duree: float) -> None:
    """Mixe la piste vidéo et la piste audio dans le fichier final."""
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video,
        "-i", audio,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duree),
        "-movflags", "+faststart",
        sortie,
    ], "Mixage vidéo + audio", duree_estimee=30)


def _assembler_simple(image: str, audio: str, sortie: str) -> None:
    """Mode individual/short : image fixe + audio."""
    duree = _duree(audio)
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-loop", "1", "-i", image,
        "-i", audio,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(duree),           # durée explicite (plus fiable que -shortest)
        "-movflags", "+faststart",
        sortie,
    ], "Assemblage vidéo", duree_estimee=duree * 0.3)


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def generer_videos(config: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère les MP4 selon le mode. Retourne la liste des chemins MP4 produits.
    """
    mode       = config.get("mode", "medium")
    titre      = config.get("title", "video")
    input_dir  = os.path.join(base_dir, config["input_folder"])
    output_dir = os.path.join(base_dir, config["output_folder"])
    clips_dir  = os.path.join(output_dir, "clips")
    image      = os.path.join(output_dir, "background.png")
    os.makedirs(output_dir, exist_ok=True)

    mp3s = _lister_mp3(input_dir)
    print(f"  → {len(mp3s)} fichier(s) MP3 trouvé(s) dans input/")
    videos = []

    # ── INDIVIDUAL ────────────────────────────────────────────────────────────
    if mode == "individual":
        if not os.path.exists(image):
            raise FileNotFoundError(f"Image de fond introuvable : {image}")
        for i, mp3 in enumerate(mp3s, 1):
            nom    = os.path.splitext(os.path.basename(mp3))[0]
            sortie = os.path.join(output_dir, f"{_slug(nom)}.mp4")
            if os.path.exists(sortie) and not force:
                print(f"  → [{i}/{len(mp3s)}] Déjà existant, ignoré.")
                videos.append(sortie); continue
            print(f"  → [{i}/{len(mp3s)}] {os.path.basename(mp3)}")
            _assembler_simple(image, mp3, sortie)
            taille = os.path.getsize(sortie) / (1024 * 1024)
            print(f"     📹 {os.path.basename(sortie)} ({taille:.1f} Mo)")
            videos.append(sortie)

    # ── SHORT ─────────────────────────────────────────────────────────────────
    elif mode == "short":
        if not os.path.exists(image):
            raise FileNotFoundError(f"Image de fond introuvable : {image}")
        sortie = os.path.join(output_dir, f"{_slug(titre)}.mp4")
        if os.path.exists(sortie) and not force:
            print(f"  → Déjà existant, ignoré.")
            return [sortie]
        _assembler_simple(image, mp3s[0], sortie)
        taille = os.path.getsize(sortie) / (1024 * 1024)
        print(f"     📹 {os.path.basename(sortie)} ({taille:.1f} Mo)")
        videos.append(sortie)

    # ── MEDIUM / LONG ─────────────────────────────────────────────────────────
    elif mode in ("medium", "long"):
        duree_cible = DUREES[mode]
        sortie      = os.path.join(output_dir, f"{_slug(titre)}.mp4")
        video_loop  = os.path.join(output_dir, "_video_loop.mp4")

        if os.path.exists(sortie) and not force:
            print(f"  → Déjà existant, ignoré.")
            return [sortie]

        # A — Audio
        print("\n  ── A) Préparation audio")
        audio_concat, duree_reelle = _concatener_audio(mp3s, duree_cible, output_dir)

        # B — Clips ralentis
        print("\n  ── B) Ralentissement des clips Motion (×6)")
        clips_originaux = _lister_clips(clips_dir)
        print(f"  → {len(clips_originaux)} clip(s) trouvé(s) dans output/clips/")
        clips_ralentis = _preparer_clips_ralentis(clips_originaux, output_dir, force=force)

        # C — Boucle vidéo
        print("\n  ── C) Boucle vidéo")
        video_loop_path = _boucler_clips(clips_ralentis, duree_reelle, output_dir)

        # D — Mixage final
        print(f"\n  ── D) Mixage final → {os.path.basename(sortie)}")
        _mixer(video_loop_path, audio_concat, sortie, duree_reelle)

        # Nettoyage temporaires
        for tmp in [audio_concat, video_loop_path]:
            if os.path.exists(tmp):
                os.remove(tmp)

        taille = os.path.getsize(sortie) / (1024 * 1024)
        print(f"\n     📹 {os.path.basename(sortie)} ({taille:.1f} Mo)")
        videos.append(sortie)

    else:
        raise ValueError(f"Mode inconnu : '{mode}'. Valeurs acceptées : individual, short, medium, long")

    return videos
