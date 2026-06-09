#!/usr/bin/env python3
"""
cine_short.py — Cinematic short-film generator (2 min, 24 shots × 5s).

Workflow :
  1. scenario  : Claude → story.json (24 shots, narrative arc)
  2. clips     : Leonardo Motion 2.0 → 24 × MP4 dans clips/
  3. montage   : ffmpeg concat + audio + fade

Usage :
  # Étape 1 — génère le scénario depuis logline + tone
  python3 scripts/cine_short/cine_short.py scenario \\
      --logline "Noir detective in rainy Tokyo finds a clue at 3AM" \\
      --tone "moody, neon-lit, melancholic"

  # → produit output/cine/<slug>/story.json

  # Étape 2 — génère les 24 clips via Leonardo Motion 2.0
  python3 scripts/cine_short/cine_short.py clips --slug noir-detective-tokyo

  # Étape 3 — montage final + audio
  python3 scripts/cine_short/cine_short.py montage \\
      --slug noir-detective-tokyo \\
      --audio /path/to/instrumental_track.mp3
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
HERE     = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OUTPUT_DIR = BASE_DIR / "output" / "cine"


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:60] or "untitled"


def load_story(slug: str) -> tuple[Path, dict]:
    scenario_dir = OUTPUT_DIR / slug
    story_file = scenario_dir / "story.json"
    if not story_file.exists():
        sys.exit(f"❌ story.json introuvable : {story_file}\n   Lance d'abord : cine_short.py scenario --logline ...")
    return scenario_dir, json.loads(story_file.read_text(encoding="utf-8"))


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_scenario(args) -> None:
    from scenario import generate_scenario

    print(f"  🎬 Génération scénario via Claude...")
    print(f"     Logline : {args.logline}")
    print(f"     Tone    : {args.tone}")

    sc = generate_scenario(args.logline, args.tone, model=args.model)
    title = sc.get("title", "untitled")
    slug  = args.slug or slugify(title)

    out_dir = OUTPUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "story.json"
    out_file.write_text(json.dumps(sc, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"✅ Scénario écrit → {out_file}")
    print(f"   Slug   : {slug}")
    print(f"   Titre  : {title}")
    print(f"   Shots  : {len(sc.get('shots', []))}")
    print()
    print(f"  Prochaines étapes :")
    print(f"    python3 scripts/cine_short/cine_short.py clips --slug {slug}")
    print(f"    python3 scripts/cine_short/cine_short.py montage --slug {slug} --audio <track.mp3>")


def cmd_clips(args) -> None:
    from leonardo_motion import generate_clip

    scenario_dir, sc = load_story(args.slug)
    clips_dir = scenario_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    shots = sc.get("shots", [])
    total = len(shots)
    if not total:
        sys.exit("❌ Aucune shot dans story.json")

    done = 0
    failed = 0
    for shot in shots:
        i = shot["id"]
        dest = clips_dir / f"shot_{i:02d}.mp4"
        beat = shot.get("story_beat", "?")
        kind = shot.get("shot_type", "?")
        mvmt = shot.get("movement", "?")

        print(f"\n── Shot {i}/{total}  [{beat}]  ({kind}, {mvmt})")
        print(f"   {shot.get('prompt', '')[:120]}{'…' if len(shot.get('prompt','')) > 120 else ''}")

        if dest.exists() and not args.force:
            print(f"   ♻️  Déjà généré, skip ({dest.name})")
            done += 1
            continue

        gen_id_cache = clips_dir / f"shot_{i:02d}.gen_id"
        try:
            generate_clip(
                shot["prompt"],
                dest,
                duration_sec=shot.get("duration_sec", 5),
                gen_id_cache=gen_id_cache,
            )
            # Clip OK : on peut nettoyer le cache du gen_id
            gen_id_cache.unlink(missing_ok=True)
            done += 1
        except Exception as e:
            failed += 1
            print(f"   ❌ Échec : {e}")
            if args.stop_on_error:
                sys.exit(1)

    print(f"\n  📊 {done}/{total} shots générés ({failed} échecs)")
    if done == total:
        print(f"\n  Prochaine étape :")
        print(f"    python3 scripts/cine_short/cine_short.py montage --slug {args.slug} --audio <track.mp3>")


def cmd_montage(args) -> None:
    from montage import concat_clips, add_audio, fade_in_out

    scenario_dir, sc = load_story(args.slug)
    clips_dir = scenario_dir / "clips"
    if not clips_dir.exists():
        sys.exit(f"❌ {clips_dir} manquant. Lance d'abord : cine_short.py clips --slug {args.slug}")

    clips = sorted(clips_dir.glob("shot_*.mp4"))
    if not clips:
        sys.exit("❌ Aucun clip dans clips/")

    print(f"  🎞  Concat {len(clips)} clip(s)...")
    concat_path = scenario_dir / "_concat.mp4"
    concat_clips(clips, concat_path)

    if args.audio:
        audio_path = Path(args.audio).expanduser().resolve()
        if not audio_path.exists():
            sys.exit(f"❌ Audio introuvable : {audio_path}")
        print(f"  🎵 Add audio : {audio_path.name}")
        with_audio = scenario_dir / "_with_audio.mp4"
        add_audio(concat_path, audio_path, with_audio, loop_audio=args.loop_audio)
        source = with_audio
    else:
        print(f"  ⚠️  Pas d'audio fourni — final sera muet")
        source = concat_path

    print(f"  ✨ Fade in/out + encode final ({args.fade_sec}s)...")
    final = scenario_dir / f"{args.slug}.mp4"
    fade_in_out(source, final, fade_sec=args.fade_sec)

    # cleanup intermediates if final exists
    if final.exists() and not args.keep_intermediates:
        for tmp in (concat_path, scenario_dir / "_with_audio.mp4"):
            if tmp.exists() and tmp != final:
                tmp.unlink()

    print()
    print(f"✅ Film final → {final}")
    print(f"   Durée  : ~{len(clips) * 5}s")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cinematic short-film generator (Claude scenario + Leonardo Motion 2.0 + ffmpeg)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("scenario", help="Génère story.json depuis logline + tone (via Claude)")
    p1.add_argument("--logline", required=True, help="Phrase d'accroche (1 phrase)")
    p1.add_argument("--tone",    default="cinematic, atmospheric, dramatic")
    p1.add_argument("--slug",    default=None, help="Override le slug auto-généré depuis le titre")
    p1.add_argument("--model",   default="claude-sonnet-4-6")
    p1.set_defaults(func=cmd_scenario)

    p2 = sub.add_parser("clips", help="Génère les 24 clips via Leonardo Motion 2.0")
    p2.add_argument("--slug", required=True)
    p2.add_argument("--force", action="store_true", help="Régénère même si le clip existe déjà")
    p2.add_argument("--stop-on-error", action="store_true")
    p2.set_defaults(func=cmd_clips)

    p3 = sub.add_parser("montage", help="Concat + audio + fade → MP4 final")
    p3.add_argument("--slug",  required=True)
    p3.add_argument("--audio", default=None, help="MP3/WAV path (optionnel)")
    p3.add_argument("--loop-audio", action="store_true", help="Loop l'audio si plus court que la vidéo")
    p3.add_argument("--fade-sec", type=float, default=1.0)
    p3.add_argument("--keep-intermediates", action="store_true")
    p3.set_defaults(func=cmd_montage)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
