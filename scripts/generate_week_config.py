#!/usr/bin/env python3
"""
generate_week_config.py
Génère today/config.json avec 35 tracks pour la semaine
(5 morceaux par jour × 7 jours, slots 08:15/12:10/16:13/20:02/23:16).

Les tracks sont définis dans scripts/week_tracks_data.py (TRACKS list).

Usage:
  python3 scripts/generate_week_config.py
  python3 scripts/generate_week_config.py --start-date 2026-04-25
  python3 scripts/generate_week_config.py --output /tmp/preview.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "today" / "week_config.json"

DAILY_SLOTS = ["08:15", "12:10", "16:13", "20:02", "23:16"]
TIMEZONE = "Europe/Paris"
TZ_OFFSET = "+02:00"  # CEST (avr/mai)
LEONARDO_MODEL = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"

DISTRIBUTION = {
    "youtube": True,
    "youtube_short": True,
    "distrokid": True,
    "tiktok": True,
    "instagram_reels": True,
}

ALL_TRACKS_PLAYLIST = "🎵 Assirem Music PROD — All Tracks"

# Mapping anciens → nouveaux noms de playlists, suite à la réorganisation
# (cf. scripts/reorganize_playlists.py qui définit la nouvelle taxonomie 14 playlists).
# Les 10 tracks legacy de config.json référencent les anciens noms ; on les
# traduit ici pour qu'ils tapent dans la bonne playlist au moment de l'upload.
LEGACY_PLAYLIST_MAP = {
    "☕ Soft morning café vibes — Assirem Music PROD":           "📚 Focus, Lo-Fi & Coffee Work",
    "🇫🇷 Pop Française — Assirem Music PROD":                    "🇫🇷 Pop Française",
    "🌍 World Music Series — Assirem Music PROD":               "🌏 World Music",
    "🌘 Dark Vibes — Assirem Music PROD":                       "🌘 Dark Vibes & Night Drive",
    "🌙 Oriental Vibes — Assirem Music PROD":                   "🌙 Oriental, Oud & Maghreb",
    "🌸 Pop & Chill — Assirem Music PROD":                      "🌸 Pop, Chill & Indie Rock",
    "🎸🌐 MIX 🎼🎵 — Assirem Music PROD":                          ALL_TRACKS_PLAYLIST,
    "👾 Electronic & House & Techno — Assirem Music PROD":      "🔮 Electronic, House & Techno",
    "💪 Going Hard Gym Motivation 🔥 — Assirem Music PROD":      "💪 Workout, Gym & Motivation",
    "📚 Focus & Deep Work — Assirem Music PROD":                "📚 Focus, Lo-Fi & Coffee Work",
    "🔥 Hip Hop Rap & RnB essentials — Assirem Music PROD":     "🎤 Hip-Hop, Rap & R&B",
    "🧘 Yoga & Meditation — Assirem Music PROD":                "🧘 Meditation, Sleep & Wellness",
}


def _migrate_playlists(names: list[str]) -> list[str]:
    """Traduit les anciens noms de playlists en nouveaux. Garde l'ordre, dé-duplique."""
    seen = set()
    out = []
    for n in names:
        new = LEGACY_PLAYLIST_MAP.get(n, n)
        if new not in seen:
            seen.add(new)
            out.append(new)
    return out

# Ordre curé par mood/slot pour les 10 tracks existants (jours 1-2).
# 5 slots/jour × 2 jours :
#   08:15 morning chill | 12:10 midi pop | 16:13 afternoon focus | 20:02 evening | 23:16 night
LEGACY_SLUG_ORDER = [
    # Day 1
    "bedroom-hours-lofi-vocals-2026",        # 08:15 — morning lofi chill
    "paris-minuit-french-pop-2026",          # 12:10 — lunch french pop
    "neural-drift-synthwave-coding-2026",    # 16:13 — afternoon focus synthwave
    "midnight-confessions-dark-rnb-2026",    # 20:02 — evening dark R&B
    "crystal-waters-ambient-healing-2026",   # 23:16 — night ambient sleep
    # Day 2
    "kalahari-dawn-africa-world-2026",       # 08:15 — morning African meditative
    "golden-days-indie-pop-2026",            # 12:10 — lunch indie nostalgia
    "berserk-mode-gym-phonk-2026",           # 16:13 — afternoon phonk workout
    "oriental-night-market-vibes-2026",      # 20:02 — evening oriental
    "no-cap-zone-uk-drill-2026",             # 23:16 — night intense drill
]


def build_track(t: dict, priority: int, scheduled_at: str) -> dict:
    """Compose un track JSON complet à partir d'une entrée template."""
    playlists = list(t["playlists"])
    if ALL_TRACKS_PLAYLIST not in playlists:
        playlists.append(ALL_TRACKS_PLAYLIST)
    primary = t["playlists"][0]

    track = {
        "slug": t["slug"],
        "priority": priority,
        "category": t.get("category", "trending"),
        "scheduled_at": scheduled_at,

        "suno_lyrics": t["suno_lyrics"],
        "suno_style": t["suno_style"],
        "suno_title": t["suno_title"],
        "suno_exclude_styles": t.get("suno_exclude_styles", "country, polka, novelty"),
        "suno_vocal_gender": t.get("suno_vocal_gender"),
        "suno_lyrics_mode": "manual",
        "suno_weirdness": t.get("suno_weirdness", 35),
        "suno_style_influence": t.get("suno_style_influence", 50),

        "mode": t.get("mode", "medium"),
        "title": t["title"],
        "description": t["description"],
        "tags": t["tags"],

        "playlists": playlists,
        "playlist_name": primary,

        "leonardo_model": LEONARDO_MODEL,
        "distribution": DISTRIBUTION,

        "video": {
            "intro_fade_sec": t.get("intro_fade_sec", 2),
            "outro_fade_sec": t.get("outro_fade_sec", 3),
            "title_card": {
                "enabled": True,
                "duration_sec": 3,
                "text": t["suno_title"],
                "subtitle": t.get("subtitle", primary),
                "style": "minimal_dark",
            },
            "end_card": {
                "enabled": True,
                "duration_sec": 5,
                "subscribe_cta": True,
            },
            "short_clip": {
                "start_sec": t.get("short_start", 15),
                "duration_sec": 55,
            },
        },

        "scenes": [
            {"prompt": p, "motion_strength": ms}
            for p, ms in t["scenes"]
        ],
    }

    if "country" in t:
        track["country"] = t["country"]
    if "country_flag" in t:
        track["country_flag"] = t["country_flag"]
    if "activity_type" in t:
        track["activity_type"] = t["activity_type"]

    return track


def main():
    parser = argparse.ArgumentParser(
        description="Génère today/config.json avec 35 tracks pour la semaine."
    )
    parser.add_argument(
        "--start-date",
        default="2026-04-25",
        help="Date ISO du jour 1 (défaut : 2026-04-25 samedi).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Chemin de sortie (défaut : today/config.json).",
    )
    args = parser.parse_args()

    # ── Tracks jours 1-2 : on réutilise les 10 existants de config.json ──────
    # Ordre dicté par LEGACY_SLUG_ORDER pour respecter la curation par mood/slot,
    # pas l'ordre brut "priority" du config.json source.
    legacy_path = BASE_DIR / "config.json"
    if not legacy_path.exists():
        raise SystemExit(f"❌ Introuvable : {legacy_path}")
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    by_slug = {t["slug"]: t for t in legacy.get("tracks", [])}
    missing = [s for s in LEGACY_SLUG_ORDER if s not in by_slug]
    if missing:
        raise SystemExit(
            f"❌ Slugs introuvables dans config.json : {missing}"
        )
    legacy_tracks = [by_slug[s] for s in LEGACY_SLUG_ORDER]

    # ── Tracks jours 3-7 : 25 nouveaux templates ─────────────────────────────
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from week_tracks_data import TRACKS as NEW_TEMPLATES

    if len(NEW_TEMPLATES) != 25:
        raise SystemExit(
            f"❌ week_tracks_data.TRACKS doit contenir 25 entrées (jours 3-7), "
            f"trouvé {len(NEW_TEMPLATES)}."
        )

    start = datetime.fromisoformat(args.start_date)
    out_tracks = []

    # Jours 1-2 : conserve le contenu existant, ajoute scheduled_at + priority
    for i, raw in enumerate(legacy_tracks):
        day = i // 5
        slot = DAILY_SLOTS[i % 5]
        scheduled_at = (
            f"{(start + timedelta(days=day)).date()}T{slot}:00{TZ_OFFSET}"
        )
        track = dict(raw)  # shallow copy
        track["priority"] = i + 1
        track["scheduled_at"] = scheduled_at
        # Migration old → new playlist names + ajout de All Tracks
        playlists = _migrate_playlists(list(track.get("playlists") or []))
        if ALL_TRACKS_PLAYLIST not in playlists:
            playlists.append(ALL_TRACKS_PLAYLIST)
        track["playlists"] = playlists
        # playlist_name primaire = première playlist non-"All Tracks" si possible
        primary = next((p for p in playlists if p != ALL_TRACKS_PLAYLIST), ALL_TRACKS_PLAYLIST)
        track["playlist_name"] = primary
        out_tracks.append(track)

    # Jours 3-7 : 25 nouveaux tracks via templates
    for j, t in enumerate(NEW_TEMPLATES):
        idx = 10 + j  # 10..34
        day = idx // 5
        slot = DAILY_SLOTS[idx % 5]
        scheduled_at = (
            f"{(start + timedelta(days=day)).date()}T{slot}:00{TZ_OFFSET}"
        )
        out_tracks.append(build_track(t, idx + 1, scheduled_at))

    config = {
        "date": args.start_date,
        "priority_slug": out_tracks[0]["slug"],
        "schedule": {
            "timezone": TIMEZONE,
            "daily_slots_local": DAILY_SLOTS,
            "start_date": args.start_date,
            "end_date": str((start + timedelta(days=6)).date()),
            "tracks_per_day": 5,
            "total_tracks": 35,
        },
        "tracks": out_tracks,
    }

    output_path = Path(args.output) if args.output else OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✅ {len(out_tracks)} tracks → {output_path}")
    print()
    print(f"  {'#':>3}  {'Date':10}  {'Slot':5}  Slug")
    print(f"  {'-'*3}  {'-'*10}  {'-'*5}  {'-'*40}")
    for t in out_tracks:
        date_part, time_part = t["scheduled_at"].split("T")
        slot_short = time_part[:5]
        print(f"  {t['priority']:>3}  {date_part}  {slot_short}  {t['slug']}")


if __name__ == "__main__":
    main()
