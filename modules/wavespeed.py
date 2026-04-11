"""
Module wavespeed.py — Génération vidéo par scène via WaveSpeed AI (Wan2.1 t2v)

Remplace Leonardo AI pour la génération visuelle.
Workflow : pour chaque scène, envoie le prompt → clip MP4 ~5s directement.
Pas d'étape image intermédiaire (contrairement à Leonardo).

Sorties :
  output/<slug>/clips/clip_001.mp4  ...
"""

import os
import sys
import time
import threading
import requests

WAVESPEED_API_BASE = "https://api.wavespeed.ai/api/v3"
DEFAULT_MODEL = "wavespeed-ai/ltx-2-19b/text-to-video"


def _lire_cle_api(base_dir: str) -> str:
    path = os.path.join(base_dir, "credentials", "wavespeed.key")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Clé API WaveSpeed introuvable : {path}\n"
            "Créez credentials/wavespeed.key avec votre clé API."
        )
    cle = open(path).read().strip()
    if not cle:
        raise ValueError("credentials/wavespeed.key est vide.")
    return cle


def _headers(cle: str) -> dict:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {cle}",
    }


def _spinner(label: str, stop: threading.Event) -> threading.Thread:
    def _run():
        syms = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        debut = time.time()
        i = 0
        while not stop.is_set():
            sys.stdout.write(f"\r  {syms[i % len(syms)]} {label} ({int(time.time() - debut)}s)")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)
        elapsed = int(time.time() - debut)
        sys.stdout.write(f"\r  ✅ {label} — {elapsed}s                    \n")
        sys.stdout.flush()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _soumettre_generation(cle: str, prompt: str, idx: int) -> str:
    """Soumet une génération vidéo text-to-video. Retourne le prediction_id."""
    r = requests.post(
        f"{WAVESPEED_API_BASE}/{DEFAULT_MODEL}",
        headers=_headers(cle),
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
    stop = threading.Event()
    _spinner(label, stop)
    for _ in range(120):  # max 10 min
        time.sleep(5)
        r = requests.get(
            f"{WAVESPEED_API_BASE}/predictions/{pred_id}/result",
            headers=_headers(cle),
            timeout=30,
        )
        if r.status_code != 200:
            stop.set()
            raise RuntimeError(f"Polling error ({r.status_code}) : {r.text}")

        body = r.json()
        data = body.get("data", body)  # v3 peut retourner directement l'objet
        status = data.get("status", "")

        if status == "completed":
            stop.set()
            time.sleep(0.15)
            outputs = data.get("outputs", [])
            if not outputs:
                raise RuntimeError(f"WaveSpeed clip complété mais aucun output (ID: {pred_id})")
            return outputs[0]

        if status in ("failed", "error"):
            stop.set()
            raise RuntimeError(f"WaveSpeed génération échouée (ID: {pred_id}) : {data}")

    stop.set()
    raise TimeoutError(f"Timeout WaveSpeed (ID: {pred_id})")


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
    cle = _lire_cle_api(base_dir)

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

        resp = requests.get(video_url, timeout=120)
        resp.raise_for_status()
        with open(clp_path, "wb") as f:
            f.write(resp.content)

        taille = os.path.getsize(clp_path) // 1024
        print(f"     → clip_{i:03d}.mp4 ({taille} Ko)")
        clips.append(clp_path)

    return clips
