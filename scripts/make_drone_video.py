#!/usr/bin/env python3
"""
make_drone_video.py — Montage clips drone + MP3

Usage:
    python scripts/make_drone_video.py \
        --clips /chemin/vers/clips_drone/ \
        --mp3   /chemin/vers/a_mallorca.mp3 \
        --output output/a_mallorca.mp4

Options:
    --clips     Dossier contenant les clips drone (.mp4 / .mov)
    --mp3       Fichier audio MP3
    --output    Fichier de sortie  (default: output/drone_video.mp4)
    --shuffle   Mélanger aléatoirement l'ordre des clips
    --speed     Facteur de vitesse (default: 1.0, ex: 0.7 = léger ralenti)
    --fade      Durée fade in/out audio en secondes (default: 3)
    --title     Titre à afficher au début (optionnel)
    --artist    Artiste à afficher au début (optionnel)
    --title-dur Durée d'affichage du titre en secondes (default: 4)
"""

import os
import sys
import glob
import random
import argparse
import subprocess
import tempfile


FFMPEG_TIMEOUT = 60 * 60  # 1h max


def run(cmd: list, label: str = "") -> None:
    if label:
        print(f"  → {label}...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
    if result.returncode != 0:
        print(f"\nErreur FFmpeg :\n{result.stderr[-3000:]}", file=sys.stderr)
        sys.exit(1)


def duree(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def lister_clips(dossier: str, exclure: str = "") -> list:
    exts = ["*.mp4", "*.MP4", "*.mov", "*.MOV", "*.m4v"]
    clips = []
    for ext in exts:
        clips.extend(glob.glob(os.path.join(dossier, ext)))
    clips = sorted(set(clips))
    # exclure le fichier audio s'il est dans le même dossier
    if exclure:
        exclure_abs = os.path.abspath(exclure)
        clips = [c for c in clips if os.path.abspath(c) != exclure_abs]
    if not clips:
        print(f"Aucun clip vidéo trouvé dans : {dossier}", file=sys.stderr)
        sys.exit(1)
    return clips


def font_path() -> str:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def escape_dt(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def main():
    parser = argparse.ArgumentParser(description="Montage clips drone + MP3")
    parser.add_argument("--clips",     required=True,  help="Dossier des clips drone")
    parser.add_argument("--audio",     required=True,  help="Fichier audio (MP3, MP4, WAV…)")
    parser.add_argument("--mp3",       default=None,   help="Alias --audio (rétrocompat)")
    parser.add_argument("--output",    default="output/drone_video.mp4")
    parser.add_argument("--shuffle",   action="store_true", help="Ordre aléatoire")
    parser.add_argument("--speed",     type=float, default=1.0,
                        help="Vitesse des clips (0.7 = ralenti 30%%)")
    parser.add_argument("--fade",      type=int, default=3, help="Fade audio (s)")
    parser.add_argument("--title",     default="", help="Titre affiché au début")
    parser.add_argument("--artist",    default="", help="Artiste affiché au début")
    parser.add_argument("--title-dur", type=int, default=4, dest="title_dur")
    args = parser.parse_args()

    # --mp3 est un alias de --audio pour rétrocompatibilité
    audio_file = args.audio if args.audio else args.mp3

    # ── Validation ───────────────────────────────────────────────────────────
    if not os.path.isdir(args.clips):
        print(f"Dossier introuvable : {args.clips}", file=sys.stderr)
        sys.exit(1)
    if not audio_file or not os.path.isfile(audio_file):
        print(f"Fichier audio introuvable : {audio_file}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    # ── Clips ────────────────────────────────────────────────────────────────
    clips = lister_clips(args.clips, exclure=audio_file)
    if args.shuffle:
        random.shuffle(clips)

    print(f"  {len(clips)} clip(s) trouvé(s)")
    for c in clips:
        print(f"    {os.path.basename(c)}  ({duree(c):.1f}s)")

    duree_mp3 = duree(audio_file)
    print(f"  Durée MP3 : {duree_mp3:.1f}s ({duree_mp3/60:.1f} min)")

    # ── Normaliser les clips (résolution + fps uniformes) ────────────────────
    with tempfile.TemporaryDirectory(prefix="drone_build_") as tmp:

        # Déterminer résolution cible (premier clip)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", clips[0]],
            capture_output=True, text=True, timeout=30,
        )
        try:
            w, h = probe.stdout.strip().split("x")
            w, h = int(w), int(h)
        except Exception:
            w, h = 1920, 1080
        print(f"  Résolution cible : {w}x{h}")

        # Appliquer vitesse si différente de 1.0
        speed_filter = ""
        if abs(args.speed - 1.0) > 0.01:
            pts = 1.0 / args.speed
            speed_filter = f",setpts={pts:.4f}*PTS"

        # Normaliser chaque clip → tmp/norm_000.mp4
        norm_clips = []
        for i, clip in enumerate(clips):
            dest = os.path.join(tmp, f"norm_{i:03d}.mp4")
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2{speed_filter}"
            run([
                "ffmpeg", "-y", "-i", clip,
                "-vf", vf,
                "-r", "30",
                "-an",          # supprimer audio d'origine
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                dest,
            ], f"Normalisation clip {i+1}/{len(clips)}")
            norm_clips.append(dest)

        # ── Construire liste concat (boucle si clips trop courts) ────────────
        total = sum(duree(c) for c in norm_clips)
        playlist = list(norm_clips)
        # Boucle en ajoutant des passes entières si nécessaire
        passes = 0
        while sum(duree(c) for c in playlist) < duree_mp3 and passes < 20:
            playlist.extend(norm_clips)
            passes += 1

        concat_list = os.path.join(tmp, "concat.txt")
        with open(concat_list, "w") as f:
            for c in playlist:
                f.write(f"file '{c}'\n")

        # ── Concat vidéo (sans audio, peut dépasser la durée du MP3) ────────
        raw_video = os.path.join(tmp, "raw_video.mp4")
        run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-r", "30",
            raw_video,
        ], "Concaténation des clips")

        # ── Mixer vidéo + MP3, couper à la durée exacte du MP3 ──────────────
        fade_out_start = duree_mp3 - args.fade
        af = f"afade=t=in:st=0:d={args.fade},afade=t=out:st={fade_out_start:.2f}:d={args.fade}"

        # Filtre vidéo : title card si demandé (nécessite drawtext dans FFmpeg)
        vf_final = ""
        has_drawtext = subprocess.run(
            ["ffmpeg", "-filters"], capture_output=True, text=True, timeout=10
        ).stdout + subprocess.run(
            ["ffmpeg", "-filters"], capture_output=True, text=True, timeout=10
        ).stderr
        drawtext_ok = "drawtext" in has_drawtext
        if not drawtext_ok and (args.title or args.artist):
            print("  ⚠ drawtext non dispo dans ce build FFmpeg — titre désactivé")
        if (args.title or args.artist) and font_path() and drawtext_ok:
            fp = font_path()
            parts = []
            if args.title:
                t = escape_dt(args.title)
                parts.append(
                    f"drawtext=fontfile='{fp}':text='{t}':fontsize=60:fontcolor=white"
                    f":x=(w-text_w)/2:y=(h-text_h)/2-30"
                    f":alpha='if(lt(t,{args.title_dur}),min(t,1),max(0,{args.title_dur}-t+1))'"
                )
            if args.artist:
                a = escape_dt(args.artist)
                parts.append(
                    f"drawtext=fontfile='{fp}':text='{a}':fontsize=36:fontcolor=white@0.8"
                    f":x=(w-text_w)/2:y=(h-text_h)/2+40"
                    f":alpha='if(lt(t,{args.title_dur}),min(t,1),max(0,{args.title_dur}-t+1))'"
                )
            vf_final = ",".join(parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", raw_video,
            "-i", audio_file,
            "-t", str(duree_mp3),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-af", af,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
        ]
        if vf_final:
            cmd += ["-vf", vf_final]
        cmd.append(args.output)

        run(cmd, "Mixage vidéo + audio")

    print(f"\n✅ Vidéo générée : {args.output}")
    print(f"   Durée : {duree(args.output):.1f}s")


if __name__ == "__main__":
    main()
