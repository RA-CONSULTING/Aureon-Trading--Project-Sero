import ast, json, sys
from pathlib import Path

ws = Path(r"C:\Users\user\.kimi_openclaw\workspace")
data = json.loads((ws / "aureon_fusion" / "personas.json").read_text(encoding="utf-8"))
assert [p["name"] for p in data["personas"]] == ["Sero", "Queen", "Seer", "Lyra"]
for p in data["personas"]:
    for k in ("name", "modules", "role", "voice_lines", "status"):
        assert k in p, (p.get("name"), k)
print("personas.json OK:", len(data["personas"]), "personas,",
      sum(len(p["modules"]) for p in data["personas"]), "modules,",
      sum(len(p["voice_lines"]) for p in data["personas"]), "voice lines")

up = ws / "aureon-os-upstream"
for rel in ("aureon/wisdom/maeshowe_seer_decode.py",
            "aureon/intelligence/aureon_seer.py",
            "aureon/trading/aureon_lyra.py"):
    ast.parse((up / rel).read_text(encoding="utf-8"))
    print("ast.parse OK:", rel)
print("ALL VERIFY PASS")
