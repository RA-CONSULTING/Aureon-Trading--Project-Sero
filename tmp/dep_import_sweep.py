"""Dependency import sweep for the Aureon fleet. Read-only w.r.t. source."""
import json
import os
import subprocess
import sys

MODULES = [
    # scope scan (aureon_fusion, aureon_radar, root daemons)
    "aiohttp", "alpaca", "bs4", "cryptography", "dash", "dotenv", "matplotlib",
    "mne", "numpy", "pandas", "plotly", "psutil", "requests", "rich", "scipy",
    "sklearn", "skyfield", "sseclient", "urllib3", "websocket", "websockets",
    "wikipedia",
    # fleet-referenced aureon.* (aureon-os-upstream) third-party
    "anthropic", "astroquery", "bleak", "certifi", "cv2", "dateutil", "ephem",
    "fitz", "flask", "flask_socketio", "gtts", "imageio", "keyboard",
    "krakenex", "nest_asyncio", "networkx", "opentelemetry", "paramiko",
    "pdfminer", "PIL", "prometheus_client", "pyaudio", "pyautogui", "pycaw",
    "PyPDF2", "pypdf", "pyperclip", "pytesseract", "pyttsx3", "redis",
    "sounddevice", "speech_recognition", "waitress", "werkzeug", "wikipediaapi",
    "win32com", "winrm", "winrt", "yfinance", "yaml", "ccxt", "openpyxl",
    "reportlab",
]

CHILD = r"""
import importlib, importlib.metadata as md, json, sys
name = sys.argv[1]
result = {"module": name, "ok": False, "version": None, "error": None}
try:
    mod = importlib.import_module(name)
    result["ok"] = True
    top = name.split(".")[0]
    dist_map = {
        "bs4": "beautifulsoup4", "sklearn": "scikit-learn", "dotenv": "python-dotenv",
        "yaml": "pyyaml", "PIL": "pillow", "cv2": "opencv-python", "fitz": "pymupdf",
        "alpaca": "alpaca-py", "websocket": "websocket-client", "sseclient": "sseclient-py",
        "wikipedia": "wikipedia", "win32com": "pywin32", "cryptography": "cryptography",
        "pdfminer": "pdfminer.six", "speech_recognition": "speechrecognition",
        "dateutil": "python-dateutil",
    }
    dist = dist_map.get(top, top)
    for cand in {dist, top}:
        try:
            result["version"] = md.version(cand)
            result["package"] = cand
            break
        except md.PackageNotFoundError:
            continue
except Exception as e:
    result["error"] = f"{type(e).__name__}: {e}"[:300]
print(json.dumps(result))
"""

env = dict(os.environ)
env["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
env["AUREON_AUDIT_MODE"] = "1"

out = []
for m in MODULES:
    p = subprocess.run(
        [sys.executable, "-c", CHILD, m],
        capture_output=True, text=True, env=env, timeout=60,
        cwd=os.path.expanduser("~/.kimi_openclaw/workspace"),
    )
    line = (p.stdout or "").strip().splitlines()
    if line:
        try:
            out.append(json.loads(line[-1]))
            continue
        except json.JSONDecodeError:
            pass
    out.append({"module": m, "ok": False, "version": None,
                "error": f"sweep-failure rc={p.returncode}: {(p.stderr or '')[:200]}"})

print(json.dumps(out, indent=1))
