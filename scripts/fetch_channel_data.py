"""
fetch_channel_data.py
Fetches all videos and playlists from the authenticated YouTube channel
using the YouTube Data API v3 with stored OAuth credentials.
"""

import pickle
import json
import sys
from pathlib import Path

from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline")
PICKLE_PATH = BASE_DIR / "credentials" / "youtube_oauth.pickle"

# ── Auth ─────────────────────────────────────────────────────────────────────
def get_credentials():
    with open(PICKLE_PATH, "rb") as fh:
        creds = pickle.load(fh)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(PICKLE_PATH, "wb") as fh:
            pickle.dump(creds, fh)
    return creds


# ── Helpers ──────────────────────────────────────────────────────────────────
def paginate(api_call, **kwargs):
    """Yield every item across all pages of a list-style API call."""
    request = api_call(**kwargs)
    while request is not None:
        response = request.execute()
        yield from response.get("items", [])
        request = api_call(**{**kwargs, "pageToken": response.get("nextPageToken")}) \
                  if response.get("nextPageToken") else None


def parse_iso8601_duration(duration: str) -> str:
    """Return a human-readable duration string from an ISO 8601 duration."""
    import re
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
    )
    if not match:
        return duration
    hours, minutes, seconds = (int(x or 0) for x in match.groups())
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ── Fetch channel info ────────────────────────────────────────────────────────
def fetch_channel_info(youtube):
    resp = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        mine=True
    ).execute()
    ch = resp["items"][0]
    return {
        "channelId":          ch["id"],
        "title":              ch["snippet"]["title"],
        "description":        ch["snippet"].get("description", ""),
        "subscriberCount":    int(ch["statistics"].get("subscriberCount", 0)),
        "videoCount":         int(ch["statistics"].get("videoCount", 0)),
        "viewCount":          int(ch["statistics"].get("viewCount", 0)),
        "uploadsPlaylistId":  ch["contentDetails"]["relatedPlaylists"]["uploads"],
    }


# ── Fetch all video IDs from uploads playlist ─────────────────────────────────
def fetch_upload_ids(youtube, uploads_playlist_id):
    ids = []
    for item in paginate(
        youtube.playlistItems().list,
        part="contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=50,
    ):
        ids.append(item["contentDetails"]["videoId"])
    return ids


# ── Fetch video details in batches of 50 ─────────────────────────────────────
def fetch_video_details(youtube, video_ids):
    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch),
            maxResults=50,
        ).execute()
        for v in resp.get("items", []):
            snip  = v["snippet"]
            stats = v.get("statistics", {})
            cd    = v.get("contentDetails", {})
            videos.append({
                "id":           v["id"],
                "title":        snip.get("title", ""),
                "description":  snip.get("description", ""),
                "tags":         snip.get("tags", []),
                "publishedAt":  snip.get("publishedAt", ""),
                "duration":     parse_iso8601_duration(cd.get("duration", "PT0S")),
                "durationRaw":  cd.get("duration", ""),
                "viewCount":    int(stats.get("viewCount",    0)),
                "likeCount":    int(stats.get("likeCount",    0)),
                "commentCount": int(stats.get("commentCount", 0)),
            })
    # Sort newest first
    videos.sort(key=lambda x: x["publishedAt"], reverse=True)
    return videos


# ── Fetch all playlists ───────────────────────────────────────────────────────
def fetch_playlist_video_ids(youtube, playlist_id):
    """Return ordered list of videoIds in a playlist."""
    ids = []
    for item in paginate(
        youtube.playlistItems().list,
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=50,
    ):
        ids.append(item["contentDetails"]["videoId"])
    return ids


def fetch_playlists(youtube):
    playlists = []
    for item in paginate(
        youtube.playlists().list,
        part="snippet,contentDetails",
        mine=True,
        maxResults=50,
    ):
        playlist_id = item["id"]
        print(f"  → Fetching items for playlist: {item['snippet']['title']}", file=sys.stderr)
        video_ids = fetch_playlist_video_ids(youtube, playlist_id)
        playlists.append({
            "id":          playlist_id,
            "title":       item["snippet"]["title"],
            "description": item["snippet"].get("description", ""),
            "publishedAt": item["snippet"].get("publishedAt", ""),
            "videoCount":  item["contentDetails"]["itemCount"],
            "videoIds":    video_ids,
        })
    playlists.sort(key=lambda x: x["publishedAt"], reverse=True)
    return playlists


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Authenticating...", file=sys.stderr)
    creds   = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    print("Fetching channel info...", file=sys.stderr)
    channel = fetch_channel_info(youtube)

    print(f"Fetching video IDs from uploads playlist ({channel['uploadsPlaylistId']})...", file=sys.stderr)
    video_ids = fetch_upload_ids(youtube, channel["uploadsPlaylistId"])
    print(f"  → {len(video_ids)} video IDs found", file=sys.stderr)

    print("Fetching video details...", file=sys.stderr)
    videos = fetch_video_details(youtube, video_ids)
    print(f"  → {len(videos)} videos fetched", file=sys.stderr)

    print("Fetching playlists...", file=sys.stderr)
    playlists = fetch_playlists(youtube)
    print(f"  → {len(playlists)} playlists fetched", file=sys.stderr)

    # ── Summary stats ─────────────────────────────────────────────────────────
    total_views   = sum(v["viewCount"]   for v in videos)
    total_likes   = sum(v["likeCount"]   for v in videos)
    total_comments= sum(v["commentCount"] for v in videos)
    top5_views    = sorted(videos, key=lambda x: x["viewCount"],   reverse=True)[:5]
    top5_likes    = sorted(videos, key=lambda x: x["likeCount"],   reverse=True)[:5]

    # ── Videos not in any playlist ────────────────────────────────────────────
    all_playlist_video_ids = set()
    for pl in playlists:
        all_playlist_video_ids.update(pl["videoIds"])
    videos_not_in_any_playlist = [
        {"id": v["id"], "title": v["title"], "publishedAt": v["publishedAt"]}
        for v in videos
        if v["id"] not in all_playlist_video_ids
    ]
    print(f"  → {len(videos_not_in_any_playlist)} videos not in any playlist", file=sys.stderr)

    summary = {
        "channel": channel,
        "stats": {
            "totalVideos":         len(videos),
            "totalPlaylists":      len(playlists),
            "totalViews":          total_views,
            "totalLikes":          total_likes,
            "totalComments":       total_comments,
            "top5ByViews": [
                {"id": v["id"], "title": v["title"], "viewCount": v["viewCount"]}
                for v in top5_views
            ],
            "top5ByLikes": [
                {"id": v["id"], "title": v["title"], "likeCount": v["likeCount"]}
                for v in top5_likes
            ],
        },
        "videos":    videos,
        "playlists": playlists,
        "videosNotInAnyPlaylist": videos_not_in_any_playlist,
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # ── Save full raw JSON to file ────────────────────────────────────────────
    OUTPUT_PATH = BASE_DIR / "scripts" / "channel_data.json"
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
