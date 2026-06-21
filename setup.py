#!/usr/bin/env python3
"""
Alice Yandex Proxy — Setup & Readiness Checker v2
==================================================
Beautiful cross-platform setup with progress bars, spinners, and colors.

Usage:
    python setup.py          # check + install everything
    python setup.py --check  # check only, don't install
"""

import sys
import os
import platform
import subprocess
import shutil
import importlib
import time
import threading
import unicodedata
from pathlib import Path

# ─── Enable ANSI on Windows ────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"

if IS_WINDOWS:
    os.system("")  # Enable ANSI escape sequences in Windows Terminal
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# Force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─── Colors & Styles ───────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK   = "\033[5m"
    STRIKE  = "\033[9m"

    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # Bright foreground
    B_RED     = "\033[91m"
    B_GREEN   = "\033[92m"
    B_YELLOW  = "\033[93m"
    B_BLUE    = "\033[94m"
    B_MAGENTA = "\033[95m"
    B_CYAN    = "\033[96m"
    B_WHITE   = "\033[97m"

    # Background
    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"

    # Bright background
    BG_B_BLACK   = "\033[100m"
    BG_B_RED     = "\033[101m"
    BG_B_GREEN   = "\033[102m"
    BG_B_YELLOW  = "\033[103m"
    BG_B_BLUE    = "\033[104m"
    BG_B_MAGENTA = "\033[105m"
    BG_B_CYAN    = "\033[106m"


# ─── Unicode helpers ───────────────────────────────────────────────
def wide(text):
    """Convert ASCII text to Unicode WIDE (fullwidth) characters."""
    result = []
    for ch in text:
        code = ord(ch)
        if 0x21 <= code <= 0x7E:
            result.append(chr(code + 0xFEE0))
        elif code == 0x20:
            result.append("\u3000")  # ideographic space
        else:
            result.append(ch)
    return "".join(result)


def bold_unicode(text):
    """Convert ASCII text to Unicode MATHEMATICAL BOLD characters."""
    result = []
    for ch in text:
        code = ord(ch)
        if 0x41 <= code <= 0x5A:  # A-Z
            result.append(chr(code - 0x41 + 0x1D400))
        elif 0x61 <= code <= 0x7A:  # a-z
            result.append(chr(code - 0x61 + 0x1D41A))
        elif 0x30 <= code <= 0x39:  # 0-9
            result.append(chr(code - 0x30 + 0x1D7CE))
        else:
            result.append(ch)
    return "".join(result)


# ─── Terminal width ────────────────────────────────────────────────
def term_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def center(text, width=None):
    if width is None:
        width = term_width()
    # Strip ANSI for length calc
    import re
    clean = re.sub(r'\033\[[0-9;]*m', '', text)
    padding = max(0, (width - len(clean)) // 2)
    return " " * padding + text


# ─── Spinner animation ─────────────────────────────────────────────
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_ACTIVE = False
SPINNER_THREAD = None
SPINNER_MSG = ""


def _spinner_loop():
    global SPINNER_ACTIVE
    i = 0
    while SPINNER_ACTIVE:
        frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        print(f"\r  {C.B_CYAN}{frame}{C.RESET} {C.DIM}{SPINNER_MSG}{C.RESET}", end="", flush=True)
        i += 1
        time.sleep(0.08)
    print("\r" + " " * (len(SPINNER_MSG) + 10) + "\r", end="", flush=True)


def spinner_start(msg):
    global SPINNER_ACTIVE, SPINNER_THREAD, SPINNER_MSG
    SPINNER_MSG = msg
    SPINNER_ACTIVE = True
    SPINNER_THREAD = threading.Thread(target=_spinner_loop, daemon=True)
    SPINNER_THREAD.start()


def spinner_stop():
    global SPINNER_ACTIVE, SPINNER_THREAD
    SPINNER_ACTIVE = False
    if SPINNER_THREAD:
        SPINNER_THREAD.join(timeout=2)
        SPINNER_THREAD = None


# ─── Progress bar ──────────────────────────────────────────────────
def progress_bar(current, total, width=30, label=""):
    pct = current / total if total > 0 else 1
    filled = int(width * pct)
    empty = width - filled

    if pct >= 1.0:
        bar_color = C.B_GREEN
        fill_char = "█"
        empty_char = "░"
    elif pct >= 0.6:
        bar_color = C.B_CYAN
        fill_char = "█"
        empty_char = "░"
    elif pct >= 0.3:
        bar_color = C.B_YELLOW
        fill_char = "▓"
        empty_char = "░"
    else:
        bar_color = C.B_RED
        fill_char = "▒"
        empty_char = "░"

    bar = f"{bar_color}{fill_char * filled}{C.DIM}{empty_char * empty}{C.RESET}"
    pct_str = f"{pct*100:.0f}%"
    return f"  {bar} {C.BOLD}{pct_str}{C.RESET}  {C.DIM}{label}{C.RESET}"


# ─── Output helpers ────────────────────────────────────────────────
CHECKS = []
INSTALL_QUEUE = []
CHECK_RESULTS = {}


def ok(msg):
    print(f"  {C.B_GREEN}✓{C.RESET}  {msg}")

def fail(msg):
    print(f"  {C.B_RED}✗{C.RESET}  {msg}")

def warn(msg):
    print(f"  {C.B_YELLOW}⚠{C.RESET}  {msg}")

def info(msg):
    print(f"  {C.B_BLUE}→{C.RESET}  {msg}")

def skip(msg):
    print(f"  {C.DIM}○  {msg}{C.RESET}")


def section(num, title, icon=""):
    w = term_width()
    print()
    # Gradient-like header with box drawing
    print(f"  {C.B_CYAN}┌{'─' * (w - 6)}┐{C.RESET}")
    num_str = f" {num} "
    title_str = f" {icon}{title}" if icon else f" {title}"
    pad = w - 6 - len(num_str) - len(title_str)
    if pad < 0:
        pad = 1
    print(f"  {C.B_CYAN}│{C.RESET}{C.BG_B_CYAN}{C.BLACK}{C.BOLD}{num_str}{C.RESET}{C.BOLD}{C.B_WHITE}{title_str}{' ' * pad}{C.RESET}{C.B_CYAN}│{C.RESET}")
    print(f"  {C.B_CYAN}└{'─' * (w - 6)}┘{C.RESET}")


def run(cmd, capture=True, shell=True, timeout=120):
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=capture, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def get_python_cmd():
    for cmd in ["python3", "python", sys.executable]:
        success, out, _ = run(f"{cmd} --version")
        if success:
            return cmd
    return sys.executable


def get_pip_cmd(python_cmd):
    success, _, _ = run(f"{python_cmd} -m pip --version")
    if success:
        return f"{python_cmd} -m pip"
    for cmd in ["pip3", "pip"]:
        success, _, _ = run(f"{cmd} --version")
        if success:
            return cmd
    return None


# ─── CHECKS ────────────────────────────────────────────────────────

def check_python_version():
    section("1", "Python Version", "🐍")
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 10:
        ok(f"Python {C.BOLD}{version_str}{C.RESET}")
        return True
    fail(f"Python {version_str} — need 3.10+")
    INSTALL_QUEUE.append(("python", "Install Python 3.10+ from https://python.org"))
    return False


def check_pip():
    section("2", "pip Package Manager", "📦")
    python_cmd = get_python_cmd()
    pip_cmd = get_pip_cmd(python_cmd)
    if pip_cmd:
        success, out, _ = run(f"{pip_cmd} --version")
        if success:
            version_line = out.strip().split("\n")[0]
            ok(f"{version_line}")
            return True
    fail("pip not found")
    INSTALL_QUEUE.append(("pip", f"{python_cmd} -m ensurepip --upgrade"))
    return False


def check_pip_packages():
    section("3", "Python Packages", "📚")
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn[standard]",
        "playwright": "playwright",
        "httpx": "httpx",
        "pydantic": "pydantic",
    }

    all_ok = True
    missing = []

    for module_name, pip_name in required.items():
        try:
            mod = importlib.import_module(module_name)
            version = getattr(mod, "__version__", "?")
            ok(f"{C.BOLD}{module_name}{C.RESET}  {C.DIM}v{version}{C.RESET}")
        except ImportError:
            fail(f"{C.BOLD}{module_name}{C.RESET}  {C.DIM}not installed{C.RESET}")
            missing.append(pip_name)
            all_ok = False

    if missing:
        python_cmd = get_python_cmd()
        pip_cmd = get_pip_cmd(python_cmd)
        install_cmd = f"{pip_cmd} install {' '.join(missing)}"
        INSTALL_QUEUE.append(("packages", install_cmd))

    return all_ok


def check_chrome():
    section("4", "Chrome / Chromium Browser", "🌐")

    chrome_paths = []
    chrome_cmd = None

    if IS_WINDOWS:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif IS_LINUX:
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        chrome_cmd = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    elif IS_MACOS:
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]

    for p in chrome_paths:
        if os.path.exists(p):
            ok(f"Chrome found: {C.DIM}{p}{C.RESET}")
            return True

    if chrome_cmd:
        ok(f"Chrome in PATH: {C.DIM}{chrome_cmd}{C.RESET}")
        return True

    if IS_WINDOWS:
        success, out, _ = run("where chrome 2>nul")
        if success and out.strip():
            ok(f"Chrome in PATH: {out.strip().split(chr(10))[0]}")
            return True

    fail("Chrome/Chromium not found")

    if IS_LINUX:
        if shutil.which("apt"):
            INSTALL_QUEUE.append(("chrome", "wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list && sudo apt update && sudo apt install -y google-chrome-stable"))
        elif shutil.which("dnf"):
            INSTALL_QUEUE.append(("chrome", "sudo dnf install -y fedora-workstation-repositories && sudo dnf config-manager --set-enabled google-chrome && sudo dnf install -y google-chrome-stable"))
        elif shutil.which("pacman"):
            INSTALL_QUEUE.append(("chrome", "sudo pacman -S --noconfirm chromium"))
        else:
            INSTALL_QUEUE.append(("chrome", "Install Chrome from https://google.com/chrome"))
    elif IS_WINDOWS:
        INSTALL_QUEUE.append(("chrome", "winget install Google.Chrome"))
    elif IS_MACOS:
        INSTALL_QUEUE.append(("chrome", "brew install --cask google-chrome"))

    return False


def check_playwright_browsers():
    section("5", "Playwright Browsers", "🎭")

    try:
        import playwright
    except ImportError:
        skip("playwright package not installed — will be checked after install")
        return False

    browser_found = False

    if IS_WINDOWS:
        pw_dir = Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "ms-playwright"
    else:
        pw_dir = Path.home() / ".cache" / "ms-playwright"

    if pw_dir.exists():
        chromium_dirs = sorted(pw_dir.glob("chromium-*"))
        if chromium_dirs:
            ok(f"Playwright Chromium: {C.BOLD}{chromium_dirs[-1].name}{C.RESET}")
            browser_found = True

    if not browser_found:
        custom_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if custom_path and Path(custom_path).exists():
            chromium_dirs = sorted(Path(custom_path).glob("chromium-*"))
            if chromium_dirs:
                ok(f"Playwright Chromium (custom): {C.BOLD}{chromium_dirs[-1].name}{C.RESET}")
                browser_found = True

    if not browser_found:
        fail("Playwright Chromium browser not installed")
        INSTALL_QUEUE.append(("playwright_browsers", f"{get_python_cmd()} -m playwright install chromium"))
        return False

    return True


def check_port():
    section("6", "Port Availability", "🔌")
    port = int(os.environ.get("PORT", "8976"))

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
        sock.close()
        ok(f"Port {C.BOLD}{port}{C.RESET} is available")
        return True
    except OSError:
        warn(f"Port {C.BOLD}{port}{C.RESET} is already in use {C.DIM}(server may already be running){C.RESET}")
        info(f"Use a different port: {C.BOLD}PORT=9000 python server.py{C.RESET}")
        return True  # Not a blocker — server might already be running


def check_project_structure():
    section("7", "Project Structure", "📁")
    project_dir = Path(__file__).parent

    all_ok = True

    # Required files
    for f, desc in [("server.py", "Main server")]:
        path = project_dir / f
        if path.exists():
            size = path.stat().st_size
            ok(f"{C.BOLD}{f}{C.RESET}  {C.DIM}{desc} ({size:,} bytes){C.RESET}")
        else:
            fail(f"{C.BOLD}{f}{C.RESET}  {C.DIM}MISSING ({desc}){C.RESET}")
            all_ok = False

    # Optional files
    for f, desc in [(".gitignore", "Git rules"), ("README.md", "Documentation"), ("setup.py", "Setup checker")]:
        path = project_dir / f
        if path.exists():
            ok(f"{C.BOLD}{f}{C.RESET}  {C.DIM}{desc}{C.RESET}")
        else:
            skip(f"{f}  {desc}")

    # Directories
    for d in ["state", "cache", "media"]:
        dir_path = project_dir / d
        dir_path.mkdir(exist_ok=True)
        count = len(list(dir_path.glob("*"))) if dir_path.exists() else 0
        ok(f"{C.BOLD}{d}/{C.RESET}  {C.DIM}ready ({count} files){C.RESET}")

    return all_ok


def check_git():
    section("8", "Git (optional)", "🔧")
    success, out, _ = run("git --version")
    if success:
        ok(f"{out.strip()}")
        return True
    skip("git not found — version control unavailable")
    return True  # Not critical


# ─── INSTALLER ─────────────────────────────────────────────────────

def run_installs():
    if not INSTALL_QUEUE:
        return True

    w = term_width()
    print()
    print(f"  {C.BG_B_YELLOW}{C.BLACK}{C.BOLD}  INSTALLING MISSING COMPONENTS  {C.RESET}")
    print(f"  {C.B_YELLOW}{'─' * (w - 6)}{C.RESET}")
    print()

    all_success = True
    total = len(INSTALL_QUEUE)

    for idx, (name, cmd) in enumerate(INSTALL_QUEUE, 1):
        if name == "python":
            warn(f"Python 3.10+ required. {cmd}")
            warn("Please install Python manually, then re-run this script.")
            all_success = False
            continue

        # Show what we're installing
        print(f"  {C.B_CYAN}[{idx}/{total}]{C.RESET} {C.BOLD}{name}{C.RESET}")

        if len(cmd) > 60:
            # Truncate long commands for display
            display_cmd = cmd[:57] + "..."
        else:
            display_cmd = cmd
        print(f"  {C.DIM}$ {display_cmd}{C.RESET}")

        # Start spinner
        spinner_start(f"Installing {name}...")

        success, out, err = run(cmd, timeout=300)

        # Stop spinner
        spinner_stop()

        if success:
            ok(f"{C.B_GREEN}{name}{C.RESET} installed successfully")
        else:
            fail(f"{C.B_RED}{name}{C.RESET} installation failed")
            if err and len(err) > 10:
                # Show first line of error
                err_line = err.strip().split("\n")[0][:80]
                print(f"      {C.DIM}{err_line}{C.RESET}")
            all_success = False

        # Progress
        print(progress_bar(idx, total, label=f"{idx}/{total} done"))
        print()

    return all_success


# ─── BANNER ────────────────────────────────────────────────────────

def print_banner():
    w = term_width()

    # Clear screen (optional — comment out if too aggressive)
    # print("\033[2J\033[H", end="")

    print()

    # Top border
    border = "═" * (w - 4)
    print(f"  {C.B_CYAN}╔{border}╗{C.RESET}")

    # Logo line 1
    logo1 = f"{C.B_CYAN}{C.BOLD}   ████  Alice Yandex Proxy{C.RESET}"
    pad1 = w - 4 - 30
    print(f"  {C.B_CYAN}║{C.RESET}{logo1}{' ' * max(0, pad1)}{C.B_CYAN}║{C.RESET}")

    # Logo line 2
    subtitle = f"   {C.DIM}OpenAI-Compatible API for Yandex Alice{C.RESET}"
    pad2 = w - 4 - 42
    print(f"  {C.B_CYAN}║{C.RESET}{subtitle}{' ' * max(0, pad2)}{C.B_CYAN}║{C.RESET}")

    # Version + OS
    os_name = platform.system()
    os_icons = {"Windows": "🪟", "Linux": "🐧", "Darwin": "🍎"}
    os_icon = os_icons.get(os_name, "💻")
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ver_line = f"   {C.B_YELLOW}v5.1{C.RESET}  {C.DIM}│{C.RESET}  {os_icon} {os_name} {platform.release()}  {C.DIM}│{C.RESET}  🐍 Python {py_ver}  {C.DIM}│{C.RESET}  🏗 {platform.machine()}"
    # Approximate visible length (emoji count as ~2 chars)
    vis_len = 60
    pad3 = max(0, w - 4 - vis_len)
    print(f"  {C.B_CYAN}║{C.RESET}{ver_line}{' ' * pad3}{C.B_CYAN}║{C.RESET}")

    # Bottom border
    print(f"  {C.B_CYAN}╚{border}╝{C.RESET}")
    print()


# ─── SUMMARY ───────────────────────────────────────────────────────

def print_summary(results, install_success):
    w = term_width()
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print()
    print(f"  {C.B_CYAN}┌{'─' * (w - 6)}┐{C.RESET}")
    print(f"  {C.B_CYAN}│{C.RESET}  {C.BOLD}{C.B_WHITE}  SUMMARY{C.RESET}{' ' * (w - 17)}{C.B_CYAN}│{C.RESET}")
    print(f"  {C.B_CYAN}├{'─' * (w - 6)}┤{C.RESET}")

    # Individual results
    labels = {
        "python": ("🐍 Python", "Python 3.10+"),
        "pip": ("📦 pip", "Package manager"),
        "packages": ("📚 Packages", "fastapi, uvicorn, playwright..."),
        "chrome": ("🌐 Chrome", "Browser engine"),
        "playwright": ("🎭 Playwright", "Browser automation"),
        "port": ("🔌 Port", "Network availability"),
        "structure": ("📁 Structure", "Project files"),
        "git": ("🔧 Git", "Version control"),
    }

    for key, (icon_name, desc) in labels.items():
        status = results.get(key, False)
        if status:
            mark = f"{C.B_GREEN}✓ PASS{C.RESET}"
        else:
            mark = f"{C.B_RED}✗ FAIL{C.RESET}"
        pad = w - 6 - 38
        print(f"  {C.B_CYAN}│{C.RESET}  {mark}  {C.BOLD}{icon_name}{C.RESET}  {C.DIM}{desc}{C.RESET}{' ' * max(0, pad)}{C.B_CYAN}│{C.RESET}")

    print(f"  {C.B_CYAN}├{'─' * (w - 6)}┤{C.RESET}")

    # Overall bar
    bar = progress_bar(passed, total, width=20, label=f"{passed}/{total} checks")
    print(f"  {C.B_CYAN}│{C.RESET}{bar}{' ' * max(0, w - 6 - 55)}{C.B_CYAN}│{C.RESET}")

    print(f"  {C.B_CYAN}└{'─' * (w - 6)}┘{C.RESET}")

    # Final verdict
    print()
    if passed == total and not INSTALL_QUEUE:
        print(f"  {C.BG_B_GREEN}{C.BLACK}{C.BOLD}  ✓ EVERYTHING IS READY!  {C.RESET}")
        print()
        print(f"  {C.BOLD}Start the server:{C.RESET}")
        print(f"  {C.B_CYAN}python server.py{C.RESET}")
        print()
        print(f"  {C.DIM}Server will be available at {C.B_YELLOW}http://localhost:8976{C.RESET}")
        print()
    elif install_success:
        print(f"  {C.BG_B_GREEN}{C.BLACK}{C.BOLD}  ✓ INSTALLATION COMPLETE  {C.RESET}")
        print()
        print(f"  {C.BOLD}Start the server:{C.RESET}")
        print(f"  {C.B_CYAN}python server.py{C.RESET}")
        print()
    else:
        print(f"  {C.BG_B_YELLOW}{C.BLACK}{C.BOLD}  ⚠ SOME ITEMS NEED ATTENTION  {C.RESET}")
        print()
        if INSTALL_QUEUE:
            print(f"  {C.BOLD}Items that need manual installation:{C.RESET}")
            for name, cmd in INSTALL_QUEUE:
                print(f"    {C.B_YELLOW}•{C.RESET} {C.BOLD}{name}{C.RESET}: {C.DIM}{cmd[:70]}{C.RESET}")
            print()
        print(f"  {C.DIM}After fixing, run:{C.RESET}  {C.BOLD}python setup.py --check{C.RESET}")
        print()


# ─── MAIN ──────────────────────────────────────────────────────────

def main():
    check_only = "--check" in sys.argv

    print_banner()

    if check_only:
        print(f"  {C.B_YELLOW}⚡ Check-only mode — no installations will be performed{C.RESET}")

    results = {}
    results["python"] = check_python_version()
    results["pip"] = check_pip()
    results["packages"] = check_pip_packages()
    results["chrome"] = check_chrome()
    results["playwright"] = check_playwright_browsers()
    results["port"] = check_port()
    results["structure"] = check_project_structure()
    results["git"] = check_git()

    install_success = True
    if INSTALL_QUEUE and not check_only:
        install_success = run_installs()

        # Re-check after install
        if install_success:
            print()
            print(f"  {C.B_CYAN}↻ Re-verifying after installation...{C.RESET}")
            time.sleep(1)

            # Quick re-check of packages
            try:
                importlib.import_module("playwright")
                ok("playwright now available")
                results["packages"] = True
            except ImportError:
                pass

    print_summary(results, install_success)

    passed = sum(1 for v in results.values() if v)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
