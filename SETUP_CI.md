# Setup CI — Pipeline Assirem (Drive → YouTube)

## Ce que tu fais

1. Tu crées ton MP3 (Suno ou autre)
2. Tu crées ton image cover
3. Tu les glisses dans Google Drive
4. Le pipeline compile la vidéo et uploade sur YouTube tout seul

---

## Architecture

```
[iPhone / PC]
   │  drag & drop
   ▼
Google Drive : "Assirem Stock/incoming/"
   slug.mp3  +  slug.jpg  (+ slug.json optionnel)
   │
   ▼  4x/jour — 6h / 11h / 16h / 21h UTC
GitHub Actions
   1. Download depuis Drive
   2. JSON auto-généré si absent (depuis le nom de fichier)
   3. python pipeline.py --skip-visual --all
      ├─ Ton image → scènes vidéo (Ken Burns)
      ├─ FFmpeg → vidéo .mp4
      └─ YouTube → upload
   4. Fichiers déplacés vers Drive done/
```

---

## Setup en 4 étapes (one-time)

### 1. Google Drive — dossier stock

Le dossier est déjà créé : `18mvbvMGDe4za7aAgAgfea-O3qtjibgJ6`

Crée un sous-dossier **"incoming"** dedans si ce n'est pas déjà fait.

---

### 2. Google Service Account — accès Drive en CI

1. Va sur [console.cloud.google.com](https://console.cloud.google.com)
2. **APIs & Services → Enable APIs** → active **Google Drive API**
3. **IAM & Admin → Service Accounts → Create Service Account**
   - Nom : `assirem-ci` (peu importe)
4. Dans le service account → **Keys → Add Key → JSON** → télécharge
5. Note l'email du compte (ex: `assirem-ci@mon-projet.iam.gserviceaccount.com`)
6. **Partage ton dossier Drive** avec cet email (droits Éditeur)

---

### 3. YouTube OAuth — exporter le token

Le pipeline YouTube utilise OAuth. En CI, on passe le token existant.

```bash
# Sur ton Mac, dans le dossier du projet :
base64 credentials/youtube_oauth.pickle | pbcopy
# → ça copie le token dans ton presse-papiers
```

---

### 4. GitHub — ajouter les 3 secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret** :

| Secret | Valeur |
|--------|--------|
| `YOUTUBE_CLIENT_SECRET_JSON` | Contenu de `credentials/client_secret.json` |
| `YOUTUBE_OAUTH_PICKLE_B64` | Output de la commande `base64` ci-dessus |
| `GOOGLE_DRIVE_SA_JSON` | Contenu du JSON du service account (étape 2) |

C'est tout.

---

## Convention de nommage des fichiers

Le **slug** = nom du fichier sans extension. Les deux fichiers doivent avoir le même nom :

```
lofi-coffee-shop.mp3
lofi-coffee-shop.jpg
```

Tu peux aussi ajouter un `lofi-coffee-shop.json` si tu veux contrôler
le titre/description/tags YouTube. Sinon, ils sont auto-générés depuis le slug.

---

## Lancer manuellement (sans attendre le cron)

GitHub → onglet **Actions** → **"Assirem Pipeline (Drive Stock)"** → **Run workflow**

Options disponibles :
- `slug` : pour traiter un track spécifique uniquement
- `skip_upload` : dry-run (compile la vidéo mais n'uploade pas)

---

## Structure Drive après utilisation

```
Assirem Stock/
  incoming/    ← tu déposes ici
  done/        ← après succès (créé automatiquement)
  failed/      ← si erreur (créé automatiquement)
```
