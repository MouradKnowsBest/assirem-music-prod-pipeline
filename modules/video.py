"""
Module video.py — Assemblage vidéo cinématique par track

Workflow medium/long :
  A) Concat MP3 depuis input/<slug>/ (ou input/ en fallback) → audio N min
  B) Ralentit les clips de scène ×6 (~5s → ~30s) → clips_slow/
  C) Boucle les clips ralentis EN ORDRE (narratif) → vidéo loop
  D) Mixe vidéo + audio + fade in/out + title_card + end_card → output/<slug>/<slug>.mp4
  E) (optionnel) Génère un short vertical 9:16 → output/<slug>/shorts/<slug>_short.mp4
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
        return "drawtext" in result.stdout
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

    liste = list(clips)
    cumul_total = total
    while cumul_total < duree_cible:
        liste.extend(clips)
        cumul_total += total

    clips_finaux, cumul = [], 0.0
    durees_ext = durees * ((len(liste) // len(clips)) + 2)
    for c, d in zip(liste, durees_ext):
        if cumul >= duree_cible:
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
    _run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", liste_path,
            "-t", str(duree_cible),
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
    title_card: dict = None,
    end_card: dict = None,
) -> str:
    """
    Construit la chaîne de filtres vidéo :
    fade in/out + drawtext title_card + drawtext end_card.
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

    # Title card (texte affiché pendant les N premières secondes)
    if title_card and title_card.get("enabled") and _check_drawtext():
        dur = float(title_card.get("duration_sec", 3))
        text = _escape_drawtext(title_card.get("text", ""))
        subtitle = _escape_drawtext(title_card.get("subtitle", ""))
        if text:
            filtres.append(
                f"drawtext={font_arg}text='{text}':"
                f"fontsize=72:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-40:"
                f"shadowcolor=black:shadowx=2:shadowy=2:"
                f"enable='lt(t,{dur})'"
            )
        if subtitle:
            filtres.append(
                f"drawtext={font_arg}text='{subtitle}':"
                f"fontsize=36:fontcolor=white@0.85:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+40:"
                f"shadowcolor=black:shadowx=1:shadowy=1:"
                f"enable='lt(t,{dur})'"
            )

    # End card (texte affiché pendant les M dernières secondes)
    if end_card and end_card.get("enabled") and _check_drawtext():
        dur = float(end_card.get("duration_sec", 5))
        start_t = max(0.0, duree - dur)
        msg_parts = []
        if end_card.get("subscribe_cta"):
            msg_parts.append("👍 SUBSCRIBE for more music")
        custom = end_card.get("text", "")
        if custom:
            msg_parts.append(custom)
        msg = " — ".join(msg_parts) or "Assirem Music PROD"
        msg = _escape_drawtext(msg)
        filtres.append(
            f"drawtext={font_arg}text='{msg}':"
            f"fontsize=60:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"box=1:boxcolor=black@0.6:boxborderw=20:"
            f"enable='gt(t,{start_t})'"
        )

    return ",".join(filtres)


def _mixer(
    video: str,
    audio: str,
    sortie: str,
    duree: float,
    intro_fade: float = 0,
    outro_fade: float = 0,
    title_card: dict = None,
    end_card: dict = None,
) -> None:
    vf = _build_video_filter(duree, intro_fade, outro_fade, title_card, end_card)
    # Si on a des filtres vidéo, on doit ré-encoder la vidéo ; sinon copy direct.
    if vf:
        video_args = ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-vf", vf]
    else:
        video_args = ["-c:v", "copy"]

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
        duree_estimee=30 if not vf else duree * 0.05,
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


# ─── Short vertical 9:16 ──────────────────────────────────────────────────────

def generer_short(track: dict, video_source: str, output_dir: str, force: bool = False) -> str:
    """
    Génère un short vertical 1080×1920 depuis la vidéo horizontale source.
    Utilise track['video']['short_clip'] (start_sec, duration_sec).
    Retourne le chemin du short, ou "" si pas configuré.
    """
    short_cfg = (track.get("video") or {}).get("short_clip")
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

def generer_videos(track: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère le MP4 final pour un track.
    Retourne [chemin_mp4] (+ short si configuré, ajouté en fin de liste).
    """
    slug = track["slug"]
    mode = track.get("mode", "medium")
    input_dir = os.path.join(base_dir, track.get("input_folder", "input"))
    output_dir = os.path.join(base_dir, "output", slug)
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(output_dir, exist_ok=True)

    mp3s = _lister_mp3(input_dir, slug)
    print(f"  → {len(mp3s)} MP3 trouvé(s)")

    # ─── Extraction des options vidéo ───────────────────────────────────────
    video_cfg = track.get("video") or {}
    intro_fade = float(video_cfg.get("intro_fade_sec", 0))
    outro_fade = float(video_cfg.get("outro_fade_sec", 0))
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

    print("\n  ── B) Ralentissement clips ×6")
    clips = _lister_clips(clips_dir)
    print(f"  → {len(clips)} clip(s) cinématiques trouvés (scènes en ordre)")
    clips_lents = _preparer_clips_ralentis(clips, output_dir, force=force)

    print("\n  ── C) Boucle vidéo narrative")
    video_loop = _boucler_clips(clips_lents, duree_reelle, output_dir)

    print(f"\n  ── D) Mixage final → {os.path.basename(sortie)}")
    if intro_fade or outro_fade:
        print(f"     ✨ Fade in {intro_fade}s / out {outro_fade}s")
    if title_card and title_card.get("enabled"):
        print(f"     🎬 Title card : \"{title_card.get('text','')}\"")
    if end_card and end_card.get("enabled"):
        print(f"     📢 End card (CTA subscribe)")
    _mixer(
        video_loop, audio_concat, sortie, duree_reelle,
        intro_fade=intro_fade,
        outro_fade=outro_fade,
        title_card=title_card,
        end_card=end_card,
    )

    for tmp in [audio_concat, video_loop]:
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
