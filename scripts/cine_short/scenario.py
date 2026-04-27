"""
scenario.py — Generate a cinematic shot list from a logline + tone.

Calls Claude API to produce a structured JSON scenario (24 shots × 5s = 120s)
with a real narrative arc, varied shot types and camera movements.

Requires ANTHROPIC_API_KEY env var or credentials/anthropic.key file.
"""

import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SCENARIO_PROMPT = """You are a cinematographer writing a 2-minute cinematic short film.

LOGLINE: {logline}
TONE: {tone}
TARGET DURATION: 120 seconds (24 shots × 5 seconds each)

Build a complete narrative with arc:
  Setup (shots 1-4)
  Inciting Incident (5-8)
  Rising Action (9-16)
  Climax (17-21)
  Resolution (22-24)

HARD RULES:
- Each shot is 5 seconds at REAL TIME / NORMAL SPEED
- Never write "slow motion", "ralenti", "time-lapse", "freeze" — actions should
  unfold at natural human pace
- Vary shot types : wide / medium / close-up / insert / over-shoulder
- Vary camera movement : static / pan / tracking / tilt / dolly — but always
  at NATURAL CINEMATIC PACE (no whip pans, no extreme slow drifts)
- Maintain visual continuity across shots (same character look, same locations,
  consistent lighting/time-of-day progression)
- Each prompt should be 25-40 words, with explicit lighting + mood + composition
- Prompts must be self-contained (Leonardo Motion 2.0 has no memory between shots),
  so re-mention character description in each shot they appear

Return ONLY valid JSON, no markdown fences, no commentary, no preamble.

Schema:
{{
  "title": "<3-6 words>",
  "logline": "<refined 1-sentence>",
  "tone": "<refined>",
  "duration_sec": 120,
  "shots": [
    {{
      "id": 1,
      "story_beat": "Setup",
      "shot_type": "wide",
      "movement": "static",
      "duration_sec": 5,
      "prompt": "Wide establishing shot: <full cinematic prompt with lighting + mood>"
    }},
    ... 24 shots total ...
  ]
}}

Begin:"""


def get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    key_path = BASE_DIR / "credentials" / "anthropic.key"
    if key_path.exists():
        return key_path.read_text().strip()
    raise RuntimeError(
        "ANTHROPIC_API_KEY missing.\n"
        "→ export ANTHROPIC_API_KEY=sk-ant-...\n"
        "→ or echo 'sk-ant-...' > credentials/anthropic.key"
    )


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def generate_scenario(
    logline: str,
    tone: str = "cinematic, atmospheric",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 8000,
) -> dict:
    """Call Claude API and return the parsed scenario dict."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("Install: pip install anthropic")

    client = Anthropic(api_key=get_anthropic_key())
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": SCENARIO_PROMPT.format(logline=logline, tone=tone),
        }],
    )
    text = _strip_code_fence(msg.content[0].text)
    scenario = json.loads(text)

    # Sanity checks
    shots = scenario.get("shots", [])
    if not shots:
        raise ValueError("Scenario has no 'shots' field")
    if len(shots) != 24:
        print(f"⚠️  Got {len(shots)} shots (expected 24) — continuing anyway")

    return scenario
