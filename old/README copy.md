# 🎵 Assirem Music PROD — Pipeline d'automatisation YouTube

Pipeline complet pour générer et publier automatiquement des vidéos musicales sur YouTube :
**Image Leonardo AI** → **Vidéo FFmpeg** → **Upload YouTube**.

---

## Structure du projet

```
assirem-music-prod-pipeline/
├── pipeline.py              # Script principal à lancer
├── config.json              # Configuration par batch (à modifier avant chaque lancement)
├── input/                   # 📂 Placez vos fichiers MP3 ici
├── output/                  # 📂 Fichiers générés (background.png, *.mp4)
├── credentials/
│   ├── leonardo.key         # Clé API Leonardo AI (déjà configurée)
│   ├── client_secret.json   # À télécharger depuis Google Cloud Console
│   └── youtube_oauth.pickle # Généré automatiquement au premier lancement
└── modules/
    ├── visual.py            # Génération image via Leonardo AI
    ├── video.py             # Assemblage MP4 via FFmpeg
    └── youtube.py           # Upload YouTube Data API v3
```

---

## Configuration de `config.json`

Modifiez ce fichier avant chaque batch :

```json
{
  "mode": "medium",
  "title": "Titre de la vidéo YouTube",
  "description": "Description YouTube...\n\n#tag1 #tag2",
  "tags": ["musique kabyle", "kabyle", "amazigh"],
  "playlist_name": "Nom de la playlist YouTube cible",
  "visual_prompt": "Prompt texte pour Leonardo AI (description de l'image de fond)",
  "leonardo_model": "aa77f04e-3eec-4034-9c07-d0a0c2b8d367",
  "input_folder": "input",
  "output_folder": "output"
}
```

### Modes disponibles

| Mode         | Comportement                                               |
|--------------|------------------------------------------------------------|
| `individual` | Une vidéo MP4 par fichier MP3                              |
| `short`      | Une vidéo avec le premier MP3 uniquement                   |
| `medium`     | Une vidéo de ~30 min (concatène / loope les MP3)           |
| `long`       | Une vidéo de ~2h (concatène / loope les MP3)               |

---

## Obtenir les credentials YouTube OAuth2 (première fois)

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un projet (ou sélectionnez-en un existant)
3. Activez **YouTube Data API v3** dans *APIs & Services → Bibliothèque*
4. Dans *APIs & Services → Identifiants* :
   - Créez un **ID client OAuth 2.0** de type **Application de bureau**
   - Téléchargez le fichier JSON
5. Renommez-le `client_secret.json` et placez-le dans `credentials/`
6. Au premier `python pipeline.py`, un navigateur s'ouvre pour vous authentifier
7. Le token est sauvegardé dans `credentials/youtube_oauth.pickle` → plus besoin de vous authentifier ensuite

---

## Lancer le pipeline

```bash
cd ~/Coding/assirem-music-prod-pipeline

# Pipeline complet
python pipeline.py

# Forcer la regénération des fichiers déjà existants
python pipeline.py --force

# Sauter la génération d'image (réutiliser background.png existant)
python pipeline.py --skip-visual

# Sauter la génération vidéo (réutiliser les MP4 existants dans output/)
python pipeline.py --skip-video

# Générer image + vidéo sans uploader sur YouTube
python pipeline.py --skip-upload

# Combiner les options (ex: régénérer les vidéos et uploader sans refaire l'image)
python pipeline.py --skip-visual

# Mode debug (affiche les stack traces complets en cas d'erreur)
python pipeline.py --debug
```

---

## Workflow typique par batch

```bash
# 1. Déposez vos MP3 dans input/
cp ~/Downloads/*.mp3 input/

# 2. Modifiez config.json (titre, description, mode, prompt visuel...)
nano config.json   # ou ouvrez dans votre éditeur préféré

# 3. Lancez le pipeline
python pipeline.py

# 4. La vidéo est publiée et son lien YouTube est affiché dans le terminal ✅
```

---

## Dépendances

| Outil            | Rôle                            | Installation              |
|------------------|---------------------------------|---------------------------|
| Python 3.8+      | Langage principal               | Préinstallé sur macOS     |
| FFmpeg           | Assemblage audio/vidéo          | `brew install ffmpeg`     |
| requests         | Appels API Leonardo AI          | `pip install requests`    |
| google-api-python-client | YouTube Data API v3   | `pip install google-api-python-client google-auth-oauthlib` |

Pour tout installer d'un coup :
```bash
brew install ffmpeg
pip install requests google-auth google-auth-oauthlib google-api-python-client
```

---

## Résolution des problèmes fréquents

**`FileNotFoundError: credentials/leonardo.key`**
→ Le fichier existe déjà avec votre clé. Vérifiez qu'il n'est pas vide.

**`FileNotFoundError: credentials/client_secret.json`**
→ Téléchargez votre fichier OAuth depuis Google Cloud Console (voir section ci-dessus).

**`Aucun fichier MP3 trouvé dans input/`**
→ Placez vos fichiers `.mp3` dans le dossier `input/` avant de lancer le pipeline.

**`Erreur Leonardo API (401)`**
→ Clé API Leonardo invalide ou expirée. Vérifiez `credentials/leonardo.key`.

**L'image existe déjà mais vous voulez la regénérer**
→ Lancez avec `python pipeline.py --force` ou supprimez `output/background.png`.

**La vidéo existe déjà et n'est pas reuploadée**
→ Le pipeline ne recrée pas les fichiers existants par défaut. Utilisez `--force`.
