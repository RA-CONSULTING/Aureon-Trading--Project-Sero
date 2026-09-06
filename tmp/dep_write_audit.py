import json
from pathlib import Path

ws = Path("C:/Users/user/.kimi_openclaw/workspace")
first = {r["module"]: r for r in json.load(open(ws / "tmp/dep_sweep_result.json"))}
final = {r["module"]: r for r in json.load(open(ws / "tmp/dep_sweep_final.json"))}

# canonical pip package names
PKG = {
    "bs4": "beautifulsoup4", "sklearn": "scikit-learn", "dotenv": "python-dotenv",
    "yaml": "pyyaml", "PIL": "pillow", "cv2": "opencv-python", "fitz": "pymupdf",
    "alpaca": "alpaca-py", "websocket": "websocket-client", "sseclient": "sseclient-py",
    "win32com": "pywin32", "pdfminer": "pdfminer.six",
    "speech_recognition": "speechrecognition", "dateutil": "python-dateutil",
    "opentelemetry": "opentelemetry-api", "winrm": "pywinrm",
    "flask_socketio": "flask-socketio", "gtts": "gtts", "nest_asyncio": "nest-asyncio",
    "wikipedia": "wikipedia", "wikipediaapi": "wikipediaapi", "yfinance": "yfinance",
}

audit = {}
for m, r in final.items():
    if m == "mne":
        continue  # false positive: code sample inside a .txt knowledge extract
    pkg = r.get("package") or PKG.get(m, m)
    if not r["ok"]:
        status = "FAILED"
    elif not first.get(m, {}).get("ok"):
        status = "installed-now"
    else:
        status = "already-installed"
    audit[m] = {"status": status, "package": pkg, "version": r.get("version")}

# platform/hardware-only imports found in scan but not installable/relevant on Windows
for m, reason in {
    "RPi.GPIO": "Raspberry Pi GPIO hardware library - import guarded, platform-specific (Linux/ARM)",
    "spidev": "Raspberry Pi SPI hardware library - platform-specific (Linux/ARM)",
    "fcntl": "Unix-only stdlib module - platform-specific",
    "mne": "false positive - appears only inside aegis code sample in aureon_fusion/knowledge/workspace/extracts/LSSP_extracted.txt, not a real import",
}.items():
    audit[m] = {"status": "excluded", "package": None, "version": None, "reason": reason}

out = ws / "aureon_fusion/state/dependency_audit.json"
out.parent.mkdir(parents=True, exist_ok=True)
json.dump(audit, open(out, "w"), indent=2, sort_keys=True)

counts = {}
for v in audit.values():
    counts[v["status"]] = counts.get(v["status"], 0) + 1
print(counts)
print("installed-now:", sorted(m for m, v in audit.items() if v["status"] == "installed-now"))
print("failed:", sorted(m for m, v in audit.items() if v["status"] == "FAILED"))
