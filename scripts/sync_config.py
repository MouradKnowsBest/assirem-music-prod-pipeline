#!/usr/bin/env python3
"""
sync_config.py
--------------
1. Copie le config.json source → destination.
2. Lit les slugs des tracks dans le config.
3. Archive le contenu de `input/`  → `input archive/YYYY-MM-DD`
4. Archive le contenu de `OUTPUT/` → `OUTPUT archive/YYYY-MM-DD`
   (ajoute _2, _3, … si le dossier-date existe déjà — idempotent)
5. Crée un dossier numéroté par track dans `input/` : 1-slug, 2-slug, …
   (OUTPUT/ n'est pas pré-créé : le pipeline le gère lui-même via output/slug)
"""

import json
import shutil
from datetime import date
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────

SOURCE_CONFIG   = Path("/Users/mourad.knowsbest/Documents/Claude/Scheduled/amp-assirem-music-prod-growth/pipeline/config.json")
DEST_CONFIG     = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/config.json")
INPUT_DIR       = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/input")
INPUT_ARCHIVE   = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/input archive")
OUTPUT_DIR      = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/OUTPUT")
OUTPUT_ARCHIVE  = Path("/Users/mourad.knowsbest/Coding/assirem-music-prod-pipeline/OUTPUT archive")

# ── 1. Copie du config ────────────────────────────────────────────────────────

def copier_config() -> dict:
    if not SOURCE_CONFIG.exists():
        raise FileNotFoundError(f"Config source introuvable : {SOURCE_CONFIG}")

    with open(SOURCE_CONFIG, "r", encoding="utf-8") as f:
        data = json.load(f)

    shutil.copy2(SOURCE_CONFIG, DEST_CONFIG)
    print(f"✓ Config copié : {SOURCE_CONFIG.name} → {DEST_CONFIG}")
    return data


# ── 2. Lecture des slugs ──────────────────────────────────────────────────────

def lire_slugs(data: dict) -> list[str]:
    tracks = data.get("tracks", [])
    slugs = [t["slug"] for t in tracks if "slug" in t]
    if slugs:
        print(f"✓ {len(slugs)} track(s) trouvé(s) :")
        for i, s in enumerate(slugs, 1):
            print(f"   {i}. {s}")
    else:
        print("⚠ Aucun slug de track trouvé dans le config.")
    return slugs


# ── Helpers archive ───────────────────────────────────────────────────────────

def _noms_attendus(slugs: list[str]) -> set[str]:
    """Noms de dossiers attendus : '1-slug', '2-slug', …"""
    return {f"{i}-{s}" for i, s in enumerate(slugs, 1)}


def _dossier_disponible(archive_dir: Path) -> Path:
    """Retourne un chemin YYYY-MM-DD (ou YYYY-MM-DD_N) libre."""
    base = archive_dir / date.today().isoformat()
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = archive_dir / f"{date.today().isoformat()}_{n}"
        if not candidate.exists():
            return candidate
        n += 1


def _archiver(source_dir: Path, archive_dir: Path, slugs: list[str], label: str):
    if not source_dir.exists():
        print(f"⚠ {label}/ introuvable, rien à archiver.")
        return

    contenu = list(source_dir.iterdir())
    if not contenu:
        print(f"⚠ {label}/ vide, rien à archiver.")
        return

    # Idempotence : déjà les bons dossiers numérotés → skip
    noms_actuels = {item.name for item in contenu}
    if noms_actuels == _noms_attendus(slugs):
        print(f"⏭ {label}/ déjà à jour — aucune archive créée.")
        return

    archive_dir.mkdir(exist_ok=True)
    dest = _dossier_disponible(archive_dir)
    dest.mkdir()

    for item in contenu:
        shutil.move(str(item), dest / item.name)

    print(f"✓ {len(contenu)} élément(s) archivé(s) → {dest.relative_to(archive_dir.parent)}")


def _creer_dossiers(target_dir: Path, slugs: list[str], label: str):
    if not slugs:
        print(f"⚠ Aucun slug, aucun dossier créé dans {label}/.")
        return

    target_dir.mkdir(exist_ok=True)
    for i, slug in enumerate(slugs, 1):
        dossier = target_dir / f"{i}-{slug}"
        dossier.mkdir(exist_ok=True)
        print(f"   📁 {i}-{slug}")

    print(f"✓ {len(slugs)} dossier(s) créé(s) dans {label}/")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n── Sync config ─────────────────────────────────────────────────────")
    data = copier_config()

    print("\n── Tracks dans le nouveau config ───────────────────────────────────")
    slugs = lire_slugs(data)

    print("\n── Archive input/ ──────────────────────────────────────────────────")
    _archiver(INPUT_DIR, INPUT_ARCHIVE, slugs, "input")

    print("\n── Archive OUTPUT/ ─────────────────────────────────────────────────")
    _archiver(OUTPUT_DIR, OUTPUT_ARCHIVE, slugs, "OUTPUT")

    print("\n── Création des dossiers input/ ────────────────────────────────────")
    _creer_dossiers(INPUT_DIR, slugs, "input")

    print("\n✅ Terminé.\n")
