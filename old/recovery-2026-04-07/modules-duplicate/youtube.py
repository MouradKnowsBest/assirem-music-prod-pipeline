"""
Module youtube.py - Upload des MP4 sur YouTube via YouTube Data API v3
"""

import os
import json
import time
import pickle

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE  = "youtube"
API_VERSION  = "v3"

CLIENT_SECRETS_PATH = "credentials/client_secret.json"
OAUTH_TOKEN_PATH    = "credentials/youtube_oauth.pickle"

CHUNK_SIZE = 4 * 1024 * 1024  # 4 Mo par chunk


# ─── Authentification ─────────────────────────────────────────────────────────

def _authentifier(base_dir: str):
    """
    Retourne un service YouTube authentifié.
    - Si credentials/youtube_oauth.pickle existe → rechargement du token.
    - Sinon → flux OAuth2 navigateur (génère le pickle pour les prochaines fois).
    Nécessite credentials/client_secret.json (téléchargé depuis Google Cloud Console).
    """
    token_path  = os.path.join(base_dir, OAUTH_TOKEN_PATH)
    secret_path = os.path.join(base_dir, CLIENT_SECRETS_PATH)

    creds = None

    # Charger le token existant
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        print("  → Token OAuth2 chargé depuis le cache.")

    # Rafraîchir si expiré
    if creds and creds.expired and creds.refresh_token:
        import google.auth.transport.requests
        creds.refresh(google.auth.transport.requests.Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        print("  → Token rafraîchi automatiquement.")

    # Nouveau flux OAuth2 (première utilisation)
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


# ─── Gestion des playlists ────────────────────────────────────────────────────

def _trouver_ou_creer_playlist(youtube, nom: str) -> str:
    """
    Cherche une playlist par nom dans la chaîne.
    La crée si elle n'existe pas. Retourne l'ID de la playlist.
    """
    # Chercher dans les playlists existantes
    req = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while req:
        resp = req.execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"].strip().lower() == nom.strip().lower():
                playlist_id = item["id"]
                print(f"  → Playlist trouvée : \"{nom}\" (ID: {playlist_id})")
                return playlist_id
        req = youtube.playlists().list_next(req, resp)

    # Créer la playlist
    print(f"  → Création de la playlist : \"{nom}\"...")
    resp = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": nom,
                "description": f"Playlist gérée automatiquement par Assirem Music PROD Pipeline",
            },
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    playlist_id = resp["id"]
    print(f"  → Playlist créée (ID: {playlist_id})")
    return playlist_id


def _ajouter_a_playlist(youtube, video_id: str, playlist_id: str) -> None:
    """Ajoute une vidéo à une playlist."""
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


# ─── Upload ───────────────────────────────────────────────────────────────────

def _uploader_video(youtube, chemin: str, titre: str, description: str, tags: list) -> str:
    """
    Upload un MP4 sur YouTube avec reprise automatique en cas d'erreur réseau.
    Retourne l'ID de la vidéo uploadée.
    """
    taille_mo = os.path.getsize(chemin) / (1024 * 1024)
    print(f"  → Upload : {os.path.basename(chemin)} ({taille_mo:.1f} Mo)...")

    body = {
        "snippet": {
            "title": titre,
            "description": description,
            "tags": tags,
            "categoryId": "10",  # Musique
            "defaultLanguage": "fr",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(chemin, chunksize=CHUNK_SIZE, resumable=True)
    requete = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    erreurs_consecutives = 0
    MAX_ERREURS = 10
    ERREURS_RESEAU = (500, 502, 503, 504)

    while response is None:
        try:
            status, response = requete.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                barres = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r     [{barres}] {pct}%", end="", flush=True)
            erreurs_consecutives = 0
        except googleapiclient.errors.HttpError as e:
            if e.resp.status in ERREURS_RESEAU:
                erreurs_consecutives += 1
                if erreurs_consecutives > MAX_ERREURS:
                    raise RuntimeError(
                        f"Trop d'erreurs réseau consécutives lors de l'upload : {e}"
                    )
                attente = 2 ** erreurs_consecutives
                print(f"\n  ⚠️  Erreur {e.resp.status}, nouvelle tentative dans {attente}s...")
                time.sleep(attente)
            else:
                raise RuntimeError(f"Erreur YouTube API lors de l'upload : {e}")

    print()  # nouvelle ligne après la barre de progression
    video_id = response["id"]
    return video_id


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def uploader_videos(config: dict, videos: list, base_dir: str) -> None:
    """
    Upload chaque MP4 de la liste sur YouTube, crée/trouve la playlist,
    et ajoute chaque vidéo à la playlist.
    """
    if not videos:
        print("  → Aucune vidéo à uploader.")
        return

    titre         = config.get("title", "Assirem Music")
    description   = config.get("description", "")
    tags          = config.get("tags", [])
    playlist_nom  = config.get("playlist_name", "Assirem Music")

    print("  → Authentification YouTube...")
    youtube = _authentifier(base_dir)

    print("  → Recherche / création de la playlist...")
    playlist_id = _trouver_ou_creer_playlist(youtube, playlist_nom)

    for i, chemin_video in enumerate(videos, 1):
        # Adapter le titre si plusieurs vidéos (mode individual)
        if len(videos) > 1:
            nom_fichier = os.path.splitext(os.path.basename(chemin_video))[0]
            titre_video = f"{titre} - {nom_fichier.replace('_', ' ').title()}"
        else:
            titre_video = titre

        print(f"\n  ── Vidéo {i}/{len(videos)} : {os.path.basename(chemin_video)}")
        video_id = _uploader_video(youtube, chemin_video, titre_video, description, tags)

        print(f"  → Ajout à la playlist \"{playlist_nom}\"...")
        _ajouter_a_playlist(youtube, video_id, playlist_id)

        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"  ✅ Vidéo publiée : {url}")
