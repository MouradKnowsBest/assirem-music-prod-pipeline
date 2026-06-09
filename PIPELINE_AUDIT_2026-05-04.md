# Assirem Music PROD — Pipeline Audit & Handoff
**Date :** 2026-05-04  
**Destinataire :** Claude (Mac Mini — générateur de config hebdo)  
**Auteur :** Claude (MacBook — opérateur pipeline)

---

## 1. Architecture générale

```
assirem-music-prod-pipeline/
├── pipeline.py                      ← orchestrateur principal
├── modules/
│   ├── visual.py                    ← génération images + clips (Leonardo AI)
│   ├── video.py                     ← assemblage FFmpeg (MP4 main + short 9:16)
│   ├── youtube.py                   ← upload YouTube + gestion playlists
│   ├── scheduler.py                 ← calcul publish_at intelligent (analytics)
│   └── distribution.py             ← multi-plateforme (DistroKid, TikTok…)
├── scripts/
│   ├── generate_week_config.py      ← TU GÈRES CE FICHIER (génère week_config.json)
│   ├── week_tracks_data.py          ← TU GÈRES CE FICHIER (35 tracks templates)
│   ├── sync_config.py               ← crée les dossiers input/1-slug…
│   ├── fetch_channel_data.py        ← analytics YouTube → channel_data.json
│   ├── smart_schedule.json          ← règles de scheduling par catégorie
│   ├── playlists_map.json           ← 14 playlists fixées (NE JAMAIS en créer de nouvelles)
│   └── channel_data.json            ← analytics historiques (auto-refresh au lancement)
├── today/
│   ├── week_config.json             ← ← ← CONFIG PRINCIPALE (généré par toi)
│   └── config.json                  ← config ponctuelle ad hoc (priorité BASSE)
├── youtube_upload_tracker.json      ← compteur daily uploads (reset chaque jour)
└── youtube_uploaded_videos.json     ← tracker persistant cross-day (slug/fichier → URL)
```

---

## 2. Priorité de lecture des configs dans pipeline.py

```
1. today/week_config.json   ← LU EN PREMIER (le tien)
2. today/config.json        ← lu si week_config.json absent
3. config.json              ← legacy fallback, ne plus utiliser
```

**Important :** Si `today/week_config.json` existe, `today/config.json` est ignoré. L'opérateur utilise `--config today/config.json` pour forcer un batch ad hoc sans effacer le tien.

---

## 3. Schema du track — FORMAT OFFICIEL (generate_week_config.py)

Voici le format exact que `build_track()` dans `generate_week_config.py` produit. **C'est la référence.**

```json
{
  "slug": "tokyo-morning-cafe-lofi-2026",
  "priority": 11,
  "category": "activity",
  "scheduled_at": "2026-04-27T08:15:00+02:00",

  "suno_lyrics": "[Instrumental]",
  "suno_style": "lofi hip hop, vinyl crackle, 75 BPM, cozy",
  "suno_title": "Tokyo Morning Café",
  "suno_exclude_styles": "trap, edm, country",
  "suno_vocal_gender": null,
  "suno_lyrics_mode": "manual",
  "suno_weirdness": 25,
  "suno_style_influence": 50,

  "mode": "medium",
  "title": "☕ Tokyo Morning Café — Lofi Coffee Vibes 2026 | Assirem Music PROD",
  "description": "...",
  "tags": ["lofi hip hop", "study music", "..."],

  "playlists": ["📚 Focus, Lo-Fi & Coffee Work", "🌸 Pop, Chill & Indie Rock", "🎵 Assirem Music PROD — All Tracks"],
  "playlist_name": "📚 Focus, Lo-Fi & Coffee Work",

  "leonardo_model": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3",
  "distribution": {
    "youtube": true,
    "youtube_short": true,
    "distrokid": true,
    "tiktok": true,
    "instagram_reels": true
  },

  "video": {
    "intro_fade_sec": 2,
    "outro_fade_sec": 3,
    "title_card": {
      "enabled": true,
      "duration_sec": 3,
      "text": "Tokyo Morning Café",
      "subtitle": "📚 Focus, Lo-Fi & Coffee Work",
      "style": "minimal_dark"
    },
    "end_card": {
      "enabled": true,
      "duration_sec": 5,
      "subscribe_cta": true
    },
    "short_clip": {
      "start_sec": 15,
      "duration_sec": 55
    }
  },

  "scenes": [
    {"prompt": "Wide shot: Tokyo café at dawn, steam rising from matcha, rain on glass, cinematic 4K", "motion_strength": 2},
    {"prompt": "Close-up: vinyl record spinning, warm orange light, jazz café interior, cinematic 4K", "motion_strength": 3}
  ]
}
```

### Champs critiques

| Champ | Type | Obligatoire | Notes |
|-------|------|-------------|-------|
| `slug` | string | ✅ | kebab-case, unique, se termine par `-2026` |
| `priority` | int | ✅ | 1 = le plus prioritaire, ordre d'exécution |
| `category` | string | ✅ | `trending` / `activity` / `world_music` / `national_holiday` |
| `playlists` | array | ✅ | premier élément = playlist primaire |
| `playlist_name` | string | ✅ | = `playlists[0]` (dupliqué pour compat legacy) |
| `scenes` | array de dicts | ✅ | **format dict** `{"prompt": str, "motion_strength": int}` |
| `video.short_clip.start_sec` | int | ✅ | détermine le début du Short YouTube |
| `scheduled_at` | ISO 8601 | ✅ | slot de la semaine (calculé par generate_week_config.py) |
| `publish_at` | ISO 8601 | ❌ | injecté par le smart scheduler au moment du lancement |

---

## 4. Playlists disponibles — LISTE FIGÉE (ne JAMAIS en créer de nouvelles)

Défini dans `scripts/playlists_map.json`. Le matching se fait par alias (3 niveaux : exact → alias → default).

| Nom officiel | Usage |
|---|---|
| `🎵 Assirem Music PROD — All Tracks` | Catch-all, toujours inclure dans `playlists[]` |
| `🌏 World Music` | Musique du monde, patriotic, folk |
| `🌙 Oriental, Oud & Maghreb` | Oriental, oud, raï, gnawa, tuareg |
| `📚 Focus, Lo-Fi & Coffee Work` | Lofi, study, focus, café |
| `🌸 Pop, Chill & Indie Rock` | Pop, chill, indie, bedroom pop |
| `🎤 Hip-Hop, Rap & R&B` | Hip hop, rap, drill, R&B |
| `💪 Workout, Gym & Motivation` | Gym, phonk, running |
| `🌘 Dark Vibes & Night Drive` | Dark, phonk, midnight |
| `🔮 Electronic, House & Techno` | EDM, synthwave, house |
| `🧘 Meditation, Sleep & Wellness` | Ambient, healing, yoga |
| `🕊️ Cinematic & Epic` | Orchestral, cinematic, anthems |
| `🌍 Afrofuturism & Afrobeats` | Afrobeats, amapiano |
| `🤘 Rock & Alternative` | Rock, metal, punk |
| `🇫🇷 Pop Française` | Chanson française |

---

## 5. Format `week_tracks_data.py` — template source

Les tracks dans `TRACKS[]` utilisent un format simplifié. `build_track()` les complète.

```python
{
    "slug": "mon-track-2026",
    "category": "activity",                    # ou world_music, trending
    "activity_type": "focus",                  # si category == activity
    "country": "Japan",                        # si category == world_music
    "country_flag": "🇯🇵",                    # si category == world_music
    "title": "☕ Mon Track — Subtitle 2026 | Assirem Music PROD",
    "description": "...",
    "tags": ["tag1", "tag2"],
    "playlists": ["📚 Focus, Lo-Fi & Coffee Work"],  # sans All Tracks (ajouté auto)
    "suno_title": "Mon Track",
    "suno_style": "lofi, jazzy, 75 BPM, cozy",
    "suno_exclude_styles": "trap, edm",
    "suno_vocal_gender": None,                 # None = instrumental
    "suno_lyrics": "[Instrumental]",
    "suno_weirdness": 25,
    "suno_style_influence": 50,
    "short_start": 15,                         # secondes → short_clip.start_sec
    "intro_fade_sec": 2,
    "outro_fade_sec": 3,
    "scenes": [                                # TOUJOURS des tuples (prompt, motion_strength)
        ("Wide shot: Tokyo café at dawn, steam, rain, cinematic 4K", 2),
        ("Close-up: vinyl record spinning, warm orange light, 4K", 3),
        ("Medium shot: hands on piano keys, soft window light, 4K", 2),
        ("Aerial: rainy street at night, neon reflections, 4K", 3),
        ("Wide: bookshelf with plants and lamp, cozy interior, 4K", 1),
        ("Final wide: cityscape at dawn, mist, silence, 4K", 2),
    ],
}
```

**Règle sur `scenes` :** Dans `week_tracks_data.py` → **tuples** `(prompt, motion_strength)`.  
`build_track()` les convertit en **dicts** `{"prompt": ..., "motion_strength": ...}` dans le JSON final.  
`visual.py` supporte maintenant les deux formats (fix appliqué le 2026-05-02).

---

## 6. Système de déduplication upload — NE PAS CASSER

Deux fichiers tracent les uploads :

### `youtube_upload_tracker.json` — reset daily
```json
{"date": "2026-05-04", "uploads": 8, "slugs": ["slug-a", "slug-b"]}
```
Limite : 16 uploads/jour (8 tracks × main + short). Si `date` ≠ aujourd'hui, le tracker se réinitialise.

### `youtube_uploaded_videos.json` — persistant cross-day
```json
{"videos": {"slug/fichier.mp4": {"video_id": "abc123", "uploaded_at": "...", "url": "..."}}}
```
Ce fichier **ne se réinitialise jamais**. Si un slug est dedans, le pipeline skip l'upload avec `♻️`.

**Pour forcer un re-upload** (ex : vidéo supprimée puis recréée) :
1. Supprimer l'entrée dans `youtube_uploaded_videos.json`
2. Retirer le slug de `youtube_upload_tracker.json`
3. Relancer avec `--skip-visual --force`

---

## 7. Commandes de référence

```bash
# Générer le config hebdomadaire (TON JOB)
python3 scripts/generate_week_config.py
python3 scripts/generate_week_config.py --start-date 2026-05-05

# Créer les dossiers input/ pour y déposer les MP3
python3 scripts/sync_config.py                        # lit today/week_config.json
python3 scripts/sync_config.py --config today/config.json  # lit un config spécifique

# Lancer le pipeline complet
python3 pipeline.py --all                             # lit week_config.json en priorité
python3 pipeline.py --config today/config.json --all  # force un config spécifique
python3 pipeline.py --all --skip-upload               # génère sans uploader
python3 pipeline.py --all --skip-visual               # skip Leonardo AI (clips déjà prêts)
python3 pipeline.py --slug mon-slug-2026              # un seul track
python3 pipeline.py --list                            # liste les tracks du config actif
```

---

## 8. Smart Scheduler — comportement

Au lancement, le pipeline :
1. Refresh les analytics YouTube (`scripts/fetch_channel_data.py`)
2. Calcule `publish_at` optimal pour chaque track sans `publish_at` explicite
3. Injecte les dates directement dans les dicts en mémoire (le JSON n'est pas modifié)

Règles (`scripts/smart_schedule.json`) :
- Fenêtre : 7 jours
- Max 3 vidéos/jour, gap minimum 2h entre uploads
- Plages autorisées : 08h–21h UTC

**Si tu veux fixer manuellement un créneau** dans `week_tracks_data.py`, ajoute `"publish_at": "2026-05-07T18:00:00+00:00"` dans le template — le scheduler le respecte et ne le recalcule pas.

---

## 9. Changements récents importants (depuis 2026-04-22)

| Date | Changement | Impact |
|------|-----------|--------|
| 2026-04-22 | `playlists_map.json` créé — 14 playlists figées | Plus de création dynamique de playlists |
| 2026-04-22 | `modules/scheduler.py` créé | `publish_at` calculé automatiquement |
| 2026-05-02 | `visual.py` : support format scènes tableau `[prompt, motion]` en plus des dicts | Compatibilité config ad hoc |
| 2026-05-02 | `video.py` : support champ `short_start` flat en plus de `video.short_clip.start_sec` | Compatibilité config ad hoc |
| 2026-05-02 | `youtube_uploaded_videos.json` : tracker persistant cross-day | Évite les doublons sur re-lancement |

**Format canonique pour `generate_week_config.py` : utilise toujours les dicts et `video.short_clip.start_sec`. Les supports alternatifs sont uniquement pour les configs manuels ad hoc.**

---

## 10. Checklist avant de générer un nouveau week_config.json

- [ ] Les slugs sont uniques et se terminent par `-2026`
- [ ] Chaque track a 6 scènes (tuples dans `week_tracks_data.py`)
- [ ] `playlists[0]` correspond exactement à un nom dans `playlists_map.json`
- [ ] `"🎵 Assirem Music PROD — All Tracks"` est dans chaque `playlists[]` (ajouté auto par `build_track`)
- [ ] Les slots de `scheduled_at` sont 5/jour : 08:15 / 12:10 / 16:13 / 20:02 / 23:16
- [ ] `TZ_OFFSET` dans `generate_week_config.py` est à jour (+02:00 en été, +01:00 en hiver)
- [ ] `suno_vocal_gender` est `"male"`, `"female"`, ou `null` (instrumental)
