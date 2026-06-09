"""
Module lyrics.py — Forced alignment (stable-ts) + overlay lyrics vidéo

Workflow :
  1. aligner_lyrics(mp3, suno_lyrics_raw)  → timings ligne par ligne (stable-ts)
  2. sauver_timing / charger_timing        → cache JSON dans output/<slug>/
  3. etendre_pour_boucle()                 → répète sur toute la durée vidéo
  4. appliquer_lyrics(video, dest, lines)  → overlay PNG (sans libass)
"""

import os
import re
import json
import subprocess

# ── Helpers texte ──────────────────────────────────────────────────────────────

def nettoyer_lyrics(lyrics_raw: str) -> str:
    """Supprime [Section], lignes vides → texte chanté uniquement."""
    lines = []
    for line in lyrics_raw.split("\n"):
        line = line.strip()
        if not line or re.match(r"^\[.+\]$", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _lignes_lyrics(lyrics_raw: str) -> list:
    return [l for l in nettoyer_lyrics(lyrics_raw).split("\n") if l.strip()]


# ── Cache ──────────────────────────────────────────────────────────────────────

def sauver_timing(lines: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=2)


def charger_timing(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Alignment principal ────────────────────────────────────────────────────────

def aligner_lyrics(mp3_path: str, suno_lyrics_raw: str,
                   model_size: str = "small",
                   cache_path: str = None) -> list:
    """
    Forced alignment via stable-ts : aligne les paroles connues sur l'audio.
    Retourne [{"text": str, "start": float, "end": float}, ...] par ligne.
    Cache dans cache_path si fourni.
    """
    if cache_path and os.path.exists(cache_path):
        lines = charger_timing(cache_path)
        print(f"  → Cache alignment : {len(lines)} lignes")
        return lines

    try:
        import stable_whisper
    except ImportError:
        raise ImportError("stable-ts non installé. Lancez : pip install stable-ts")

    lignes = _lignes_lyrics(suno_lyrics_raw)
    if not lignes:
        return []

    texte = "\n".join(lignes)
    print(f"  → stable-ts align ({model_size}) — {len(lignes)} lignes sur {os.path.basename(mp3_path)}...")

    model = stable_whisper.load_model(model_size)

    # align() requiert une langue explicite — détection rapide d'abord
    detect = model.transcribe(mp3_path, fp16=False, verbose=False)
    lang   = getattr(detect, "language", None) or "en"
    print(f"  → Langue détectée : {lang}")

    result = model.align(mp3_path, texte, language=lang)

    # Extraire les segments — filtrer les entrées à durée nulle (audio trop court)
    out = []
    for seg in result.segments:
        text = seg.text.strip()
        if not text:
            continue
        start = round(float(seg.start), 2)
        end   = round(float(seg.end),   2)
        if end - start < 0.15:   # durée trop courte = alignement raté
            continue
        out.append({"text": text, "start": start, "end": end})

    if not out:
        return []

    print(f"  → {len(out)} ligne(s) alignée(s) (/{len(result.segments)} segments)")

    if cache_path:
        sauver_timing(out, cache_path)
        print(f"  → Cache sauvé : {os.path.basename(cache_path)}")

    return out


def lyrics_proportionnels(suno_lyrics_raw: str, duree_mp3: float) -> list:
    """
    Fallback : timing proportionnel quand l'alignment échoue.
    Chaque ligne occupe duree_mp3 / nb_lignes secondes.
    """
    lignes = _lignes_lyrics(suno_lyrics_raw)
    if not lignes:
        return []
    tpl = duree_mp3 / len(lignes)
    return [
        {
            "text":  ligne,
            "start": round(i * tpl, 2),
            "end":   round((i + 1) * tpl - 0.1, 2),
        }
        for i, ligne in enumerate(lignes)
    ]


# ── Extension boucle ───────────────────────────────────────────────────────────

def etendre_pour_boucle(lines: list, duree_mp3: float, duree_totale: float) -> list:
    """Répète les timings à chaque boucle du MP3 pour couvrir duree_totale."""
    if not lines or duree_mp3 <= 0:
        return lines
    extended = []
    offset = 0.0
    while offset < duree_totale:
        for line in lines:
            t_s = line["start"] + offset
            t_e = line["end"]   + offset
            if t_s >= duree_totale:
                break
            extended.append({
                "text":  line["text"],
                "start": round(t_s, 2),
                "end":   round(min(t_e, duree_totale), 2),
            })
        offset += duree_mp3
    return extended


# ── Génération ASS (référence / archivage) ────────────────────────────────────

def _fmt_ass_time(sec: float) -> str:
    h  = int(sec // 3600); m  = int((sec % 3600) // 60)
    s  = int(sec % 60);    cs = int(round((sec - int(sec)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generer_ass(lines: list, path: str, w: int = 1536, h: int = 864,
                font_size: int = 52) -> None:
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,2,1,2,10,10,40,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        for line in lines:
            text = line["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
            f.write(f"Dialogue: 0,{_fmt_ass_time(line['start'])},{_fmt_ass_time(line['end'])},Default,,0,0,0,,{text}\n")
    print(f"  → ASS : {os.path.basename(path)} ({len(lines)} lignes)")


# ── Rendu PNG lyrics video (sans libass) ──────────────────────────────────────

def _charger_font(size: int):
    """Futura (moderne/clip) → GillSans → SF Pro → Arial → fallback."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for candidate in [
        "/System/Library/Fonts/Supplemental/Futura.ttc",          # primary
        "/System/Library/Fonts/Supplemental/GillSans.ttc",        # fallback 1
        "/System/Library/Fonts/Supplemental/SFNS.ttf",            # fallback 2
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw) -> str:
    """Coupe le texte en lignes pour qu'il tienne dans max_width pixels."""
    words = text.split()
    if not words:
        return text
    lines_out, current = [], words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        if (draw.textbbox((0, 0), test, font=font)[2]) > max_width:
            lines_out.append(current)
            current = word
        else:
            current = test
    lines_out.append(current)
    return "\n".join(lines_out)


def _pill(draw, x0, y0, x1, y1, radius: int, fill):
    """Rounded rectangle compatible Pillow < 8.2."""
    try:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)
    except AttributeError:
        draw.rectangle([x0, y0, x1, y1], fill=fill)


def _generer_lyrics_pngs(lines: list, tmp_dir: str,
                          w: int = 1536, h: int = 864,
                          font_size: int = 50) -> list:
    """
    Génère un PNG RGBA par ligne — style lyrics vidéo chic :
    - Futura, taille 50, texte automatiquement wrappé pour rester dans le cadre
    - Pill sombre centrée (pas pleine largeur), ombre 1px
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise ImportError("Pillow requis. Lancez : pip install pillow")

    os.makedirs(tmp_dir, exist_ok=True)
    cache: dict = {}
    paths: list = []
    max_text_w  = w - 120   # 60px marge de chaque côté

    for i, line in enumerate(lines):
        text = line["text"]
        if text in cache:
            paths.append(cache[text])
            continue

        png_path = os.path.join(tmp_dir, f"line_{i:04d}.png")
        img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = _charger_font(font_size)

        # Wrap si trop large
        wrapped = _wrap_text(text, font, max_text_w, draw)
        n_lines  = wrapped.count("\n") + 1

        # Mesurer le bloc multi-lignes
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        x = (w - tw) // 2
        y = h - th - 90    # lower third

        # Pill centrée
        pad_x, pad_y = 36, 10
        _pill(draw, x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y,
              radius=8, fill=(0, 0, 0, 155))

        # Ombre + texte
        draw.multiline_text((x + 1, y + 1), wrapped, font=font,
                            fill=(0, 0, 0, 120), spacing=8, align="center")
        draw.multiline_text((x, y), wrapped, font=font,
                            fill=(255, 255, 255, 255), spacing=8, align="center")

        img.save(png_path, "PNG")
        cache[text] = png_path
        paths.append(png_path)

    return paths


def _generer_card_png(path: str, lines_text: list, w: int = 1536, h: int = 864,
                      font_size_title: int = 54, font_size_sub: int = 32,
                      style: str = "info") -> None:
    """
    Génère un PNG overlay pour carte d'intro ou CTA finale.
    style='info'  → présentation du morceau (fond semi-transparent, titre centré)
    style='cta'   → like/subscribe (pill sobre en bas)
    """
    from PIL import Image, ImageDraw
    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if style == "info":
        # Fond semi-transparent sur toute la hauteur basse
        draw.rectangle([0, h // 2, w, h], fill=(0, 0, 0, 160))
        y_cursor = h // 2 + 28
        for j, (txt, size) in enumerate(lines_text):
            font  = _charger_font(size)
            bbox  = draw.textbbox((0, 0), txt, font=font)
            tw    = bbox[2] - bbox[0]
            x     = (w - tw) // 2
            draw.text((x + 1, y_cursor + 1), txt, font=font, fill=(0, 0, 0, 100))
            color = (255, 220, 100, 255) if j == 0 else (220, 220, 220, 255)
            draw.text((x, y_cursor), txt, font=font, fill=color)
            y_cursor += (bbox[3] - bbox[1]) + 14

    elif style == "cta":
        # Pill sobre centrée en bas
        y_base = h - 180
        for j, (txt, size) in enumerate(lines_text):
            font  = _charger_font(size)
            max_w = w - 120
            wrapped = _wrap_text(txt, font, max_w, draw)
            bbox  = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (w - tw) // 2
            _pill(draw, x - 36, y_base - 10, x + tw + 36, y_base + th + 10,
                  radius=8, fill=(0, 0, 0, 170))
            draw.multiline_text((x + 1, y_base + 1), wrapped, font=font,
                                fill=(0, 0, 0, 100), spacing=6, align="center")
            color = (255, 220, 80, 255) if j == 0 else (220, 220, 220, 255)
            draw.multiline_text((x, y_base), wrapped, font=font,
                                fill=color, spacing=6, align="center")
            y_base += th + 22

    img.save(path, "PNG")


def _png_to_silent_mp4(png_path: str, mp4_path: str, duree: float,
                        w: int = 1536, h: int = 864,
                        fade_out: bool = True) -> None:
    """Convertit un PNG en vidéo silencieuse (carte noire) via FFmpeg."""
    vf = f"fade=t=in:st=0:d=0.4"
    if fade_out:
        vf += f",fade=t=out:st={duree - 0.4}:d=0.4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duree),
        mp4_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"PNG→MP4 error : {proc.stderr[-800:]}")


def _generer_carte_lyrics(tmp_dir: str, track_info: dict,
                            w: int = 1536, h: int = 864) -> tuple:
    """
    Génère les segments MP4 noirs intro + outro pour le WITH_LYRICS.
    Retourne (intro_mp4_path, outro_mp4_path, intro_dur, outro_dur).
    """
    from PIL import Image, ImageDraw

    def _black_card(png_path, text_rows):
        img  = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        total_h = sum(draw.textbbox((0,0), t, font=_charger_font(s))[3] + 16
                      for t, s in text_rows)
        y = (h - total_h) // 2
        for j, (txt, size) in enumerate(text_rows):
            font = _charger_font(size)
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw   = bbox[2] - bbox[0]
            th   = bbox[3] - bbox[1]
            x    = (w - tw) // 2
            draw.text((x + 1, y + 1), txt, font=font, fill=(0, 0, 0, 180))
            color = (255, 215, 80) if j == 0 else (210, 210, 210)
            draw.text((x, y), txt, font=font, fill=color)
            y += th + 16
        img.save(png_path, "PNG")

    os.makedirs(tmp_dir, exist_ok=True)

    # Intro : titre + style + Assirem Music PROD
    intro_rows = []
    if track_info.get("tribute"):
        intro_rows.append((track_info["tribute"], 30))
    intro_rows.append((track_info.get("title", "Assirem Music PROD"), 56))
    if track_info.get("style"):
        intro_rows.append((track_info["style"], 28))
    intro_rows.append(("♪  Assirem Music PROD", 24))

    intro_png = os.path.join(tmp_dir, "_intro_card.png")
    intro_mp4 = os.path.join(tmp_dir, "_intro_card.mp4")
    _black_card(intro_png, intro_rows)
    intro_dur = 6.0
    _png_to_silent_mp4(intro_png, intro_mp4, intro_dur, w, h, fade_out=False)

    # Outro : CTA like/subscribe
    outro_rows = [
        ("👍  Like & Subscribe", 52),
        ("🔔  Turn on notifications", 34),
        ("Support Assirem Music PROD — Free music, forever", 24),
    ]
    outro_png = os.path.join(tmp_dir, "_outro_card.png")
    outro_mp4 = os.path.join(tmp_dir, "_outro_card.mp4")
    _black_card(outro_png, outro_rows)
    outro_dur = 7.0
    _png_to_silent_mp4(outro_png, outro_mp4, outro_dur, w, h)

    return intro_mp4, outro_mp4, intro_dur, outro_dur


def _concat_mp4s(segments: list, dest: str) -> None:
    """Concatène plusieurs MP4 via FFmpeg concat filter (PTS toujours corrects)."""
    n = len(segments)
    inputs = []
    for seg in segments:
        inputs += ["-i", seg]
    stream_tags = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{stream_tags}concat=n={n}:v=1:a=1[vout][aout]"
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        dest,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"Concat error : {proc.stderr[-800:]}")


def appliquer_lyrics(
    video_path: str,
    dest_path: str,
    lines: list,
    tmp_dir: str = None,
    font_size: int = 50,
    track_info: dict = None,
    video_dur: float = 0.0,
) -> None:
    """
    Génère le WITH_LYRICS video :
    [carte_intro_noire] + [vidéo_avec_lyrics] + [carte_outro_noire_CTA]

    Les cartes sont des segments MP4 noirs séparés — elles ne s'écrasent
    jamais sur la vidéo ou les lyrics.
    track_info : {"title", "style", "tribute"}
    """
    if not lines:
        raise ValueError("appliquer_lyrics() nécessite une liste de lignes non vide")

    if tmp_dir is None:
        tmp_dir = os.path.join(os.path.dirname(dest_path), "_lyrics_pngs")
    os.makedirs(tmp_dir, exist_ok=True)

    # ── 1. PNGs lyrics + overlay sur la vidéo principale ─────────────────────
    png_paths   = _generer_lyrics_pngs(lines, tmp_dir, font_size=font_size)
    unique_pngs = list(dict.fromkeys(png_paths))
    png_index   = {p: i + 1 for i, p in enumerate(unique_pngs)}

    inputs = ["-i", video_path]
    for p in unique_pngs:
        inputs += ["-i", p]

    parts = []
    prev  = "0:v"
    for idx, (line, png_path) in enumerate(zip(lines, png_paths)):
        label  = f"v{idx + 1}"
        stream = png_index[png_path]
        t_s, t_e = line["start"], line["end"]
        parts.append(
            f"[{prev}][{stream}:v]overlay=0:0"
            f":enable='between(t,{t_s},{t_e})'[{label}]"
        )
        prev = label

    # Vidéo principale avec lyrics (temp si on concat après)
    use_cards = bool(track_info)
    main_dest = os.path.join(tmp_dir, "_main_with_lyrics.mp4") if use_cards else dest_path

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(parts),
        "-map", f"[{prev}]",
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        main_dest,
    ]

    print(f"  → Overlay lyrics ({len(lines)} lignes, {len(unique_pngs)} PNGs)...")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error :\n{proc.stderr[-2000:]}")

    # ── 2. Cartes noires (intro + outro) + concat ─────────────────────────────
    if use_cards:
        print("  → Génération cartes noires intro/outro...")
        intro_mp4, outro_mp4, _, _ = _generer_carte_lyrics(tmp_dir, track_info)
        print("  → Concatenation finale...")
        _concat_mp4s([intro_mp4, main_dest, outro_mp4], dest_path)

    taille = os.path.getsize(dest_path) // (1024 * 1024)
    print(f"  ✅ Lyrics vidéo ({taille} Mo) → {os.path.basename(dest_path)}")
