#!/usr/bin/env python3
"""
drive_stock.py — Gestion du "stock" Google Drive pour le pipeline Assirem

Structure Drive attendue (dossier partagé avec le service account) :
  Assirem Stock/
    pocket-of-matches/  ← tu déposes ici un dossier par track (slug = nom du dossier)
      Pocket of Matches.mp3
      Image générée 1.png
    done/               ← créé automatiquement après succès
    failed/             ← créé automatiquement après échec

Convention de nommage :
  Le "slug" est le nom du dossier.
  Exemple : dossier "pocket-of-matches" → slug = "pocket-of-matches"

Usage :
  python scripts/drive_stock.py list
  python scripts/drive_stock.py download ./stock
  python scripts/drive_stock.py download ./stock --slug lofi-coffee-shop
  python scripts/drive_stock.py mark-done lofi-coffee-shop
  python scripts/drive_stock.py mark-failed lofi-coffee-shop

Variables d'environnement :
  DRIVE_SERVICE_ACCOUNT_JSON  — JSON du service account (inline ou chemin vers fichier)
  DRIVE_ROOT_FOLDER_ID        — ID du dossier racine "Assirem Stock" dans Drive
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    print("❌ Install: pip install google-api-python-client google-auth", file=sys.stderr)
    sys.exit(1)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

AUDIO_EXTS = {"mp3", "wav", "m4a", "flac", "aac", "ogg"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
DOWNLOAD_EXTS = AUDIO_EXTS | IMAGE_EXTS | {"json"}


def _build_service():
    raw = os.environ.get("DRIVE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError(
            "Variable DRIVE_SERVICE_ACCOUNT_JSON manquante.\n"
            "Crée un Service Account Google, partage le dossier Drive avec son email,\n"
            "puis stocke le JSON en secret GitHub GOOGLE_DRIVE_SA_JSON."
        )
    info = json.loads(raw) if raw.strip().startswith("{") else json.load(open(raw))
    creds = service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_folder_id(svc, parent_id: str, name: str) -> Optional[str]:
    name_esc = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents"
        f" and name='{name_esc}'"
        f" and mimeType='application/vnd.google-apps.folder'"
        f" and trashed=false"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _ensure_folder(svc, parent_id: str, name: str) -> str:
    existing = _get_folder_id(svc, parent_id, name)
    if existing:
        return existing
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = svc.files().create(body=meta, fields="id").execute()
    return folder["id"]


def list_tracks(svc, root_id: str) -> list[dict]:
    """
    Retourne la liste des tracks directement dans le dossier racine (Assirem Stock/).

    Structure Drive attendue :
      Assirem Stock/
        pocket-of-matches/    ← slug = nom du dossier
          Pocket of Matches.mp3
          Image générée 1.png
        done/                 ← géré automatiquement
        failed/               ← géré automatiquement

    Chaque élément : {"slug": str, "folder_id": str, "files": {type: filename}, "file_ids": {type: id}}
    """
    SYSTEM_FOLDERS = {"done", "failed", "incoming", "processing"}

    # Liste les sous-dossiers directs de la racine (hors dossiers système)
    q = (
        f"'{root_id}' in parents"
        f" and mimeType='application/vnd.google-apps.folder'"
        f" and trashed=false"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1000).execute()
    folders = [f for f in res.get("files", []) if f["name"].lower() not in SYSTEM_FOLDERS]

    tracks = []
    for folder in folders:
        slug = folder["name"]
        folder_id = folder["id"]

        # Liste les fichiers dans ce dossier
        q2 = f"'{folder_id}' in parents and trashed=false"
        res2 = svc.files().list(q=q2, fields="files(id,name,size)", pageSize=100).execute()

        track = {"slug": slug, "folder_id": folder_id, "files": {}, "file_ids": {}, "_audio_all": []}
        for f in res2.get("files", []):
            name = f["name"]
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            if ext not in DOWNLOAD_EXTS:
                continue
            if ext == "json":
                key = "json"
            elif ext in AUDIO_EXTS:
                key = "audio"
            else:
                key = "img"

            if ext in AUDIO_EXTS:
                # Collecte TOUS les fichiers audio (pour concaténation)
                track["_audio_all"].append((f["id"], name))
                if "audio" not in track["files"]:
                    track["files"]["audio"] = name
                    track["file_ids"]["audio"] = f["id"]
            else:
                # img et json : garde le premier seulement
                if key not in track["files"]:
                    track["files"][key] = name
                    track["file_ids"][key] = f["id"]

        tracks.append(track)

    return tracks


def _download_file(svc, file_id: str, dest: Path, filename: str):
    dest.parent.mkdir(parents=True, exist_ok=True)
    size_mb = ""
    try:
        meta = svc.files().get(fileId=file_id, fields="size").execute()
        size_mb = f" ({int(meta.get('size', 0)) / 1e6:.1f} MB)"
    except Exception:
        pass

    print(f"  ↓ {filename}{size_mb}")
    req = svc.files().get_media(fileId=file_id)
    with open(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()


def download_tracks(svc, root_id: str, dest_dir: str, slug: Optional[str] = None) -> list[dict]:
    """
    Télécharge les fichiers depuis incoming/ vers dest_dir/<slug>/.
    Retourne la liste des tracks téléchargés avec leurs chemins locaux.
    """
    tracks = list_tracks(svc, root_id)
    if slug:
        tracks = [t for t in tracks if t["slug"] == slug]
        if not tracks:
            print(f"  ⚠️  Track '{slug}' introuvable dans incoming/")
            return []

    downloaded = []
    for track in tracks:
        if "audio" not in track["files"]:
            print(f"  ⚠️  {track['slug']} : pas de fichier audio, ignoré")
            continue

        slug_dir = Path(dest_dir) / track["slug"]
        paths = {"slug": track["slug"]}

        # Télécharge TOUS les fichiers audio
        audio_list = track.get("_audio_all") or [(track["file_ids"]["audio"], track["files"]["audio"])]
        for file_id, filename in audio_list:
            dest = slug_dir / filename
            _download_file(svc, file_id, dest, filename)
        paths["audio"] = str(slug_dir)

        # Télécharge img et json (premier seulement)
        for key in ("img", "json"):
            if key in track["file_ids"]:
                filename = track["files"][key]
                dest = slug_dir / filename
                _download_file(svc, track["file_ids"][key], dest, filename)
                paths[key] = str(dest)

        n_audio = len(audio_list)
        print(f"  ✅ {track['slug']} → {slug_dir}/  ({n_audio} audio{'s' if n_audio > 1 else ''})")
        downloaded.append(paths)

    return downloaded


def move_to_subfolder(svc, root_id: str, slug: str, target: str):
    """Déplace le dossier slug depuis la racine vers done/ ou failed/."""
    target_id = _ensure_folder(svc, root_id, target)

    folder_id = _get_folder_id(svc, root_id, slug)
    if not folder_id:
        print(f"  ⚠️  Dossier '{slug}' introuvable dans la racine")
        return

    svc.files().update(
        fileId=folder_id,
        addParents=target_id,
        removeParents=root_id,
        fields="id,parents",
    ).execute()
    print(f"  → {slug}/ → {target}/")


def main():
    parser = argparse.ArgumentParser(
        description="Assirem Drive Stock Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scripts/drive_stock.py list
  python scripts/drive_stock.py download ./stock
  python scripts/drive_stock.py download ./stock --slug lofi-coffee-shop
  python scripts/drive_stock.py mark-done lofi-coffee-shop
  python scripts/drive_stock.py mark-failed lofi-coffee-shop
""",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Liste les tracks disponibles dans incoming/")

    dl = sub.add_parser("download", help="Télécharge les tracks depuis Drive")
    dl.add_argument("dest", nargs="?", default="./stock", help="Dossier de destination (défaut: ./stock)")
    dl.add_argument("--slug", help="Télécharger un slug spécifique uniquement")

    done_cmd = sub.add_parser("mark-done", help="Déplace un track vers done/")
    done_cmd.add_argument("slug")

    fail_cmd = sub.add_parser("mark-failed", help="Déplace un track vers failed/")
    fail_cmd.add_argument("slug")

    args = parser.parse_args()

    root_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
    if not root_id:
        print(
            "❌ DRIVE_ROOT_FOLDER_ID manquant.\n"
            "   Ajoute l'ID du dossier 'Assirem Stock' comme variable GitHub (vars.DRIVE_ROOT_FOLDER_ID).",
            file=sys.stderr,
        )
        sys.exit(1)

    svc = _build_service()

    if args.cmd == "list":
        tracks = list_tracks(svc, root_id)
        if not tracks:
            print("  (aucun track dans incoming/)")
        else:
            print(f"  {len(tracks)} track(s) dans incoming/ :")
            for t in tracks:
                has_audio = "audio" in t["files"]
                has_img = "img" in t["files"]
                has_json = "json" in t["files"]
                status = (
                    "✅ prêt" if has_audio and has_json
                    else "⚠️  JSON manquant (sera auto-généré)" if has_audio
                    else "❌ audio manquant"
                )
                icons = f"{'🎵' if has_audio else '  '} {'🖼 ' if has_img else '  '} {'📄' if has_json else '  '}"
                print(f"    {icons}  {t['slug']}  — {status}")

    elif args.cmd == "download":
        downloaded = download_tracks(svc, root_id, args.dest, slug=args.slug)
        print(f"\n  {len(downloaded)} track(s) téléchargé(s) vers {args.dest}/")

    elif args.cmd == "mark-done":
        move_to_subfolder(svc, root_id, args.slug, "done")

    elif args.cmd == "mark-failed":
        move_to_subfolder(svc, root_id, args.slug, "failed")


if __name__ == "__main__":
    main()
