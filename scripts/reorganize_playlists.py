#!/usr/bin/env python3
"""
reorganize_playlists.py
-----------------------
Step 1: Delete all 31 existing playlists from the channel.
Step 2: Create 8 new playlists and populate them based on keyword rules.
"""

import json
import pickle
import os
import time
import sys

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

# ── paths ──────────────────────────────────────────────────────────────────────
CREDENTIALS_DIR = "/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/credentials"
PICKLE_PATH     = os.path.join(CREDENTIALS_DIR, "youtube_oauth.pickle")
SECRET_PATH     = os.path.join(CREDENTIALS_DIR, "client_secret.json")
DATA_PATH       = "/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/scripts/channel_data.json"

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
    """Return True if ANY keyword appears in the lower-cased title."""
    t = title.lower()
    for kw in keywords:
        if kw.lower() in t:
            return True
    # also check for flag emojis directly (they are multi-byte but still 'in')
    for kw in keywords:
        if kw in title:   # non-lower check for emoji flags
            return True
    return False


# ── playlist definitions ───────────────────────────────────────────────────────

PLAYLISTS = [
    {
        "title": "🌍 Afrofuturism — Assirem Music PROD",
        "description": "Cosmic Afrobeats, African futurism and electronic sounds from Assirem Music PROD.",
        "keywords": ["afrofutur", "afro futur"],
    },
    {
        "title": "🌏 World Music Series — Assirem Music PROD",
        "description": "A world music journey — Andean, Vietnamese, Georgian, Māori, Bossa Nova and more.",
        "keywords": [
            "andean", "vietnam", "georgian", "maori", "bossa nova",
            "aotearoa", "hoi an", "perú", "peru",
            "🇵🇪", "🇻🇳", "🇬🇪", "🇳🇿",
        ],
    },
    {
        "title": "🔮 Melodic Techno — Assirem Music PROD",
        "description": "Dark progressive melodic techno for late-night focus.",
        "keywords": ["techno", "melodic techno"],
    },
    {
        "title": "📚 Focus & Deep Work — Assirem Music PROD",
        "description": "Lo-fi, study, coding and deep-work beats to keep you in the zone.",
        "keywords": [
            "lofi", "lo-fi", "focus", "study", "coding", "vibe cod",
            "deep work", "coffee shop", "café", "cafe",
        ],
    },
    {
        "title": "🌙 Dark Vibes — Assirem Music PROD",
        "description": "Phonk, dark beats, pluggnb and midnight rides.",
        "keywords": [
            "phonk", "dark", "pluggnb", "plug", "midnight",
            "desert prayers", "3 a.m", "romantic",
        ],
    },
    {
        "title": "💪 Energy & Workout — Assirem Music PROD",
        "description": "High-energy gym, workout and motivation bangers.",
        "keywords": [
            "gym", "workout", "motivation", "iron will",
            "coachella", "bieberchella",
        ],
    },
    {
        "title": "🕊️ Cinematic & Orchestral — Assirem Music PROD",
        "description": "Epic cinematic and orchestral scores for big moments.",
        "keywords": [
            "cinematic", "orchestral", "peace", "hope", "ceasefire",
            "artemis", "diplomatic", "dawn", "prayer",
        ],
    },
    {
        "title": "🇫🇷 Pop Française — Assirem Music PROD",
        "description": "French pop hits — NRJ vibes, énergie française.",
        "keywords": [
            "française", "français", "pop fr", "nrj", "brûle",
            "soleil", "jusqu'au bout", "libre", "paris la nuit",
            "danyl", "miki",
        ],
    },
]

# ── trap/gym special rule ──────────────────────────────────────────────────────
# "trap" only counts for Energy & Workout when it's alongside gym/workout context.
WORKOUT_CONTEXT = ["gym", "workout", "iron will", "coachella", "bieberchella", "motivation"]

def video_matches_playlist(title: str, playlist_title: str, keywords: list[str]) -> bool:
    """Per-playlist matching with the trap special-case for Energy & Workout."""
    if "Energy & Workout" in playlist_title:
        t = title.lower()
        # base keywords minus "trap"
        base_kw = [k for k in keywords if k != "trap"]
        if title_matches(title, base_kw):
            return True
        # trap only if workout context also present
        if "trap" in t and any(c in t for c in WORKOUT_CONTEXT):
            return True
        return False
    return title_matches(title, keywords)


# ── step 1: delete all existing playlists ─────────────────────────────────────

def delete_all_playlists(youtube, playlists: list[dict]):
    log(f"\n{'='*60}")
    log(f"STEP 1 — Deleting {len(playlists)} existing playlists…")
    log(f"{'='*60}")
    deleted = 0
    errors  = 0
    for pl in playlists:
        pid   = pl["id"]
        ptitle = pl["title"]
        try:
            youtube.playlists().delete(id=pid).execute()
            log(f"  🗑️  Deleted: [{pid}] {ptitle}")
            deleted += 1
        except HttpError as e:
            log(f"  ❌  Error deleting [{pid}] {ptitle}: {e}")
            errors += 1
        time.sleep(0.3)   # be gentle with the API quota
    log(f"\n  → Deleted {deleted} playlists, {errors} errors.")
    return deleted, errors


# ── step 2: create playlists and add videos ────────────────────────────────────

def create_playlist(youtube, title: str, description: str) -> str | None:
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


def add_video_to_playlist(youtube, playlist_id: str, video_id: str, video_title: str):
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
        }
    }
    try:
        youtube.playlistItems().insert(part="snippet", body=body).execute()
        log(f"      ➕  Added: [{video_id}] {video_title}")
        return True
    except HttpError as e:
        log(f"      ❌  Error adding [{video_id}] {video_title}: {e}")
        return False


def reorganize_playlists(youtube, videos: list[dict]):
    log(f"\n{'='*60}")
    log(f"STEP 2 — Creating 8 new playlists and adding videos…")
    log(f"{'='*60}")

    total_added  = 0
    total_errors = 0

    for pl_def in PLAYLISTS:
        pl_title   = pl_def["title"]
        pl_desc    = pl_def["description"]
        keywords   = pl_def["keywords"]

        log(f"\n  📂  Playlist: {pl_title}")

        # find matching videos
        matching = [
            v for v in videos
            if video_matches_playlist(v["title"], pl_title, keywords)
        ]
        log(f"      → {len(matching)} video(s) matched.")

        if not matching:
            log("      ⚠️  No videos matched — skipping playlist creation.")
            continue

        # create playlist
        playlist_id = create_playlist(youtube, pl_title, pl_desc)
        if not playlist_id:
            log("      ❌  Could not create playlist — skipping.")
            continue

        time.sleep(0.5)

        # add each video
        for v in matching:
            ok = add_video_to_playlist(youtube, playlist_id, v["id"], v["title"])
            if ok:
                total_added += 1
            else:
                total_errors += 1
            time.sleep(0.3)

    return total_added, total_errors


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    log("🎵  Assirem Music PROD — Playlist Reorganisation Script")
    log(f"    Data file : {DATA_PATH}")
    log(f"    OAuth pkl : {PICKLE_PATH}")

    # load data
    data     = load_data()
    playlists = data["playlists"]
    videos    = data["videos"]
    log(f"\n  Loaded {len(playlists)} existing playlists and {len(videos)} videos.")

    # build API client
    youtube = build_youtube()
    log("  YouTube API client ready.\n")

    # ── Step 1 ──
    del_ok, del_err = delete_all_playlists(youtube, playlists)

    # ── Step 2 ──
    add_ok, add_err = reorganize_playlists(youtube, videos)

    # ── Summary ──
    log(f"\n{'='*60}")
    log("SUMMARY")
    log(f"{'='*60}")
    log(f"  Playlists deleted   : {del_ok}  (errors: {del_err})")
    log(f"  Videos added        : {add_ok}  (errors: {add_err})")
    log("  Done! ✅")


if __name__ == "__main__":
    main()
