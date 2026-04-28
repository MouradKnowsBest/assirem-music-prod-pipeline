"""
leonardo_motion.py — Leonardo Motion 2.0 (text-to-video) wrapper.

Submits a text-to-video generation job, polls until complete, downloads the
resulting MP4 to disk. Designed to be called once per shot from cine_short.py.

Requires credentials/leonardo.key (existing in this repo).
"""

import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LEONARDO_KEY_PATH = BASE_DIR / "credentials" / "leonardo.key"

API_BASE = "https://cloud.leonardo.ai/api/rest/v1"
SUBMIT_PATH = "/generations-text-to-video"  # Motion 2.0 endpoint
GENERATION_PATH = "/generations-text-to-video/{id}"

# Default generation params for cine_short
DEFAULT_RESOLUTION  = "RESOLUTION_720"
DEFAULT_ASPECT      = "RATIO_16_9"
DEFAULT_FRAME_RATE  = "FPS_24"


def _headers() -> dict:
    if not LEONARDO_KEY_PATH.exists():
        raise RuntimeError(f"Leonardo API key missing: {LEONARDO_KEY_PATH}")
    key = LEONARDO_KEY_PATH.read_text().strip()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def submit_text_to_video(
    prompt: str,
    duration_sec: int = 5,
    resolution: str = DEFAULT_RESOLUTION,
    aspect_ratio: str = DEFAULT_ASPECT,
    frame_rate: str = DEFAULT_FRAME_RATE,
) -> str:
    """Submit a Motion 2.0 text-to-video job. Returns the generation id."""
    # Anti-ralenti baked into the prompt (Motion 2.0 ne supporte pas
    # negative_prompt — l'API rejette ce champ au niveau racine).
    anti_slowmo = "Natural cinematic pace, real-time motion, no slow-motion."
    full_prompt = f"{prompt} {anti_slowmo}"[:1500]

    body = {
        "prompt":       full_prompt,
        "duration_sec": duration_sec,
        "resolution":   resolution,
        "aspect_ratio": aspect_ratio,
        "frame_rate":   frame_rate,
    }
    r = requests.post(API_BASE + SUBMIT_PATH, headers=_headers(), json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(
            f"Leonardo Motion submit failed [{r.status_code}]: {r.text[:500]}"
        )
    data = r.json()
    # Response shape varies by endpoint version; cover the common cases
    gen_id = (
        data.get("generationId")
        or data.get("sdGenerationJob", {}).get("generationId")
        or data.get("motionVideoGenerationJob", {}).get("generationId")
    )
    if not gen_id:
        raise RuntimeError(f"Unexpected submit response: {data}")
    return gen_id


def poll_until_done(
    gen_id: str,
    timeout_sec: int = 900,
    interval_sec: int = 8,
) -> str:
    """Poll the generation. Returns the final MP4 URL."""
    url = API_BASE + GENERATION_PATH.format(id=gen_id)
    deadline = time.time() + timeout_sec
    last_status = None
    while time.time() < deadline:
        r = requests.get(url, headers=_headers(), timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"Poll failed [{r.status_code}]: {r.text[:300]}")
        data = r.json()
        gen = (
            data.get("motionVideoGeneration")
            or data.get("generations_by_pk")
            or data
        )
        status = gen.get("status") or gen.get("state")
        if status != last_status:
            print(f"     [{gen_id[:8]}] status: {status}")
            last_status = status
        if status in ("COMPLETE", "completed", "Complete"):
            video_url = (
                gen.get("video_url")
                or gen.get("url")
                or (gen.get("generated_videos") or [{}])[0].get("url")
                or (gen.get("videos") or [{}])[0].get("url")
            )
            if not video_url:
                raise RuntimeError(f"COMPLETE but no video_url: {gen}")
            return video_url
        if status in ("FAILED", "failed", "Failed"):
            raise RuntimeError(f"Generation {gen_id} failed: {gen}")
        time.sleep(interval_sec)
    raise TimeoutError(f"Generation {gen_id} did not complete in {timeout_sec}s")


def download_video(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def generate_clip(prompt: str, dest: Path, duration_sec: int = 5) -> None:
    """End-to-end : submit → poll → download a single shot."""
    gen_id = submit_text_to_video(prompt, duration_sec=duration_sec)
    print(f"     Job submitted: {gen_id}")
    video_url = poll_until_done(gen_id)
    print(f"     Downloading...")
    download_video(video_url, dest)
    print(f"     ✓ {dest.name}")
