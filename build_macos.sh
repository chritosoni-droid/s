#!/bin/bash
# Crea FisioEvidenceBot.app per macOS con PyInstaller

set -e

echo "🔨 Build FisioEvidenceBot.app"
echo "================================"

# 1. Installa dipendenze
echo "📦 Installazione dipendenze..."
pip install -r requirements.txt
pip install pyinstaller

# 2. Pulizia build precedente
rm -rf build dist FisioEvidenceBot.spec

# 3. Crea .app con PyInstaller
echo "🏗️  Compilazione .app..."
pyinstaller \
    --windowed \
    --onedir \
    --name "FisioEvidenceBot" \
    --add-data "exercise_library.json:." \
    --hidden-import "anthropic" \
    --hidden-import "requests" \
    --hidden-import "pypdf" \
    --hidden-import "tkinter" \
    --hidden-import "tkinter.ttk" \
    --hidden-import "tkinter.filedialog" \
    --hidden-import "tkinter.scrolledtext" \
    --collect-all "anthropic" \
    --noconfirm \
    app.py

echo ""
echo "✅ Build completata!"
echo "   App: dist/FisioEvidenceBot.app"
echo ""
echo "📋 COME USARE L'APP:"
echo "   1. Apri Finder → vai in dist/"
echo "   2. Doppio click su FisioEvidenceBot.app"
echo "   3. Se macOS blocca: Finder → click destro → Apri → Apri"
echo ""
echo "⚙️  CONFIGURAZIONE API KEY (una volta sola):"
echo "   Metodo 1 — terminale prima di aprire l'app:"
echo "   export ANTHROPIC_API_KEY='sk-ant-...'"
echo ""
echo "   Metodo 2 — permanente (aggiunge al tuo .zshrc):"
echo "   echo 'export ANTHROPIC_API_KEY=\"sk-ant-...\"' >> ~/.zshrc"
echo "   source ~/.zshrc"
echo ""
echo "   Poi lancia: open dist/FisioEvidenceBot.app"
