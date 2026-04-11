#!/usr/bin/env node

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const CONFIG_PATH = path.join(__dirname, "../../config.json");
const CDP_PORT = 9222;
const AUTO_DOWNLOAD = process.argv.includes("--download");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  console.log("\n🎵 Suno Fill Automation (Attach Mode v2)\n");

  // 1. Lire config.json
  const configData = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
  const tracks = configData.tracks || [];
  console.log(`✓ ${tracks.length} track(s) trouvée(s) dans config.json\n`);

  // 2. Connexion au Chrome en debug mode
  console.log(`🔌 Connexion au Chrome sur le port ${CDP_PORT}...`);

  let browser, page;
  try {
    browser = await chromium.connectOverCDP(`http://localhost:${CDP_PORT}`);
    const contexts = browser.contexts();

    if (contexts.length === 0) {
      throw new Error(
        "Aucun contexte disponible. Assure-toi que Chrome est ouvert!",
      );
    }

    const context = contexts[0];
    const pages = context.pages();

    if (pages.length === 0) {
      throw new Error(
        "Aucun onglet ouvert. Ouvre suno.com/create dans Chrome!",
      );
    }

    page = pages[0];
    console.log(
      `✓ Utilisation d'un onglet existant (${pages.length} onglet(s) ouverts)`,
    );

    const currentUrl = page.url();
    if (!currentUrl.includes("suno.com")) {
      await page.goto("https://suno.com/create", {
        waitUntil: "domcontentloaded",
      });
      await sleep(3000);
      console.log("✓ Navigation vers Suno Create");
    } else {
      console.log("✓ Déjà sur Suno");
    }

    await sleep(2000);

    // 3. Boucle sur chaque track
    for (let i = 0; i < tracks.length; i++) {
      const track = tracks[i];
      const num = i + 1;

      console.log(`\n━━━ Track ${num}/${tracks.length} : ${track.slug} ━━━`);

      const title = track.suno_title || track.title || track.slug;
      const style = track.suno_style || "";
      const lyrics = track.suno_lyrics || "[Instrumental]";
      const isInstrumental = lyrics.trim().toLowerCase() === "[instrumental]";

      console.log(`📝 Titre  : ${title}`);
      console.log(`🎨 Style  : ${style.substring(0, 60)}...`);
      console.log(
        `📄 Lyrics : ${isInstrumental ? "[Instrumental]" : "Custom"}`,
      );

      try {
        // Étape 1: Essayer de détecter le mode actif et basculer si nécessaire
        console.log("  → Détection mode interface Suno...");

        // Chercher les onglets Simple/Advanced/Sounds
        const advancedTab = page
          .locator(
            'button:has-text("Advanced"), button.active:has-text("Advanced")',
          )
          .first();
        const simpleTab = page.locator('button:has-text("Simple")').first();

        let modeDetected = "unknown";

        // Vérifier quel mode est actif
        if ((await advancedTab.count()) > 0) {
          const isActive = await advancedTab.getAttribute("class");
          if (isActive && isActive.includes("active")) {
            modeDetected = "advanced";
            console.log("  ℹ️  Mode Advanced détecté");
          }
        }

        // Si on n'est pas en mode Advanced, essayer de remplir directement
        // Chercher n'importe quel textarea visible pour la description
        await sleep(1000);

        // Stratégie 1: Chercher un textarea vide et visible (le plus commun)
        const textareas = await page.locator("textarea").all();
        let targetTextarea = null;

        for (const textarea of textareas) {
          const isVisible = await textarea.isVisible();
          const placeholder = await textarea.getAttribute("placeholder");
          const value = await textarea.inputValue();

          console.log(
            `  🔍 Textarea trouvé: visible=${isVisible}, placeholder="${placeholder?.substring(0, 30)}..."`,
          );

          if (isVisible && !value && placeholder) {
            // Priorité aux textarea avec placeholder pertinent
            if (
              placeholder.toLowerCase().includes("song") ||
              placeholder.toLowerCase().includes("chanson") ||
              placeholder.toLowerCase().includes("describe")
            ) {
              targetTextarea = textarea;
              console.log(
                `  ✅ Textarea cible trouvé: "${placeholder.substring(0, 50)}..."`,
              );
              break;
            }
          }
        }

        // Si toujours pas trouvé, prendre le premier textarea visible et vide
        if (!targetTextarea) {
          for (const textarea of textareas) {
            const isVisible = await textarea.isVisible();
            const value = await textarea.inputValue();
            if (isVisible && !value) {
              targetTextarea = textarea;
              console.log(
                "  ℹ️  Utilisation du premier textarea vide disponible",
              );
              break;
            }
          }
        }

        if (!targetTextarea) {
          throw new Error("Aucun textarea utilisable trouvé sur la page");
        }

        console.log("  → Remplissage du champ...");

        const description = `${style}`;
        await targetTextarea.click();
        await sleep(300);
        await targetTextarea.fill(description);
        await sleep(1000);

        console.log("  ✓ Champ rempli");

        // Cocher "Instrumental" si nécessaire
        if (isInstrumental) {
          const instrumentalBtns = await page
            .locator(
              'button:has-text("Instrumental"), button[aria-label*="instrumental"]',
            )
            .all();
          for (const btn of instrumentalBtns) {
            if (await btn.isVisible()) {
              console.log("  → Activation Instrumental...");
              await btn.click();
              await sleep(500);
              console.log("  ✓ Instrumental activé");
              break;
            }
          }
        }

        // Attendre que le bouton Create soit activé
        console.log("\n  ⏳ Attente activation bouton Create...");

        const createBtn = page
          .locator(
            'button[aria-label="Create song"], button:has-text("Create")',
          )
          .first();

        // Attendre que le bouton ne soit plus disabled (max 15s)
        let attempts = 0;
        while (attempts < 30) {
          // 30 * 0.5s = 15s max
          const isDisabled = await createBtn.isDisabled();
          if (!isDisabled) {
            break;
          }
          await sleep(500);
          attempts++;
        }

        if (await createBtn.isDisabled()) {
          throw new Error("Bouton Create toujours désactivé après 15s");
        }

        console.log("  ✓ Bouton Create activé");
        await sleep(1000);

        await createBtn.click();
        console.log("  ✓ Bouton Create cliqué !\n");

        // Attendre que Suno traite la requête
        await sleep(5000);

        // Retour à /create pour la prochaine track
        if (i < tracks.length - 1) {
          console.log("  🔄 Retour à /create pour la prochaine track...\n");
          await page.goto("https://suno.com/create", {
            waitUntil: "domcontentloaded",
          });
          await sleep(3000);
        }
      } catch (error) {
        console.log(`  ❌ Erreur: ${error.message}`);

        // Screenshot pour debug
        try {
          const screenshotPath = `/tmp/suno-error-${track.slug}.png`;
          await page.screenshot({ path: screenshotPath, fullPage: true });
          console.log(`  💾 Screenshot: ${screenshotPath}`);
        } catch (e) {
          // Ignore screenshot errors
        }

        console.log("  → Passage à la track suivante...\n");

        // Retour à /create
        await page.goto("https://suno.com/create", {
          waitUntil: "domcontentloaded",
        });
        await sleep(3000);
      }
    }

    console.log("\n✅ Toutes les tracks ont été soumises !\n");
  } catch (error) {
    console.error("\n❌ Erreur:", error.message);
    console.error("\n💡 Vérif ces points:");
    console.error("  1. Chrome est lancé avec --remote-debugging-port=9222");
    console.error("  2. Tu es connecté sur suno.com");
    console.error("  3. Tu as un onglet ouvert sur /create\n");
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

main();
