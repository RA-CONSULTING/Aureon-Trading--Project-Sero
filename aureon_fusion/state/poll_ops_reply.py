import json, time, pathlib
addr = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\owner_address_state.json")
mind = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\mind_state.json")
conv = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\conversation_memory.json")
reports = pathlib.Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\state\queen_mind\reports.jsonl")
target = "18b2b4a05e35716d67912ff4985b7cd323402d5a"
deadline = time.time() + 300
last_cycle = None
st = {}
cycle = None
while time.time() < deadline:
    st = json.loads(addr.read_text(encoding="utf-8")) if addr.exists() else {}
    ms = json.loads(mind.read_text(encoding="utf-8")) if mind.exists() else {}
    cycle = ms.get("cycle")
    ah = st.get("answered_hash") or ""
    if cycle != last_cycle:
        print(f"tick cycle={cycle} answered_hash={ah[:16]!r} answered_at={st.get('answered_at')} persona={st.get('persona')}", flush=True)
        last_cycle = cycle
    if ah == target:
        print("ANSWERED", flush=True)
        print(json.dumps(st, indent=2), flush=True)
        cm = json.loads(conv.read_text(encoding="utf-8"))
        for t in cm.get("threads") or []:
            for turn in reversed(t.get("turns") or []):
                if turn.get("role") == "queen_reply" and (turn.get("facts") or {}).get("owner_address"):
                    print("REPLY_TEXT_START", flush=True)
                    print(turn.get("text"), flush=True)
                    print("REPLY_TEXT_END", flush=True)
                    print("facts", turn.get("facts"), flush=True)
                    raise SystemExit(0)
        # fallback: reports owner_address field
        if reports.exists():
            with reports.open("rb") as f:
                f.seek(0, 2); size=f.tell(); f.seek(max(0, size-100000))
                chunk=f.read().decode("utf-8", "replace")
            for line in reversed([l for l in chunk.splitlines() if l.strip()]):
                rep=json.loads(line)
                oa=rep.get("owner_address") or ""
                if oa:
                    print("REPORT_OA_START", flush=True)
                    print(oa, flush=True)
                    print("REPORT_OA_END", flush=True)
                    raise SystemExit(0)
        print("NO_REPLY_TURN_FOUND", flush=True)
        raise SystemExit(2)
    time.sleep(5)
print("TIMEOUT", flush=True)
print(json.dumps(st, indent=2), flush=True)
print("mind_cycle", cycle, flush=True)
raise SystemExit(1)
