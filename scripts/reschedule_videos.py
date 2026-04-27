#!/usr/bin/env python3
"""
reschedule_videos.py
--------------------
Repositionne sur YouTube chaque vidéo de today/week_config.json à son
scheduled_at d'origine (status.privacyStatus = private + status.publishAt).

Sources de mapping slug → video_id(s) :
  1. youtube_uploaded_videos.json (tracker persistant local) — préféré
  2. Match par titre via upload_status.py (mêmes 5 stratégies)

Important : repasser une vidéo public→private+publishAt PRÉSERVE
les stats (vues, likes, commentaires). La vidéo redevient public au
publishAt, avec son historique intact.

API cost : ~50 unités par videos().update. 70 vidéos × 50 = 3 500 unités.

Usage :
  python3 scripts/reschedule_videos.py                      # dry-run par défaut
  python3 scripts/reschedule_videos.py --live               # exécute pour de vrai
  python3 scripts/reschedule_videos.py --slug X --live      # une seule track
  python3 scripts/reschedule_videos.py --skip-public --live # ne touche pas aux déjà-public
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG  = BASE_DIR / "today" / "week_config.json"
PERSISTENT_FILE = BASE_DIR / "youtube_uploaded_videos.json"
PICKLE_PATH     = BASE_DIR / "credentials" / "youtube_oauth.pickle"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"
B = "\033[1m";  D = "\033[2m";  RESET = "\033[0m"


def to_rfc3339_utc(iso_str: str) -> str:
    """'2026-04-25T08:15:00+02:00' → '2026-04-25T06:15:00Z'."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def auth_youtube():
    import pickle
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    if not PICKLE_PATH.exists():
        sys.exit(f"❌ Token OAuth introuvable : {PICKLE_PATH}")
    with open(PICKLE_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def load_tracker_video_ids() -> dict[str, list[str]]:
    """Retourne {slug: [video_id, ...]} depuis le tracker persistant."""
    if not PERSISTENT_FILE.exists():
        return {}
    data = json.loads(PERSISTENT_FILE.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for key, info in data.get("videos", {}).items():
        slug = key.split("/", 1)[0]
        vid = info.get("video_id")
        if slug and vid:
            out.setdefault(slug, []).append(vid)
    return out


def fetch_video_status(yt, video_ids: list[str]) -> dict[str, dict]:
    """Retourne {video_id: {privacyStatus, publishAt}}."""
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        resp = yt.videos().list(part="status", id=",".join(batch)).execute()
        for v in resp.get("items", []):
            out[v["id"]] = v.get("status", {})
    return out


class QuotaExceeded(Exception):
    """Raised when YouTube API daily quota is exhausted — caller stops cleanly."""


def _set_status(yt, video_id: str, body_status: dict) -> None:
    """Wrapper qui propage QuotaExceeded comme exception dédiée."""
    body = {"id": video_id, "status": {**body_status, "selfDeclaredMadeForKids": False}}
    try:
        yt.videos().update(part="status", body=body).execute()
    except Exception as e:
        msg = str(e)
        if "quotaExceeded" in msg:
            raise QuotaExceeded(msg) from e
        raise


def reschedule_one(yt, video_id: str, publish_at_utc: str,
                   current_status: dict, dry_run: bool) -> str:
    """
    Repositionne une vidéo à publish_at_utc. Stratégie :
      - Si déjà private + publishAt == cible → skip (idempotent)
      - Si déjà private (avec ou sans publishAt) → 1 call (update publishAt)
      - Si public  → 2 calls : d'abord private nu, puis private + publishAt
        (YouTube refuse public → private+publishAt en un seul appel)
    Retourne 'updated' / 'skipped-already' / 'dry-run' / 'error: <msg>'.
    Lève QuotaExceeded si le quota saute (pour bail-out propre).
    """
    priv = current_status.get("privacyStatus")
    current_pa = current_status.get("publishAt", "")

    # Idempotence : déjà au bon état
    if priv == "private" and current_pa[:19] == publish_at_utc[:19]:
        return "skipped-already"

    if dry_run:
        return "dry-run"

    try:
        if priv == "public":
            # 2-step : public → private nu, puis private + publishAt
            _set_status(yt, video_id, {"privacyStatus": "private"})
            _set_status(yt, video_id, {"privacyStatus": "private", "publishAt": publish_at_utc})
        else:
            _set_status(yt, video_id, {"privacyStatus": "private", "publishAt": publish_at_utc})
        return "updated"
    except QuotaExceeded:
        raise
    except Exception as e:
        return f"error: {e}"


def main():
    parser = argparse.ArgumentParser(description="Reschedule des vidéos YouTube vers leur slot d'origine.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--live", action="store_true",
                        help="Exécute pour de vrai. Sans ce flag : dry-run (rien n'est touché).")
    parser.add_argument("--slug", type=str, default=None,
                        help="Limite à un seul track (pour tester sur 1 vidéo)")
    parser.add_argument("--skip-public", action="store_true",
                        help="Ne touche pas aux vidéos déjà 'public' (ne reschedule QUE les private/scheduled)")
    parser.add_argument("--manual-map", type=Path, default=None,
                        help="JSON {slug: [video_id, ...]} pour overrider les sources auto")
    args = parser.parse_args()

    dry_run = not args.live
    mode = f"{Y}🔍 DRY-RUN{RESET}" if dry_run else f"{R}{B}⚡ LIVE{RESET}"
    print(f"\n{B}── reschedule_videos.py — {mode}{RESET}\n")

    # 1. Charger le config + filtrer
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    tracks = cfg.get("tracks", [])
    if args.slug:
        tracks = [t for t in tracks if t["slug"] == args.slug]
        if not tracks:
            sys.exit(f"❌ Slug '{args.slug}' introuvable dans {args.config}")

    # 2. Source 1 : tracker persistant (slug → video_ids)
    tracker_map = load_tracker_video_ids()

    # 3. Source 2 : manual map override (optionnel)
    manual_map: dict[str, list[str]] = {}
    if args.manual_map:
        manual_map = json.loads(args.manual_map.read_text(encoding="utf-8"))

    # 4. Auth + fetch des status courants
    yt = auth_youtube()
    all_ids: set[str] = set()
    track_to_ids: dict[str, list[str]] = {}
    for t in tracks:
        slug = t["slug"]
        ids = manual_map.get(slug) or tracker_map.get(slug, [])
        track_to_ids[slug] = list(dict.fromkeys(ids))  # dedupe, preserve order
        all_ids.update(ids)

    print(f"  → {len(tracks)} track(s) à traiter, {len(all_ids)} vidéo(s) cibles")
    print(f"  → Fetching current status of {len(all_ids)} videos...")
    status_map = fetch_video_status(yt, list(all_ids)) if all_ids else {}

    # 5. Reschedule
    counts = {"updated": 0, "dry-run": 0, "skipped-already": 0, "skipped-public": 0,
              "skipped-noslot": 0, "skipped-novids": 0, "error": 0, "quota-bail": 0}

    print(f"\n  {'#':>3}  {'Status before':>22}  {'New publishAt (UTC)':<22}  Action          Slug")
    print(f"  {'-'*3}  {'-'*22}  {'-'*22}  {'-'*15}  {'-'*45}")

    quota_hit = False
    for i, t in enumerate(tracks, 1):
        if quota_hit:
            counts["quota-bail"] += 1
            continue
        slug = t["slug"]
        scheduled_at = t.get("scheduled_at")
        if not scheduled_at:
            counts["skipped-noslot"] += 1
            print(f"  {i:>3}  {D}{'(no scheduled_at)':>22}{RESET}  {'-':<22}  {Y}skip-noslot{RESET}      {slug}")
            continue
        publish_at_utc = to_rfc3339_utc(scheduled_at)
        ids = track_to_ids.get(slug, [])
        if not ids:
            counts["skipped-novids"] += 1
            print(f"  {i:>3}  {D}{'(no video found)':>22}{RESET}  {publish_at_utc:<22}  {R}skip-novids{RESET}      {slug}")
            continue

        for vid in ids:
            if quota_hit:
                break
            st = status_map.get(vid, {})
            priv = st.get("privacyStatus", "?")
            current_pa = st.get("publishAt", "")
            label_before = f"{priv}" + (f" sched→{current_pa[:16]}" if current_pa else "")

            if args.skip_public and priv == "public":
                counts["skipped-public"] += 1
                print(f"  {i:>3}  {G}{label_before:>22}{RESET}  {publish_at_utc:<22}  {Y}skip-pub{RESET}         {slug} [{vid}]")
                continue

            try:
                result = reschedule_one(yt, vid, publish_at_utc, st, dry_run)
            except QuotaExceeded as e:
                quota_hit = True
                print(f"  {i:>3}  {label_before:>22}  {publish_at_utc:<22}  {R}QUOTA-BAIL{RESET}      {slug} [{vid}]")
                break

            counts.setdefault(result.split(":")[0], 0)
            if result.startswith("error"):
                counts["error"] += 1
            else:
                counts[result] = counts.get(result, 0) + 1

            tag = {
                "dry-run":         f"{C}DRY{RESET}            ",
                "updated":         f"{G}OK{RESET}             ",
                "skipped-already": f"{D}♻️  already-OK{RESET}",
            }.get(result, f"{R}ERR{RESET}            ")
            print(f"  {i:>3}  {label_before:>22}  {publish_at_utc:<22}  {tag}  {slug} [{vid}]")
            if result.startswith("error"):
                print(f"       {R}{result}{RESET}")

    # 6. Récap
    print(f"\n{B}── Résumé ──────────────────────────────────────────────────────{RESET}")
    if dry_run:
        print(f"  {C}🔍 Dry-run : {counts.get('dry-run', 0)} vidéo(s) seraient repogrammées{RESET}")
    else:
        print(f"  {G}✅ Updated         : {counts.get('updated', 0)}{RESET}")
    if counts.get("skipped-already"):
        print(f"  {D}♻️  Déjà au bon état : {counts['skipped-already']}{RESET}")
    if counts.get("skipped-public"):
        print(f"  {Y}⏭  Skipped public  : {counts['skipped-public']}{RESET}")
    if counts.get("skipped-noslot"):
        print(f"  {Y}⏭  Skipped no slot : {counts['skipped-noslot']}{RESET}")
    if counts.get("skipped-novids"):
        print(f"  {R}⏭  Skipped no video: {counts['skipped-novids']}{RESET}")
    if counts.get("error"):
        print(f"  {R}❌ Errors          : {counts['error']}{RESET}")
    if quota_hit or counts.get("quota-bail"):
        print(f"  {R}⛔ Quota bail-out  : {counts.get('quota-bail', 0)} track(s) non traités (quota épuisé){RESET}")
        print(f"\n  {Y}→ Quota YouTube reset à minuit Pacific (~9h Paris). Relance demain :{RESET}")
        print(f"     python3 scripts/reschedule_videos.py --live")
        print(f"     {D}(les vidéos déjà au bon publishAt seront skip automatiquement){RESET}")
    elif dry_run:
        print(f"\n  {D}# Pour exécuter pour de vrai :{RESET}")
        print(f"  python3 scripts/reschedule_videos.py --live")
    print()


if __name__ == "__main__":
    main()
