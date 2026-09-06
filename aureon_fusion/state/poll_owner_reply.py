import json, time, pathlib
addr = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\owner_address_state.json")
mind = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\mind_state.json")
conv = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\conversation_memory.json")
target = "e04fb1693fbfa4269097037b9715276f24a98720"
deadline = time.time() + 240
last_cycle = None
st = {}
cycle = None
while time.time() < deadline:
    st = json.loads(addr.read_text(encoding="utf-8"))
    ms = json.loads(mind.read_text(encoding="utf-8"))
    cycle = ms.get("cycle")
    ah = st.get("answered_hash") or ""
    if cycle != last_cycle:
        print(f"tick cycle={cycle} answered_hash={ah[:16]!r} answered_at={st.get('answered_at')} persona={st.get('persona')}", flush=True)
        last_cycle = cycle
    answered = False
    if ah == target:
        answered = True
    elif ah and st.get("cleared_at") and float(st.get("answered_at") or 0) > float(st.get("cleared_at") or 0):
        answered = True
    if answered:
        print("ANSWERED", flush=True)
        print(json.dumps(st, indent=2), flush=True)
        cm = json.loads(conv.read_text(encoding="utf-8"))
        found = False
        for t in cm.get("threads") or []:
            for turn in reversed(t.get("turns") or []):
                if turn.get("role") == "queen_reply" and (turn.get("facts") or {}).get("owner_address"):
                    print("REPLY_TEXT_START", flush=True)
                    print(turn.get("text"), flush=True)
                    print("REPLY_TEXT_END", flush=True)
                    print("facts", turn.get("facts"), flush=True)
                    print("ts", turn.get("timestamp"), flush=True)
                    found = True
                    break
                if turn.get("role") == "queen_reply":
                    print("LATEST_QUEEN_REPLY_START", flush=True)
                    print(turn.get("text"), flush=True)
                    print("LATEST_QUEEN_REPLY_END", flush=True)
                    print("facts", turn.get("facts"), flush=True)
                    print("ts", turn.get("timestamp"), flush=True)
                    found = True
                    break
            if found:
                break
        raise SystemExit(0)
    time.sleep(5)
print("TIMEOUT", flush=True)
print(json.dumps(st, indent=2), flush=True)
print("mind_cycle", cycle, flush=True)
