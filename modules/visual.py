"""
Module visual.py - Génération image + clips vidéo via Leonardo AI
Workflow :
  1. Génère une image de base via l'API Generations
  2. Génère N clips vidéo courts (~5s) via l'API Motion (image-to-video)
  3. Sauvegarde les clips dans output/clips/
"""

import os
import sys
import time
import threading
import requests

LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _lire_cle_api(base_dir: str) -> str:
    cle_path = os.path.join(base_dir, "credentials", "leonardo.key")
    if not os.path.exists(cle_path):
        raise FileNotFoundError(
            f"Clé API Leonardo introuvable : {cle_path}\n"
            "Créez le fichier et collez-y votre clé API Leonardo AI."
        )
    with open(cle_path, "r") as f:
        cle = f.read().strip()
    if not cle:
        raise ValueError("Le fichier credentials/leonardo.key est vide.")
    return cle


def _headers(cle: str) -> dict:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {cle}",
    }


def _spinner(label: str, stop_event: threading.Event) -> threading.Thread:
    """Affiche un spinner animé pendant une opération longue."""
    def _run():
        symboles = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        debut = time.time()
        while not stop_event.is_set():
            elapsed = int(time.time() - debut)
            sys.stdout.write(f"\r  {symboles[i % len(symboles)]} {label} ({elapsed}s)")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)
        elapsed = int(time.time() - debut)
        sys.stdout.write(f"\r  ✅ {label} — terminé en {elapsed}s                    \n")
        sys.stdout.flush()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _attendre_generation(cle: str, generation_id: str, label: str = "Génération") -> dict:
    """
    Polling sur GET /generations/{id} jusqu'à COMPLETE ou FAILED.
    Retourne la génération complète (generations_by_pk).
    """
    stop = threading.Event()
    _spinner(label, stop)

    for _ in range(60):  # max 5 min
        time.sleep(5)
        resp = requests.get(
            f"{LEONARDO_API_BASE}/generations/{generation_id}",
            headers=_headers(cle),
            timeout=30,
        )
        if resp.status_code != 200:
            stop.set()
            raise RuntimeError(f"Erreur polling ({resp.status_code}) : {resp.text}")

        generation = resp.json().get("generations_by_pk", {})
        status = generation.get("status", "")

        if status == "COMPLETE":
            stop.set()
            time.sleep(0.15)
            return generation
        elif status == "FAILED":
            stop.set()
            raise RuntimeError(f"La génération Leonardo AI a échoué (ID: {generation_id})")

    stop.set()
    raise TimeoutError("Timeout : la génération Leonardo AI n'a pas abouti dans les délais (5 min).")


# ─── Étape 1 : Génération de l'image de base ─────────────────────────────────

def generer_image(config: dict, base_dir: str, force: bool = False) -> tuple:
    """
    Génère une image 1536x864 via Leonardo AI.
    Retourne (chemin_image, image_id).
    """
    output_dir = os.path.join(base_dir, config["output_folder"])
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, "background.png")
    id_cache = os.path.join(output_dir, ".image_id")

    # Réutiliser si déjà générée
    if os.path.exists(dest) and os.path.exists(id_cache) and not force:
        with open(id_cache) as f:
            image_id = f.read().strip()
        print(f"  → Image déjà présente (ID: {image_id}) — utilisez --force pour regénérer")
        return dest, image_id

    print("  → Lecture de la clé API Leonardo...")
    cle = _lire_cle_api(base_dir)

    prompt   = config.get("visual_prompt", "abstract music background, vibrant colors")
    model_id = config.get("leonardo_model", "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3")

    print(f"  → Génération de l'image (prompt: \"{prompt[:60]}...\")")

    resp = requests.post(
        f"{LEONARDO_API_BASE}/generations",
        headers=_headers(cle),
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
    if resp.status_code != 200:
        raise RuntimeError(f"Erreur Leonardo API ({resp.status_code}) : {resp.text}")

    generation_id = resp.json().get("sdGenerationJob", {}).get("generationId")
    if not generation_id:
        raise RuntimeError(f"Réponse inattendue : {resp.json()}")

    generation = _attendre_generation(cle, generation_id, "Génération image")

    images = generation.get("generated_images", [])
    if not images:
        raise RuntimeError("Génération terminée mais aucune image retournée.")

    image_url = images[0].get("url")
    image_id  = images[0].get("id")

    print(f"  → Téléchargement de l'image...")
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(img_resp.content)

    # Sauvegarder l'image_id pour les clips Motion
    with open(id_cache, "w") as f:
        f.write(image_id)

    taille_ko = os.path.getsize(dest) // 1024
    print(f"  → Image sauvegardée : background.png ({taille_ko} Ko) | ID: {image_id}")
    return dest, image_id


# ─── Étape 2 : Génération des clips vidéo Motion ─────────────────────────────

def generer_clips_motion(config: dict, base_dir: str, image_id: str, force: bool = False) -> list:
    """
    Génère N clips vidéo courts (~5s) via l'API Motion de Leonardo AI.
    Retourne la liste des chemins MP4 des clips.
    """
    nb_clips       = config.get("nb_clips", 6)
    motion_strength = config.get("motion_strength", 5)
    output_dir     = os.path.join(base_dir, config["output_folder"])
    clips_dir      = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    print(f"  → Lecture de la clé API Leonardo...")
    cle = _lire_cle_api(base_dir)

    clips = []
    for i in range(1, nb_clips + 1):
        clip_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")

        if os.path.exists(clip_path) and not force:
            taille_ko = os.path.getsize(clip_path) // 1024
            print(f"  → Clip {i}/{nb_clips} déjà existant ({taille_ko} Ko), ignoré")
            clips.append(clip_path)
            continue

        print(f"  → Clip {i}/{nb_clips} : lancement génération Motion...")

        resp = requests.post(
            f"{LEONARDO_API_BASE}/generations-motion-svd",
            headers=_headers(cle),
            json={
                "imageId": image_id,
                "motionStrength": motion_strength,
                "isPublic": False,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Erreur API Motion clip {i}/{nb_clips} ({resp.status_code}) : {resp.text}"
            )

        generation_id = resp.json().get("motionSvdGenerationJob", {}).get("generationId")
        if not generation_id:
            raise RuntimeError(f"Réponse Motion inattendue : {resp.json()}")

        generation = _attendre_generation(cle, generation_id, f"Clip {i}/{nb_clips}")

        # Récupérer l'URL vidéo dans motionMP4URL
        images = generation.get("generated_images", [])
        if not images:
            raise RuntimeError(f"Clip {i} : génération terminée mais aucun résultat.")

        video_url = images[0].get("motionMP4URL")
        if not video_url:
            raise RuntimeError(
                f"Clip {i} : champ motionMP4URL absent dans la réponse.\n"
                f"Réponse : {images[0]}"
            )

        print(f"  → Téléchargement clip {i}/{nb_clips}...")
        vid_resp = requests.get(video_url, timeout=120)
        vid_resp.raise_for_status()
        with open(clip_path, "wb") as f:
            f.write(vid_resp.content)

        taille_ko = os.path.getsize(clip_path) // 1024
        print(f"  → Clip {i}/{nb_clips} sauvegardé : {os.path.basename(clip_path)} ({taille_ko} Ko)")
        clips.append(clip_path)

        # Petite pause entre les générations pour éviter le rate limiting
        if i < nb_clips:
            time.sleep(2)

    return clips


# ─── Point d'entrée combiné (appelé par pipeline.py) ─────────────────────────

def generer_visuel(config: dict, base_dir: str, force: bool = False) -> list:
    """
    Orchestre image + clips Motion.
    Retourne la liste des chemins des clips MP4 générés.
    """
    print("\n  ── Étape A : Image de base")
    _, image_id = generer_image(config, base_dir, force=force)

    print(f"\n  ── Étape B : Clips vidéo Motion ({config.get('nb_clips', 6)} clips)")
    clips = generer_clips_motion(config, base_dir, image_id, force=force)

    print(f"\n  → {len(clips)} clip(s) prêt(s) dans output/clips/")
    return clips
