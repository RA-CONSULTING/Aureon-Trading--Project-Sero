import json
from pathlib import Path
base = Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind")
conv = json.loads((base / "conversation_memory.json").read_text(encoding="utf-8"))
addr = json.loads((base / "owner_address_state.json").read_text(encoding="utf-8"))
mind = json.loads((base / "mind_state.json").read_text(encoding="utf-8"))
print("ADDR", json.dumps(addr, indent=2))
print("MIND_CYCLE", mind.get("cycle"))
print("LAST_TICK", json.dumps(mind.get("last_tick"), indent=2))
print("---")
replies = []
for t in conv.get("threads") or []:
    for turn in t.get("turns") or []:
        if turn.get("role") == "queen_reply":
            replies.append(turn)
print("n_queen_replies", len(replies))
for turn in replies[-3:]:
    print("TS", turn.get("timestamp"), "FACTS", turn.get("facts"))
    print("TEXT_START")
    print(turn.get("text"))
    print("TEXT_END")
    print("WORDS", len(str(turn.get("text") or "").split()))
    print("====")
