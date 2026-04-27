"""
Module youtube.py - Upload des MP4 sur YouTube via YouTube Data API v3
"""

import os
import time
import pickle

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE = "youtube"
API_VERSION = "v3"

CLIENT_SECRETS_PATH = "credentials/client_secret.json"
OAUTH_TOKEN_PATH = "credentials/youtube_oauth.pickle"

CHUNK_SIZE = 4 * 1024 * 1024

# Playlist generaliste : reçoit toute vidéo (et sert de fallback quand
# une playlist thématique demandée est introuvable).
ALL_TRACKS_PLAYLIST = "🎵 Assirem Music PROD — All Tracks"


class UploadLimitExceeded(Exception):
    """Levée quand YouTube refuse l'upload pour limite quotidienne dépassée."""


def _authentifier(base_dir: str):
    """
    Retourne un service YouTube authentifié.
    - Si credentials/youtube_oauth.pickle existe → rechargement du token.
    - Sinon → flux OAuth2 navigateur (génère le pickle pour les prochaines fois).
    Nécessite credentials/client_secret.json.
    """
    token_path = os.path.join(base_dir, OAUTH_TOKEN_PATH)
    secret_path = os.path.join(base_dir, CLIENT_SECRETS_PATH)

    creds = None

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        print("  → Token OAuth2 chargé depuis le cache.")

    if creds and creds.expired and creds.refresh_token:
        import google.auth.transport.requests

        creds.refresh(google.auth.transport.requests.Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        print("  → Token rafraîchi automatiquement.")

    if not creds or not creds.valid:
        if not os.path.exists(secret_path):
            raise FileNotFoundError(
                f"Fichier introuvable : {secret_path}\n"
                "Téléchargez votre client_secret.json depuis Google Cloud Console\n"
                "(APIs & Services → Identifiants → Télécharger OAuth 2.0)\n"
                "et placez-le dans credentials/client_secret.json"
            )
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            secret_path, SCOPES
        )
        print("  → Ouverture du navigateur pour l'authentification YouTube...")
        creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        print(f"  → Token sauvegardé : {token_path}")

    return googleapiclient.discovery.build(API_SERVICE, API_VERSION, credentials=creds)


def _trouver_playlist(youtube, nom: str):
    """
    Cherche une playlist existante (match case-insensitive sur le titre, après
    .strip()). Retourne l'ID si trouvée, None sinon.
    Ne crée JAMAIS de playlist : la taxonomie est figée par
    scripts/reorganize_playlists.py et doit pas se refragmenter.
    """
    cible = nom.strip().lower()
    req = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while req:
        resp = req.execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"].strip().lower() == cible:
                playlist_id = item["id"]
                print(f"  → Playlist trouvée : \"{nom}\" (ID: {playlist_id})")
                return playlist_id
        req = youtube.playlists().list_next(req, resp)
    return None


def _ajouter_a_playlist(youtube, video_id: str, playlist_id: str) -> None:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            }
        },
    ).execute()


def _uploader_video(
    youtube,
    chemin: str,
    titre: str,
    description: str,
    tags: list,
    is_short: bool = False,
    publish_at: str = None,
) -> str:
    taille_mo = os.path.getsize(chemin) / (1024 * 1024)
    label = "Short" if is_short else "Upload"
    sched_label = f" → publish {publish_at}" if publish_at else ""
    print(f"  → {label} : {os.path.basename(chemin)} ({taille_mo:.1f} Mo){sched_label}...")

    # YouTube détecte automatiquement les Shorts via ratio d'aspect vertical
    # + durée ≤ 60s, mais on ajoute #Shorts au titre/description pour l'algo.
    if is_short:
        if "#Shorts" not in titre and "#shorts" not in titre:
            titre = f"{titre} #Shorts"
        if "#Shorts" not in description and "#shorts" not in description:
            description = f"{description}\n\n#Shorts"

    status = {"selfDeclaredMadeForKids": False}
    if publish_at:
        # Scheduled publish: must be private at upload, YouTube flips to public at publishAt
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": titre[:100],  # YouTube limite à 100 caractères
            "description": description,
            "tags": tags,
            "categoryId": "10",
            "defaultLanguage": "fr",
        },
        "status": status,
    }

    media = MediaFileUpload(chemin, chunksize=CHUNK_SIZE, resumable=True)
    requete = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    erreurs_consecutives = 0
    max_erreurs = 10
    erreurs_reseau = (500, 502, 503, 504)

    while response is None:
        try:
            status, response = requete.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                barres = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r     [{barres}] {pct}%", end="", flush=True)
            erreurs_consecutives = 0
        except googleapiclient.errors.HttpError as e:
            if e.resp.status in erreurs_reseau:
                erreurs_consecutives += 1
                if erreurs_consecutives > max_erreurs:
                    raise RuntimeError(
                        f"Trop d'erreurs réseau consécutives lors de l'upload : {e}"
                    )
                attente = 2 ** erreurs_consecutives
                print(f"\n  ⚠️  Erreur {e.resp.status}, nouvelle tentative dans {attente}s...")
                time.sleep(attente)
            else:
                err_str = str(e)
                if "uploadLimitExceeded" in err_str:
                    raise UploadLimitExceeded(
                        f"⛔ Limite d'upload YouTube atteinte pour aujourd'hui.\n"
                        f"  YouTube limite le nombre de vidéos uploadées par jour par chaîne.\n"
                        f"  → Réessayez demain, ou vérifiez/authentifiez votre chaîne pour augmenter la limite.\n"
                        f"  → Détail : {e}"
                    )
                if "quotaExceeded" in err_str or "quota.*exceeded" in err_str.lower():
                    raise UploadLimitExceeded(
                        f"⛔ Quota YouTube Data API atteint pour aujourd'hui.\n"
                        f"  Quota par défaut = 10 000 unités/jour, 1 upload ≈ 1 600 unités\n"
                        f"  → ~6 uploads/jour max au quota standard.\n"
                        f"  → Reset à minuit Pacific Time (~9h Paris).\n"
                        f"  → Demande d'augmentation : Google Cloud Console\n"
                        f"     → APIs & Services → Quotas → YouTube Data API v3 → Edit\n"
                        f"  → Détail : {e}"
                    )
                raise RuntimeError(f"Erreur YouTube API lors de l'upload : {e}")

    print()
    return response["id"]


def uploader_videos(
    config: dict,
    videos: list,
    base_dir: str,
    *,
    skip_playlists: bool = False,
    force_playlist: str | None = None,
) -> None:
    """
    Upload chaque MP4 de la liste sur YouTube, crée/trouve la playlist,
    et ajoute chaque vidéo à la playlist.

    Une vidéo dont le chemin contient '/shorts/' est uploadée en mode Short
    (avec #Shorts ajouté automatiquement) et N'EST PAS ajoutée à la playlist.

    Lève UploadLimitExceeded si YouTube refuse (limite quotidienne).
    """
    if not videos:
        print("  → Aucune vidéo à uploader.")
        return

    slug = config.get("slug", "unknown")
    titre = config.get("title", "Assirem Music")
    description = config.get("description", "")
    tags = config.get("tags", [])
    publish_at = config.get("publish_at")  # ISO RFC3339 UTC, ex: "2026-04-25T06:15:00Z"

    tracker = _charger_tracker(base_dir)
    if tracker["uploads"] > 0:
        print(f"  📊 Uploads aujourd'hui : {tracker['uploads']} vidéo(s) ({', '.join(tracker['slugs'])})")

    print("  → Authentification YouTube...")
    youtube = _authentifier(base_dir)

    # ── Résolution des playlists cibles ─────────────────────────────────────
    playlist_ids: list[tuple[str, str]] = []  # (nom_logique, id) sans doublon d'id

    if skip_playlists:
        print(f"  ⏭  Playlists ignorées (--no-playlists). La vidéo sera uploadée nue.")
    else:
        # Mode 1 — force_playlist : on n'utilise QUE celle-ci, ignore le config.
        if force_playlist:
            pid = _trouver_playlist(youtube, force_playlist)
            if pid is None:
                print(f"  ❌ Playlist forcée introuvable : \"{force_playlist}\"")
                print(f"     → Upload sans playlist (fallback safe).")
            else:
                playlist_ids.append((force_playlist, pid))
        else:
            # Mode 2 — config-driven : playlists du track + fallback All Tracks
            playlist_noms = list(config.get("playlists") or [])
            primary = config.get("playlist_name")
            if primary and primary not in playlist_noms:
                playlist_noms.insert(0, primary)

            all_tracks_id = _trouver_playlist(youtube, ALL_TRACKS_PLAYLIST)
            if all_tracks_id is None:
                print(f"  ⚠️  Playlist generaliste introuvable : \"{ALL_TRACKS_PLAYLIST}\"")
                print(f"     → Crée-la via reorganize_playlists.py — pour cette fois, upload nu.")

            print(f"  → Résolution des playlists cibles ({len(playlist_noms)})...")
            seen_ids: set[str] = set()
            for nom in playlist_noms:
                pid = _trouver_playlist(youtube, nom)
                if pid is None:
                    if all_tracks_id is None:
                        print(f"  ⚠️  Playlist introuvable, et pas de fallback dispo : \"{nom}\"")
                        continue
                    print(f"  ⚠️  Playlist introuvable, fallback {ALL_TRACKS_PLAYLIST} : \"{nom}\"")
                    pid = all_tracks_id
                    nom = f"{ALL_TRACKS_PLAYLIST} (fallback ← {nom})"
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    playlist_ids.append((nom, pid))

            # Garantie : All Tracks toujours dans la liste si dispo.
            if all_tracks_id is not None and all_tracks_id not in seen_ids:
                playlist_ids.append((ALL_TRACKS_PLAYLIST, all_tracks_id))

    persistent = _charger_persistent(base_dir)

    for i, chemin_video in enumerate(videos, 1):
        is_short = os.sep + "shorts" + os.sep in chemin_video or "/shorts/" in chemin_video

        # Skip si déjà uploadé (tracker persistant cross-day)
        pkey = _persistent_key(slug, chemin_video)
        existing = persistent.get("videos", {}).get(pkey)
        if existing:
            print(f"\n  ── {'Short' if is_short else 'Vidéo'} {i}/{len(videos)} : "
                  f"{os.path.basename(chemin_video)}")
            print(f"  ♻️  Déjà uploadé le {existing.get('uploaded_at','?')[:10]}, skip.")
            print(f"     URL : {existing.get('url','?')}")
            continue

        if len(videos) > 1 and not is_short:
            nom_fichier = os.path.splitext(os.path.basename(chemin_video))[0]
            titre_video = f"{titre} - {nom_fichier.replace('_', ' ').title()}"
        elif is_short:
            # Short : titre plus court, sans le branding long
            titre_video = titre.split("—")[0].strip()[:90]
        else:
            titre_video = titre

        print(f"\n  ── {'Short' if is_short else 'Vidéo'} {i}/{len(videos)} : {os.path.basename(chemin_video)}")
        video_id = _uploader_video(
            youtube, chemin_video, titre_video, description, tags,
            is_short=is_short, publish_at=publish_at,
        )

        if not is_short:
            for nom, pid in playlist_ids:
                try:
                    print(f"  → Ajout à la playlist \"{nom}\"...")
                    _ajouter_a_playlist(youtube, video_id, pid)
                except googleapiclient.errors.HttpError as e:
                    print(f"  ⚠️  Échec ajout playlist \"{nom}\" (continue) : {e}")

        tracker["uploads"] += 1
        if slug not in tracker["slugs"]:
            tracker["slugs"].append(slug)
        _sauver_tracker(base_dir, tracker)

        url = f"https://www.youtube.com/watch?v={video_id}"

        # Tracker persistant cross-day
        persistent.setdefault("videos", {})[pkey] = {
            "video_id":    video_id,
            "uploaded_at": _dt.now().isoformat(timespec="seconds"),
            "url":         url,
            "is_short":    is_short,
            "publish_at":  publish_at,
        }
        _sauver_persistent(base_dir, persistent)

        if publish_at:
            label = "Short programmé" if is_short else "Vidéo programmée"
            print(f"  ✅ {label} (publish {publish_at}) : {url}")
        else:
            label = "Short publié" if is_short else "Vidéo publiée"
            print(f"  ✅ {label} : {url}")
        print(f"  📊 Total uploads aujourd'hui : {tracker['uploads']}")


# ── Tracker d'uploads journalier ─────────────────────────────────────────────

import json
from datetime import date as _date, datetime as _dt

_TRACKER_FILE = "youtube_upload_tracker.json"
_PERSISTENT_FILE = "youtube_uploaded_videos.json"


def _charger_tracker(base_dir: str) -> dict:
    """Charge le tracker du jour (remet à zéro si c'est un nouveau jour)."""
    path = os.path.join(base_dir, _TRACKER_FILE)
    today = str(_date.today())
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            return data
    return {"date": today, "uploads": 0, "slugs": []}


def _sauver_tracker(base_dir: str, tracker: dict) -> None:
    """Persiste le tracker sur disque."""
    path = os.path.join(base_dir, _TRACKER_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)


def get_upload_count_today(base_dir: str) -> tuple:
    """Retourne (nb_uploads_aujourd'hui, liste_de_slugs)."""
    tracker = _charger_tracker(base_dir)
    return tracker["uploads"], tracker["slugs"]


# ── Tracker persistant cross-day (pour reprise après quotaExceeded) ──────────

def _charger_persistent(base_dir: str) -> dict:
    """
    Charge le tracker persistant des uploads (jamais réinitialisé).
    Format : { "videos": { "<slug>/<basename>": {"video_id": "...", "uploaded_at": "ISO", "url": "..."} } }
    """
    path = os.path.join(base_dir, _PERSISTENT_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"videos": {}}


def _sauver_persistent(base_dir: str, data: dict) -> None:
    path = os.path.join(base_dir, _PERSISTENT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _persistent_key(slug: str, video_path: str) -> str:
    return f"{slug}/{os.path.basename(video_path)}"


def is_already_uploaded(base_dir: str, slug: str, video_path: str) -> dict | None:
    """Retourne le record persistant si la vidéo a déjà été uploadée, None sinon."""
    persistent = _charger_persistent(base_dir)
    return persistent.get("videos", {}).get(_persistent_key(slug, video_path))
