#!/usr/bin/env python3
"""
sync_config.py
--------------
Prépare l'arborescence input/ pour un batch de tracks défini dans un config JSON.

Étapes (dans l'ordre) :
  1. (Optionnel, --copy-from) Copie un config externe → config local.
  2. Lit la liste des tracks depuis le fichier config (--config).
  3. Archive le contenu actuel de `input/`  → `input archive/YYYY-MM-DD[_N]`.
  4. Archive le contenu actuel de `OUTPUT/` → `OUTPUT archive/YYYY-MM-DD[_N]`
     (idempotent : skip si déjà à jour).
  5. Crée un dossier numéroté par track dans `input/` : 1-slug, 2-slug, …
     OUTPUT/ n'est pas pré-créé : le pipeline le gère via output/<slug>.

Usage :
  python3 scripts/sync_config.py
      → lit today/config.json (défaut), crée 35 dossiers

  python3 scripts/sync_config.py --config config.json
      → lit config.json racine (10 tracks legacy)

  python3 scripts/sync_config.py --config /chemin/quelconque.json

  python3 scripts/sync_config.py --copy-from "/Users/.../pipeline/config.json"
      → copie le fichier externe en local AVANT de l'utiliser comme source
"""

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

# ── Chemins du repo (relatifs à l'emplacement du script) ─────────────────────

BASE_DIR        = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG  = BASE_DIR / "today" / "config.json"
LEGACY_CONFIG   = BASE_DIR / "config.json"
INPUT_DIR       = BASE_DIR / "input"
INPUT_ARCHIVE   = BASE_DIR / "input archive"
OUTPUT_DIR      = BASE_DIR / "OUTPUT"
OUTPUT_ARCHIVE  = BASE_DIR / "OUTPUT archive"


# ── 1. (Optionnel) Copie d'un config externe vers le repo ────────────────────

def copier_config(source: Path, dest: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Config source introuvable : {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    print(f"✓ Config copié : {source} → {dest}")


# ── 2. Lecture du config local ───────────────────────────────────────────────

def lire_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def lire_slugs(data: dict) -> list[str]:
    tracks = data.get("tracks", [])
    slugs = [t["slug"] for t in tracks if "slug" in t]
    if slugs:
        print(f"✓ {len(slugs)} track(s) trouvé(s) :")
        for i, s in enumerate(slugs, 1):
            print(f"   {i:>3}. {s}")
    else:
        print("⚠ Aucun slug de track trouvé dans le config.")
    return slugs


# ── Helpers archive ──────────────────────────────────────────────────────────

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


def _archiver(source_dir: Path, archive_dir: Path, slugs: list[str], label: str) -> None:
    if not source_dir.exists():
        print(f"⚠ {label}/ introuvable, rien à archiver.")
        return

    contenu = list(source_dir.iterdir())
    if not contenu:
        print(f"⚠ {label}/ vide, rien à archiver.")
        return

    # Idempotence : si les dossiers présents matchent déjà la cible, skip.
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


def _creer_dossiers(target_dir: Path, slugs: list[str], label: str) -> None:
    if not slugs:
        print(f"⚠ Aucun slug, aucun dossier créé dans {label}/.")
        return

    target_dir.mkdir(exist_ok=True)
    for i, slug in enumerate(slugs, 1):
        dossier = target_dir / f"{i}-{slug}"
        dossier.mkdir(exist_ok=True)
        print(f"   📁 {i}-{slug}")

    print(f"✓ {len(slugs)} dossier(s) créé(s) dans {label}/")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prépare input/ pour un batch de tracks à partir d'un config JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python3 scripts/sync_config.py\n"
            "      → today/config.json (défaut, 35 tracks de la semaine)\n\n"
            "  python3 scripts/sync_config.py --config config.json\n"
            "      → config.json racine (legacy 10 tracks)\n\n"
            "  python3 scripts/sync_config.py --copy-from /Users/.../pipeline/config.json\n"
            "      → copie d'abord le fichier externe en local\n"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Fichier JSON source (défaut : {DEFAULT_CONFIG.relative_to(BASE_DIR)}).",
    )
    parser.add_argument(
        "--copy-from",
        type=Path,
        default=None,
        help="Si fourni, copie ce fichier externe vers --config AVANT lecture.",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Saute l'archivage de input/ et OUTPUT/ (utile pour preview).",
    )
    args = parser.parse_args()

    print("\n── Sync config ─────────────────────────────────────────────────────")
    if args.copy_from is not None:
        copier_config(args.copy_from, args.config)
    print(f"✓ Source : {args.config}")

    print("\n── Tracks dans le config ───────────────────────────────────────────")
    data = lire_config(args.config)
    slugs = lire_slugs(data)
    if not slugs:
        print("\n❌ Aucun slug → arrêt.")
        return 1

    if not args.no_archive:
        print("\n── Archive input/ ──────────────────────────────────────────────────")
        _archiver(INPUT_DIR, INPUT_ARCHIVE, slugs, "input")

        print("\n── Archive OUTPUT/ ─────────────────────────────────────────────────")
        _archiver(OUTPUT_DIR, OUTPUT_ARCHIVE, slugs, "OUTPUT")
    else:
        print("\n── Archive ignorée (--no-archive) ──────────────────────────────────")

    print("\n── Création des dossiers input/ ────────────────────────────────────")
    _creer_dossiers(INPUT_DIR, slugs, "input")

    print("\n✅ Terminé.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
