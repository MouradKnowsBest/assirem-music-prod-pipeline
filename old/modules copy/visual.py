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
import sys
import time
import threading
import requests

LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"
DEFAULT_MODEL     = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _lire_cle_api(base_dir: str) -> str:
    path = os.path.join(base_dir, "credentials", "leonardo.key")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Clé API Leonardo introuvable : {path}\n"
            "Créez credentials/leonardo.key avec votre clé API."
        )
    cle = open(path).read().strip()
    if not cle:
        raise ValueError("credentials/leonardo.key est vide.")
    return cle


def _headers(cle: str) -> dict:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {cle}",
    }


def _spinner(label: str, stop: threading.Event) -> threading.Thread:
    def _run():
        syms  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        debut = time.time()
        i = 0
        while not stop.is_set():
            sys.stdout.write(f"\r  {syms[i%len(syms)]} {label} ({int(time.time()-debut)}s)")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)
        elapsed = int(time.time() - debut)
        sys.stdout.write(f"\r  ✅ {label} — {elapsed}s                    \n")
        sys.stdout.flush()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _attendre_generation(cle: str, gen_id: str, label: str) -> dict:
    """Poll /generations/{id} jusqu'à COMPLETE. Retourne generations_by_pk."""
    stop = threading.Event()
    _spinner(label, stop)
    for _ in range(60):
        time.sleep(5)
        r = requests.get(
            f"{LEONARDO_API_BASE}/generations/{gen_id}",
            headers=_headers(cle), timeout=30
        )
        if r.status_code != 200:
            stop.set()
            raise RuntimeError(f"Polling error ({r.status_code}) : {r.text}")
        gen = r.json().get("generations_by_pk", {})
        if gen.get("status") == "COMPLETE":
            stop.set(); time.sleep(0.15)
            return gen
        if gen.get("status") == "FAILED":
            stop.set()
            raise RuntimeError(f"Génération échouée (ID: {gen_id})")
    stop.set()
    raise TimeoutError(f"Timeout génération Leonardo (ID: {gen_id})")


# ─── Génération image pour une scène ─────────────────────────────────────────

def _generer_image_scene(
    cle: str, model_id: str, prompt: str,
    dest: str, id_cache: str, idx: int, total: int
) -> str:
    """Génère l'image d'une scène. Retourne l'image_id Leonardo."""
    print(f"  → Scène {idx}/{total} — image : \"{prompt[:55]}...\"")
    r = requests.post(
        f"{LEONARDO_API_BASE}/generations",
        headers=_headers(cle),
        json={
            "prompt": prompt,
            "modelId": model_id,
            "width": 1536, "height": 864,
            "num_images": 1, "public": False,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erreur image scène {idx} ({r.status_code}) : {r.text}")

    gen_id = r.json().get("sdGenerationJob", {}).get("generationId")
    if not gen_id:
        raise RuntimeError(f"Réponse inattendue scène {idx} : {r.json()}")

    gen      = _attendre_generation(cle, gen_id, f"Image scène {idx}/{total}")
    images   = gen.get("generated_images", [])
    if not images:
        raise RuntimeError(f"Scène {idx} : aucune image retournée.")

    image_id  = images[0]["id"]
    image_url = images[0]["url"]

    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)

    with open(id_cache, "w") as f:
        f.write(image_id)

    taille = os.path.getsize(dest) // 1024
    print(f"     → scene_{idx:03d}.png ({taille} Ko) | ID: {image_id}")
    return image_id


# ─── Génération clip Motion pour une scène ───────────────────────────────────

def _generer_clip_scene(
    cle: str, image_id: str, motion_strength: int,
    dest: str, idx: int, total: int
) -> None:
    """Génère le clip Motion d'une scène depuis son image_id."""
    print(f"  → Scène {idx}/{total} — clip Motion (force: {motion_strength})...")
    r = requests.post(
        f"{LEONARDO_API_BASE}/generations-motion-svd",
        headers=_headers(cle),
        json={"imageId": image_id, "motionStrength": motion_strength, "isPublic": False},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erreur Motion scène {idx} ({r.status_code}) : {r.text}")

    gen_id = r.json().get("motionSvdGenerationJob", {}).get("generationId")
    if not gen_id:
        raise RuntimeError(f"Réponse Motion inattendue scène {idx} : {r.json()}")

    gen    = _attendre_generation(cle, gen_id, f"Clip scène {idx}/{total}")
    images = gen.get("generated_images", [])
    if not images:
        raise RuntimeError(f"Scène {idx} : aucun clip retourné.")

    video_url = images[0].get("motionMP4URL")
    if not video_url:
        raise RuntimeError(f"Scène {idx} : motionMP4URL absent. Réponse: {images[0]}")

    resp = requests.get(video_url, timeout=120)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)

    taille = os.path.getsize(dest) // 1024
    print(f"     → clip_{idx:03d}.mp4 ({taille} Ko)")


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def generer_visuel(track: dict, base_dir: str, force: bool = False) -> list:
    """
    Génère image + clip pour chaque scène d'un track.
    Retourne la liste des clips dans l'ORDRE des scènes (narratif).
    """
    slug      = track["slug"]
    scenes    = track.get("scenes", [])
    model_id  = track.get("leonardo_model", DEFAULT_MODEL)

    if not scenes:
        raise ValueError(f"Track '{slug}' : aucune scène définie dans scenes[].")

    output_dir = os.path.join(base_dir, "output", slug)
    scenes_dir = os.path.join(output_dir, "scenes")
    clips_dir  = os.path.join(output_dir, "clips")
    os.makedirs(scenes_dir, exist_ok=True)
    os.makedirs(clips_dir,  exist_ok=True)

    print(f"  → {len(scenes)} scène(s) cinématiques pour le track '{slug}'")
    cle = _lire_cle_api(base_dir)

    clips = []
    for i, scene in enumerate(scenes, 1):
        prompt   = scene.get("prompt", "")
        motion   = scene.get("motion_strength", 5)
        img_path = os.path.join(scenes_dir, f"scene_{i:03d}.png")
        id_cache = os.path.join(scenes_dir, f".id_{i:03d}")
        clp_path = os.path.join(clips_dir,  f"clip_{i:03d}.mp4")

        # ── Image ──────────────────────────────────────────────────────────
        if os.path.exists(img_path) and os.path.exists(id_cache) and not force:
            image_id = open(id_cache).read().strip()
            print(f"  → Scène {i}/{len(scenes)} image déjà présente (ID: {image_id})")
        else:
            image_id = _generer_image_scene(
                cle, model_id, prompt, img_path, id_cache, i, len(scenes)
            )

        # ── Clip Motion ────────────────────────────────────────────────────
        if os.path.exists(clp_path) and not force:
            taille = os.path.getsize(clp_path) // 1024
            print(f"  → Scène {i}/{len(scenes)} clip déjà présent ({taille} Ko)")
        else:
            _generer_clip_scene(cle, image_id, motion, clp_path, i, len(scenes))
            if i < len(scenes):
                time.sleep(2)  # éviter rate limiting entre générations

        clips.append(clp_path)

    print(f"\n  → {len(clips)} clip(s) prêts dans output/{slug}/clips/")
    return clips
