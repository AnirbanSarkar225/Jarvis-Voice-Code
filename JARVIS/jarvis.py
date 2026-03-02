"""
JARVIS - Local Voice Assistant
Full laptop control via voice commands
"""
import os
import sys
import time
import subprocess
import threading
import re
import webbrowser
import platform
import queue
from datetime import datetime
import speech_recognition as sr
import pyttsx3

CONFIG = {
    "wake_word": "jarvis",
    "voice_rate": 160,
    "voice_volume": 1.0,
    "timeout": 5,
    "phrase_time": 7,
    "energy_threshold": 500,
    "pause_threshold": 0.6,
    "min_confidence_length": 2,
    "log_file": os.path.expanduser("~/.jarvis/jarvis.log"),
}

OS = platform.system().lower()
os.makedirs(os.path.expanduser("~/.jarvis"), exist_ok=True)

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(CONFIG["log_file"], "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Speaker in its own thread — never blocks mic ──
class Speaker:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _init_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", CONFIG["voice_rate"])
        engine.setProperty("volume", CONFIG["voice_volume"])
        voices = engine.getProperty("voices")
        for v in voices:
            if "english" in v.name.lower() or "zira" in v.name.lower() or "david" in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        return engine

    def _worker(self):
        engine = self._init_engine()
        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                log(f"JARVIS: {text}")
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                log(f"TTS error: {e}", "ERROR")
                try:
                    engine = self._init_engine()
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    def say(self, text):
        self._queue.put(text)

    def wait(self):
        # Wait max 15s so it can never block forever
        try:
            self._thread.join(0)  # non-blocking check
            self._queue.join()
        except Exception:
            pass

speaker = Speaker()

# ── Recognizer — fixed settings, no dynamic threshold ──
recognizer = sr.Recognizer()
recognizer.energy_threshold = CONFIG["energy_threshold"]
recognizer.dynamic_energy_threshold = False   # FIXED: dynamic threshold causes lag
recognizer.pause_threshold = CONFIG["pause_threshold"]
recognizer.non_speaking_duration = 0.3

HALLUCINATION_PHRASES = {
    "", "thank you", "thanks", "thanks for watching", "thank you for watching",
    "you", "the", "a", "oh", "um", "uh", "hmm", "bye", "goodbye",
    "subscribe", "please subscribe", "like and subscribe",
    "www.youtube.com", "copyright", "music", ".", "..", "...",
    "foreign", "[music]", "subtitles", "captions",
    "thank you for watching this video",
}

def is_hallucination(text: str) -> bool:
    t = text.strip().lower()
    if not t or len(t) < CONFIG["min_confidence_length"]:
        return True
    if t in HALLUCINATION_PHRASES:
        return True
    if len(set(t.replace(" ", ""))) <= 2 and len(t) > 4:
        return True
    return False

# Shared microphone instance to avoid re-opening it every loop
_mic = sr.Microphone()

def listen_once(timeout=5, phrase_time=7):
    """Listen for one phrase. Returns text or None. Never hangs."""
    try:
        with _mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.1)  # FIXED: was 0.3, too slow
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time)
            except sr.WaitTimeoutError:
                return None
    except Exception as e:
        log(f"Mic error: {e}", "ERROR")
        return None

    # Run API call in thread with hard 4s timeout to prevent hanging
    result = [None]
    done = threading.Event()

    def recognize():
        try:
            text = recognizer.recognize_google(audio, language="en-IN").lower().strip()
            result[0] = text
        except sr.UnknownValueError:
            result[0] = None
        except Exception as e:
            log(f"Recognition error: {e}", "ERROR")
            result[0] = None
        finally:
            done.set()

    t = threading.Thread(target=recognize, daemon=True)
    t.start()
    done.wait(timeout=4)  # FIXED: hard 4s cap, was 6s

    text = result[0]
    if text and is_hallucination(text):
        log(f"Filtered: '{text}'", "WARN")
        return None
    if text:
        log(f"Heard: {text}")
    return text

def listen_for_command():
    """Try twice to get a valid command."""
    for attempt in range(2):
        cmd = listen_once(timeout=CONFIG["timeout"], phrase_time=CONFIG["phrase_time"])
        if cmd:
            return cmd
        if attempt == 0:
            speaker.say("Say again.")
            speaker.wait()
    return None

# ── System helpers ──
def run(cmd, shell=False):
    try:
        flags = subprocess.CREATE_NO_WINDOW if OS == "windows" else 0
        subprocess.Popen(cmd if shell else cmd.split(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         shell=shell, creationflags=flags)
        return True
    except Exception as e:
        log(f"Run error: {e}", "ERROR")
        return False

def run_out(cmd, shell=False):
    try:
        flags = subprocess.CREATE_NO_WINDOW if OS == "windows" else 0
        return subprocess.check_output(cmd if shell else cmd.split(),
                                       stderr=subprocess.DEVNULL, shell=shell,
                                       text=True, timeout=5, creationflags=flags).strip()
    except Exception:
        return ""

# ── Command handlers ──
def volume_up():
    if OS == "windows":
        run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]175)", shell=True)
    elif OS == "linux":
        run("amixer -D pulse sset Master 10%+", shell=True)
    speaker.say("Volume increased.")

def volume_down():
    if OS == "windows":
        run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]174)", shell=True)
    elif OS == "linux":
        run("amixer -D pulse sset Master 10%-", shell=True)
    speaker.say("Volume decreased.")

def volume_mute():
    if OS == "windows":
        run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]173)", shell=True)
    elif OS == "linux":
        run("amixer -D pulse sset Master toggle", shell=True)
    speaker.say("Volume toggled.")

def set_volume(percent):
    percent = max(0, min(100, percent))
    if OS == "linux":
        run(f"amixer -D pulse sset Master {percent}%", shell=True)
    elif OS == "windows":
        run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]173)", shell=True)
        time.sleep(0.1)
        run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]173)", shell=True)
        for _ in range(percent // 2):
            run("powershell -c (New-Object -COM WScript.Shell).SendKeys([char]175)", shell=True)
            time.sleep(0.02)
    speaker.say(f"Volume set to {percent} percent.")

def brightness_up():
    if OS == "windows":
        run("powershell -c (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,[math]::Min(100,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness+10))", shell=True)
    speaker.say("Brightness increased.")

def brightness_down():
    if OS == "windows":
        run("powershell -c (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,[math]::Max(0,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness-10))", shell=True)
    speaker.say("Brightness decreased.")

APP_MAP = {
    "terminal":      {"windows": "start cmd",                    "linux": "gnome-terminal",         "darwin": "open -a Terminal"},
    "file manager":  {"windows": "start explorer",               "linux": "nautilus",                "darwin": "open ~"},
    "chrome":        {"windows": "start chrome",                  "linux": "google-chrome",           "darwin": "open -a 'Google Chrome'"},
    "firefox":       {"windows": "start firefox",                 "linux": "firefox",                 "darwin": "open -a Firefox"},
    "brave":         {"windows": "start brave",                   "linux": "brave-browser",           "darwin": "open -a Brave"},
    "edge":          {"windows": "start msedge",                  "linux": "microsoft-edge",          "darwin": "open -a 'Microsoft Edge'"},
    "vscode":        {"windows": "start code",                    "linux": "code",                    "darwin": "open -a 'Visual Studio Code'"},
    "vs code":       {"windows": "start code",                    "linux": "code",                    "darwin": "open -a 'Visual Studio Code'"},
    "visual studio": {"windows": "start code",                    "linux": "code",                    "darwin": "open -a 'Visual Studio Code'"},
    "notepad":       {"windows": "start notepad",                 "linux": "gedit",                   "darwin": "open -a TextEdit"},
    "calculator":    {"windows": "start calc",                    "linux": "gnome-calculator",        "darwin": "open -a Calculator"},
    "settings":      {"windows": "start ms-settings:",           "linux": "gnome-control-center",    "darwin": "open -a 'System Preferences'"},
    "discord":       {"windows": "start discord",                 "linux": "discord",                 "darwin": "open -a Discord"},
    "spotify":       {"windows": "start spotify",                 "linux": "spotify",                 "darwin": "open -a Spotify"},
    "vlc":           {"windows": "start vlc",                     "linux": "vlc",                     "darwin": "open -a VLC"},
    "zoom":          {"windows": "start zoom",                    "linux": "zoom",                    "darwin": "open -a zoom.us"},
    "slack":         {"windows": "start slack",                   "linux": "slack",                   "darwin": "open -a Slack"},
    "task manager":  {"windows": "start taskmgr",                 "linux": "gnome-system-monitor",    "darwin": "open -a 'Activity Monitor'"},
    "paint":         {"windows": "start mspaint",                 "linux": "gimp",                    "darwin": "open -a Preview"},
    "word":          {"windows": "start winword",                 "linux": "libreoffice --writer",    "darwin": "open -a 'Microsoft Word'"},
    "excel":         {"windows": "start excel",                   "linux": "libreoffice --calc",      "darwin": "open -a 'Microsoft Excel'"},
    "whatsapp":      {"windows": "start whatsapp",                "linux": "whatsapp",                "darwin": "open -a WhatsApp"},
    "telegram":      {"windows": "start telegram",                "linux": "telegram-desktop",        "darwin": "open -a Telegram"},
    "steam":         {"windows": "start steam",                   "linux": "steam",                   "darwin": "open -a Steam"},
    "camera":        {"windows": "start microsoft.windows.camera:","linux": "cheese",                 "darwin": "open -a Photo Booth"},
}

def open_app(name):
    name = name.lower().strip()
    for filler in ["please", "can you", "could you", "the", " an ", " a "]:
        name = name.replace(filler, "").strip()
    for key, platforms in APP_MAP.items():
        if key in name:
            run(platforms.get(OS, ""), shell=True)
            speaker.say(f"Opening {key}.")
            return
    run(f"start {name}" if OS == "windows" else name, shell=True)
    speaker.say(f"Trying to open {name}.")

SEARCH_ENGINES = {
    "google":    "https://www.google.com/search?q=",
    "youtube":   "https://www.youtube.com/results?search_query=",
    "wikipedia": "https://en.wikipedia.org/wiki/",
    "github":    "https://github.com/search?q=",
    "maps":      "https://www.google.com/maps/search/",
}

def open_website(url):
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    speaker.say(f"Opening {url}.")

def search_web(query, engine="google"):
    query = query.strip()
    if not query:
        speaker.say("What should I search for?")
        return
    webbrowser.open(SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"]) + query.replace(" ", "+"))
    speaker.say(f"Searching {engine} for {query}.")

def take_screenshot():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.expanduser(f"~/Pictures/screenshot_{ts}.png")
    os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
    if OS == "windows":
        script = f'Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $b=[System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g=[System.Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$b.Size); $b.Save("{path}")'
        run(f'powershell -c "{script}"', shell=True)
    elif OS == "linux":
        run(f"scrot {path}", shell=True)
    speaker.say("Screenshot saved.")

def lock_screen():
    if OS == "windows":
        run("rundll32.exe user32.dll,LockWorkStation", shell=True)
    elif OS == "linux":
        run("loginctl lock-session", shell=True)
    speaker.say("Screen locked.")

def sleep_system():
    speaker.say("Going to sleep.")
    speaker.wait()
    time.sleep(1)
    if OS == "windows":
        run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
    elif OS == "linux":
        run("systemctl suspend", shell=True)

def shutdown():
    speaker.say("Shutting down in 5 seconds.")
    speaker.wait()
    time.sleep(5)
    run("shutdown /s /t 0" if OS == "windows" else "systemctl poweroff", shell=True)

def restart():
    speaker.say("Restarting in 5 seconds.")
    speaker.wait()
    time.sleep(5)
    run("shutdown /r /t 0" if OS == "windows" else "systemctl reboot", shell=True)

def tell_time():
    speaker.say(f"It is {datetime.now().strftime('%I:%M %p')}.")

def tell_date():
    speaker.say(f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.")

def tell_battery():
    if OS == "windows":
        out = run_out("WMIC PATH Win32_Battery Get EstimatedChargeRemaining", shell=True)
        pct = re.search(r"(\d+)", out)
        if pct:
            speaker.say(f"Battery is at {pct.group(1)} percent.")
            return
    speaker.say("Could not read battery level.")

def tell_ip():
    if OS == "windows":
        out = run_out("powershell -c (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'}).IPAddress", shell=True)
    else:
        out = run_out("hostname -I", shell=True).split()[0] if run_out("hostname -I", shell=True) else ""
    speaker.say(f"Your IP is {out}." if out else "Could not find IP.")

def wifi_on():
    run('netsh interface set interface "Wi-Fi" enable' if OS == "windows" else "nmcli radio wifi on", shell=True)
    speaker.say("Wi-Fi turned on.")

def wifi_off():
    run('netsh interface set interface "Wi-Fi" disable' if OS == "windows" else "nmcli radio wifi off", shell=True)
    speaker.say("Wi-Fi turned off.")

def minimize_window():
    run("powershell -c (New-Object -COM WScript.Shell).SendKeys('%{F9}')" if OS == "windows" else "xdotool getactivewindow windowminimize", shell=True)
    speaker.say("Minimized.")

def close_window():
    run("powershell -c (New-Object -COM WScript.Shell).SendKeys('%{F4}')" if OS == "windows" else "xdotool getactivewindow windowclose", shell=True)
    speaker.say("Closed.")

def tell_joke():
    import random
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "Why did the computer go to the doctor? Because it had a virus.",
        "I would tell you a joke about UDP, but you might not get it.",
        "There are 10 types of people. Those who understand binary, and those who don't.",
    ]
    speaker.say(random.choice(jokes))

# ── Command Router ──
def route(text):
    t = text.lower().strip()
    t = re.sub(r"^jarvis[,\.\s]*", "", t).strip()

    if not t:
        speaker.say("Yes? How can I help?")
        return

    log(f"Routing: {t}")

    if re.search(r"\bvolume\b.*(up|increase|louder|raise|higher)", t) or t == "louder":
        m = re.search(r"(\d+)\s*percent", t)
        set_volume(int(m.group(1))) if m else volume_up()
    elif re.search(r"\bvolume\b.*(down|decrease|lower|quiet|reduce)", t) or t == "quieter":
        m = re.search(r"(\d+)\s*percent", t)
        set_volume(int(m.group(1))) if m else volume_down()
    elif re.search(r"\b(mute|unmute|silence)\b", t):
        volume_mute()
    elif m := re.search(r"set\s+volume\s+to\s+(\d+)", t):
        set_volume(int(m.group(1)))
    elif m := re.search(r"volume\s+(\d+)", t):
        set_volume(int(m.group(1)))
    elif re.search(r"\bbrightness\b.*(up|increase|higher|raise|more)", t) or t == "brighter":
        brightness_up()
    elif re.search(r"\bbrightness\b.*(down|decrease|lower|dim|less|reduce)", t) or t == "dimmer":
        brightness_down()
    elif re.search(r"(screenshot|capture\s+screen)", t):
        take_screenshot()
    elif re.search(r"\block\b", t):
        lock_screen()
    elif re.search(r"\b(sleep|suspend|hibernate)\b", t):
        sleep_system()
    elif re.search(r"\b(shutdown|shut\s+down|power\s+off)\b", t):
        shutdown()
    elif re.search(r"\b(restart|reboot)\b", t):
        restart()
    elif re.search(r"(turn\s+on|enable)\s+wi.?fi", t):
        wifi_on()
    elif re.search(r"(turn\s+off|disable)\s+wi.?fi", t):
        wifi_off()
    elif re.search(r"\b(time|clock)\b", t):
        tell_time()
    elif re.search(r"\b(date|day|today)\b", t):
        tell_date()
    elif re.search(r"\b(battery|charge)\b", t):
        tell_battery()
    elif re.search(r"\b(ip|ip\s+address)\b", t):
        tell_ip()
    elif re.search(r"\b(joke|funny)\b", t):
        tell_joke()
    elif re.search(r"\bminimize\b", t):
        minimize_window()
    elif re.search(r"\bclose\b.*(window|this|app)", t):
        close_window()
    elif m := re.search(r"(search|look\s+up|find|google)\s+(.+?)(\s+on\s+(youtube|wikipedia|github|google|maps))?$", t):
        search_web(m.group(2).strip(), m.group(4) or "google")
    elif m := re.search(r"\byoutube\b\s+(.+)", t):
        search_web(m.group(1), "youtube")
    elif m := re.search(r"\bplay\b\s+(.+)\s+on\s+youtube", t):
        search_web(m.group(1), "youtube")
    elif m := re.search(r"\bplay\b\s+(.+)", t):
        search_web(m.group(1), "youtube")
    elif m := re.search(r"\bwikipedia\b\s+(.+)", t):
        search_web(m.group(1), "wikipedia")
    elif m := re.search(r"(open|go\s+to|visit)\s+(https?://\S+)", t):
        open_website(m.group(2))
    elif m := re.search(r"(open|go\s+to|visit)\s+([\w\-]+\.(com|org|net|io|in|edu|gov|co)[\w/]*)", t):
        open_website(m.group(2))
    elif m := re.search(r"(open|launch|start|run)\s+(.+)", t):
        open_app(m.group(2).strip())
    elif re.search(r"\b(help|what can you do|commands)\b", t):
        speaker.say("I can open apps, search the web, control volume and brightness, take screenshots, check battery, lock your screen, and more. Just ask!")
    elif re.search(r"^(hello|hi|hey)$", t):
        hour = datetime.now().hour
        g = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        speaker.say(f"{g}! How can I help?")
    elif re.search(r"\bhow\s+are\s+you\b", t):
        speaker.say("Doing great and ready to help!")
    elif re.search(r"\b(stop|exit|quit|bye|goodbye)\b", t):
        speaker.say("Goodbye!")
        speaker.wait()
        sys.exit(0)
    else:
        speaker.say("I didn't get that. Say help to hear what I can do.")
        log(f"Unrecognized: {t}", "WARN")

# ── Main Loop ──
def main():
    log("JARVIS starting up...")
    time.sleep(2)
    speaker.say("Jarvis is ready. Say Jarvis to wake me up.")
    speaker.wait()

    wake = CONFIG["wake_word"]

    while True:
        try:
            heard = listen_once(timeout=None, phrase_time=4)

            if not heard:
                continue

            if wake not in heard:
                continue

            rest = re.sub(r"^[,\.\s]*jarvis[,\.\s]*", "", heard).strip()

            if rest and not is_hallucination(rest):
                speaker.say("Got it.")
                route(rest)
            else:
                speaker.say("Yes?")
                speaker.wait()
                cmd = listen_for_command()
                if cmd:
                    speaker.say("Got it.")
                    route(cmd)
                else:
                    speaker.say("Didn't catch that, try again.")

        except KeyboardInterrupt:
            speaker.say("Jarvis shutting down. Goodbye!")
            speaker.wait()
            break
        except Exception as e:
            log(f"Main loop error: {e}", "ERROR")
            time.sleep(1)

if __name__ == "__main__":
    main()
