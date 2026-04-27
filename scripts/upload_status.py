#!/usr/bin/env python3
"""
upload_status.py
----------------
Diagnostic des 35 tracks de la semaine — quels uploads ont réussi,
quels MP4 sont prêts mais pas uploadés, et quels tracks ne sont pas prêts.

Sources croisées :
  1. today/week_config.json       → liste des 35 tracks attendus
  2. youtube_uploaded_videos.json → tracker persistant cross-day
  3. output/<slug>/*.mp4          → MP4 générés sur disque
  4. (optionnel) YouTube API      → ground truth via --check-youtube

Usage :
  python3 scripts/upload_status.py
  python3 scripts/upload_status.py --check-youtube
  python3 scripts/upload_status.py --config today/config.json
  python3 scripts/upload_status.py --json   # sortie JSON pour scripting
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG    = BASE_DIR / "today" / "week_config.json"
PERSISTENT_FILE   = BASE_DIR / "youtube_uploaded_videos.json"
OUTPUT_DIR        = BASE_DIR / "output"

# Couleurs ANSI
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"
B = "\033[1m";  D = "\033[2m";  RESET = "\033[0m"


def load_tracks(config_path: Path) -> list[dict]:
    if not config_path.exists():
        sys.exit(f"❌ Config introuvable : {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    tracks = data.get("tracks", [])
    if not tracks:
        sys.exit(f"❌ Aucun track dans {config_path}")
    return tracks


def load_persistent_tracker() -> dict:
    if not PERSISTENT_FILE.exists():
        return {"videos": {}}
    return json.loads(PERSISTENT_FILE.read_text(encoding="utf-8"))


def find_local_videos(slug: str) -> dict:
    """Retourne {'main': [paths], 'shorts': [paths]} pour un slug."""
    slug_dir = OUTPUT_DIR / slug
    if not slug_dir.exists():
        return {"main": [], "shorts": []}
    main = sorted(p for p in slug_dir.glob("*.mp4")
                  if p.is_file() and not p.name.startswith("_"))
    shorts_dir = slug_dir / "shorts"
    shorts = sorted(shorts_dir.glob("*.mp4")) if shorts_dir.exists() else []
    return {"main": [str(p) for p in main], "shorts": [str(p) for p in shorts]}


def fetch_youtube_titles() -> dict[str, dict]:
    """
    Fetch all videos from the user's uploads playlist.
    Returns {title: {video_id, published_at, status}}.
    Coûte ~5-10 unités quota (negligible).
    """
    try:
        import pickle
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
    except ImportError:
        sys.exit("❌ Dépendances Google manquantes. Installe : pip install google-api-python-client")

    pickle_path = BASE_DIR / "credentials" / "youtube_oauth.pickle"
    if not pickle_path.exists():
        sys.exit(f"❌ Token OAuth introuvable : {pickle_path}")

    with open(pickle_path, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(pickle_path, "wb") as f:
            pickle.dump(creds, f)

    yt = build("youtube", "v3", credentials=creds)

    # 1. Get uploads playlist ID
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads_pid = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 2. Paginate through uploads
    titles_to_video: dict[str, dict] = {}
    req = yt.playlistItems().list(
        part="snippet,status",
        playlistId=uploads_pid,
        maxResults=50,
    )
    while req is not None:
        resp = req.execute()
        for item in resp.get("items", []):
            sn = item["snippet"]
            titles_to_video[sn["title"]] = {
                "video_id":     sn["resourceId"]["videoId"],
                "published_at": sn.get("publishedAt"),
                "privacy":      item.get("status", {}).get("privacyStatus"),
            }
        req = yt.playlistItems().list_next(req, resp)

    return titles_to_video


def classify(track: dict, persistent: dict, yt_titles: dict | None) -> dict:
    """
    Retourne un dict :
      slug, title, scheduled_at, status, detail
    Status ∈ {"uploaded", "ready_not_uploaded", "partial", "missing"}
    """
    slug = track["slug"]
    title = track.get("title", "")
    scheduled_at = track.get("scheduled_at", "?")

    locals = find_local_videos(slug)
    n_main = len(locals["main"])
    n_shorts = len(locals["shorts"])
    n_files = n_main + n_shorts

    # Persistant : combien de vidéos pour ce slug ont été tracées ?
    pkeys = [k for k in persistent.get("videos", {}) if k.startswith(f"{slug}/")]
    n_uploaded_persistent = len(pkeys)

    # YouTube ground truth : ce titre exact existe-t-il sur la chaîne ?
    yt_match = None
    if yt_titles is not None:
        yt_match = yt_titles.get(title)

    status = "missing"
    detail_parts = []

    if n_files == 0:
        status = "missing"
        detail_parts.append(f"{R}aucun MP4{RESET}")
    elif yt_match is not None:
        status = "uploaded"
        detail_parts.append(f"{G}YT: {yt_match['video_id']}{RESET}")
    elif n_uploaded_persistent >= n_files:
        status = "uploaded"
        detail_parts.append(f"{G}tracker: {n_uploaded_persistent}/{n_files}{RESET}")
    elif n_uploaded_persistent > 0:
        status = "partial"
        detail_parts.append(f"{Y}tracker: {n_uploaded_persistent}/{n_files}{RESET}")
    else:
        status = "ready_not_uploaded"
        detail_parts.append(f"{Y}MP4 OK ({n_main}+{n_shorts} short){RESET}")

    return {
        "slug":         slug,
        "title":        title,
        "scheduled_at": scheduled_at,
        "status":       status,
        "n_main":       n_main,
        "n_shorts":     n_shorts,
        "n_uploaded":   n_uploaded_persistent,
        "yt_video_id":  yt_match["video_id"] if yt_match else None,
        "detail":       " · ".join(detail_parts),
    }


def main():
    parser = argparse.ArgumentParser(description="Status des 35 uploads de la semaine.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check-youtube", action="store_true",
                        help="Fetch la liste des vidéos uploadées sur YouTube (ground truth, ~10 unités quota)")
    parser.add_argument("--json", action="store_true", help="Sortie JSON brute")
    args = parser.parse_args()

    tracks = load_tracks(args.config)
    persistent = load_persistent_tracker()
    yt_titles = fetch_youtube_titles() if args.check_youtube else None

    rows = [classify(t, persistent, yt_titles) for t in tracks]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    # Buckets
    uploaded = [r for r in rows if r["status"] == "uploaded"]
    partial  = [r for r in rows if r["status"] == "partial"]
    ready    = [r for r in rows if r["status"] == "ready_not_uploaded"]
    missing  = [r for r in rows if r["status"] == "missing"]

    # Tableau détaillé
    print(f"\n{B}── Status uploads ({args.config.name}) ─────────────────────────────────{RESET}")
    if yt_titles is not None:
        print(f"{D}  Croisé avec YouTube ({len(yt_titles)} vidéos sur la chaîne){RESET}")
    print()
    print(f"  {'#':>3}  {'Status':<22}  {'Slot':16}  Slug")
    print(f"  {'-'*3}  {'-'*22}  {'-'*16}  {'-'*45}")

    icons = {
        "uploaded":           f"{G}✅ uploadé{RESET}            ",
        "partial":            f"{Y}⚠️  partiel{RESET}           ",
        "ready_not_uploaded": f"{Y}📹 prêt, pas uploadé{RESET}",
        "missing":            f"{R}❌ pas de MP4{RESET}        ",
    }
    for i, r in enumerate(rows, 1):
        slot = r["scheduled_at"][:16] if r["scheduled_at"] != "?" else "?"
        slot = slot.replace("T", " ")
        print(f"  {i:>3}  {icons[r['status']]}  {slot}  {r['slug']}")
        if r["detail"]:
            print(f"       {D}{r['detail']}{RESET}")

    # Résumé
    total = len(rows)
    print(f"\n{B}── Résumé ──────────────────────────────────────────────────────────{RESET}")
    print(f"  {G}✅ Uploadés          : {len(uploaded):>3}/{total}{RESET}")
    print(f"  {Y}⚠️  Partiels         : {len(partial):>3}/{total}{RESET}")
    print(f"  {Y}📹 Prêts, à upload   : {len(ready):>3}/{total}{RESET}")
    print(f"  {R}❌ MP4 manquant      : {len(missing):>3}/{total}{RESET}")

    if ready or partial:
        print(f"\n{B}── Pour finir les uploads ─────────────────────────────────────────{RESET}")
        if ready or partial:
            slugs_to_run = [r["slug"] for r in (ready + partial)]
            print(f"  python3 pipeline.py --skip-visual --skip-video \\")
            for s in slugs_to_run:
                print(f"      --slug {s}")
            print()
            print(f"  {D}# ou en une fois (le tracker persistant skip ce qui est déjà fait){RESET}")
            print(f"  python3 pipeline.py --all --skip-visual --skip-video")

    if missing:
        print(f"\n{B}── MP4 à générer ──────────────────────────────────────────────────{RESET}")
        for r in missing:
            print(f"  python3 pipeline.py --slug {r['slug']} --skip-upload")

    if not yt_titles:
        print(f"\n{D}  💡 Tip : ajoute --check-youtube pour vérifier la chaîne directement{RESET}")
    print()


if __name__ == "__main__":
    main()
