#!/usr/bin/env python3
"""
drive_stock.py — Gestion du "stock" Google Drive pour le pipeline Assirem

Structure Drive attendue (dossier partagé avec le service account) :
  Assirem Stock/
    incoming/     ← tu déposes ici : slug.mp3 + slug.jpg (+ slug.json optionnel)
    processing/   ← créé automatiquement si besoin
    done/         ← après succès
    failed/       ← après échec

Convention de nommage :
  Le "slug" est le nom du fichier sans extension.
  Exemple : lofi-coffee-shop.mp3 + lofi-coffee-shop.jpg → slug = "lofi-coffee-shop"

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
    Retourne la liste des tracks dans incoming/ groupés par slug.
    Chaque élément : {"slug": str, "files": {type: filename}, "file_ids": {type: id}}
    """
    incoming_id = _get_folder_id(svc, root_id, "incoming")
    if not incoming_id:
        return []

    q = f"'{incoming_id}' in parents and trashed=false"
    res = svc.files().list(q=q, fields="files(id,name,size)", pageSize=1000).execute()

    by_slug: dict[str, dict] = {}
    for f in res.get("files", []):
        name = f["name"]
        stem, ext = os.path.splitext(name)
        ext = ext.lower().lstrip(".")
        if ext not in DOWNLOAD_EXTS:
            continue

        if stem not in by_slug:
            by_slug[stem] = {"slug": stem, "files": {}, "file_ids": {}}

        # Normalise les types
        if ext == "json":
            key = "json"
        elif ext in AUDIO_EXTS:
            key = "audio"
        else:
            key = "img"

        by_slug[stem]["files"][key] = name
        by_slug[stem]["file_ids"][key] = f["id"]

    return list(by_slug.values())


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

        for key, file_id in track["file_ids"].items():
            filename = track["files"][key]
            dest = slug_dir / filename
            _download_file(svc, file_id, dest, filename)
            paths[key] = str(dest)

        print(f"  ✅ {track['slug']} → {slug_dir}/")
        downloaded.append(paths)

    return downloaded


def move_to_subfolder(svc, root_id: str, slug: str, target: str):
    """Déplace tous les fichiers d'un slug depuis incoming/ vers target/."""
    incoming_id = _ensure_folder(svc, root_id, "incoming")
    target_id = _ensure_folder(svc, root_id, target)

    q = f"'{incoming_id}' in parents and trashed=false"
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1000).execute()

    moved = 0
    for f in res.get("files", []):
        stem = os.path.splitext(f["name"])[0]
        if stem != slug:
            continue
        svc.files().update(
            fileId=f["id"],
            addParents=target_id,
            removeParents=incoming_id,
            fields="id,parents",
        ).execute()
        print(f"  → {f['name']} → {target}/")
        moved += 1

    if moved == 0:
        print(f"  ⚠️  Aucun fichier trouvé pour slug '{slug}' dans incoming/")


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
