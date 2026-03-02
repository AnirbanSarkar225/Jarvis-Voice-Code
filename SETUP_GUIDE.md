# JARVIS Voice Assistant — Setup Guide

---

## What's in this folder

| File             | What it does                                      |
|------------------|---------------------------------------------------|
| jarvis.py        | The main assistant — all voice commands live here |
| setup.sh         | One-click installer for Linux / macOS             |
| requirements.txt | Python packages list                              |
| SETUP_GUIDE.md   | This file                                         |

---

## Step 1 — Install

### Linux / macOS (Automatic)

Open a terminal inside the JARVIS folder and run:

    chmod +x setup.sh
    ./setup.sh

This will automatically:
- Install all system packages (portaudio, espeak, xdotool, scrot, etc.)
- Create a Python virtual environment
- Install all Python dependencies
- Set up autostart on every boot
- Create a start_jarvis.sh launcher

### Windows

Open Command Prompt or PowerShell inside the JARVIS folder and run:

    python -m venv venv
    venv\Scripts\activate
    pip install SpeechRecognition pyttsx3 pyaudio

If pyaudio fails on Windows, install it manually:
- Go to https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
- Download the .whl file matching your Python version
- Run: pip install PyAudio-x.x.x-cpXX-cpXX-win_amd64.whl

---

## Step 2 — Run JARVIS

### Linux / macOS

    ./start_jarvis.sh

### Windows

    venv\Scripts\activate
    python jarvis.py

---

## Step 3 — Autostart on Windows

To make JARVIS start automatically on boot:

1. Press Win + R, type: shell:startup, press Enter
2. Create a new file called start_jarvis.bat in that folder
3. Add this content (update the path to match where you saved JARVIS):

    @echo off
    cd /d D:\JARVIS
    call venv\Scripts\activate
    pythonw jarvis.py

4. Save the file. JARVIS will now start silently on every login.

---

## How to Use

Say "Jarvis" to wake it up, then speak your command.

Examples:
  "Jarvis, open Chrome"
  "Jarvis, search YouTube for lo-fi music"
  "Jarvis, set volume to 60"
  "Jarvis, take a screenshot"

---

## Voice Commands

VOLUME
  "volume up"            — Increase volume
  "volume down"          — Decrease volume
  "mute" / "unmute"      — Toggle mute
  "set volume to 50"     — Set exact percentage

BRIGHTNESS
  "brightness up"        — Increase brightness
  "brightness down"      — Decrease brightness

OPEN APPS
  "open Chrome"          — Launch Chrome
  "open Firefox"         — Launch Firefox
  "open terminal"        — Launch terminal
  "open VS Code"         — Launch VS Code
  "open Spotify"         — Launch Spotify
  "open Discord"         — Launch Discord
  "open calculator"      — Launch calculator
  "open file manager"    — Launch file manager
  "open settings"        — Launch system settings
  "open task manager"    — Launch task manager
  "open notepad"         — Launch notepad / text editor

WEB & SEARCH
  "open google.com"             — Open any website
  "search how to boil eggs"     — Google search
  "search YouTube for lo-fi"    — YouTube search
  "youtube Rick Astley"         — YouTube search
  "wikipedia Albert Einstein"   — Wikipedia search

SYSTEM
  "take a screenshot"    — Saved to ~/Pictures
  "lock the screen"      — Locks your session
  "sleep"                — Suspends the laptop
  "shutdown"             — Powers off (5 second delay)
  "restart"              — Reboots (5 second delay)

NETWORK
  "turn on WiFi"         — Enable WiFi
  "turn off WiFi"        — Disable WiFi
  "my IP address"        — Reads out your IP

INFO
  "what's the time"      — Current time
  "what's the date"      — Today's date
  "battery level"        — Battery percentage

WINDOW
  "minimize"             — Minimize active window
  "close window"         — Close active window

---

## Manage Autostart (Linux)

    systemctl --user start jarvis      # Start now
    systemctl --user stop jarvis       # Stop
    systemctl --user status jarvis     # Check if running
    systemctl --user disable jarvis    # Disable autostart
    journalctl --user -u jarvis -f     # Live logs

Logs are saved to: ~/.jarvis/jarvis.log

---

## Customize

Open jarvis.py and edit the CONFIG block at the top:

    CONFIG = {
        "wake_word": "jarvis",    # Change to any word you like
        "voice_rate": 165,         # Speech speed (words per minute)
        "voice_volume": 0.95,      # Volume 0.0 to 1.0
        "energy_threshold": 300,   # Mic sensitivity (lower = more sensitive)
    }

---

## Troubleshooting

Mic not detected:
    python3 -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"

No audio output on Linux:
    pulseaudio --start

Brightness control needs permission (Linux):
    sudo usermod -aG video $USER
    (then log out and back in)

App not opening:
    Make sure the app is installed. JARVIS tries to run the name directly as a fallback.

PyAudio install fails on Windows:
    Use the pre-built wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

---

That's it. Say "Jarvis" and start talking.
