"""
Module video.py — Assemblage vidéo cinématique par track

Workflow medium/long (SVD) :
  A) Concat MP3 depuis input/<slug>/ (ou input/ en fallback) → audio N min
  B) Ralentit les clips de scène ×6 (~5s → ~30s) → clips_slow/
  C) Boucle les clips ralentis EN ORDRE (narratif) → vidéo loop
  D) Mixe vidéo + audio + fade in/out + title_card + end_card → output/<slug>/<slug>.mp4
  E) (optionnel) Génère un short vertical 9:16 → output/<slug>/shorts/<slug>_short.mp4

Workflow medium/long (Ken Burns — --ken-burns) :
  A) identique
  B_KB) Applique zoompan FFmpeg sur chaque image scène → clips_kb/
  C) identique (boucle)
  D-E) identiques
"""

import os
import re
import sys
import glob
import subprocess
import threading
import time

DUREES = {
    "short": 30 * 60,
    "medium": 30 * 60,
    "long": 2 * 60 * 60,
}
FACTEUR_RALENTI = 6

# ─── Ken Burns ────────────────────────────────────────────────────────────────
_KB_CLIP_SEC = 30   # durée par clip Ken Burns (secondes)
_KB_FPS      = 30
_KB_MOVES      = ["zoom_in", "zoom_out", "pan_lr", "pan_rl", "pan_tb", "pan_diag"]
_KB_PAIRS      = [("zoom_in", "zoom_out"), ("pan_lr", "pan_rl"), ("pan_tb", "pan_diag")]
_KB_MOVES_ZOOM = ["zoom_in", "zoom_out"]
_KB_PAIRS_ZOOM = [("zoom_in", "zoom_out")]

# Timeout par défaut pour les commandes FFmpeg (60 min).
# Suffisant pour une vidéo de 2h en preset fast.
FFMPEG_TIMEOUT_DEFAULT = 60 * 60

# Polices candidates pour drawtext (macOS + Linux).
# La première qui existe est utilisée. Override via env ASSIREM_FONT=<path>.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def _font_path() -> str:
    """Retourne un chemin de police utilisable par drawtext."""
    env = os.environ.get("ASSIREM_FONT")
    if env and os.path.exists(env):
        return env
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # Dernier recours : FFmpeg utilise sa police par défaut sans fontfile
    return ""


def _drawtext_available() -> bool:
    """Vérifie que le filtre drawtext est disponible dans cette installation FFmpeg."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10
        )
        combined = result.stdout + result.stderr
        return "drawtext" in combined
    except Exception:
        return False


_DRAWTEXT_OK: bool | None = None


def _check_drawtext() -> bool:
    """Résultat mis en cache de _drawtext_available()."""
    global _DRAWTEXT_OK
    if _DRAWTEXT_OK is None:
        _DRAWTEXT_OK = _drawtext_available()
        if not _DRAWTEXT_OK:
            print(
                "  ⚠️  drawtext non disponible (FFmpeg sans libfreetype) — "
                "title_card et end_card désactivés.\n"
                "  → Pour activer : brew install ffmpeg-full",
                flush=True,
            )
    return _DRAWTEXT_OK


def _slug_safe(texte: str) -> str:
    texte = texte.lower()
    texte = re.sub(r"[^\w\s-]", "", texte)
    texte = re.sub(r"[\s_-]+", "_", texte)
    return texte.strip("_")[:80]


def _escape_drawtext(texte: str) -> str:
    """Échappe un texte pour le filtre drawtext FFmpeg."""
    # Ordre important : backslash d'abord, puis caractères spéciaux
    texte = texte.replace("\\", "\\\\")
    texte = texte.replace(":", "\\:")
    texte = texte.replace("'", "\\'")
    texte = texte.replace("%", "\\%")
    return texte


def _duree(chemin: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        chemin,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 0.0
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def _escape_concat(chemin: str) -> str:
    """Échappe les apostrophes pour le format concat FFmpeg (Don't → Don'\\''t)."""
    return chemin.replace("'", "'\\''")


def _lister_mp3(input_dir: str, slug: str) -> list:
    """Cherche les MP3 dans input/<slug>/ ou input/<N>-<slug>/ puis input/ en fallback."""
    # Cherche le dossier exact ou un dossier numéroté (ex: 3-slug)
    slug_dir = os.path.join(input_dir, slug)
    if not os.path.isdir(slug_dir):
        candidats = glob.glob(os.path.join(input_dir, f"*-{slug}"))
        slug_dir = candidats[0] if candidats else slug_dir

    fichiers = sorted(glob.glob(os.path.join(slug_dir, "*.mp3")))
    if fichiers:
        print(f"  → MP3 trouvés dans input/{os.path.basename(slug_dir)}/")
        return fichiers
    fichiers = sorted(glob.glob(os.path.join(input_dir, "*.mp3")))
    if fichiers:
        print("  → MP3 trouvés dans input/ (fallback)")
        return fichiers
    raise FileNotFoundError(
        f"Aucun MP3 trouvé dans input/{slug}/ ni dans input/\n"
        f"Placez vos fichiers .mp3 dans input/{slug}/"
    )


def _resolve_output_dir(base_dir: str, slug: str) -> str:
    """Retourne output/<slug> ou output/<nn>-<slug> si ce dernier existe déjà."""
    output_root = os.path.join(base_dir, "output")
    exact = os.path.join(output_root, slug)
    if os.path.isdir(exact):
        return exact
    try:
        candidats = [
            os.path.join(output_root, name)
            for name in os.listdir(output_root)
            if os.path.isdir(os.path.join(output_root, name)) and name.endswith(f"-{slug}")
        ]
        if candidats:
            return sorted(candidats)[0]
    except FileNotFoundError:
        pass
    return exact


def _lister_clips(clips_dir: str) -> list:
    clips = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))
    if not clips:
        raise FileNotFoundError(
            f"Aucun clip trouvé dans {clips_dir}\n"
            "Lancez d'abord l'étape visuelle."
        )
    return clips


def _barre(label: str, stop: threading.Event, duree_estimee: float = None) -> threading.Thread:
    def _run():
        debut = time.time()
        syms = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while not stop.is_set():
            elapsed = time.time() - debut
            mm, ss = int(elapsed // 60), int(elapsed % 60)
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
        mm, ss = int(elapsed // 60), int(elapsed % 60)
        sys.stdout.write(f"\r  ✅ {label} — {mm:02d}:{ss:02d}                              \n")
        sys.stdout.flush()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _run_ffmpeg(
    cmd: list,
    label: str,
    duree_estimee: float = None,
    timeout: float = FFMPEG_TIMEOUT_DEFAULT,
) -> None:
    stop = threading.Event()
    _barre(label, stop, duree_estimee)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        stop.set()
        time.sleep(0.15)
        raise RuntimeError(
            f"Timeout FFmpeg [{label}] après {timeout}s. "
            f"Relancez ou augmentez le timeout si la vidéo est très longue."
        ) from e
    stop.set()
    time.sleep(0.15)
    if proc.returncode != 0:
        raise RuntimeError(f"Erreur FFmpeg [{label}] :\n{proc.stderr[-2000:]}")


def _concatener_audio(mp3s: list, duree_cible: float, output_dir: str) -> tuple:
    """Retourne (chemin_audio, duree_reelle)."""
    durees = [_duree(f) for f in mp3s]
    total = sum(d for d in durees if d > 0)
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
        if cumul >= duree_cible:
            break
        fichiers_finaux.append(chemin)
        cumul += dur

    duree_reelle = min(cumul, duree_cible)
    liste_path = os.path.join(output_dir, "_concat_list.txt")
    audio_out = os.path.join(output_dir, "_audio_concat.mp3")

    with open(liste_path, "w", encoding="utf-8") as f:
        for c in fichiers_finaux:
            f.write(f"file '{_escape_concat(os.path.abspath(c))}'\n")

    nb = len(fichiers_finaux)
    mins = int(duree_cible // 60)
    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", liste_path,
            "-t", str(duree_cible),
            "-acodec", "libmp3lame", "-q:a", "2",
            audio_out,
        ],
        f"Concat audio ({nb} fichiers → {mins} min)",
        duree_estimee=duree_cible * 0.015,
    )

    if os.path.exists(liste_path):
        os.remove(liste_path)

    duree_verif = _duree(audio_out)
    if duree_verif < duree_cible * 0.9:
        raise RuntimeError(
            f"Audio trop court : {duree_verif:.0f}s au lieu de {duree_cible:.0f}s.\n"
            "Vérifiez que les MP3 ne sont pas corrompus."
        )
    print(f"  → Audio : {duree_verif / 60:.1f} min ✓")
    return audio_out, duree_reelle


def _ralentir_clip(src: str, dest: str, facteur: int = FACTEUR_RALENTI) -> None:
    _run_ffmpeg(
        [
            "ffmpeg", "-y", "-i", src,
            "-vf", f"setpts={facteur}*PTS",
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", dest,
        ],
        f"Ralenti ×{facteur} — {os.path.basename(src)}",
        duree_estimee=15,
        timeout=10 * 60,
    )


def _preparer_clips_ralentis(clips: list, output_dir: str, force: bool = False) -> list:
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


def _boucler_clips(clips: list, duree_cible: float, output_dir: str) -> str:
    durees = [_duree(c) for c in clips]
    total = sum(durees)
    if total == 0:
        raise RuntimeError("Impossible de lire la durée des clips ralentis.")

    # Need pool ≥ duree_cible + 10 (buffer for codec alignment + mixer trim)
    target_pool = duree_cible + 10
    liste = list(clips)
    cumul_total = total
    while cumul_total < target_pool:
        liste.extend(clips)
        cumul_total += total

    clips_finaux, cumul = [], 0.0
    durees_ext = durees * ((len(liste) // len(clips)) + 2)
    for c, d in zip(liste, durees_ext):
        if cumul >= target_pool:
            break
        clips_finaux.append(c)
        cumul += d

    liste_path = os.path.join(output_dir, "_clips_list.txt")
    video_loop = os.path.join(output_dir, "_video_loop.mp4")

    with open(liste_path, "w", encoding="utf-8") as f:
        for c in clips_finaux:
            f.write(f"file '{_escape_concat(os.path.abspath(c))}'\n")

    nb = len(clips_finaux)
    mins = int(duree_cible // 60)
    # +5s buffer so video is always longer than audio; _mixer's -t trims to exact length.
    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", liste_path,
            "-t", str(duree_cible + 5),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", video_loop,
        ],
        f"Boucle vidéo ({nb} clips → {mins} min)",
        duree_estimee=duree_cible * 0.02,
    )

    if os.path.exists(liste_path):
        os.remove(liste_path)
    return video_loop


# ─── Title card / End card / Fades ───────────────────────────────────────────

def _build_video_filter(
    duree: float,
    intro_fade: float,
    outro_fade: float,
    lyrics_lines: list = None,
) -> str:
    """
    Construit la chaîne de filtres vidéo : fade in/out + lyrics overlay.
    title_card et end_card sont désormais des segments noirs concaténés séparément.
    Retourne une chaîne FFmpeg -vf utilisable, ou "" si aucun effet.
    """
    filtres = []
    font = _font_path()
    font_arg = f"fontfile='{font}':" if font else ""

    # Fades
    if intro_fade > 0:
        filtres.append(f"fade=t=in:st=0:d={intro_fade}")
    if outro_fade > 0 and duree > outro_fade:
        filtres.append(f"fade=t=out:st={duree - outro_fade}:d={outro_fade}")

    # Lyrics overlay — bottom bar semi-transparent
    if lyrics_lines and _check_drawtext():
        for line in lyrics_lines:
            t_start = line["start"]
            t_end   = line["end"]
            text = _escape_drawtext(line["text"])
            filtres.append(
                f"drawtext={font_arg}text='{text}':"
                f"fontsize=44:fontcolor=white:"
                f"x=(w-text_w)/2:y=h-110:"
                f"box=1:boxcolor=black@0.55:boxborderw=18:"
                f"enable='between(t,{t_start},{t_end})'"
            )

    return ",".join(filtres)


def _generer_carte_noire(
    dest: str,
    texte: str,
    sous_titre: str = "",
    duree: float = 5.0,
    w: int = 1536,
    h: int = 864,
    force: bool = False,
) -> str:
    """
    Génère un segment vidéo carte noire (silent) avec texte centré.
    Retourne le chemin du fichier généré.
    """
    if os.path.exists(dest) and not force:
        print(f"  → Carte déjà présente : {os.path.basename(dest)}")
        return dest

    font = _font_path()
    font_arg = f"fontfile='{font}':" if font else ""
    fade = min(0.5, duree / 5)

    filtres = [
        f"fade=t=in:st=0:d={fade}",
        f"fade=t=out:st={duree - fade}:d={fade}",
    ]

    if texte and _check_drawtext():
        y_titre = "(h-text_h)/2-45" if sous_titre else "(h-text_h)/2"
        filtres.append(
            f"drawtext={font_arg}text='{_escape_drawtext(texte)}':"
            f"fontsize=72:fontcolor=white:"
            f"x=(w-text_w)/2:y={y_titre}:"
            f"shadowcolor=black@0.8:shadowx=3:shadowy=3"
        )
    if sous_titre and _check_drawtext():
        filtres.append(
            f"drawtext={font_arg}text='{_escape_drawtext(sous_titre)}':"
            f"fontsize=36:fontcolor=white@0.85:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+45:"
            f"shadowcolor=black@0.6:shadowx=1:shadowy=1"
        )

    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duree}:r=30",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-vf", ",".join(filtres),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duree),
            dest,
        ],
        f"Carte noire ({duree:.0f}s) — {os.path.basename(dest)}",
        duree_estimee=4,
        timeout=2 * 60,
    )
    return dest


def _concatener_segments(segments: list, sortie: str, output_dir: str) -> None:
    """Concatène intro + vidéo principale + outro en un seul MP4."""
    liste_path = os.path.join(output_dir, "_final_list.txt")
    with open(liste_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{_escape_concat(os.path.abspath(seg))}'\n")

    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", liste_path,
            "-c", "copy",
            "-movflags", "+faststart",
            sortie,
        ],
        f"Assemblage final ({len(segments)} segments)",
        duree_estimee=8,
    )

    if os.path.exists(liste_path):
        os.remove(liste_path)


def _mixer(
    video: str,
    audio: str,
    sortie: str,
    duree: float,
    intro_fade: float = 0,
    outro_fade: float = 0,
    lyrics_lines: list = None,
) -> None:
    vf = _build_video_filter(duree, intro_fade, outro_fade, lyrics_lines)
    # Always re-encode to guarantee clean timestamps for segment concat.
    # -c:v copy preserves B-frame DTS offsets that break concat demuxer.
    if vf:
        video_args = ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-vf", vf]
    else:
        video_args = ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p"]

    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-i", video,
            "-i", audio,
            *video_args,
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duree),
            "-movflags", "+faststart",
            sortie,
        ],
        "Mixage vidéo + audio",
        duree_estimee=duree * 0.05,
    )


def _assembler_simple(image: str, audio: str, sortie: str) -> None:
    duree = _duree(audio)
    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image,
            "-i", audio,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duree),
            "-movflags", "+faststart",
            sortie,
        ],
        "Assemblage vidéo",
        duree_estimee=duree * 0.3,
    )


# ─── Ken Burns zoompan ───────────────────────────────────────────────────────

def _kb_vf(move: str, duration_sec: float, w: int = 1536, h: int = 864) -> str:
    """
    Retourne le filtre FFmpeg Ken Burns compatible FFmpeg 8+.
    zoom_in/zoom_out : zoompan (scale+t invalide en FFmpeg 8 init eval).
    pan_* : scale fixe + crop avec expressions t (toujours valides dans crop).
    """
    sw  = int(w * 1.15)
    sh  = int(h * 1.15)
    dur = float(duration_sec)
    fps = _KB_FPS
    n   = int(dur * fps)  # nombre total de frames

    # Supersampling 2× pour éliminer le jitter zoompan (pixels entiers → flou)
    w2, h2 = w * 2, h * 2
    # Ease-in-out cosine: range*(1-cos(PI*t))/2 → smooth start & end
    # zoom range 1.0↔1.15 (was linear 1.0↔1.12)
    moves = {
        "zoom_in":  (
            f"zoompan=z='min(1.15,1+0.075*(1-cos(3.14159*on/{n})))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={w2}x{h2}:fps={fps},"
            f"scale={w}:{h}:flags=lanczos"
        ),
        "zoom_out": (
            f"zoompan=z='max(1,1.15-0.075*(1-cos(3.14159*on/{n})))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={w2}x{h2}:fps={fps},"
            f"scale={w}:{h}:flags=lanczos"
        ),
        # Pan gauche → droite, zoom fixe 1.15
        "pan_lr":   f"scale={sw}:{sh},crop={w}:{h}:'(iw-ow)*t/{dur}':'(ih-oh)/2'",
        # Pan droite → gauche, zoom fixe 1.15
        "pan_rl":   f"scale={sw}:{sh},crop={w}:{h}:'(iw-ow)*(1-t/{dur})':'(ih-oh)/2'",
        # Pan haut → bas, zoom fixe 1.15
        "pan_tb":   f"scale={sw}:{sh},crop={w}:{h}:'(iw-ow)/2':'(ih-oh)*t/{dur}'",
        # Diagonale haut-gauche → bas-droite, zoom fixe 1.15
        "pan_diag": f"scale={sw}:{sh},crop={w}:{h}:'(iw-ow)*t/{dur}':'(ih-oh)*t/{dur}'",
    }
    return moves[move]


def _generer_clip_kb(image_path: str, dest: str, move_idx: int, clip_sec: float = None, static: bool = False) -> None:
    """Génère un clip depuis une image. static=True → photo fixe sans zoompan."""
    sec  = float(clip_sec) if clip_sec is not None else float(_KB_CLIP_SEC)
    fade = min(0.8, sec * 0.07)
    if static:
        vf = f"scale=1536:864,fade=t=in:st=0:d={fade},fade=t=out:st={sec - fade}:d={fade}"
        label = f"Static — {os.path.basename(image_path)}"
    else:
        move = _KB_MOVES[move_idx % len(_KB_MOVES)]
        vf   = _kb_vf(move, sec)
        vf  += f",fade=t=in:st=0:d={fade},fade=t=out:st={sec - fade}:d={fade}"
        label = f"Ken Burns [{move}] — {os.path.basename(image_path)}"
    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-vf", vf,
            "-t", str(sec),
            "-r", str(_KB_FPS),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", dest,
        ],
        label,
        duree_estimee=sec * 1.5,
        timeout=20 * 60,
    )


def _preparer_clips_ken_burns(
    scenes_dir: str,
    clips_kb_dir: str,
    force: bool = False,
    ping_pong: bool = False,
    clip_sec: float = None,
    static: bool = False,
    zoom_only: bool = False,
) -> list:
    """Génère les clips Ken Burns depuis les images de scènes. Retourne la liste en ordre.
    clip_sec : durée par clip (calculée dynamiquement par generer_videos si None).
    ping_pong : chaque image génère 2 clips (aller + retour).
    """
    os.makedirs(clips_kb_dir, exist_ok=True)
    images = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
    if not images:
        raise FileNotFoundError(
            f"Aucune image scène dans {scenes_dir}\n"
            "Lancez d'abord l'étape visuelle (--visual-only --ken-burns)."
        )
    sec   = float(clip_sec) if clip_sec is not None else float(_KB_CLIP_SEC)
    moves = _KB_MOVES_ZOOM if zoom_only else _KB_MOVES
    pairs = _KB_PAIRS_ZOOM if zoom_only else _KB_PAIRS

    clips = []
    for i, img in enumerate(images, 1):
        if ping_pong:
            fwd, bwd = pairs[(i - 1) % len(pairs)]
            for suffix, move in (("a", fwd), ("b", bwd)):
                dest = os.path.join(clips_kb_dir, f"clip_{i:03d}{suffix}_kb.mp4")
                move_idx = moves.index(move)
                if os.path.exists(dest) and not force:
                    dur = _duree(dest)
                    # Invalidate cached clip if duration differs by more than 2s
                    if abs(dur - sec) > 2:
                        print(f"  → KB {i}{suffix} durée incompatible ({dur:.0f}s vs {sec:.0f}s requis) → regénération")
                        os.remove(dest)
                    else:
                        print(f"  → KB ping-pong {i}{suffix}/{len(images)} déjà présent ({dur:.1f}s) [{move}]")
                        clips.append(dest)
                        continue
                print(f"  → Ken Burns scène {i}{suffix}/{len(images)} [{move}] ({sec:.0f}s)...")
                _generer_clip_kb(img, dest, move_idx, clip_sec=sec, static=static)
                print(f"     → {os.path.basename(dest)} ({_duree(dest):.1f}s)")
                clips.append(dest)
        else:
            move = moves[(i - 1) % len(moves)]
            dest = os.path.join(clips_kb_dir, f"clip_{i:03d}_kb.mp4")
            if os.path.exists(dest) and not force:
                dur = _duree(dest)
                if abs(dur - sec) > 2:
                    print(f"  → KB {i} durée incompatible ({dur:.0f}s vs {sec:.0f}s requis) → regénération")
                    os.remove(dest)
                else:
                    label = "static" if static else move
                    print(f"  → clip {i}/{len(images)} déjà présent ({dur:.1f}s) [{label}]")
                    clips.append(dest)
                    continue
            mode_label = "Static" if static else f"Ken Burns [{move}]"
            print(f"  → {mode_label} scène {i}/{len(images)} ({sec:.0f}s)...")
            _generer_clip_kb(img, dest, i - 1, clip_sec=sec, static=static)
            print(f"     → {os.path.basename(dest)} ({_duree(dest):.1f}s)")
            clips.append(dest)
    return clips


# ─── Short vertical 9:16 ──────────────────────────────────────────────────────

def generer_short(track: dict, video_source: str, output_dir: str, force: bool = False) -> str:
    """
    Génère un short vertical 1080×1920 depuis la vidéo horizontale source.
    Utilise track['video']['short_clip'] (start_sec, duration_sec).
    Retourne le chemin du short, ou "" si pas configuré.
    """
    short_cfg = (track.get("video") or {}).get("short_clip")
    # Also support flat short_start field (new config format)
    if not short_cfg and track.get("short_start") is not None:
        short_cfg = {"start_sec": track["short_start"], "duration_sec": 55}
    if not short_cfg:
        return ""

    start = float(short_cfg.get("start_sec", 10))
    duration = float(short_cfg.get("duration_sec", 55))

    shorts_dir = os.path.join(output_dir, "shorts")
    os.makedirs(shorts_dir, exist_ok=True)
    slug = track["slug"]
    sortie = os.path.join(shorts_dir, f"{_slug_safe(slug)}_short.mp4")

    if os.path.exists(sortie) and not force:
        print(f"  → Short déjà présent : {os.path.basename(sortie)}")
        return sortie

    # Crop centre 9:16 puis scale à 1080×1920
    vf = "crop=ih*9/16:ih,scale=1080:1920"

    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_source,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            sortie,
        ],
        f"Short vertical 9:16 ({int(duration)}s)",
        duree_estimee=duration * 0.5,
        timeout=20 * 60,
    )

    taille = os.path.getsize(sortie) / (1024 * 1024)
    print(f"     📱 {os.path.basename(sortie)} ({taille:.1f} Mo)")
    return sortie


# ─── Entry point ──────────────────────────────────────────────────────────────

def generer_videos(track: dict, base_dir: str, force: bool = False, ken_burns: bool = False, **kwargs) -> list:
    """
    Génère le MP4 final pour un track.
    Retourne [chemin_mp4] (+ short si configuré, ajouté en fin de liste).
    """
    slug = track["slug"]
    mode = track.get("mode", "medium")
    input_dir = os.path.join(base_dir, track.get("input_folder", "input"))
    output_dir = _resolve_output_dir(base_dir, slug)
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(output_dir, exist_ok=True)

    mp3s = _lister_mp3(input_dir, slug)
    print(f"  → {len(mp3s)} MP3 trouvé(s)")

    # ─── Extraction des options vidéo ───────────────────────────────────────
    video_cfg = track.get("video") or {}
    # KB mode defaults: 2s intro + 3s outro if not explicitly set (re-encode ensures clean timestamps)
    intro_fade = float(video_cfg.get("intro_fade_sec", track.get("intro_fade_sec", 2.0 if ken_burns else 0)))
    outro_fade = float(video_cfg.get("outro_fade_sec", track.get("outro_fade_sec", 3.0 if ken_burns else 0)))
    title_card = video_cfg.get("title_card")
    end_card   = video_cfg.get("end_card")

    # ─── Mode individual : une vidéo par MP3 ────────────────────────────────
    if mode == "individual":
        image = os.path.join(output_dir, "scenes", "scene_001.png")
        if not os.path.exists(image):
            raise FileNotFoundError(f"Image scène 1 introuvable : {image}")
        videos = []
        for i, mp3 in enumerate(mp3s, 1):
            nom = os.path.splitext(os.path.basename(mp3))[0]
            sortie = os.path.join(output_dir, f"{_slug_safe(nom)}.mp4")
            if os.path.exists(sortie) and not force:
                print(f"  → [{i}] Déjà existant, ignoré.")
                videos.append(sortie)
                continue
            print(f"  → [{i}/{len(mp3s)}] {os.path.basename(mp3)}")
            _assembler_simple(image, mp3, sortie)
            print(f"     📹 {os.path.basename(sortie)} ({os.path.getsize(sortie) / 1024 / 1024:.1f} Mo)")
            videos.append(sortie)
        return videos

    # ─── Mode short : un seul MP4 avec premier MP3 ──────────────────────────
    if mode == "short":
        image = os.path.join(output_dir, "scenes", "scene_001.png")
        sortie = os.path.join(output_dir, f"{_slug_safe(slug)}.mp4")
        if os.path.exists(sortie) and not force:
            return [sortie]
        _assembler_simple(image, mp3s[0], sortie)
        print(f"     📹 {os.path.basename(sortie)} ({os.path.getsize(sortie) / 1024 / 1024:.1f} Mo)")
        return [sortie]

    # ─── Mode medium/long : pipeline narratif complet ───────────────────────
    durees_mp3 = [_duree(f) for f in mp3s]
    duree_cible = sum(d for d in durees_mp3 if d > 0)
    if duree_cible == 0:
        duree_cible = DUREES.get(mode, DUREES["medium"])
        print(f"  ⚠️  Durée MP3 illisible via ffprobe, fallback : {duree_cible/60:.0f} min")
    else:
        print(f"  → Durée cible depuis MP3 réels : {duree_cible/60:.1f} min ({duree_cible:.0f}s)")

    sortie = os.path.join(output_dir, f"{_slug_safe(slug)}.mp4")

    if os.path.exists(sortie) and not force:
        print(f"  → Déjà existant, ignoré : {os.path.basename(sortie)}")
        result = [sortie]
        short = generer_short(track, sortie, output_dir, force=force)
        if short:
            result.append(short)
        return result

    print("\n  ── A) Audio")
    audio_concat, duree_reelle = _concatener_audio(mp3s, duree_cible, output_dir)

    if ken_burns:
        static_mode  = kwargs.get("static", False)
        mode_label   = "Photos statiques" if static_mode else "Ken Burns (zoompan FFmpeg)"
        print(f"\n  ── B) Clips {mode_label}")
        scenes_dir   = os.path.join(output_dir, "scenes")
        clips_kb_dir = os.path.join(output_dir, "clips_kb")
        ping_pong    = kwargs.get("ping_pong", False) and not static_mode

        # Dynamic clip duration: all scenes visible at least once within the track duration.
        # min 8s/clip (fast transitions) → max 30s/clip (slow cinematic).
        n_images = len(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
        n_clips_expected = n_images * (2 if ping_pong else 1)
        if n_clips_expected > 0:
            clip_sec = max(8, min(_KB_CLIP_SEC, round(duree_reelle / n_clips_expected)))
        else:
            clip_sec = _KB_CLIP_SEC
        print(f"  → Durée clip KB : {clip_sec}s ({n_images} images × {'2 (ping-pong)' if ping_pong else '1'} = {n_clips_expected} clips pour {duree_reelle:.0f}s)")

        zoom_only = kwargs.get("zoom_only", False)
        clips_a_boucler = _preparer_clips_ken_burns(
            scenes_dir, clips_kb_dir, force=force, ping_pong=ping_pong, clip_sec=clip_sec, static=static_mode, zoom_only=zoom_only
        )
    else:
        print("\n  ── B) Ralentissement clips ×6")
        clips = _lister_clips(clips_dir)
        print(f"  → {len(clips)} clip(s) cinématiques trouvés (scènes en ordre)")
        clips_a_boucler = _preparer_clips_ralentis(clips, output_dir, force=force)

    print("\n  ── C) Boucle vidéo narrative")
    video_loop = _boucler_clips(clips_a_boucler, duree_reelle, output_dir)

    # ─── D) Lyrics Whisper (si activé) ─────────────────────────────────────
    lyrics_lines = None
    if track.get("lyrics"):
        from modules.lyrics import (
            transcrire_audio, sauver_timing, charger_timing, etendre_pour_boucle
        )
        timing_path = os.path.join(output_dir, "lyrics_timing.json")
        model_size  = track.get("lyrics_model", "base")

        if os.path.exists(timing_path) and not force:
            print(f"\n  ── D) Lyrics — cache trouvé ({timing_path})")
            raw_lines = charger_timing(timing_path)
        else:
            print(f"\n  ── D) Lyrics — transcription Whisper")
            raw_lines = transcrire_audio(mp3s[0], model_size=model_size)
            sauver_timing(raw_lines, timing_path)

        duree_mp3 = _duree(mp3s[0])
        lyrics_lines = etendre_pour_boucle(raw_lines, duree_mp3, duree_reelle)
        print(f"  → {len(raw_lines)} lignes × boucles → {len(lyrics_lines)} entrées overlay")

    step = "D"

    # ─── Cartes noires intro / outro ────────────────────────────────────────
    has_intro = title_card and title_card.get("enabled")
    has_outro = end_card   and end_card.get("enabled")
    w, h = 1536, 864

    intro_path = os.path.join(output_dir, "_intro_card.mp4")
    outro_path = os.path.join(output_dir, "_outro_card.mp4")
    main_path  = os.path.join(output_dir, "_main_video.mp4")

    if has_intro:
        print(f"\n  ── {step}) Intro card")
        step = chr(ord(step) + 1)
        _generer_carte_noire(
            dest=intro_path,
            texte=title_card.get("text", ""),
            sous_titre=title_card.get("subtitle", ""),
            duree=float(title_card.get("duration_sec", 5)),
            w=w, h=h, force=force,
        )

    if has_outro:
        print(f"\n  ── {step}) Outro card (CTA)")
        step = chr(ord(step) + 1)
        cta_parts = []
        if end_card.get("subscribe_cta"):
            cta_parts.append("Like & Subscribe  🔔")
        if end_card.get("text"):
            cta_parts.append(end_card["text"])
        cta_text    = "  ".join(cta_parts) or "Assirem Music PROD"
        cta_subtitle = "Assirem Music PROD • New music every week"
        _generer_carte_noire(
            dest=outro_path,
            texte=cta_text,
            sous_titre=cta_subtitle,
            duree=float(end_card.get("duration_sec", 8)),
            w=w, h=h, force=force,
        )

    # ─── Mixage principal (vidéo + audio + fades + lyrics) ──────────────────
    print(f"\n  ── {step}) Mixage final → {os.path.basename(main_path if (has_intro or has_outro) else sortie)}")
    step = chr(ord(step) + 1)
    if intro_fade or outro_fade:
        print(f"     ✨ Fade in {intro_fade}s / out {outro_fade}s")
    if lyrics_lines is not None:
        print(f"     🎤 Lyrics overlay : {len(lyrics_lines)} lignes")

    mix_dest = main_path if (has_intro or has_outro) else sortie
    _mixer(
        video_loop, audio_concat, mix_dest, duree_reelle,
        intro_fade=intro_fade,
        outro_fade=outro_fade,
        lyrics_lines=lyrics_lines,
    )

    # ─── Assemblage final : intro + main + outro ────────────────────────────
    if has_intro or has_outro:
        print(f"\n  ── {step}) Assemblage final (concat segments)")
        segments = []
        if has_intro:  segments.append(intro_path)
        segments.append(main_path)
        if has_outro:  segments.append(outro_path)
        _concatener_segments(segments, sortie, output_dir)

    for tmp in [audio_concat, video_loop, main_path]:
        if os.path.exists(tmp):
            os.remove(tmp)

    taille = os.path.getsize(sortie) / (1024 * 1024)
    print(f"\n     📹 {os.path.basename(sortie)} ({taille:.1f} Mo)")

    result = [sortie]

    # ─── E) Short vertical optionnel ────────────────────────────────────────
    short = generer_short(track, sortie, output_dir, force=force)
    if short:
        result.append(short)

    return result
