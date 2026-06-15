#!/usr/bin/env python3
"""
auto_json.py — Génère le JSON config d'un track pour le pipeline Assirem

Depuis un slug (= nom de fichier sans extension), génère un track JSON complet
au format pipeline (config.json > tracks[]).

Sans --use-claude : génère un template intelligent basé sur le slug.
Avec  --use-claude : appelle Claude Haiku pour générer titre, description, tags et scènes.

Usage :
  python scripts/auto_json.py lofi-coffee-shop
  python scripts/auto_json.py --use-claude lofi-coffee-shop
  python scripts/auto_json.py --use-claude --genre "lofi hip hop" lofi-coffee-shop
  python scripts/auto_json.py --batch ./stock           # traite tous les slugs sans JSON
  python scripts/auto_json.py --batch ./stock --use-claude

Sortie :
  ./stock/<slug>/<slug>.json  (ou --output pour un chemin custom)
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _slugify_to_title(slug: str) -> str:
    """lofi-coffee-shop  →  Lofi Coffee Shop"""
    words = re.split(r"[-_]+", slug)
    return " ".join(w.capitalize() for w in words if w)


def _detect_genre(slug: str, genre_hint: str = "") -> str:
    """Déduit un genre depuis le slug ou le hint."""
    if genre_hint:
        return genre_hint
    slug_lower = slug.lower()
    GENRE_MAP = {
        "lofi": "lofi hip hop",
        "jazz": "jazz",
        "classical": "classical",
        "ambient": "ambient",
        "chillout": "chillout",
        "chill": "chill",
        "trap": "trap",
        "rai": "raï",
        "chaabi": "chaâbi",
        "blues": "blues",
        "rock": "rock",
        "folk": "folk",
        "reggae": "reggae",
        "afro": "afrobeat",
        "latin": "latin",
        "piano": "piano instrumental",
        "guitar": "acoustic guitar",
        "drone": "ambient drone",
        "epic": "epic orchestral",
        "cinematic": "cinematic orchestral",
        "meditation": "meditation",
        "sleep": "sleep music",
        "study": "study music",
    }
    for keyword, genre in GENRE_MAP.items():
        if keyword in slug_lower:
            return genre
    return "music"


def _make_template_track(slug: str, genre: str) -> dict:
    """Génère un track JSON template sans IA."""
    title = _slugify_to_title(slug)
    return {
        "slug": slug,
        "mode": "medium",
        "title": f"{title} | Assirem Music PROD",
        "description": (
            f"{title} — {genre} music.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Intro\n\n"
            f"🎧 Best for: {genre}, focus, relaxation\n\n"
            f"#{genre.replace(' ', '')} #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            genre,
            "assirem music prod",
            "no copyright",
            "free music",
            "2026",
        ],
        "playlists": ["🎵 Assirem Music PROD — All Tracks"],
        "auto_shorts": True,
        "scenes": [],
        "_note": "scenes vide = utilise l'image fournie dans input/<slug>/",
    }


def _generate_with_claude(slug: str, genre: str, image_path: str = "") -> dict:
    """Appelle Claude Haiku pour générer le JSON complet du track."""
    try:
        import anthropic
    except ImportError:
        print("  ⚠️  anthropic non installé. Install: pip install anthropic", file=sys.stderr)
        return _make_template_track(slug, genre)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        cred_path = Path(__file__).parent.parent / "credentials" / "anthropic.key"
        if cred_path.exists():
            api_key = cred_path.read_text().strip()

    if not api_key:
        print("  ⚠️  ANTHROPIC_API_KEY manquant, fallback template", file=sys.stderr)
        return _make_template_track(slug, genre)

    client = anthropic.Anthropic(api_key=api_key)

    system = """Tu es un expert en metadata YouTube pour une chaîne de musique Assirem Music PROD.
Tu génères des JSONs de configuration pour un pipeline de production vidéo.
Réponds UNIQUEMENT avec du JSON valide, sans markdown ni explications."""

    prompt = f"""Génère un JSON de configuration pour un track YouTube avec ces informations :

Slug : {slug}
Genre musical : {genre}
Chaîne : Assirem Music PROD
Format : vidéo musicale longue (30-60 min), cinématique

Le JSON doit respecter exactement ce schéma :
{{
  "slug": "{slug}",
  "mode": "medium",
  "title": "...",
  "description": "... (300-500 chars, chapters, hashtags)",
  "tags": ["...", "..."],  // 8-12 tags pertinents
  "playlists": ["🎵 Assirem Music PROD — All Tracks", "..."],  // 1-3 playlists
  "scenes": [
    ["prompt cinématique 4K détaillé en anglais pour Leonardo AI", nb_secondes],
    ...  // 5-7 scènes narratives
  ]
}}

Pour les scenes : prompts visuels cinématiques en anglais, style "Wide establishing shot of ..., golden hour, 4K cinematic".
Durée de chaque scène : entre 1 et 4 (en unités relatives).
Assure-toi que les scènes racontent une progression visuelle cohérente avec le genre musical."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )
        raw = response.content[0].text.strip()

        # Nettoie si markdown code block
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        track = json.loads(raw)
        track["slug"] = slug  # s'assure que le slug est correct
        return track

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Claude a renvoyé du JSON invalide : {e}. Fallback template.", file=sys.stderr)
        return _make_template_track(slug, genre)
    except Exception as e:
        print(f"  ⚠️  Erreur Claude : {e}. Fallback template.", file=sys.stderr)
        return _make_template_track(slug, genre)


def generate_json(slug: str, output_path: str, genre: str = "", use_claude: bool = False, image_path: str = ""):
    """Point d'entrée principal : génère et sauve le JSON d'un track."""
    detected_genre = _detect_genre(slug, genre)
    print(f"  🎵 {slug}  (genre: {detected_genre})")

    if use_claude:
        print("  🤖 Appel Claude Haiku...")
        track = _generate_with_claude(slug, detected_genre, image_path)
    else:
        track = _make_template_track(slug, detected_genre)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

    print(f"  ✅ JSON sauvé : {out}")
    return track


def process_batch(stock_dir: str, use_claude: bool = False, genre: str = ""):
    """Traite tous les slugs dans stock_dir/ qui n'ont pas encore de JSON."""
    stock = Path(stock_dir)
    if not stock.is_dir():
        print(f"  (stock vide ou absent — rien à traiter)")
        return

    generated = 0
    skipped = 0

    for slug_dir in sorted(stock.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name

        json_path = slug_dir / f"{slug}.json"
        if json_path.exists():
            print(f"  ⏭️  {slug} — JSON existant, ignoré")
            skipped += 1
            continue

        # Vérifie qu'il y a un fichier audio
        audio_files = list(slug_dir.glob("*.mp3")) + list(slug_dir.glob("*.wav")) + list(slug_dir.glob("*.m4a"))
        if not audio_files:
            print(f"  ⚠️  {slug} — pas d'audio, ignoré")
            continue

        # Cherche une image pour la passer à Claude
        img_files = list(slug_dir.glob("*.jpg")) + list(slug_dir.glob("*.jpeg")) + list(slug_dir.glob("*.png"))
        img_path = str(img_files[0]) if img_files else ""

        generate_json(
            slug=slug,
            output_path=str(json_path),
            genre=genre,
            use_claude=use_claude,
            image_path=img_path,
        )
        generated += 1

    print(f"\n  Résultat : {generated} JSON(s) générés, {skipped} ignorés (existants)")


def main():
    parser = argparse.ArgumentParser(
        description="Assirem auto-JSON generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("slug", nargs="?", help="Slug du track (ex: lofi-coffee-shop)")
    parser.add_argument("--use-claude", action="store_true", help="Utiliser Claude Haiku pour générer le contenu")
    parser.add_argument("--genre", default="", help="Genre musical (ex: 'lofi hip hop')")
    parser.add_argument("--output", help="Chemin de sortie du JSON (défaut: ./stock/<slug>/<slug>.json)")
    parser.add_argument("--batch", metavar="STOCK_DIR", help="Mode batch : traite tous les slugs sans JSON dans STOCK_DIR")

    args = parser.parse_args()

    if args.batch:
        process_batch(args.batch, use_claude=args.use_claude, genre=args.genre)
    elif args.slug:
        output = args.output or f"./stock/{args.slug}/{args.slug}.json"
        generate_json(
            slug=args.slug,
            output_path=output,
            genre=args.genre,
            use_claude=args.use_claude,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
