"""
Module wavespeed.py — Génération vidéo par scène via WaveSpeed AI (Wan2.1 t2v)

Remplace Leonardo AI pour la génération visuelle.
Workflow : pour chaque scène, envoie le prompt → clip MP4 ~5s directement.
Pas d'étape image intermédiaire (contrairement à Leonardo).

Sorties :
  output/<slug>/clips/clip_001.mp4  ...
"""

import os
import time
import requests

from . import _http

WAVESPEED_API_BASE = "https://api.wavespeed.ai/api/v3"
DEFAULT_MODEL = "wavespeed-ai/ltx-2-19b/text-to-video"


def _soumettre_generation(cle: str, prompt: str, idx: int) -> str:
    """Soumet une génération vidéo text-to-video. Retourne le prediction_id."""
    headers = _http.headers_json(cle)
    headers["Authorization"] = f"Bearer {cle}"  # WaveSpeed uses Authorization instead of authorization
    r = requests.post(
        f"{WAVESPEED_API_BASE}/{DEFAULT_MODEL}",
        headers=headers,
        json={
            "prompt": prompt,
            "duration": 5,
            "resolution": "720p",
            "seed": -1,
            "enable_safety_checker": False,
        },
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Erreur WaveSpeed scène {idx} ({r.status_code}) : {r.text}")

    data = r.json().get("data", {})
    pred_id = data.get("id")
    if not pred_id:
        raise RuntimeError(f"Réponse inattendue WaveSpeed scène {idx} : {r.json()}")
    return pred_id


def _attendre_clip(cle: str, pred_id: str, label: str) -> str:
    """Poll jusqu'à completed. Retourne l'URL du MP4."""
    def check_status():
        headers = _http.headers_json(cle)
        headers["Authorization"] = f"Bearer {cle}"
        r = requests.get(
            f"{WAVESPEED_API_BASE}/predictions/{pred_id}/result",
            headers=headers,
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Polling error ({r.status_code}) : {r.text}")

        body = r.json()
        data = body.get("data", body)  # v3 peut retourner directement l'objet
        status = data.get("status", "")

        if status == "completed":
            outputs = data.get("outputs", [])
            if not outputs:
                raise RuntimeError(f"WaveSpeed clip complété mais aucun output (ID: {pred_id})")
            return True, outputs[0]

        if status in ("failed", "error"):
            raise RuntimeError(f"WaveSpeed génération échouée (ID: {pred_id}) : {data}")
        
        return False, None
    
    return _http.poll_until_ready(check_status, label, timeout_sec=600, interval_sec=5)


def generer_visuel(track: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère un clip vidéo pour chaque scène du track via WaveSpeed AI.
    Interface identique à modules/visual.py — retourne la liste des clips en ordre.
    """
    slug = track["slug"]
    scenes = track.get("scenes", [])

    if not scenes:
        raise ValueError(f"Track '{slug}' : aucune scène définie dans scenes[].")

    output_dir = os.path.join(base_dir, "output", slug)
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    print(f"  → {len(scenes)} scène(s) via WaveSpeed AI (Wan2.1 t2v) pour '{slug}'")
    cle = _http.lire_cle_api(base_dir, "wavespeed")

    clips = []
    for i, scene in enumerate(scenes, 1):
        prompt = scene.get("prompt", "")
        clp_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")

        if os.path.exists(clp_path) and not force:
            taille = os.path.getsize(clp_path) // 1024
            print(f"  → Scène {i}/{len(scenes)} clip déjà présent ({taille} Ko)")
            clips.append(clp_path)
            continue

        print(f"  → Scène {i}/{len(scenes)} — \"{prompt[:60]}...\"")
        pred_id = _soumettre_generation(cle, prompt, i)
        video_url = _attendre_clip(cle, pred_id, f"Clip WaveSpeed {i}/{len(scenes)}")

        _http.telecharger_fichier(video_url, clp_path)

        taille = os.path.getsize(clp_path) // 1024
        print(f"     → clip_{i:03d}.mp4 ({taille} Ko)")
        clips.append(clp_path)

    return clips
