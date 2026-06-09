"""
Module kling.py — Génération image + clip par scène via Kling AI (Kuaishou)

API : https://api.klingai.com/v1/
Auth : JWT HMAC-SHA256 (access_key + secret_key)
Free tier : ~166 crédits/mois | Clip 5s ≈ 0.14 crédit

Credentials :
  credentials/kling_access.key  ← Access Key (dashboard Kling)
  credentials/kling_secret.key  ← Secret Key (dashboard Kling)

Sorties identiques à visual.py :
  output/<slug>/scenes/scene_001.png  ...
  output/<slug>/clips/clip_001.mp4    ...
"""

import os
import hmac
import time
import hashlib
import base64
import json
import requests

from . import _http

KLING_API_BASE = "https://api.klingai.com"
IMAGE_MODEL    = "kling-v1-5"
VIDEO_MODEL    = "kling-v1-5"


# ── Auth JWT ──────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt(access_key: str, secret_key: str) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now     = int(time.time())
    payload = _b64url(json.dumps(
        {"iss": access_key, "exp": now + 1800, "nbf": now - 5},
        separators=(",", ":")
    ).encode())
    signing = f"{header}.{payload}"
    sig     = hmac.new(secret_key.encode(), signing.encode(), hashlib.sha256).digest()
    return f"{signing}.{_b64url(sig)}"


def _headers(access_key: str, secret_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_make_jwt(access_key, secret_key)}",
    }


# ── Polling ───────────────────────────────────────────────────────────────────

def _poll_task(access_key: str, secret_key: str, endpoint: str, task_id: str, label: str) -> dict:
    def check():
        r = requests.get(
            f"{KLING_API_BASE}{endpoint}/{task_id}",
            headers=_headers(access_key, secret_key),
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Kling polling error ({r.status_code}) : {r.text}")
        data   = r.json().get("data", {})
        status = data.get("task_status")
        if status == "succeed":
            return True, data
        if status == "failed":
            raise RuntimeError(
                f"Kling task failed (ID: {task_id}) : {data.get('task_status_msg', '')}"
            )
        return False, None

    return _http.poll_until_ready(check, label, timeout_sec=300, interval_sec=5)


# ── Génération image ──────────────────────────────────────────────────────────

def _generer_image_scene(
    access_key: str, secret_key: str, prompt: str, dest: str, idx: int, total: int
) -> str:
    print(f"  → Scène {idx}/{total} — image Kling : \"{prompt[:55]}...\"")
    r = requests.post(
        f"{KLING_API_BASE}/v1/images/generations",
        headers=_headers(access_key, secret_key),
        json={
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, text, watermark, distorted",
            "image_count": 1,
            "aspect_ratio": "16:9",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Kling image scène {idx} ({r.status_code}) : {r.text}")

    task_id = r.json().get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling image: réponse inattendue scène {idx} : {r.json()}")

    data   = _poll_task(access_key, secret_key, "/v1/images/generations", task_id, f"Image Kling {idx}/{total}")
    images = data.get("task_result", {}).get("images", [])
    if not images:
        raise RuntimeError(f"Kling scène {idx} : aucune image retournée.")

    _http.telecharger_fichier(images[0]["url"], dest)
    taille = os.path.getsize(dest) // 1024
    print(f"     → scene_{idx:03d}.png ({taille} Ko)")
    return dest


# ── Génération clip ───────────────────────────────────────────────────────────

def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _generer_clip_scene(
    access_key: str, secret_key: str, img_path: str, dest: str,
    idx: int, total: int, motion_strength: int = 5
) -> None:
    print(f"  → Scène {idx}/{total} — clip Kling (strength: {motion_strength})...")
    # motion_strength 1-10 → cfg_scale 0.9-0.1 (plus fort = plus libre)
    cfg_scale = round(1.0 - (motion_strength - 1) / 9, 2)

    r = requests.post(
        f"{KLING_API_BASE}/v1/videos/image2video",
        headers=_headers(access_key, secret_key),
        json={
            "model": VIDEO_MODEL,
            "image": _image_to_base64(img_path),
            "duration": "5",
            "cfg_scale": cfg_scale,
            "mode": "std",
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Kling video scène {idx} ({r.status_code}) : {r.text}")

    task_id = r.json().get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling video: réponse inattendue scène {idx} : {r.json()}")

    data   = _poll_task(access_key, secret_key, "/v1/videos/image2video", task_id, f"Clip Kling {idx}/{total}")
    videos = data.get("task_result", {}).get("videos", [])
    if not videos:
        raise RuntimeError(f"Kling scène {idx} : aucun clip retourné.")

    video_url = videos[0].get("url")
    if not video_url:
        raise RuntimeError(f"Kling scène {idx} : URL vidéo absente. Réponse: {videos[0]}")

    _http.telecharger_fichier(video_url, dest)
    taille = os.path.getsize(dest) // 1024
    print(f"     → clip_{idx:03d}.mp4 ({taille} Ko)")


# ── Interface publique (identique à visual.py) ────────────────────────────────

def generer_visuel(track: dict, base_dir: str, force: bool = False, skip_motion: bool = False) -> list:
    """
    Génère image + clip pour chaque scène d'un track via Kling AI.
    Interface identique à visual.py — drop-in replacement.
    Retourne la liste des clips dans l'ordre des scènes.
    """
    slug   = track["slug"]
    scenes = track.get("scenes", [])
    if not scenes:
        raise ValueError(f"Track '{slug}' : aucune scène définie dans scenes[].")

    output_dir = os.path.join(base_dir, "output", slug)
    scenes_dir = os.path.join(output_dir, "scenes")
    clips_dir  = os.path.join(output_dir, "clips")
    os.makedirs(scenes_dir, exist_ok=True)
    os.makedirs(clips_dir,  exist_ok=True)

    print(f"  → {len(scenes)} scène(s) via Kling AI pour '{slug}'")

    access_key = _http.lire_cle_api(base_dir, "kling_access")
    secret_key = _http.lire_cle_api(base_dir, "kling_secret")

    if skip_motion:
        print(f"  → Mode Ken Burns : clips Motion ignorés")

    clips = []
    for i, scene in enumerate(scenes, 1):
        if isinstance(scene, (list, tuple)):
            prompt = scene[0] if len(scene) > 0 else ""
            motion = int(scene[1]) if len(scene) > 1 else 5
        else:
            prompt = scene.get("prompt", "")
            motion = scene.get("motion_strength", 5)

        img_path = os.path.join(scenes_dir, f"scene_{i:03d}.png")
        clp_path = os.path.join(clips_dir,  f"clip_{i:03d}.mp4")

        if os.path.exists(img_path) and not force:
            print(f"  → Scène {i}/{len(scenes)} image déjà présente")
        else:
            _generer_image_scene(access_key, secret_key, prompt, img_path, i, len(scenes))

        if skip_motion:
            clips.append(img_path)
            continue

        if os.path.exists(clp_path) and not force:
            taille = os.path.getsize(clp_path) // 1024
            print(f"  → Scène {i}/{len(scenes)} clip déjà présent ({taille} Ko)")
        else:
            _generer_clip_scene(access_key, secret_key, img_path, clp_path, i, len(scenes), motion)

        clips.append(clp_path)

    return clips
