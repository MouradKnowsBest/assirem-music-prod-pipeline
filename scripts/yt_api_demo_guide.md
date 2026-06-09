# Screen Recording Guide — YouTube API Compliance Review
## Assirem Music PROD · API Client Demo (~4 minutes)

---

### Before you start
- Close all unrelated tabs/windows
- Have terminal ready at project root: `cd ~/Coding/assirem-music-prod-pipeline`
- Have YouTube Studio open in a browser tab (logged in as assirem.music.prod@gmail.com)
- Resolution: 1920×1080, font size readable at normal zoom

---

## SEGMENT 1 — Config & metadata (0:00–1:00)

**Action:** Open `config.json` in editor (VS Code or `cat config.json`)

**Narrate / show clearly:**
1. A single track entry — point out:
   - `"title"` — the YouTube video title
   - `"description"` — full description text
   - `"tags"` — array of keyword tags
   - `"playlists"` — array of playlist names the video is added to
   - `"privacyStatus"` or `"scheduled_at"` — publish timing
   - `"madeForKids": false`
   - `"defaultLanguage"`, `"defaultAudioLanguage"`

2. Scroll to show the thumbnail path reference in the track or output folder:
   - `output/<slug>/<slug>_thumb.jpg` — explain this is passed to `thumbnails.set`

3. Show `modules/youtube.py` briefly — scroll to the `videos.insert` call showing
   `snippet` and `status` resource parts being built from config values.

---

## SEGMENT 2 — OAuth2 token (1:00–1:45)

**Action:** Show `credentials/` folder (blur/hide actual file contents)

**Narrate / show clearly:**
1. `credentials/client_secret.json` exists (show filename only, DO NOT open)
2. `credentials/youtube_oauth.pickle` exists → this is the cached refresh token
3. Open `modules/youtube.py`, scroll to `_authentifier()`:
   - Show the `pickle.load` path (token reuse)
   - Show `InstalledAppFlow.from_client_secrets_file` (first-time OAuth2 browser flow)
   - Show `creds.refresh(Request())` (automatic token refresh)
4. Say: "The token was generated once by signing in as the channel owner.
   All uploads are authorized against that single account."

---

## SEGMENT 3 — Upload execution (1:45–3:00)

**Action:** Run the upload pipeline in terminal

```bash
python pipeline.py --upload --slug afrofuturism-highlife-wave-2026
```

**Narrate / show clearly as output scrolls:**
1. "Loading config…" → config.json read
2. "Authenticating…" → token loaded from pickle (no browser opens = token reuse)
3. `videos.insert` call → show videoId returned in output
4. `thumbnails.set` → thumbnail upload confirmed
5. `playlistItems.insert` → video added to playlist name shown
6. Final line: "✅ Upload complete — videoId: xxxxxxxxxxx"

> If the upload limit is hit, show the `UploadLimitExceeded` error message and explain
> this is a safety guard built into the pipeline — the script does not retry blindly.

---

## SEGMENT 4 — YouTube Studio verification (3:00–4:00)

**Action:** Switch to browser → YouTube Studio (studio.youtube.com)

**Narrate / show clearly:**
1. Go to **Content** → the just-uploaded video appears at the top
2. Click the video → **Details** tab:
   - Title matches config `"title"`
   - Description matches config `"description"`
   - Tags visible
   - Custom thumbnail applied
   - Category, language fields populated
3. Go to **Playlists** tab → confirm video is in the correct playlist
4. Go to channel page `https://www.youtube.com/@AssiremMusicPROD` — channel owned by
   the same Google account used for OAuth2

---

## END — 4:00
Stop recording. Export as MP4, H.264, 1080p.
File name suggestion: `AssiremMusicPROD_API_Demo_2026.mp4`
