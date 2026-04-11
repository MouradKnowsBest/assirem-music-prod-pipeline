"""
Module visual.py — Génération cinématique image + clip par scène via Leonardo AI

Workflow par track :
  Pour chaque scène dans track['scenes'] :
    1. Génère une image 1536×864 avec scene['prompt']
    2. Génère un clip Motion ~5s depuis cette image
  Les clips sont retournés EN ORDRE de scène → assemblage narratif.

Sorties :
  output/<slug>/scenes/scene_001.png  ...
  output/<slug>/clips/clip_001.mp4    ...
"""

import os
import time
import requests

from . import _http

LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"
DEFAULT_MODEL = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"


def _attendre_generation(cle: str, gen_id: str, label: str) -> dict:
    """Poll /generations/{id} jusqu'à COMPLETE. Retourne generations_by_pk."""
    def check_status():
        r = requests.get(
            f"{LEONARDO_API_BASE}/generations/{gen_id}",
            headers=_http.headers_json(cle),
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Polling error ({r.status_code}) : {r.text}")
        gen = r.json().get("generations_by_pk", {})
        status = gen.get("status")
        if status == "COMPLETE":
            return True, gen
        if status == "FAILED":
            raise RuntimeError(f"Génération échouée (ID: {gen_id})")
        return False, None
    
    return _http.poll_until_ready(check_status, label, timeout_sec=300, interval_sec=5)


def _generer_image_scene(
    cle: str, model_id: str, prompt: str, dest: str, id_cache: str, idx: int, total: int
) -> str:
    """Génère l'image d'une scène. Retourne l'image_id Leonardo."""
    print(f"  → Scène {idx}/{total} — image : \"{prompt[:55]}...\"")
    r = requests.post(
        f"{LEONARDO_API_BASE}/generations",
        headers=_http.headers_json(cle),
        json={
            "prompt": prompt,
            "modelId": model_id,
            "width": 1536,
            "height": 864,
            "num_images": 1,
            "public": False,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erreur image scène {idx} ({r.status_code}) : {r.text}")

    gen_id = r.json().get("sdGenerationJob", {}).get("generationId")
    if not gen_id:
        raise RuntimeError(f"Réponse inattendue scène {idx} : {r.json()}")

    gen = _attendre_generation(cle, gen_id, f"Image scène {idx}/{total}")
    images = gen.get("generated_images", [])
    if not images:
        raise RuntimeError(f"Scène {idx} : aucune image retournée.")

    image_id = images[0]["id"]
    image_url = images[0]["url"]

    _http.telecharger_fichier(image_url, dest)

    with open(id_cache, "w") as f:
        f.write(image_id)

    taille = os.path.getsize(dest) // 1024
    print(f"     → scene_{idx:03d}.png ({taille} Ko) | ID: {image_id}")
    return image_id


def _generer_clip_scene(
    cle: str, image_id: str, motion_strength: int, dest: str, idx: int, total: int
) -> None:
    """Génère le clip Motion d'une scène depuis son image_id."""
    print(f"  → Scène {idx}/{total} — clip Motion (force: {motion_strength})...")
    r = requests.post(
        f"{LEONARDO_API_BASE}/generations-motion-svd",
        headers=_http.headers_json(cle),
        json={"imageId": image_id, "motionStrength": motion_strength, "isPublic": False},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erreur Motion scène {idx} ({r.status_code}) : {r.text}")

    gen_id = r.json().get("motionSvdGenerationJob", {}).get("generationId")
    if not gen_id:
        raise RuntimeError(f"Réponse Motion inattendue scène {idx} : {r.json()}")

    gen = _attendre_generation(cle, gen_id, f"Clip scène {idx}/{total}")
    images = gen.get("generated_images", [])
    if not images:
        raise RuntimeError(f"Scène {idx} : aucun clip retourné.")

    video_url = images[0].get("motionMP4URL")
    if not video_url:
        raise RuntimeError(f"Scène {idx} : motionMP4URL absent. Réponse: {images[0]}")

    _http.telecharger_fichier(video_url, dest)

    taille = os.path.getsize(dest) // 1024
    print(f"     → clip_{idx:03d}.mp4 ({taille} Ko)")


def generer_visuel(track: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère image + clip pour chaque scène d'un track.
    Retourne la liste des clips dans l'ORDRE des scènes (narratif).
    """
    slug = track["slug"]
    scenes = track.get("scenes", [])
    model_id = track.get("leonardo_model", DEFAULT_MODEL)

    if not scenes:
        raise ValueError(f"Track '{slug}' : aucune scène définie dans scenes[].")

    output_dir = os.path.join(base_dir, "output", slug)
    scenes_dir = os.path.join(output_dir, "scenes")
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(scenes_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    print(f"  → {len(scenes)} scène(s) cinématiques pour le track '{slug}'")
    cle = _http.lire_cle_api(base_dir, "leonardo")

    clips = []
    for i, scene in enumerate(scenes, 1):
        prompt = scene.get("prompt", "")
        motion = scene.get("motion_strength", 5)
        img_path = os.path.join(scenes_dir, f"scene_{i:03d}.png")
        id_cache = os.path.join(scenes_dir, f".id_{i:03d}")
        clp_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")

        if os.path.exists(img_path) and os.path.exists(id_cache) and not force:
            image_id = open(id_cache).read().strip()
            print(f"  → Scène {i}/{len(scenes)} image déjà présente (ID: {image_id})")
        else:
            image_id = _generer_image_scene(
                cle, model_id, prompt, img_path, id_cache, i, len(scenes)
            )

        if os.path.exists(clp_path) and not force:
            taille = os.path.getsize(clp_path) // 1024
            print(f"  → Scène {i}/{len(scenes)} clip déjà présent ({taille} Ko)")
        else:
            _generer_clip_scene(cle, image_id, motion, clp_path, i, len(scenes))

        clips.append(clp_path)

    return clips

