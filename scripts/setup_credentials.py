#!/usr/bin/env python3
"""
setup_credentials.py — Reconstruit le dossier credentials/ depuis les variables d'environnement

À exécuter au début d'un run GitHub Actions (ou n'importe quel CI).
Lit les variables d'environnement et écrit les fichiers dans credentials/.

Variables d'environnement :
  YOUTUBE_CLIENT_SECRET   — contenu JSON du client_secret.json
  YOUTUBE_OAUTH_PICKLE_B64 — youtube_oauth.pickle encodé en base64
  LEONARDO_API_KEY        — clé API Leonardo
  ANTHROPIC_API_KEY       — clé API Anthropic
  KLING_ACCESS_KEY        — clé accès Kling AI
  KLING_SECRET_KEY        — clé secrète Kling AI
  WAVESPEED_API_KEY       — clé API WaveSpeed
  DRIVE_SA_JSON           — JSON du service account Google Drive (pour info uniquement)
"""

import os
import base64
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CRED_DIR = BASE_DIR / "credentials"
CRED_DIR.mkdir(exist_ok=True)


def _write_if_set(env_var: str, dest: Path, mode: str = "text", label: str = ""):
    value = os.environ.get(env_var, "").strip()
    if not value:
        print(f"  ⚠️  {label or env_var} : non défini, ignoré")
        return False

    if mode == "base64":
        try:
            raw = base64.b64decode(value)
            dest.write_bytes(raw)
        except Exception as e:
            print(f"  ❌ {label or env_var} : erreur décodage base64 : {e}")
            return False
    elif mode == "json":
        # Valide que c'est du JSON valide
        try:
            json.loads(value)
        except json.JSONDecodeError as e:
            print(f"  ❌ {label or env_var} : JSON invalide : {e}")
            return False
        dest.write_text(value, encoding="utf-8")
    else:
        dest.write_text(value, encoding="utf-8")

    print(f"  ✅ {label or env_var} → {dest.relative_to(BASE_DIR)}")
    return True


def main():
    print("🔑 Setup credentials...\n")

    _write_if_set("YOUTUBE_CLIENT_SECRET", CRED_DIR / "client_secret.json",
                  mode="json", label="YouTube client_secret")

    _write_if_set("YOUTUBE_OAUTH_PICKLE_B64", CRED_DIR / "youtube_oauth.pickle",
                  mode="base64", label="YouTube OAuth pickle")

    # Vérifie que les credentials essentiels sont présents
    missing = []
    essential = [
        CRED_DIR / "client_secret.json",
        CRED_DIR / "youtube_oauth.pickle",
    ]
    for f in essential:
        if not f.exists():
            missing.append(f.name)

    if missing:
        print(f"\n  ⚠️  Credentials manquants : {', '.join(missing)}")
        print("     Le pipeline risque d'échouer pour certaines étapes.")
    else:
        print("\n  ✅ Tous les credentials essentiels sont présents.")


if __name__ == "__main__":
    main()
