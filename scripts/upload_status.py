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


def fetch_youtube_titles(since_iso: str | None = None) -> dict[str, dict]:
    """
    Fetch all videos from the user's uploads playlist.
    Returns {title: {video_id, published_at, status}}.
    Si since_iso est fourni (ex: "2026-04-25"), ne renvoie que les vidéos
    uploadées après cette date — utile pour ne pas mélanger avec l'historique.
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
            published = sn.get("publishedAt", "")
            if since_iso and published and published < since_iso:
                continue  # trop vieux
            titles_to_video[sn["title"]] = {
                "video_id":     sn["resourceId"]["videoId"],
                "published_at": published,
                "privacy":      item.get("status", {}).get("privacyStatus"),
            }
        req = yt.playlistItems().list_next(req, resp)

    # 3. Enrichir avec status.publishAt + status.privacyStatus via videos().list
    #    (1 call par batch de 50 = ~1 unité quota au total).
    ids = [info["video_id"] for info in titles_to_video.values()]
    id_to_info = {info["video_id"]: info for info in titles_to_video.values()}
    for batch_start in range(0, len(ids), 50):
        batch = ids[batch_start:batch_start + 50]
        resp = yt.videos().list(part="status", id=",".join(batch)).execute()
        for v in resp.get("items", []):
            st = v.get("status", {})
            info = id_to_info.get(v["id"])
            if info is not None:
                info["privacy"]    = st.get("privacyStatus")
                info["publish_at"] = st.get("publishAt")  # ISO si scheduled, sinon None

    return titles_to_video


def _match_youtube(track: dict, yt_titles: dict) -> list[dict]:
    """
    Cherche toutes les vidéos YouTube qui matchent ce track.
    Stratégies (par ordre de précision) :
      1. Match exact sur track['title']
      2. Match "title - <suffix>" (cas multi-vidéos main/shorts)
      3. Match prefix sur suno_title (court, unique : "Bedroom Hours")
      4. Match prefix sur la partie avant "—" (titre raccourci des shorts)
    """
    full_title = track.get("title", "").strip()
    suno_title = (track.get("suno_title") or "").strip()
    short_form = full_title.split("—")[0].strip() if "—" in full_title else None

    matches = []
    seen_ids = set()
    for yt_title, info in yt_titles.items():
        vid = info["video_id"]
        if vid in seen_ids:
            continue
        yt_low = yt_title.strip().lower()
        match_reason = None

        if full_title and yt_low == full_title.lower():
            match_reason = "exact"
        elif full_title and yt_low.startswith(full_title.lower() + " - "):
            match_reason = "title+suffix"
        elif suno_title and yt_low.startswith(suno_title.lower()):
            match_reason = "suno-prefix"
        elif suno_title and suno_title.lower() in yt_low:
            match_reason = "suno-substring"
        elif short_form and yt_low.startswith(short_form.lower()):
            match_reason = "short-prefix"

        if match_reason:
            matches.append({**info, "yt_title": yt_title, "match_reason": match_reason})
            seen_ids.add(vid)
    return matches


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

    # YouTube ground truth : matching tolérant (multi-strategy).
    yt_matches = []
    if yt_titles is not None:
        yt_matches = _match_youtube(track, yt_titles)

    status = "missing"
    detail_parts = []

    if n_files == 0:
        status = "missing"
        detail_parts.append(f"{R}aucun MP4{RESET}")
    elif yt_matches:
        # Considéré uploadé dès qu'au moins UNE vidéo correspondante existe sur la chaîne.
        # Si on a moins de vidéos sur YT que de MP4 locaux → partiel.
        if len(yt_matches) >= n_files:
            status = "uploaded"
        elif len(yt_matches) >= 1:
            status = "partial"
        ids = ", ".join(m["video_id"] for m in yt_matches[:3])
        more = f" +{len(yt_matches)-3}" if len(yt_matches) > 3 else ""
        reasons = ",".join(sorted({m["match_reason"] for m in yt_matches}))
        # Extra : montre privacy + publishAt si dispo
        extras = []
        for m in yt_matches[:3]:
            priv = m.get("privacy", "?")
            pa   = m.get("publish_at")
            if pa:
                extras.append(f"{priv} sched→{pa[:16]}")
            else:
                extras.append(priv)
        extras_str = f" {{{ ' | '.join(extras) }}}" if extras else ""
        color = G if status == "uploaded" else Y
        detail_parts.append(f"{color}YT: {len(yt_matches)}/{n_files} [{ids}{more}] ({reasons}){extras_str}{RESET}")
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
        "yt_matches":   yt_matches,
        "detail":       " · ".join(detail_parts),
    }


def main():
    parser = argparse.ArgumentParser(description="Status des 35 uploads de la semaine.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check-youtube", action="store_true",
                        help="Fetch la liste des vidéos uploadées sur YouTube (ground truth, ~10 unités quota)")
    parser.add_argument("--since", type=str, default=None,
                        help="Filtre les vidéos YouTube uploadées AVANT cette date ISO (défaut : 2 jours avant le start_date du config)")
    parser.add_argument("--debug-titles", action="store_true",
                        help="Affiche tous les titres YouTube récents pour diagnostic")
    parser.add_argument("--save-tracker", action="store_true",
                        help="Backfill youtube_uploaded_videos.json depuis les matches YouTube. "
                             "Utile pour ne pas re-uploader des vidéos déjà sur la chaîne.")
    parser.add_argument("--json", action="store_true", help="Sortie JSON brute")
    args = parser.parse_args()

    tracks = load_tracks(args.config)
    persistent = load_persistent_tracker()

    # Compute since_iso : par défaut, 2 jours avant le start_date du config.
    since_iso = args.since
    if args.check_youtube and since_iso is None:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        start = cfg.get("schedule", {}).get("start_date") or cfg.get("date")
        if start:
            from datetime import datetime as _dt, timedelta as _td
            d = _dt.fromisoformat(start) - _td(days=2)
            since_iso = d.isoformat() + "Z"

    yt_titles = fetch_youtube_titles(since_iso=since_iso) if args.check_youtube else None

    if args.debug_titles and yt_titles:
        print(f"\n{B}── Titres YouTube récents (since {since_iso}) ─────────────────{RESET}")
        for t, info in sorted(yt_titles.items(), key=lambda kv: kv[1].get("published_at", "")):
            print(f"  {info.get('published_at','?')[:19]}  [{info['video_id']}]  {t}")
        print(f"\n  Total : {len(yt_titles)} vidéo(s) sur la période")

    rows = [classify(t, persistent, yt_titles) for t in tracks]

    if args.save_tracker and yt_titles is not None:
        from datetime import datetime as _dt
        added = 0
        skipped = 0
        for r, t in zip(rows, tracks):
            slug = r["slug"]
            locals = find_local_videos(slug)
            local_main = locals["main"][0] if locals["main"] else None
            local_short = locals["shorts"][0] if locals["shorts"] else None

            for m in r.get("yt_matches", []):
                yt_title = m["yt_title"]
                is_short = "#Shorts" in yt_title or "#shorts" in yt_title
                local_path = local_short if is_short else local_main
                if not local_path:
                    skipped += 1
                    continue
                pkey = f"{slug}/{Path(local_path).name}"
                if pkey in persistent.get("videos", {}):
                    continue  # already in tracker
                persistent.setdefault("videos", {})[pkey] = {
                    "video_id":    m["video_id"],
                    "uploaded_at": m.get("published_at") or _dt.now().isoformat(timespec="seconds"),
                    "url":         f"https://www.youtube.com/watch?v={m['video_id']}",
                    "is_short":    is_short,
                    "publish_at":  None,
                    "_backfilled": True,
                    "_match_reason": m["match_reason"],
                }
                added += 1
        PERSISTENT_FILE.write_text(json.dumps(persistent, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{G}✓ Tracker mis à jour : +{added} entrées (skip {skipped} sans MP4 local){RESET}")
        print(f"  → {PERSISTENT_FILE}")

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

    # Récap planning : privacy + publishAt par track matché
    if yt_titles:
        scheduled = []
        public_now = []
        private_no_sched = []
        for r in rows:
            for m in r.get("yt_matches", []):
                priv = m.get("privacy")
                pa = m.get("publish_at")
                entry = (r["scheduled_at"][:16] if r["scheduled_at"] != "?" else "?",
                         m["video_id"], r["slug"], priv, pa)
                if pa:
                    scheduled.append(entry)
                elif priv == "public":
                    public_now.append(entry)
                else:
                    private_no_sched.append(entry)

        print(f"\n{B}── Planning vs réalité ──────────────────────────────────────────{RESET}")
        print(f"  {G}🟢 Public (déjà visible)        : {len(public_now):>3}{RESET}")
        print(f"  {Y}🕒 Scheduled (publishAt futur)  : {len(scheduled):>3}{RESET}")
        if private_no_sched:
            print(f"  {R}🔒 Private sans scheduling     : {len(private_no_sched):>3}{RESET}")

        if scheduled:
            print(f"\n  {Y}Programmées :{RESET}")
            from collections import Counter
            by_day: Counter = Counter()
            for slot, vid, slug, priv, pa in sorted(scheduled, key=lambda x: x[4]):
                day = pa[:10]
                by_day[day] += 1
                print(f"    {pa[:16]}  [{vid}]  {slug}  {D}(slot prévu : {slot}){RESET}")
            print(f"\n  {D}Distribution par jour :{RESET}")
            for day, n in sorted(by_day.items()):
                print(f"    {day} : {n} vidéo(s)")

    # Vidéos YouTube non rattachées à un track du config — utile pour debug
    if yt_titles:
        matched_ids = {m["video_id"] for r in rows for m in r.get("yt_matches", [])}
        unmatched = {t: info for t, info in yt_titles.items() if info["video_id"] not in matched_ids}
        if unmatched:
            print(f"\n{B}── Vidéos YouTube récentes non matchées ({len(unmatched)}) ─────────────{RESET}")
            print(f"  {D}(uploadées sur la période mais ne correspondent à aucun slug du config){RESET}")
            for t, info in sorted(unmatched.items(), key=lambda kv: kv[1].get("published_at", "")):
                print(f"  {D}{info.get('published_at','?')[:10]}  [{info['video_id']}]{RESET}  {t[:80]}")

    if not yt_titles:
        print(f"\n{D}  💡 Tip : ajoute --check-youtube pour vérifier la chaîne directement{RESET}")
    print()


if __name__ == "__main__":
    main()
