"""
thumbnail.py — Génération de thumbnails YouTube pour Assirem Music PROD.

Pipeline :
  1. Charger le preset visuel du tier (genre musical) depuis tier_presets.json
  2. Générer un fond atmosphérique via Leonardo AI (1280x720)
  3. Composer l'overlay final via PIL (titre + durée + logo + bordure tier)

Intégration :
    from modules.thumbnail import build_thumbnail
    thumb_path = build_thumbnail(
        track_title="Late Night Reggae",
        duration_label="2 HOURS",
        usage="studying",
        tier="reggae",
        output_dir="./output/late_night_reggae/",
    )
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

MODULE_DIR  = Path(__file__).parent
PRESETS_PATH = MODULE_DIR / "tier_presets.json"
ASSETS_DIR  = MODULE_DIR.parent / "assets"           # racine du projet / assets/
LOGO_PATH   = ASSETS_DIR / "amp_logo.png"
FONT_REGULAR = ASSETS_DIR / "Montserrat-Bold.ttf"
FONT_BOLD    = ASSETS_DIR / "Montserrat-Black.ttf"

THUMB_WIDTH  = 1280
THUMB_HEIGHT = 720

LEONARDO_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
LEONARDO_KEY_PATH = MODULE_DIR.parent / "credentials" / "leonardo.key"

# Module-level preset cache — évite de relire le JSON pour chaque track.
_PRESETS_CACHE: dict | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class ThumbnailSpec:
    track_title: str
    duration_label: str
    usage: str
    tier: str
    output_dir: Path
    custom_prompt_suffix: str = ""


def _load_presets() -> dict:
    global _PRESETS_CACHE
    if _PRESETS_CACHE is None:
        with open(PRESETS_PATH, "r", encoding="utf-8") as f:
            _PRESETS_CACHE = json.load(f)
    return _PRESETS_CACHE


def _load_leonardo_key() -> str:
    if not LEONARDO_KEY_PATH.exists():
        raise FileNotFoundError(f"Clé Leonardo introuvable : {LEONARDO_KEY_PATH}")
    return LEONARDO_KEY_PATH.read_text().strip()


# ---------------------------------------------------------------------------
# Étape 1 : génération du fond via Leonardo
# ---------------------------------------------------------------------------

def generate_background(
    spec: ThumbnailSpec,
    preset: dict,
    model_id: str = "aa77f04e-3eec-4034-9c07-d0f619684628",  # Leonardo Kino XL
    poll_attempts: int = 30,
) -> Path:
    """Génère un fond atmosphérique 1280×720 via Leonardo AI."""
    api_key = _load_leonardo_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    base_prompt    = preset["leonardo_prompt"]
    usage_modifier = preset.get("default_usage_modifiers", {}).get(spec.usage, "")
    full_prompt    = f"{base_prompt}{usage_modifier}{spec.custom_prompt_suffix}".strip()
    LOGGER.info("Leonardo prompt → %s…", full_prompt[:120])

    # 1) Lancer la génération
    payload = {
        "prompt":          full_prompt,
        "negative_prompt": preset.get("leonardo_negative_prompt", ""),
        "modelId":         model_id,
        "width":           THUMB_WIDTH,
        "height":          THUMB_HEIGHT,
        "num_images":      1,
        "guidance_scale":  7,
        "presetStyle":     "CINEMATIC",
        "alchemy":         True,
        "photoReal":       False,
    }
    r = requests.post(
        f"{LEONARDO_BASE_URL}/generations", json=payload, headers=headers, timeout=30
    )
    r.raise_for_status()
    generation_id = r.json()["sdGenerationJob"]["generationId"]
    LOGGER.info("Leonardo job lancé : %s", generation_id)

    # 2) Polling jusqu'à complétion
    image_url = None
    for _ in range(poll_attempts):
        time.sleep(3)
        poll = requests.get(
            f"{LEONARDO_BASE_URL}/generations/{generation_id}",
            headers=headers,
            timeout=15,
        )
        poll.raise_for_status()
        gen = poll.json()["generations_by_pk"]
        if gen["status"] == "COMPLETE" and gen["generated_images"]:
            image_url = gen["generated_images"][0]["url"]
            break
        if gen["status"] == "FAILED":
            raise RuntimeError(f"Leonardo a échoué : {gen}")

    if not image_url:
        raise TimeoutError(f"Leonardo n'a pas répondu en {poll_attempts * 3}s")

    # 3) Télécharger l'image (3 tentatives)
    raw_path = spec.output_dir / f"{_sanitize(spec.track_title)}_raw.png"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            img_data = requests.get(image_url, timeout=30).content
            raw_path.write_bytes(img_data)
            break
        except requests.RequestException as e:
            if attempt == 2:
                raise RuntimeError(f"Téléchargement fond Leonardo échoué : {e}") from e
            LOGGER.warning("Téléchargement échoué (tentative %d/3) : %s", attempt + 1, e)
            time.sleep(2)

    LOGGER.info("Fond téléchargé : %s", raw_path)
    return raw_path


# ---------------------------------------------------------------------------
# Étape 2 : composition de l'overlay via PIL
# ---------------------------------------------------------------------------

def compose_overlay(background_path: Path, spec: ThumbnailSpec, preset: dict) -> Path:
    """Compose le thumbnail final : fond + gradient + texte + logo + bordure."""
    img = Image.open(background_path).convert("RGBA")
    if img.size != (THUMB_WIDTH, THUMB_HEIGHT):
        img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)

    # --- Gradient sombre plus large et plus dense ---
    gradient = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)
    gradient_height = 400
    for y in range(THUMB_HEIGHT - gradient_height, THUMB_HEIGHT):
        ratio = (y - (THUMB_HEIGHT - gradient_height)) / gradient_height
        alpha = int(215 * (ratio ** 1.1))
        grad_draw.rectangle([(0, y), (THUMB_WIDTH, y + 1)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, gradient)

    # --- Préparer polices et mesures avant de dessiner ---
    draw = ImageDraw.Draw(img)

    duration_font = _load_font(FONT_BOLD, size=120)
    duration_text = spec.duration_label.upper()
    duration_pos  = _center_text(draw, duration_text, duration_font, y=THUMB_HEIGHT - 285)

    title_font = _load_font(FONT_REGULAR, size=64)
    title_text = spec.track_title
    while title_font.getlength(title_text) > THUMB_WIDTH - 160 and title_font.size > 36:
        title_font = _load_font(FONT_REGULAR, size=title_font.size - 4)
    title_pos = _center_text(draw, title_text, title_font, y=THUMB_HEIGHT - 145)

    # --- Backdrop semi-transparent derrière le bloc texte ---
    dur_bbox   = draw.textbbox(duration_pos, duration_text, font=duration_font)
    title_bbox = draw.textbbox(title_pos,    title_text,    font=title_font)
    pad_x, pad_y = 44, 20
    bx1 = min(dur_bbox[0], title_bbox[0]) - pad_x
    by1 = dur_bbox[1] - pad_y
    bx2 = max(dur_bbox[2], title_bbox[2]) + pad_x
    by2 = title_bbox[3] + pad_y

    backdrop = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd       = ImageDraw.Draw(backdrop)
    try:
        bd.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=18, fill=(0, 0, 0, 135))
    except AttributeError:
        bd.rectangle([(bx1, by1), (bx2, by2)], fill=(0, 0, 0, 135))
    img  = Image.alpha_composite(img, backdrop)
    draw = ImageDraw.Draw(img)

    # --- Texte avec ombre forte 8 directions ---
    duration_color = tuple(preset["text_color"]) + (255,)
    title_color    = tuple(preset["text_color"]) + (255,)
    shadow_color   = tuple(preset["shadow_color"]) + (230,)

    _draw_text_with_shadow(draw, duration_pos, duration_text, duration_font, duration_color, shadow_color, shadow_offset=5)
    _draw_text_with_shadow(draw, title_pos,    title_text,    title_font,    title_color,    shadow_color, shadow_offset=4)

    # --- Logo AMP en bas-droite ---
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = 110
        logo  = logo.resize((logo_size, logo_size), Image.LANCZOS)
        alpha = logo.split()[3].point(lambda p: int(p * 0.85))
        logo.putalpha(alpha)
        img.paste(logo, (THUMB_WIDTH - logo_size - 36, THUMB_HEIGHT - logo_size - 36), logo)
    else:
        LOGGER.warning("Logo introuvable à %s — thumbnail sans logo", LOGO_PATH)

    # --- Bordure couleur tier ---
    border_color = tuple(preset["border_color"]) + (preset.get("border_alpha", 230),)
    border = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rectangle([(0, 0), (THUMB_WIDTH - 1, THUMB_HEIGHT - 1)], outline=border_color, width=6)
    img = Image.alpha_composite(img, border)

    final_path = spec.output_dir / f"{_sanitize(spec.track_title)}_thumb.png"
    img.convert("RGB").save(final_path, "PNG", optimize=True)
    LOGGER.info("Thumbnail final : %s", final_path)
    return final_path


# ---------------------------------------------------------------------------
# Helpers PIL
# ---------------------------------------------------------------------------

def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if path.exists():
        return ImageFont.truetype(str(path), size=size)
    LOGGER.warning("Police introuvable %s — fallback PIL (rendu dégradé)", path)
    return ImageFont.load_default(size=size)


def _center_text(draw: ImageDraw.ImageDraw, text: str, font, y: int) -> tuple[int, int]:
    text_width = draw.textlength(text, font=font)
    return (int((THUMB_WIDTH - text_width) // 2), y)


def _draw_text_with_shadow(draw, pos, text, font, fill_color, shadow_color, shadow_offset=5):
    """Stroke 8-directions pour lisibilité maximale sur tout fond."""
    x, y = pos
    for dx in (-shadow_offset, 0, shadow_offset):
        for dy in (-shadow_offset, 0, shadow_offset):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill_color)


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name).lower()


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def build_thumbnail(
    track_title: str,
    duration_label: str,
    usage: str,
    tier: str,
    output_dir: str | Path,
    custom_prompt_suffix: str = "",
    keep_raw: bool = False,
    poll_attempts: int = 30,
) -> Path:
    """
    Génère un thumbnail YouTube 1280×720 et retourne son chemin.

    Args:
        track_title:          titre affiché (ex: "Late Night Reggae")
        duration_label:       durée en gros (ex: "2 HOURS", "1 HOUR")
        usage:                clé d'usage (ex: "studying", "focus", "sleeping")
        tier:                 clé du tier dans tier_presets.json
        output_dir:           dossier de sortie
        custom_prompt_suffix: ajout libre au prompt Leonardo
        keep_raw:             si True, garde l'image Leonardo brute
        poll_attempts:        nombre max de tentatives de polling (3s/tentative)
    """
    output_dir = Path(output_dir)
    presets = _load_presets()
    if tier not in presets:
        raise ValueError(f"Tier inconnu : '{tier}'. Disponibles : {list(presets.keys())}")
    preset = presets[tier]

    spec = ThumbnailSpec(
        track_title=track_title,
        duration_label=duration_label,
        usage=usage,
        tier=tier,
        output_dir=output_dir,
        custom_prompt_suffix=custom_prompt_suffix,
    )

    LOGGER.info("=== Build thumbnail : %s [%s/%s] ===", track_title, tier, usage)
    bg_path    = generate_background(spec, preset, poll_attempts=poll_attempts)
    final_path = compose_overlay(bg_path, spec, preset)

    if not keep_raw:
        bg_path.unlink(missing_ok=True)

    return final_path


# ---------------------------------------------------------------------------
# CLI pour test manuel
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Génère un thumbnail YouTube AMP")
    parser.add_argument("--title",    required=True)
    parser.add_argument("--duration", required=True, help="ex: '2 HOURS'")
    parser.add_argument("--usage",    default="focus")
    parser.add_argument("--tier",     required=True,
                        choices=["reggae", "world", "afro", "latin", "maghreb"])
    parser.add_argument("--output",   default="./output/thumbnails/")
    parser.add_argument("--keep-raw", action="store_true")
    parser.add_argument("--suffix",   default="")
    args = parser.parse_args()

    result = build_thumbnail(
        track_title=args.title,
        duration_label=args.duration,
        usage=args.usage,
        tier=args.tier,
        output_dir=args.output,
        custom_prompt_suffix=args.suffix,
        keep_raw=args.keep_raw,
    )
    print(f"\n✓ Thumbnail prêt : {result}")
