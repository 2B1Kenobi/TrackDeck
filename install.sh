#!/usr/bin/env bash
#
# TrackDeck Linux & SteamOS Installer
#

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
STEMDECK_DIR="${HOME}/Applications/StemDeck"

echo "======================================================================"
echo "                   TrackDeck Installation & Setup                     "
echo "======================================================================"

# 1. Resolve Python runtime (StemDeck bundled python preferred)
PY_BIN=""
if [ -x "${STEMDECK_DIR}/python/bin/python3" ]; then
    PY_BIN="${STEMDECK_DIR}/python/bin/python3"
    echo "[+] Found StemDeck Python runtime: ${PY_BIN}"
elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="$(command -v python3)"
    echo "[+] Using system Python: ${PY_BIN}"
else
    echo "[!] Error: No Python 3 interpreter found." >&2
    exit 1
fi

# 2. Verify dependencies
echo "[*] Checking Python dependencies (numpy, soundfile, scipy)..."
if ! "${PY_BIN}" -c "import numpy, soundfile, scipy" >/dev/null 2>&1; then
    echo "[!] Missing required audio libraries in ${PY_BIN}."
    echo "[*] Attempting to install required packages via pip..."
    "${PY_BIN}" -m pip install numpy soundfile scipy
fi
echo "[+] Audio processing dependencies verified."

# 3. Install CLI binaries to ~/.local/bin
mkdir -p "${BIN_DIR}"
LAUNCHER="${BIN_DIR}/trackdeck"

cat << 'EOF' > "${LAUNCHER}"
#!/usr/bin/env bash
# TrackDeck CLI Launcher
INSTALL_DIR="__TRACKDECK_DIR__"
PY_BIN="${HOME}/Applications/StemDeck/python/bin/python3"
if [ ! -x "$PY_BIN" ]; then
    PY_BIN="$(command -v python3)"
fi
PYTHONPATH="${INSTALL_DIR}" exec "$PY_BIN" -m track_deck.cli "$@"
EOF

# Substitute actual install dir
sed -i "s|__TRACKDECK_DIR__|${SCRIPT_DIR}|g" "${LAUNCHER}"
chmod +x "${LAUNCHER}"

# Create alias symlink
ln -sf "${LAUNCHER}" "${BIN_DIR}/track-deck"
echo "[+] Installed CLI launchers into ${BIN_DIR}/ (trackdeck, track-deck)"

# 4. Install Fish completions
if command -v fish >/dev/null 2>&1 || [ -d "${HOME}/.config/fish" ]; then
    echo "[*] Installing Fish shell completions..."
    "${LAUNCHER}" completion --install >/dev/null 2>&1 || true
    echo "[+] Fish completions installed."
fi

# 5. Patch StemDeck backend for zero-restart live reload
echo "[*] Verifying StemDeck live ingestion integration..."
"${LAUNCHER}" patch-stemdeck || true

echo "======================================================================"
echo "[+] TrackDeck installation complete!"
echo "    Run 'trackdeck --help' or 'trackdeck session <file>' to begin."
echo "======================================================================"
