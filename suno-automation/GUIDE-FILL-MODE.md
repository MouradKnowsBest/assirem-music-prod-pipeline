# 🎵 Suno Fill Automation — Mode Assisté

## 🎯 Concept

Script qui se connecte à **ton Chrome déjà ouvert** et automatise le remplissage complet des champs Suno + génération.

**Champs remplis automatiquement :**

- ✅ Titre (`suno_title`)
- ✅ Style (`suno_style`)
- ✅ Lyrics (`suno_lyrics`)
- ✅ Exclude Styles (`suno_exclude_styles`)
- ✅ Vocal Gender (`suno_vocal_gender`)
- ✅ Lyrics Mode (`suno_lyrics_mode`)
- ✅ Weirdness (`suno_weirdness`)
- ✅ Style Influence (`suno_style_influence`)
- ✅ Clic sur Generate

**Options :**

- Mode standard : remplit et génère
- Mode avec téléchargement : remplit, génère **et télécharge** les MP3 dans `input/X-slug/`

---

## 🚀 Mode d'emploi

### 1. Ouvrir Chrome en mode debug

Dans un terminal, lance :

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

**💡 Astuce :** Crée un alias dans ton `~/.zshrc` :

```bash
alias chrome-debug='/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"'
```

Ensuite tu pourras juste faire : `chrome-debug`

### 2. Te connecter à Suno

Dans ce Chrome qui vient de s'ouvrir :

1. Va sur https://suno.com
2. Connecte-toi normalement
3. Va sur https://suno.com/create

### 3. Lancer le script

Dans un **autre terminal**, depuis le dossier `suno-automation` :

**Option A : Remplir et générer (sans téléchargement)**

```bash
npm run fill
```

**Option B : Remplir, générer ET télécharger les MP3**

```bash
npm run fill:download
```

Le script va :

1. Se connecter au Chrome déjà ouvert
2. Lire les 10 tracks de ton `config.json`
3. Pour chaque track :
   - Remplir **tous** les champs Suno
   - Cliquer sur "Generate"
   - (Mode download) Attendre la fin de génération (max 5 min)
   - (Mode download) Télécharger le MP3 dans `input/X-slug/`
   - Retourner à `/create` pour la prochaine

**💡 Le mode download est expérimental** : il attend que chaque génération se termine avant de passer à la suivante. Ça prend plus de temps mais tu as les MP3 automatiquement !

---

## 📝 Format attendu dans config.json

Le script lit ces champs de chaque track :

```json
{
  "suno_title": "Neon Africa Afrobeats 2026",
  "suno_style": "afrobeats, amapiano, highlife, euphoric, 105 BPM",
  "suno_lyrics": "[Instrumental]",
  "suno_exclude_styles": "metal, heavy guitar, country, sad",
  "suno_vocal_gender": null, // ou "male" ou "female"
  "suno_lyrics_mode": "manual", // ou "auto"
  "suno_weirdness": 40, // 0-100
  "suno_style_influence": 52 // 0-100
}
```

---

## ⚙️ Personnalisation

### Ajuster les délais

Dans `fill-only.js`, tu peux modifier :

```javascript
await sleep(1000); // Attente entre les champs
await sleep(2000); // Attente avant Generate
await sleep(3000); // Attente après Generate
```

### Sélecteurs Suno

Si Suno change son UI, tu devras peut-être ajuster les sélecteurs dans le code :

```javascript
// Exemples de sélecteurs
const styleInput = page.locator('textarea[placeholder*="Style"]');
const generateButton = page.locator('button:has-text("Create")');
```

---

## 🐛 Troubleshooting

### "Impossible de se connecter au Chrome"

→ Vérifie que Chrome est bien lancé avec `--remote-debugging-port=9222`

### "Champ XXX non trouvé"

→ Ouvre Chrome DevTools et inspecte l'élément pour trouver le bon sélecteur

### Le bouton Generate est désactivé

→ Vérifie que tous les champs requis sont remplis (notamment le Style)

### La génération ne se lance pas

→ Augmente les délais (`sleep`) pour laisser plus de temps à l'UI de Suno

---

## 🎯 Prochaines étapes possibles

1. **Téléchargement auto des MP3** : attendre la fin de génération et télécharger
2. **Retry logic** : réessayer si un champ n'est pas rempli
3. **Logs détaillés** : sauvegarder les résultats dans un fichier JSON
4. **Mode interactif** : demander confirmation avant chaque Generate

---

## 💡 Pourquoi ça marche mieux ?

En te connectant à un Chrome **déjà authentifié** :

- Suno voit une vraie session utilisateur
- Pas de détection de bot
- Tu gardes le contrôle total
- Tu peux intervenir si besoin

C'est la **meilleure approche** pour automatiser Suno sans se battre contre les protections anti-bot ! 🚀
