#!/usr/bin/env node
/**
 * fill-only.js
 * 
 * Se connecte à un navigateur Chrome DÉJÀ OUVERT et automatise:
 * - Remplissage des champs Suno (title, style, lyrics)
 * - Clic sur Generate
 * 
 * USAGE:
 * 1. Ouvre Chrome avec: 
 *    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
 * 2. Connecte-toi à Suno manuellement dans ce Chrome
 * 3. Lance ce script: node src/fill-only.js
 */

const playwright = require("playwright");
const fs = require("fs");
const path = require("path");

// ─── Config ───────────────────────────────────────────────────────────────────

const CONFIG_PATH = path.join(__dirname, "../../config.json");
const INPUT_DIR = path.join(__dirname, "../../input");
const SUNO_BASE = "https://suno.com";
const DEBUG_PORT = 9222; // Port du Chrome en mode debug
const AUTO_DOWNLOAD = process.env.AUTO_DOWNLOAD === "true"; // Activer avec AUTO_DOWNLOAD=true

// ─── Helpers ──────────────────────────────────────────────────────────────────

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`config.json introuvable: ${CONFIG_PATH}`);
  }
  return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForGeneration(page, trackSlug, timeout = 300000) {
  console.log(`\n  ⏳ Attente de la génération (max ${timeout/1000}s)...`);
  
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeout) {
    try {
      // Vérifier si on est sur une page de chanson générée
      const currentUrl = page.url();
      
      if (currentUrl.includes("/song/")) {
        // Chercher le bouton de téléchargement
        const downloadButton = page.locator('button[aria-label*="Download"], a[download]').first();
        
        if (await downloadButton.isVisible({ timeout: 2000 })) {
          console.log("  ✅ Génération terminée !");
          return currentUrl;
        }
      }
      
      // Attendre 5 secondes avant de revérifier
      await sleep(5000);
      
      // Afficher un point toutes les 10 secondes pour montrer la progression
      if ((Date.now() - startTime) % 10000 < 5000) {
        process.stdout.write(".");
      }
    } catch (e) {
      // Continue d'attendre
    }
  }
  
  console.log("\n  ⏱ Timeout atteint, génération probablement non terminée");
  return null;
}

async function downloadMP3(page, trackSlug, trackNum) {
  try {
    console.log("\n  💾 Téléchargement du MP3...");
    
    // Créer le dossier de destination
    const destFolder = path.join(INPUT_DIR, `${trackNum}-${trackSlug}`);
    if (!fs.existsSync(destFolder)) {
      fs.mkdirSync(destFolder, { recursive: true });
    }
    
    // Trouver le lien de téléchargement
    const downloadLink = page.locator('a[download], button:has-text("Download")').first();
    
    if (await downloadLink.isVisible({ timeout: 5000 })) {
      // Récupérer l'URL du MP3
      const mp3Url = await downloadLink.getAttribute('href');
      
      if (mp3Url) {
        // Télécharger le fichier
        const response = await page.context().request.get(mp3Url);
        const buffer = await response.body();
        
        // Sauvegarder dans le bon dossier
        const filename = `${trackSlug}.mp3`;
        const filepath = path.join(destFolder, filename);
        
        fs.writeFileSync(filepath, buffer);
        console.log(`  ✅ MP3 téléchargé : ${filepath}`);
        return filepath;
      }
    }
    
    console.log("  ⚠ Impossible de trouver le lien de téléchargement");
    return null;
  } catch (e) {
    console.log(`  ❌ Erreur lors du téléchargement : ${e.message.split('\n')[0]}`);
    return null;
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("\n🎵 Suno Fill Automation (Attach Mode)\n");
  
  if (AUTO_DOWNLOAD) {
    console.log("🔽 Mode AUTO-DOWNLOAD activé : téléchargement automatique des MP3\n");
  }

  // 1. Charger les tracks du config.json
  const config = loadConfig();
  const tracks = config.tracks || [];
  
  if (tracks.length === 0) {
    console.error("❌ Aucune track trouvée dans config.json");
    process.exit(1);
  }

  console.log(`✓ ${tracks.length} track(s) trouvée(s) dans config.json\n`);

  // 2. Se connecter au Chrome déjà ouvert
  console.log(`🔌 Connexion au Chrome sur le port ${DEBUG_PORT}...`);
  
  let browser;
  try {
    browser = await playwright.chromium.connectOverCDP(`http://localhost:${DEBUG_PORT}`);
  } catch (error) {
    console.error("\n❌ Impossible de se connecter au Chrome.");
    console.error("\nAssure-toi d'avoir lancé Chrome avec:");
    console.error('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"\n');
    process.exit(1);
  }

  const contexts = browser.contexts();
  if (contexts.length === 0) {
    console.error("❌ Aucun contexte trouvé dans le navigateur");
    browser.close();
    process.exit(1);
  }

  const context = contexts[0];
  const pages = context.pages();
  
  let page;
  if (pages.length === 0) {
    console.log("📄 Création d'un nouvel onglet...");
    page = await context.newPage();
  } else {
    console.log(`✓ Utilisation d'un onglet existant (${pages.length} onglet(s) ouverts)`);
    page = pages[0];
  }

  try {
    // 3. Aller sur Suno /create (ou vérifier si on y est déjà)
    const currentUrl = page.url();
    if (!currentUrl.includes("suno.com")) {
      console.log(`\n🌐 Navigation vers Suno...`);
      await page.goto(`${SUNO_BASE}/create`, { waitUntil: "domcontentloaded" });
    } else if (!currentUrl.includes("/create")) {
      console.log(`\n🌐 Navigation vers /create...`);
      await page.goto(`${SUNO_BASE}/create`, { waitUntil: "domcontentloaded" });
    } else {
      console.log(`✓ Déjà sur Suno Create`);
    }

    await sleep(2000); // Attendre que la page se stabilise

    // 4. Boucle sur chaque track
    for (let i = 0; i < tracks.length; i++) {
      const track = tracks[i];
      const num = i + 1;
      
      console.log(`\n━━━ Track ${num}/${tracks.length} : ${track.slug} ━━━`);

      // Extraire les données
      const title = track.suno_title || track.title || track.slug;
      const style = track.suno_style || "";
      const lyrics = track.suno_lyrics || "[Instrumental]";
      const excludeStyles = track.suno_exclude_styles || "";
      const vocalGender = track.suno_vocal_gender; // null, "male", "female"
      const lyricsMode = track.suno_lyrics_mode || "manual"; // "manual" or "auto"
      const weirdness = track.suno_weirdness || 50; // 0-100
      const styleInfluence = track.suno_style_influence || 50; // 0-100
      const isInstrumental = lyrics.trim().toLowerCase() === "[instrumental]";

      console.log(`📝 Titre             : ${title}`);
      console.log(`🎨 Style             : ${style}`);
      console.log(`📄 Lyrics            : ${isInstrumental ? "[Instrumental]" : lyrics.substring(0, 50) + "..."}`);
      console.log(`🚫 Exclude Styles    : ${excludeStyles || "Aucun"}`);
      console.log(`🎤 Vocal Gender      : ${vocalGender || "Non spécifié"}`);
      console.log(`📝 Lyrics Mode       : ${lyricsMode}`);
      console.log(`🎲 Weirdness         : ${weirdness}%`);
      console.log(`🎨 Style Influence   : ${styleInfluence}%`);

      // Attendre un peu avant de remplir (pour voir ce qui se passe)
      await sleep(2000);

      // ─── Remplissage des champs ─────────────────────────────────────────────

      // Stratégie : Suno a deux interfaces possibles
      // 1. Mode "Song Description" (nouveau, plus simple) : un seul champ de description
      // 2. Mode "Custom" (ancien) : sections Lyrics + Styles séparées

      // ═══════════════════════════════════════════════════════════════════════
      // REMPLISSAGE - Utiliser le mode "Song Description" (plus simple et fiable)
      // ═══════════════════════════════════════════════════════════════════════
      
      console.log("\n  🎯 Stratégie : Remplissage via Song Description");
      
      try {
        // 1. Vérifier et scroll vers le bas de la modale si nécessaire
        await page.evaluate(() => {
          const modal = document.querySelector('.chakra-modal__body, [role="dialog"]');
          if (modal) {
            modal.scrollTop = modal.scrollHeight;
          }
        });
        await sleep(500);

        // 2. Chercher le textarea Song Description (scroll en bas)
        const descTextarea = page.locator('textarea[placeholder*="Grande chanson"], textarea[placeholder*="bluegrass"], div.css-1e86nzw textarea[maxlength="500"]').last();
        
        if (await descTextarea.isVisible({ timeout: 3000 })) {
          console.log("  ✓ Champ Song Description trouvé");
          
          // Combiner titre + style pour la description
          const description = `${title} — ${style}`;
          console.log(`  → Description: "${description.substring(0, 65)}..."`);
          
          await descTextarea.click();
          await sleep(300);
          await descTextarea.fill(description);
          await sleep(800);
          
          console.log("  ✓ Description remplie");

          // 3. Cocher "Instrumental" si nécessaire (chercher dans la même section)
          if (isInstrumental) {
            try {
              const instrumentalBtn = page.locator('button:has-text("Instrumental"), button[aria-label*="instrumental"]').last();
              if (await instrumentalBtn.isVisible({ timeout: 2000 })) {
                console.log("  → Activation mode Instrumental...");
                await instrumentalBtn.click();
                await sleep(500);
                console.log("  ✓ Mode instrumental activé");
              }
            } catch (e) {
              console.log("  ⚠ Checkbox Instrumental non accessible");
            }
          }
          
        } else {
          throw new Error("Song Description field not visible");
        }
        
      } catch (error) {
        console.log(`  ❌ Erreur remplissage: ${error.message}`);
        console.log("  → Abandon de cette track");
        continue; // Passer à la track suivante
      }
        try {
          // Activer le mode Custom
          const customButton = page.locator('button:has-text("Custom"), [role="tab"]:has-text("Custom")').first();
          if (await customButton.isVisible({ timeout: 2000 })) {
            console.log("  → Activation du mode Custom...");
            await customButton.click();
            await sleep(1500);
          }
        } catch (e) {
          console.log("  ⚠ Bouton Custom non trouvé");
        }

        // Remplir le champ "Styles"
        try {
          // Chercher le champ Styles (peut être dans une section collapsée)
          const stylesSection = page.locator('div:has-text("Styles")').first();
          if (await stylesSection.isVisible({ timeout: 1000 })) {
            // Cliquer pour déplier si nécessaire
            const expandButton = stylesSection.locator('button[role="button"][aria-expanded]').first();
            if (await expandButton.count() > 0) {
              const isExpanded = await expandButton.getAttribute('aria-expanded');
              if (isExpanded === 'false') {
                console.log("  → Dépliage de la section Styles...");
                await expandButton.click();
                await sleep(500);
              }
            }
          }

          const styleInput = page.locator('textarea[placeholder*="électro"], textarea[maxlength="1000"]').first();
          if (await styleInput.isVisible({ timeout: 2000 })) {
            console.log("  → Remplissage du style...");
            await styleInput.click();
            await styleInput.fill(style);
          } else {
            console.log("  ⚠ Champ Style non visible");
          }
        } catch (e) {
          console.log("  ⚠ Erreur lors du remplissage du style:", e.message.split('\n')[0]);
        }

        // Remplir les Lyrics si non-instrumental
        if (!isInstrumental) {
          try {
            const lyricsSection = page.locator('div:has-text("Lyrics")').first();
            if (await lyricsSection.isVisible({ timeout: 1000 })) {
              const expandButton = lyricsSection.locator('button[role="button"][aria-expanded]').first();
              if (await expandButton.count() > 0) {
                const isExpanded = await expandButton.getAttribute('aria-expanded');
                if (isExpanded === 'false') {
                  console.log("  → Dépliage de la section Lyrics...");
                  await expandButton.click();
                  await sleep(500);
                }
              }
            }

            const lyricsTextarea = page.locator('textarea[data-testid="lyrics-textarea"], textarea[placeholder*="Write some lyrics"]').first();
            if (await lyricsTextarea.isVisible({ timeout: 2000 })) {
              console.log("  → Remplissage des lyrics...");
              await lyricsTextarea.click();
              await lyricsTextarea.fill(lyrics);
            }
          } catch (e) {
            console.log("  ⚠ Erreur lors du remplissage des lyrics:", e.message.split('\n')[0]);
          }
        } else {
          console.log("  → Mode instrumental, pas de lyrics");
        }
      }

      // Remplir le titre (présent dans tous les modes)
      try {
        const titleInput = page.locator('input[placeholder*="Song Title"], input[placeholder*="Title"]').first();
        if (await titleInput.isVisible({ timeout: 2000 })) {
          console.log("  → Remplissage du titre...");
          await titleInput.click();
          await titleInput.fill(title);
        }
      } catch (e) {
        console.log("  ⚠ Champ Titre non visible");
      }

      // ─── Remplir les options avancées (si mode Custom) ──────────────────────

      if (!descriptionFilled) {
        // Déplier la section "More Options" si elle existe
        try {
          const moreOptionsSection = page.locator('div:has-text("More Options")').first();
          if (await moreOptionsSection.isVisible({ timeout: 1000 })) {
            const expandButton = moreOptionsSection.locator('button[role="button"][aria-expanded]').first();
            if (await expandButton.count() > 0) {
              const isExpanded = await expandButton.getAttribute('aria-expanded');
              if (isExpanded === 'false') {
                console.log("  → Dépliage de 'More Options'...");
                await expandButton.click();
                await sleep(500);
              }
            }
          }
        } catch (e) {
          console.log("  ⚠ Section 'More Options' non trouvée");
        }

        // Exclude Styles
        if (excludeStyles) {
          try {
            const excludeInput = page.locator('input[placeholder*="Exclude"], textarea[placeholder*="Exclude"]').first();
            if (await excludeInput.isVisible({ timeout: 1500 })) {
              console.log("  → Remplissage Exclude Styles...");
              await excludeInput.click();
              await excludeInput.fill(excludeStyles);
            }
          } catch (e) {
            console.log("  ⚠ Champ Exclude Styles non visible");
          }
        }

        // Vocal Gender
        if (vocalGender) {
          try {
            const genderButton = page.locator(`button:has-text("${vocalGender === 'male' ? 'Male' : 'Female'}")`).first();
            if (await genderButton.isVisible({ timeout: 1500 })) {
              console.log(`  → Sélection Vocal Gender : ${vocalGender}`);
              await genderButton.click();
            }
          } catch (e) {
            console.log("  ⚠ Bouton Vocal Gender non visible");
          }
        }

        // Lyrics Mode
        try {
          const lyricsModeButton = page.locator(`button:has-text("${lyricsMode === 'manual' ? 'Manual' : 'Auto'}")`).first();
          if (await lyricsModeButton.isVisible({ timeout: 1500 })) {
            console.log(`  → Sélection Lyrics Mode : ${lyricsMode}`);
            await lyricsModeButton.click();
          }
        } catch (e) {
          console.log("  ⚠ Bouton Lyrics Mode non visible");
        }

        // Weirdness Slider
        try {
          const weirdnessSlider = page.locator('div[aria-label="Weirdness"]').first();
          if (await weirdnessSlider.isVisible({ timeout: 1500 })) {
            console.log(`  → Ajustement Weirdness à ${weirdness}%...`);
            const sliderBox = await weirdnessSlider.boundingBox();
            if (sliderBox) {
              const targetX = sliderBox.x + (sliderBox.width * weirdness / 100);
              const targetY = sliderBox.y + (sliderBox.height / 2);
              await page.mouse.click(targetX, targetY);
            }
          }
        } catch (e) {
          console.log("  ⚠ Slider Weirdness non accessible");
        }

        // Style Influence Slider
        try {
          const styleInfluenceSlider = page.locator('div[aria-label="Style Influence"]').first();
          if (await styleInfluenceSlider.isVisible({ timeout: 1500 })) {
            console.log(`  → Ajustement Style Influence à ${styleInfluence}%...`);
            const sliderBox = await styleInfluenceSlider.boundingBox();
            if (sliderBox) {
              const targetX = sliderBox.x + (sliderBox.width * styleInfluence / 100);
              const targetY = sliderBox.y + (sliderBox.height / 2);
              await page.mouse.click(targetX, targetY);
            }
          }
        } catch (e) {
          console.log("  ⚠ Slider Style Influence non accessible");
        }
      }

      // ─── Clic sur Generate ──────────────────────────────────────────────────

      console.log("\n  ⏳ Attente de 3 secondes avant de générer...");
      await sleep(3000);

      try {
        // Chercher le bouton Generate/Create
        const generateButton = page.locator('button:has-text("Create"), button:has-text("Generate"), button:text-is("Create")').first();
        
        if (await generateButton.isVisible({ timeout: 5000 })) {
          const isDisabled = await generateButton.isDisabled();
          if (isDisabled) {
            console.log("  ⚠ Le bouton Generate est désactivé (champs manquants?)");
            
            // Prendre un screenshot pour debug
            try {
              const screenshotPath = `/tmp/suno-debug-${track.slug}.png`;
              await page.screenshot({ path: screenshotPath });
              console.log(`  💾 Screenshot sauvegardé : ${screenshotPath}`);
            } catch (e) {
              // Ignore screenshot errors
            }
          } else {
            console.log("  ✅ Clic sur Generate !");
            await generateButton.click();
            
            // Attendre un peu pour que Suno traite la requête
            await sleep(5000);
            
            // Si AUTO_DOWNLOAD est activé, attendre la génération et télécharger
            if (AUTO_DOWNLOAD) {
              const songUrl = await waitForGeneration(page, track.slug);
              
              if (songUrl) {
                await downloadMP3(page, track.slug, num);
              } else {
                console.log("  ⚠ Génération non terminée, téléchargement ignoré");
              }
            } else {
              // Vérifier si on est redirigé
              const currentUrl = page.url();
              if (currentUrl.includes("/song/")) {
                console.log("  ✓ Génération lancée ! Redirection vers la chanson...");
              } else {
                console.log("  ✓ Génération lancée !");
              }
            }
          }
        } else {
          console.log("  ❌ Bouton Generate introuvable");
        }
      } catch (e) {
        console.log("  ❌ Erreur lors du clic sur Generate:", e.message.split('\n')[0]);
      }

      // Retour à /create pour la prochaine track
      if (i < tracks.length - 1) {
        console.log("\n  🔄 Retour à /create pour la prochaine track...");
        await page.goto(`${SUNO_BASE}/create`, { waitUntil: "domcontentloaded" });
        await sleep(2000);
      }
    }

    console.log("\n\n✅ Toutes les tracks ont été soumises !\n");
    console.log("💡 Tu peux maintenant aller sur suno.com pour voir tes générations.\n");

  } catch (error) {
    console.error("\n❌ Erreur:", error.message);
  } finally {
    // Ne PAS fermer le navigateur (pour que tu puisses continuer à l'utiliser)
    console.log("🌐 Navigateur laissé ouvert pour ton usage.\n");
  }
}

// ─── Run ──────────────────────────────────────────────────────────────────────

main().catch((error) => {
  console.error("💥 Erreur fatale:", error);
  process.exit(1);
});
