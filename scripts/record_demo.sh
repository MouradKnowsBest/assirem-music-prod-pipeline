#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# record_demo.sh — Screen recording + upload demo for YouTube API compliance
#
# Usage:
#   bash scripts/record_demo.sh
#
# What it does:
#   1. Starts screen recording (macOS built-in screencapture)
#   2. Runs the full upload pipeline on a real track
#   3. Stops the recording
#   4. Output: scripts/compliance_screenshots/AssiremMusicPROD_API_Demo_2026.mp4
#
# Before running:
#   - Make sure a video MP4 is ready in output/afrofuturism-highlife-wave-2026/
#   - You are logged into YouTube Studio in your browser (for the final step)
#   - Terminal window is full-screen or maximized
# ──────────────────────────────────────────────────────────────────────────────

set -e
CD="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CD"

OUT="scripts/compliance_screenshots/AssiremMusicPROD_API_Demo_2026.mp4"
SLUG="afrofuturism-highlife-wave-2026"

echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│   Assirem Music PROD — API Compliance Demo Recording    │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
echo "  Slug    : $SLUG"
echo "  Output  : $OUT"
echo ""
echo "  ⚠️  Make sure:"
echo "     • This terminal window is maximized"
echo "     • YouTube Studio is open in Chrome (logged in)"
echo "     • No sensitive info visible on screen"
echo ""
echo "  Recording starts in 3 seconds..."
sleep 3

# ── Start background screen recording ────────────────────────────────────────
# Uses ffmpeg avfoundation (macOS) — screen index 1 (main display)
# Check available devices: ffmpeg -f avfoundation -list_devices true -i ""
ffmpeg -y \
  -f avfoundation \
  -framerate 30 \
  -i "1:0" \
  -vf "scale=1920:1080" \
  -c:v libx264 \
  -preset ultrafast \
  -crf 23 \
  -c:a aac \
  -b:a 128k \
  "$OUT" \
  > /tmp/ffmpeg_record.log 2>&1 &

FFMPEG_PID=$!
echo "  🔴 Recording started (PID $FFMPEG_PID)"
sleep 2

# ── SEGMENT 1 : Show config.json ─────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SEGMENT 1 — Metadata config (config.json / week_config.json)"
echo "════════════════════════════════════════════════════════════"
sleep 1
echo ""
echo "  Track configuration:"
python -c "
import json
data = json.load(open('today/week_config.json'))
t = next(x for x in data['tracks'] if x['slug']=='afrofuturism-highlife-wave-2026')
fields = ['slug','title','tags','playlists','scheduled_at','madeForKids','defaultLanguage']
out = {k: t.get(k,'') for k in fields}
import json as j
print(j.dumps(out, indent=4, ensure_ascii=False))
"
sleep 5

# ── SEGMENT 2 : OAuth2 token ─────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SEGMENT 2 — OAuth2 authentication (token cache)"
echo "════════════════════════════════════════════════════════════"
sleep 1
echo ""
python -c "
import pickle, os
p = 'credentials/youtube_oauth.pickle'
creds = pickle.load(open(p,'rb'))
print('  credentials/youtube_oauth.pickle — exists')
print(f'  Token valid        : {creds.valid}')
print(f'  Token expired      : {creds.expired}')
print(f'  Has refresh_token  : {bool(creds.refresh_token)}')
print()
print('  → Token will be refreshed automatically via creds.refresh(Request())')
print('  → No browser prompt. Single owner account only.')
"
sleep 5

# ── SEGMENT 3 : Upload ───────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SEGMENT 3 — Running upload pipeline"
echo "════════════════════════════════════════════════════════════"
sleep 1
echo ""
python pipeline.py --upload --slug "$SLUG"
sleep 3

# ── SEGMENT 4 : Instruction for YouTube Studio ───────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SEGMENT 4 — Open YouTube Studio now"
echo "  Go to: https://studio.youtube.com → Content"
echo "  Show: uploaded video, thumbnail, playlist"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  (switch to browser — recording still running)"
sleep 25   # 25s to switch to browser and show Studio

# ── Stop recording ────────────────────────────────────────────────────────────
kill $FFMPEG_PID 2>/dev/null || true
sleep 2
echo ""
echo "  ⏹  Recording stopped"
echo "  ✅  Saved to: $OUT"
echo ""
