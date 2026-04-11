#!/bin/bash

# launch-chrome.sh
# Lance Chrome en mode debug pour Suno automation

echo "🌐 Lancement de Chrome en mode debug..."
echo ""
echo "💡 Une fois Chrome ouvert :"
echo "   1. Va sur https://suno.com"
echo "   2. Connecte-toi"
echo "   3. Va sur /create"
echo "   4. Lance 'npm run fill' dans un autre terminal"
echo ""

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug" \
  https://suno.com/create
