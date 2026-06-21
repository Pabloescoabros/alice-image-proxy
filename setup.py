#!/usr/bin/env python3
"""
Alice Yandex Proxy — Setup & Readiness Checker
================================================
Cross-platform (Windows/Linux/macOS) setup script.
Checks all prerequisites and installs missing dependencies automatically.

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
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"

# ANSI colors
GREEN = "\033[92m" if not IS_WINDOWS else ""
RED = "\033[91m" if not IS_WINDOWS else ""
YELLOW = "\033[93m" if not IS_WINDOWS else ""
BLUE = "\033[94m" if not IS_WINDOWS else ""
RESET = "\033[0m" if not IS_WINDOWS else ""
BOLD = "\033[1m" if not IS_WINDOWS else ""

CHECKS = []
INSTALL_QUEUE = []


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")

def info(msg):
    print(f"  {BLUE}→{RESET} {msg}")

def section(msg):
    print(f"\n{BOLD}{msg}{RESET}")
    print("─" * 50)


def run(cmd, capture=True, shell=True):
    """Run a command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=capture, text=True, timeout=120
        )
        return result.returncode == 0, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def get_python_cmd():
    """Get the correct python command for this system."""
    # Try python3 first (Linux/macOS), then python (Windows)
    for cmd in ["python3", "python", sys.executable]:
        success, out, _ = run(f"{cmd} --version")
        if success:
            return cmd
    return sys.executable


def get_pip_cmd(python_cmd):
    """Get pip command."""
    success, _, _ = run(f"{python_cmd} -m pip --version")
    if success:
        return f"{python_cmd} -m pip"
    for cmd in ["pip3", "pip"]:
        success, _, _ = run(f"{cmd} --version")
        if success:
            return cmd
    return None


# ─── CHECKS ───────────────────────────────────────────────

def check_python_version():
    """Check Python >= 3.10"""
    section("1. Python Version")
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 10:
        ok(f"Python {version_str}")
        return True
    fail(f"Python {version_str} — need 3.10+")
    INSTALL_QUEUE.append(("python", "Install Python 3.10+ from https://python.org"))
    return False


def check_pip():
    """Check pip availability."""
    section("2. pip")
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
    """Check required Python packages."""
    section("3. Python Packages")
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
            ok(f"{module_name} ({version})")
        except ImportError:
            fail(f"{module_name} — not installed")
            missing.append(pip_name)
            all_ok = False

    if missing:
        python_cmd = get_python_cmd()
        pip_cmd = get_pip_cmd(python_cmd)
        install_cmd = f"{pip_cmd} install {' '.join(missing)}"
        INSTALL_QUEUE.append(("packages", install_cmd))

    return all_ok


def check_chrome():
    """Check Google Chrome / Chromium installation."""
    section("4. Chrome / Chromium Browser")

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

    # Check paths
    for p in chrome_paths:
        if os.path.exists(p):
            ok(f"Chrome found: {p}")
            return True

    # Check PATH
    if chrome_cmd:
        ok(f"Chrome found in PATH: {chrome_cmd}")
        return True

    # Check with 'where' on Windows
    if IS_WINDOWS:
        success, out, _ = run("where chrome 2>nul")
        if success and out.strip():
            ok(f"Chrome in PATH: {out.strip().split(chr(10))[0]}")
            return True

    fail("Chrome/Chromium not found")

    if IS_LINUX:
        # Try to detect package manager
        if shutil.which("apt"):
            INSTALL_QUEUE.append(("chrome", "wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list && sudo apt update && sudo apt install -y google-chrome-stable"))
        elif shutil.which("dnf"):
            INSTALL_QUEUE.append(("chrome", "sudo dnf install -y fedora-workstation-repositories && sudo dnf config-manager --set-enabled google-chrome && sudo dnf install -y google-chrome-stable"))
        elif shutil.which("pacman"):
            INSTALL_QUEUE.append(("chrome", "sudo pacman -S --noconfirm chromium"))
        else:
            INSTALL_QUEUE.append(("chrome", "Install Chrome manually from https://google.com/chrome"))
    elif IS_WINDOWS:
        INSTALL_QUEUE.append(("chrome", "winget install Google.Chrome || echo 'Download from https://google.com/chrome'"))
    elif IS_MACOS:
        INSTALL_QUEUE.append(("chrome", "brew install --cask google-chrome || echo 'Download from https://google.com/chrome'"))

    return False


def check_playwright_browsers():
    """Check if Playwright Chromium browser is installed."""
    section("5. Playwright Browsers")

    try:
        import playwright
    except ImportError:
        warn("playwright package not installed — skipping browser check")
        return False

    # Check if chromium is installed by trying to find the browser path
    success, out, err = run(f"{get_python_cmd()} -c \"from playwright._impl._driver import compute_driver_executable; print(compute_driver_executable())\"")

    # Alternative: try playwright install --dry-run or check env
    env_check = run(f"{get_python_cmd()} -m playwright install --help")

    # Simple check: look for playwright browsers in known locations
    browser_found = False

    if IS_WINDOWS:
        # Playwright stores browsers in %USERPROFILE%\AppData\Local\ms-playwright
        pw_dir = Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "ms-playwright"
        if pw_dir.exists():
            chromium_dirs = list(pw_dir.glob("chromium-*"))
            if chromium_dirs:
                ok(f"Playwright Chromium found: {chromium_dirs[0].name}")
                browser_found = True
    else:
        # Linux/macOS: ~/.cache/ms-playwright
        pw_dir = Path.home() / ".cache" / "ms-playwright"
        if pw_dir.exists():
            chromium_dirs = list(pw_dir.glob("chromium-*"))
            if chromium_dirs:
                ok(f"Playwright Chromium found: {chromium_dirs[0].name}")
                browser_found = True

    if not browser_found:
        # Also check PLAYWRIGHT_BROWSERS_PATH env
        custom_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if custom_path and Path(custom_path).exists():
            chromium_dirs = list(Path(custom_path).glob("chromium-*"))
            if chromium_dirs:
                ok(f"Playwright Chromium found (custom path): {chromium_dirs[0].name}")
                browser_found = True

    if not browser_found:
        fail("Playwright Chromium browser not installed")
        INSTALL_QUEUE.append(("playwright_browsers", f"{get_python_cmd()} -m playwright install chromium"))
        return False

    return True


def check_port():
    """Check if port 8976 is available."""
    section("6. Port Availability")
    port = int(os.environ.get("PORT", "8976"))

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
        sock.close()
        ok(f"Port {port} is available")
        return True
    except OSError:
        fail(f"Port {port} is already in use")
        warn(f"Set a different port: PORT=9000 python server.py")
        return False


def check_project_structure():
    """Check that required project files exist."""
    section("7. Project Structure")
    project_dir = Path(__file__).parent

    required_files = {
        "server.py": "Main server file",
    }
    optional_files = {
        ".gitignore": "Git ignore rules",
        "README.md": "Documentation",
    }

    all_ok = True
    for f, desc in required_files.items():
        path = project_dir / f
        if path.exists():
            ok(f"{f} — {desc}")
        else:
            fail(f"{f} — MISSING ({desc})")
            all_ok = False

    for f, desc in optional_files.items():
        path = project_dir / f
        if path.exists():
            ok(f"{f} — {desc}")
        else:
            warn(f"{f} — not found ({desc})")

    # Create required directories
    for d in ["state", "cache", "media"]:
        dir_path = project_dir / d
        dir_path.mkdir(exist_ok=True)
        ok(f"Directory {d}/ ready")

    return all_ok


def check_git():
    """Check git availability (optional)."""
    section("8. Git (optional)")
    success, out, _ = run("git --version")
    if success:
        ok(f"{out.strip()}")
        return True
    warn("git not found — version control unavailable")
    return False


# ─── INSTALLER ────────────────────────────────────────────

def run_installs():
    """Execute queued installations."""
    if not INSTALL_QUEUE:
        section("Installation")
        ok("Nothing to install — all checks passed!")
        return True

    section("Installing Missing Components")
    print()

    all_success = True
    for name, cmd in INSTALL_QUEUE:
        if name == "python":
            warn(f"Python 3.10+ required. {cmd}")
            warn("Please install Python manually, then re-run this script.")
            all_success = False
            continue

        info(f"Installing {name}...")
        print(f"    {BLUE}$ {cmd}{RESET}")
        print()

        success, out, err = run(cmd)
        if success:
            ok(f"{name} installed successfully")
        else:
            fail(f"{name} installation failed")
            if err:
                print(f"    Error: {err[:200]}")
            all_success = False

    return all_success


# ─── MAIN ─────────────────────────────────────────────────

def main():
    check_only = "--check" in sys.argv

    print(f"\n{BOLD}{'='*50}{RESET}")
    print(f"{BOLD}  Alice Yandex Proxy — Setup Checker v5.1{RESET}")
    print(f"{BOLD}{'='*50}{RESET}")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Arch: {platform.machine()}")

    results = {}
    results["python"] = check_python_version()
    results["pip"] = check_pip()
    results["packages"] = check_pip_packages()
    results["chrome"] = check_chrome()
    results["playwright"] = check_playwright_browsers()
    results["port"] = check_port()
    results["structure"] = check_project_structure()
    results["git"] = check_git()

    # Summary
    section("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    color = GREEN if passed == total else (YELLOW if passed >= total - 2 else RED)
    print(f"  {color}{passed}/{total} checks passed{RESET}")

    if INSTALL_QUEUE and not check_only:
        print()
        success = run_installs()

        if success:
            print(f"\n{GREEN}{BOLD}✓ All dependencies installed. Ready to launch!{RESET}")
            print(f"\n  {BOLD}Start the server:{RESET}")
            print(f"  python server.py\n")
        else:
            print(f"\n{YELLOW}{BOLD}⚠ Some items need manual installation. See errors above.{RESET}")
            print(f"\n  After fixing, run: {BOLD}python setup.py --check{RESET}")
            print(f"  Then start:        {BOLD}python server.py{RESET}\n")
    elif check_only and INSTALL_QUEUE:
        print(f"\n{YELLOW}Items that need installation:{RESET}")
        for name, cmd in INSTALL_QUEUE:
            print(f"  • {name}: {cmd}")
        print(f"\n  Run {BOLD}python setup.py{RESET} (without --check) to install automatically.\n")
    elif not INSTALL_QUEUE:
        print(f"\n{GREEN}{BOLD}✓ Everything is ready!{RESET}")
        print(f"\n  {BOLD}Start the server:{RESET}")
        print(f"  python server.py\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
