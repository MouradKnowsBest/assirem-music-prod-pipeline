#!/usr/bin/env node
/**
 * debug-suno.js
 * 
 * Script de debug pour comprendre l'interface Suno
 */

const playwright = require("playwright");

const DEBUG_PORT = 9222;

async function main() {
  console.log("\n🔍 Suno Debug Tool\n");

  // Se connecter au Chrome ouvert
  console.log(`🔌 Connexion au Chrome sur le port ${DEBUG_PORT}...`);
  
  let browser;
  try {
    browser = await playwright.chromium.connectOverCDP(`http://localhost:${DEBUG_PORT}`);
  } catch (error) {
    console.error("\n❌ Impossible de se connecter au Chrome.");
    console.error("Lance Chrome avec: ./launch-chrome.sh\n");
    process.exit(1);
  }

  const context = browser.contexts()[0];
  const page = context.pages()[0] || await context.newPage();

  console.log(`✓ Connecté à: ${page.url()}\n`);

  // Analyser l'interface
  console.log("📊 Analyse de l'interface Suno...\n");

  // 1. Chercher tous les textarea
  const textareas = await page.locator('textarea').all();
  console.log(`🔤 ${textareas.length} textarea(s) trouvé(s):`);
  for (let i = 0; i < textareas.length; i++) {
    const ta = textareas[i];
    const placeholder = await ta.getAttribute('placeholder').catch(() => 'N/A');
    const maxlength = await ta.getAttribute('maxlength').catch(() => 'N/A');
    const isVisible = await ta.isVisible().catch(() => false);
    const testId = await ta.getAttribute('data-testid').catch(() => 'N/A');
    
    console.log(`  ${i + 1}. placeholder="${placeholder}" maxlength="${maxlength}" visible=${isVisible} testid="${testId}"`);
  }

  // 2. Chercher tous les input type=text
  console.log(`\n📝 Input fields:`);
  const inputs = await page.locator('input[type="text"], input:not([type])').all();
  for (let i = 0; i < inputs.length; i++) {
    const inp = inputs[i];
    const placeholder = await inp.getAttribute('placeholder').catch(() => 'N/A');
    const name = await inp.getAttribute('name').catch(() => 'N/A');
    const isVisible = await inp.isVisible().catch(() => false);
    
    console.log(`  ${i + 1}. placeholder="${placeholder}" name="${name}" visible=${isVisible}`);
  }

  // 3. Chercher les boutons importants
  console.log(`\n🔘 Boutons principaux:`);
  const buttons = await page.locator('button:has-text("Create"), button:has-text("Generate"), button:has-text("Custom"), button:has-text("Instrumental")').all();
  for (let i = 0; i < buttons.length; i++) {
    const btn = buttons[i];
    const text = await btn.innerText().catch(() => 'N/A');
    const isVisible = await btn.isVisible().catch(() => false);
    const isDisabled = await btn.isDisabled().catch(() => false);
    
    console.log(`  ${i + 1}. "${text}" visible=${isVisible} disabled=${isDisabled}`);
  }

  // 4. Chercher les sections (Lyrics, Styles, etc.)
  console.log(`\n📂 Sections détectées:`);
  const sections = await page.locator('div:has-text("Lyrics"), div:has-text("Styles"), div:has-text("Song Description"), div:has-text("Advanced Options")').all();
  for (let i = 0; i < sections.length; i++) {
    const section = sections[i];
    const text = await section.innerText().catch(() => '');
    const heading = text.split('\n')[0]; // Première ligne
    const isVisible = await section.isVisible().catch(() => false);
    
    console.log(`  ${i + 1}. "${heading}" visible=${isVisible}`);
  }

  console.log(`\n✅ Analyse terminée\n`);
  console.log(`💡 Conseil: Regarde les éléments 'visible=true' pour savoir quoi cibler\n`);
}

main().catch((error) => {
  console.error("💥 Erreur:", error.message);
  process.exit(1);
});
