"""
Upload the Latino/Reggae compilation video to YouTube.
Run from the pipeline root: python scripts/upload_compilation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.youtube import _authentifier, _uploader_video, _ajouter_a_playlist, _trouver_playlist

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_PATH = os.path.join(BASE_DIR, "output/_compilation_latino/reggae_mix_compilation_2026.mp4")

TITLE = "Reggae Mix 2026 🎵 Roots · Reggaeton · Salsa · Tropical Latino — Assirem Music"

DESCRIPTION = """\
🎵 Reggae Mix 2026 — The ultimate collection of Reggae, Reggaeton, Salsa & Tropical Latino vibes by Assirem Music.

🌴 Tracklist:
00:00 - Intro
00:08 - Roots Reggae — Jah Love
03:19 - Reggaeton Romántico — Noche
05:26 - Reggaeton Clásico Old School
20:07 - Latin Lovers Reggae
22:44 - Tropical Reggae Latino
24:39 - Cumbia Reggae Tropical
26:52 - Latin Trap Reggae — Las Calles
28:26 - Salsa Tropical — Cali Style
31:19 - Son Cubano — Havana Nights
33:09 - Cinco de Mayo — Viva México
35:09 - Dembow Latino Urbano
36:54 - Tropical Afropop Paradise

🔔 Subscribe for daily world music drops!

#Reggae #ReggaeMix #Reggaeton #Salsa #Latino #TropicalMusic #WorldMusic #AssiremMusic #ChillMusic #LatinMusic #RootsReggae #Dembow #SalsaTropical #Cumbia
"""

TAGS = [
    "reggae", "reggae mix", "reggaeton", "salsa", "latin music", "tropical",
    "roots reggae", "dembow", "cumbia", "son cubano", "latin trap", "assirem music",
    "world music", "chill music", "latin vibes", "reggae 2026", "music mix 2026",
]

PLAYLIST_NAME = "🎵 Assirem Music PROD — All Tracks"


def main():
    if not os.path.exists(VIDEO_PATH):
        print(f"ERROR: File not found: {VIDEO_PATH}")
        sys.exit(1)

    size_mb = os.path.getsize(VIDEO_PATH) / (1024 * 1024)
    print(f"File: {os.path.basename(VIDEO_PATH)} ({size_mb:.1f} MB)")
    print(f"Title: {TITLE}")
    print()

    youtube = _authentifier(BASE_DIR)

    video_id = _uploader_video(
        youtube,
        chemin=VIDEO_PATH,
        titre=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        is_short=False,
        publish_at=None,  # publish immediately as public
    )
    print(f"\n✅ Uploaded: https://www.youtube.com/watch?v={video_id}")

    playlist_id = _trouver_playlist(youtube, PLAYLIST_NAME, BASE_DIR)
    if playlist_id:
        _ajouter_a_playlist(youtube, video_id, playlist_id)
        print(f"✅ Added to playlist: {PLAYLIST_NAME}")
    else:
        print(f"⚠️  Playlist not found: {PLAYLIST_NAME} — video is public but not in playlist")

    print("\nDone.")


if __name__ == "__main__":
    main()
