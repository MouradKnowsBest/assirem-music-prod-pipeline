#!/usr/bin/env python3
"""
reorganize_playlists.py
-----------------------
Step 1: Delete ALL existing playlists from the channel.
Step 2: Create 13 thematic playlists + 1 generalist catch-all, and
        populate them from channel_data.json using keyword rules on
        video titles.

Every video goes into the generalist playlist (#0) and into 0-2
thematic playlists (most into 1).

Safety:
  * Defaults to --dry-run. You must pass --live to actually mutate
    the YouTube channel (delete existing playlists, create new ones).

Usage:
    python scripts/reorganize_playlists.py               # dry-run (default)
    python scripts/reorganize_playlists.py --live        # actually do it
    python scripts/reorganize_playlists.py --skip-delete # keep old playlists, only create new
"""

import argparse
import json
import pickle
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request


# ── paths (relative to repo root, no hardcoded user paths) ────────────────────
BASE_DIR        = Path(__file__).resolve().parent.parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
PICKLE_PATH     = CREDENTIALS_DIR / "youtube_oauth.pickle"
DATA_PATH       = BASE_DIR / "scripts" / "channel_data.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


# ── helpers ────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(msg, flush=True)


def build_youtube():
    with open(PICKLE_PATH, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        log("🔄  Refreshing expired credentials…")
        creds.refresh(Request())
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(creds, f)
        log("✅  Credentials refreshed and saved.")

    return build("youtube", "v3", credentials=creds)


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def title_matches(title: str, keywords: list[str]) -> bool:
    """Return True if ANY keyword appears in the title (case-insensitive for
    ASCII keywords, case-sensitive for emoji / flag keywords which are passed
    verbatim)."""
    t_low = title.lower()
    for kw in keywords:
        # emoji / flag keywords contain non-ASCII; match on the raw title.
        if any(ord(c) > 127 for c in kw):
            if kw in title:
                return True
        else:
            if kw in t_low:
                return True
    return False


# ── taxonomy ──────────────────────────────────────────────────────────────────
#
# Order matters only for logs — each video is independently tested against
# every thematic playlist. One video can land in several playlists.
#
# The generalist playlist (#0) always gets every video, no keyword filter.

GENERALIST_PLAYLIST = {
    "title": "🎵 Assirem Music PROD — All Tracks",
    "description": (
        "Every track published on Assirem Music PROD — AI-generated "
        "electronic, lo-fi, world, cinematic and more. New music every week."
    ),
}

PLAYLISTS = [
    {
        "title": "🌍 Afrofuturism — Assirem Music PROD",
        "description": (
            "Cosmic Afrobeats, Amapiano, Afro House and African futurism. "
            "Modern African sounds with electronic edge."
        ),
        "keywords": [
            "afrofutur", "afro futur", "afrofuturism",
            "afrobeat", "afropop", "afro pop", "afro house",
            "amapiano",
            "african sunrise", "african summer", "african tribal",
            "neon africa", "africa rising", "motherland",
            "stellar ancestors", "cosmic tribe", "cosmic african",
            "tropical afropop", "tropical crossover",
            "diaspora paris", "hip hop afro",
        ],
    },
    {
        "title": "🌏 World Music — Assirem Music PROD",
        "description": (
            "A world music journey through countries and traditions — "
            "Andean, Vietnamese, Georgian, Māori, Mongolian, Balinese, "
            "Bossa Nova and more."
        ),
        "keywords": [
            "andean", "andes", "perú", "peru",
            "vietnam", "vietnamese", "hoi an", "lotus",
            "georgian", "caucas",
            "maori", "aotearoa",
            "mongolian", "khöömei", "khoomei", "steppes", "throat singing",
            "gamelan", "bali", "balinese", "sacred bali",
            "bossa nova",
            "cuore mio", "italian",
            # country flags (non-African, non-Maghreb, non-Latin)
            "🇵🇪", "🇻🇳", "🇬🇪", "🇳🇿", "🇲🇳", "🇮🇩", "🇮🇹",
        ],
    },
    {
        "title": "🌙 Oriental, Oud & Maghreb — Assirem Music PROD",
        "description": (
            "Oud, Raï, Turkish, Arabic, Persian, Kabyle and Gnawa — "
            "soulful melodies from the Maghreb and the Middle East."
        ),
        "keywords": [
            "oud", "raï", "rai ", "rai|", "rai 2026",
            "oriental", "turkish", "arabic", "persian", "maqam",
            "gnawa", "ya ruh", "istanbul",
            "algérien", "algerien", "algerienne", "algérienne",
            "kabyle", "tineghren", "cheb", "desert soul",
            "morocco", "moroccan", "maghreb",
            "🇩🇿", "🇲🇦", "🇹🇷",
        ],
    },
    {
        "title": "🌶️ Latin, Caribbean & Reggae — Assirem Music PROD",
        "description": (
            "Reggaeton, Salsa, Latin pop, Reggae and Roots. Tropical and "
            "Caribbean grooves."
        ),
        "keywords": [
            "latin", "reggaeton", "salsa",
            "corazón", "corazon", "la vida está", "la vida esta",
            "reggae", "roots reggae", "rasta", "jah rising",
            "jamaic", "caribbean", "caribe",
            "venezuela", "venezuela libre",
            "pan-african anthem", "africa reggae",
            "🇯🇲", "🇻🇪",
        ],
    },
    {
        "title": "🔮 Electronic, House & Techno — Assirem Music PROD",
        "description": (
            "Melodic Techno, Deep House, Synthwave, UK Garage, Hyperpop — "
            "club and electronic productions."
        ),
        "keywords": [
            "techno", "melodic techno",
            "house", "deep house", "melodic house",
            "electronic", "electro",
            "synthwave", "synth wave", "night drive synthwave",
            "uk garage", "2-step", "garage revival",
            "hyperpop", "bubblegum",
            "club beats", "night out club",
            "party music",
        ],
    },
    {
        "title": "📚 Focus, Lo-Fi & Coffee Work — Assirem Music PROD",
        "description": (
            "Lo-fi, study, deep work, vibe coding, coffee jazz and reading "
            "music — stay in the zone."
        ),
        "keywords": [
            "lofi", "lo-fi", "lo fi",
            "focus", "deep focus", "study", "deep work", "concentration",
            "beats to study",
            "vibe cod", "vibe coding", "coding", "programming",
            "developer beats",
            "coffee shop", "coffee jazz", "café", "cafe du matin",
            "remote work",
            "reading music", "sunday reading", "acoustic folk",
            "art studio", "creative work", "flow state",
            "kitchen jazz", "cooking music",
            "morning routine", "peaceful wake up",
            "indie game lofi", "gaming music",
        ],
    },
    {
        "title": "💪 Workout, Gym & Motivation — Assirem Music PROD",
        "description": (
            "Gym Trap, Phonk workout, sports, running, hustle and CEO "
            "mindset — high-energy bangers."
        ),
        "keywords": [
            "gym", "workout", "pre-workout",
            "motivation", "iron will", "iron mind",
            "sports", "sports performance", "running",
            "fitness", "hiit",
            "hustle", "entrepreneur", "ceo", "morning hustle",
            "mindset", "coachella", "bieberchella",
        ],
    },
    {
        "title": "🌙 Dark Vibes & Night Drive — Assirem Music PROD",
        "description": (
            "Phonk, PluggnB, Midnight, Dark R&B and late-night rides."
        ),
        "keywords": [
            "phonk", "dark phonk",
            "pluggnb", "plug",
            "midnight", "midnight drip", "midnight drift",
            "night drive", "late night", "3 a.m",
            "dark r&b", "dark rnb", "dark neo-soul", "dark neo soul",
            "bedroom pop dark", "bedroom dark",
            "desert prayers", "dark moody", "shoegaze dark",
        ],
    },
    {
        "title": "🎤 Hip-Hop, Rap & R&B — Assirem Music PROD",
        "description": (
            "Rap, Hip-Hop, R&B, Neo Soul, Trap and Drill essentials."
        ),
        "keywords": [
            "rap", "hip hop", "hip-hop",
            "rnb", "r&b",
            "neo soul", "neo-soul",
            "drill", "latin drill",
            "rue d'alger", "hip hop conscient",
            "euphoria",  # dramatic rap-adjacent score context
        ],
    },
    {
        "title": "🕊️ Cinematic & Orchestral — Assirem Music PROD",
        "description": (
            "Epic cinematic and orchestral scores — space, hope, drama "
            "and big-screen moments."
        ),
        "keywords": [
            "cinematic", "orchestral", "epic orchestral",
            "epic space", "space", "artemis",
            "diplomatic", "ceasefire", "dawn of freedom",
            "score", "scores", "drama score",
            "hymn", "symphonic",
            "dark cinematic",
        ],
    },
    {
        "title": "🇫🇷 Pop Française — Assirem Music PROD",
        "description": (
            "Pop française — variété, NRJ vibes, énergie française."
        ),
        "keywords": [
            "française", "français",
            "pop fr", "pop française",
            "nrj", "variété", "variete",
            "brûle", "brule",
            "jusqu'au bout", "libre",
            "paris la nuit", "paris pop",
            "danyl", "miki",
        ],
    },
    {
        "title": "🌸 Pop, Chill & Indie Rock — Assirem Music PROD",
        "description": (
            "Chill pop, bedroom pop, indie and rock 'n' roll — light, "
            "dreamy, and guitar-driven vibes."
        ),
        "keywords": [
            "pop chill", "chill pop", "pop & chill", "pop and chill",
            "bedroom pop", "indie",
            "alt-rock", "alt rock", "rock n roll", "rock 'n' roll", "rock",
            "shoegaze", "fading signal", "hall of forever",
            "desert glow", "spring pop",
            "spring in my heart",
            "road trip", "travel vibes", "travel music",
            "blooming", "days i don't think",
            "coffee pop",
        ],
    },
    {
        "title": "🧘 Meditation, Sleep & Wellness — Assirem Music PROD",
        "description": (
            "Meditation, Yoga, Sleep, Healing frequencies, Spa, ASMR, "
            "Rain and Nature ambiences."
        ),
        "keywords": [
            "meditation", "yoga", "morning yoga",
            "sleep", "deep sleep", "study sleep",
            "healing", "healing frequencies",
            "432hz", "528hz", "tibetan", "zen", "ambient healing",
            "spa", "wellness", "massage",
            "asmr",
            "rain ambiance", "rainy day", "rain ambient",
            "nature walk", "forest ambient",
            "white noise",
            "breathwork",
        ],
    },
]


# ── trap/gym special rule ──────────────────────────────────────────────────────
# "trap" is ambiguous: it matches Hip-Hop by default, but in workout context
# (gym/workout/motivation/running/hiit) it should land in Workout instead.

WORKOUT_CONTEXT = [
    "gym", "workout", "iron will", "iron mind",
    "motivation", "running", "sports", "hiit",
    "coachella", "bieberchella",
    "pre-workout", "ceo", "entrepreneur", "hustle",
]


def video_matches_playlist(title: str, playlist_title: str, keywords: list[str]) -> bool:
    """Per-playlist matching with trap/workout disambiguation."""
    t_low = title.lower()

    # Workout playlist: trap counts only if workout context is present.
    if "Workout" in playlist_title:
        # Does any non-trap keyword match?
        base_kw = [k for k in keywords if k.lower() != "trap"]
        if title_matches(title, base_kw):
            return True
        # trap only if workout context is also in the title
        if "trap" in t_low and any(c in t_low for c in WORKOUT_CONTEXT):
            return True
        return False

    # Hip-Hop playlist: trap matches only if NO workout context
    # (otherwise the Workout playlist grabs it).
    if "Hip-Hop" in playlist_title:
        if title_matches(title, keywords):
            if "trap" in t_low and any(c in t_low for c in WORKOUT_CONTEXT):
                # Pure workout trap → skip Hip-Hop.
                # But if OTHER keywords match (rap, rnb, drill…), keep it.
                other_matched = any(
                    (kw in t_low) for kw in keywords if kw.lower() != "trap"
                )
                return other_matched
            return True
        return False

    return title_matches(title, keywords)


# ── step 1: delete all existing playlists ─────────────────────────────────────

def delete_all_playlists(youtube, playlists: list[dict], *, dry_run: bool):
    log(f"\n{'='*60}")
    log(f"STEP 1 — Deleting {len(playlists)} existing playlists"
        f"{' (DRY-RUN)' if dry_run else ''}…")
    log(f"{'='*60}")
    deleted = 0
    errors  = 0
    for pl in playlists:
        pid    = pl["id"]
        ptitle = pl["title"]
        if dry_run:
            log(f"  [dry-run] 🗑️  Would delete: [{pid}] {ptitle}")
            deleted += 1
            continue
        try:
            youtube.playlists().delete(id=pid).execute()
            log(f"  🗑️  Deleted: [{pid}] {ptitle}")
            deleted += 1
        except HttpError as e:
            log(f"  ❌  Error deleting [{pid}] {ptitle}: {e}")
            errors += 1
        time.sleep(0.3)
    log(f"\n  → Deleted {deleted} playlists, {errors} errors.")
    return deleted, errors


# ── step 2: create playlists and add videos ────────────────────────────────────

def create_playlist(youtube, title: str, description: str, *, dry_run: bool) -> str | None:
    if dry_run:
        log(f"  [dry-run] ✅  Would create: {title}")
        return "DRYRUN_PLAYLIST_ID"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "defaultLanguage": "en",
        },
        "status": {"privacyStatus": "public"},
    }
    try:
        resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
        pid  = resp["id"]
        log(f"  ✅  Created playlist: [{pid}] {title}")
        return pid
    except HttpError as e:
        log(f"  ❌  Error creating playlist '{title}': {e}")
        return None


def add_video_to_playlist(youtube, playlist_id: str, video_id: str,
                          video_title: str, *, dry_run: bool) -> bool:
    if dry_run:
        log(f"      [dry-run] ➕  Would add: [{video_id}] {video_title}")
        return True

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    try:
        youtube.playlistItems().insert(part="snippet", body=body).execute()
        log(f"      ➕  Added: [{video_id}] {video_title}")
        return True
    except HttpError as e:
        log(f"      ❌  Error adding [{video_id}] {video_title}: {e}")
        return False


def build_all_playlists(youtube, videos: list[dict], *, dry_run: bool):
    log(f"\n{'='*60}")
    log(f"STEP 2 — Creating 1 generalist + {len(PLAYLISTS)} thematic playlists"
        f"{' (DRY-RUN)' if dry_run else ''}…")
    log(f"{'='*60}")

    total_added  = 0
    total_errors = 0
    per_playlist_counts: dict[str, int] = {}
    unmatched: list[dict] = []

    # ── 0. Generalist playlist: every video goes here ─────────────────────────
    log(f"\n  📂  Playlist: {GENERALIST_PLAYLIST['title']}")
    log(f"      → {len(videos)} video(s) (all channel uploads).")
    gen_id = create_playlist(
        youtube,
        GENERALIST_PLAYLIST["title"],
        GENERALIST_PLAYLIST["description"],
        dry_run=dry_run,
    )
    if gen_id:
        time.sleep(0.3 if not dry_run else 0)
        for v in videos:
            ok = add_video_to_playlist(
                youtube, gen_id, v["id"], v["title"], dry_run=dry_run,
            )
            total_added += int(ok)
            total_errors += int(not ok)
            if not dry_run:
                time.sleep(0.25)
        per_playlist_counts[GENERALIST_PLAYLIST["title"]] = len(videos)

    # ── 1..N. Thematic playlists ──────────────────────────────────────────────
    video_matched_somewhere = {v["id"]: False for v in videos}

    for pl_def in PLAYLISTS:
        pl_title = pl_def["title"]
        pl_desc  = pl_def["description"]
        keywords = pl_def["keywords"]

        log(f"\n  📂  Playlist: {pl_title}")

        matching = [
            v for v in videos
            if video_matches_playlist(v["title"], pl_title, keywords)
        ]
        log(f"      → {len(matching)} video(s) matched.")
        per_playlist_counts[pl_title] = len(matching)

        if not matching:
            log("      ⚠️  No videos matched — creating empty playlist anyway "
                "(pipeline will use it for future uploads).")

        playlist_id = create_playlist(youtube, pl_title, pl_desc, dry_run=dry_run)
        if not playlist_id:
            log("      ❌  Could not create playlist — skipping.")
            continue

        time.sleep(0.3 if not dry_run else 0)

        for v in matching:
            ok = add_video_to_playlist(
                youtube, playlist_id, v["id"], v["title"], dry_run=dry_run,
            )
            if ok:
                total_added += 1
                video_matched_somewhere[v["id"]] = True
            else:
                total_errors += 1
            if not dry_run:
                time.sleep(0.25)

    # ── Unmatched report (videos that landed ONLY in the generalist) ─────────
    for v in videos:
        if not video_matched_somewhere[v["id"]]:
            unmatched.append(v)

    return total_added, total_errors, per_playlist_counts, unmatched


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Actually delete and create playlists. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--skip-delete", action="store_true",
        help="Do not delete existing playlists, only create the new taxonomy.",
    )
    args = parser.parse_args()

    dry_run = not args.live

    log("🎵  Assirem Music PROD — Playlist Reorganisation Script")
    log(f"    Data file : {DATA_PATH}")
    log(f"    OAuth pkl : {PICKLE_PATH}")
    log(f"    Mode      : {'DRY-RUN (no changes)' if dry_run else 'LIVE (will mutate channel!)'}")
    if args.skip_delete:
        log("    Delete    : SKIPPED (existing playlists will be kept)")

    # load data
    data      = load_data()
    playlists = data["playlists"]
    videos    = data["videos"]
    log(f"\n  Loaded {len(playlists)} existing playlists and {len(videos)} videos.")

    # build API client (skip in dry-run to allow running without credentials)
    youtube = None
    if not dry_run:
        youtube = build_youtube()
        log("  YouTube API client ready.\n")
    else:
        log("  (dry-run) Skipping YouTube API client build.\n")

    # ── Step 1 ──
    if args.skip_delete:
        del_ok, del_err = 0, 0
    else:
        del_ok, del_err = delete_all_playlists(youtube, playlists, dry_run=dry_run)

    # ── Step 2 ──
    add_ok, add_err, counts, unmatched = build_all_playlists(
        youtube, videos, dry_run=dry_run,
    )

    # ── Summary ──
    log(f"\n{'='*60}")
    log("SUMMARY")
    log(f"{'='*60}")
    log(f"  Mode                : {'DRY-RUN' if dry_run else 'LIVE'}")
    log(f"  Playlists deleted   : {del_ok}  (errors: {del_err})")
    log(f"  Videos added        : {add_ok}  (errors: {add_err})")
    log("")
    log("  Per-playlist counts:")
    for title, count in counts.items():
        log(f"    {count:4d}  {title}")
    log("")
    log(f"  Videos NOT matched by any thematic playlist "
        f"(only in generalist): {len(unmatched)}")
    if unmatched:
        log("  → Review these titles and extend keyword lists if needed:")
        for v in unmatched[:30]:
            log(f"      [{v['id']}] {v['title']}")
        if len(unmatched) > 30:
            log(f"      … and {len(unmatched) - 30} more.")

    if dry_run:
        log("\n  ℹ️   This was a DRY-RUN. Re-run with --live to actually apply changes.")
    log("  Done! ✅")


if __name__ == "__main__":
    main()
