#!/bin/bash
# ============================================================
#  JARVIS - One-click Install & Autostart Setup
# ============================================================
set -e

JARVIS_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$JARVIS_DIR/venv"
SCRIPT="$JARVIS_DIR/jarvis.py"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  JARVIS Voice Assistant - Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

OS=$(uname -s)
echo "Detected OS: $OS"

if [[ "$OS" == "Linux" ]]; then
    echo "[*] Installing Linux system packages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        portaudio19-dev \
        python3-pyaudio \
        espeak espeak-ng \
        libespeak-dev \
        scrot \
        xdotool \
        xclip \
        ffmpeg \
        flac \
        pulseaudio \
        network-manager 2>/dev/null || true

elif [[ "$OS" == "Darwin" ]]; then
    echo "[*] Installing macOS packages via Homebrew..."
    brew install portaudio espeak 2>/dev/null || true
fi

echo "[*] Creating Python virtual environment..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"

echo "[*] Installing Python dependencies..."
pip install --upgrade pip -q
pip install SpeechRecognition pyttsx3 pyaudio -q
pip install pocketsphinx 2>/dev/null || echo "  (pocketsphinx optional - skipped)"

echo "[*] Dependencies installed!"

chmod +x "$SCRIPT"

LAUNCHER="$JARVIS_DIR/start_jarvis.sh"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
source "$VENV/bin/activate"
exec python3 "$SCRIPT" "\$@"
EOF
chmod +x "$LAUNCHER"
echo "[*] Launcher created: $LAUNCHER"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Autostart Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$OS" == "Linux" ]]; then
    SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"

    cat > "$SERVICE_DIR/jarvis.service" <<EOF
[Unit]
Description=JARVIS Voice Assistant
After=graphical-session.target pulseaudio.service
Wants=pulseaudio.service

[Service]
Type=simple
ExecStart=$LAUNCHER
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus
StandardOutput=append:$HOME/.jarvis/jarvis.log
StandardError=append:$HOME/.jarvis/jarvis.log

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable jarvis.service
    echo "[✓] Systemd service enabled"

    mkdir -p "$HOME/.config/autostart"
    cat > "$HOME/.config/autostart/jarvis.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=JARVIS Voice Assistant
Exec=$LAUNCHER
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
    echo "[✓] XDG autostart entry created"

elif [[ "$OS" == "Darwin" ]]; then
    PLIST="$HOME/Library/LaunchAgents/com.jarvis.assistant.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.jarvis.assistant</string>
    <key>ProgramArguments</key>
    <array><string>$LAUNCHER</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$HOME/.jarvis/jarvis.log</string>
    <key>StandardErrorPath</key><string>$HOME/.jarvis/jarvis.log</string>
</dict>
</plist>
EOF
    launchctl load "$PLIST"
    echo "[✓] macOS LaunchAgent installed"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  JARVIS is installed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Run:       ./start_jarvis.sh"
echo "  Wake word: 'Jarvis'"
echo "  Example:   'Jarvis, open Chrome'"
echo "  Logs:      ~/.jarvis/jarvis.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
