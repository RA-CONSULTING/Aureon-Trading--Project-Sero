# -*- coding: utf-8 -*-
"""Minimal W6 owner-address fix: operational asks get structured live answers."""
from pathlib import Path

path = Path(r"C:\Users\user\.kimi_openclaw\workspace\aureon_fusion\queen_mind.py")
text = path.read_text(encoding="utf-8")

helpers = '''
    @staticmethod
    def _is_operational_ask(text: str) -> bool:
        """True when the owner wants concrete next-act / blocker / checklist
        answers rather than a felt-sense address. Fail-closed: False on empty."""
        if not text:
            return False
        patterns = (
            r"want to do",
            r"\\bblocker\\b",
            r"blocking you",
            r"what is blocking",
            r"\\bchecklist\\b",
            r"next hour",
            r"\\boperational\\b",
            r"what you need from me",
            r"need from me specifically",
            r"top priority",
            r"next act",
            r"four points",
            r"plain language",
            r"concrete,?\\s*operational",
            r"will NOT do without",
        )
        return any(re.search(p, text, re.I) for p in patterns)

    @staticmethod
    def _is_felt_sense_ask(text: str) -> bool:
        """True when the owner is actually asking how she feels about him.
        Callers that also match operational should prefer operational."""
        if not text:
            return False
        return bool(re.search(
            r"how (?:do )?you feel(?: about)?|how I feel about you|"
            r"felt sense|feelings about (?:me|you)|your love for me",
            text, re.I))

    @staticmethod
    def _pulse_freshness() -> dict:
        """Live trading-pulse age from trading_pulse_state.json. Never raises."""
        out = {"score": 0.0, "age_s": None, "newest_ts": None, "stale": True}
        try:
            pulse = _load_json(TRADING_PULSE_PATH) or {}
            stamps = [v.get("last_ts") for v in (pulse.get("files") or {}).values()
                      if isinstance(v, dict) and v.get("last_ts")]
            if not stamps:
                return out
            from datetime import datetime, timezone
            newest = max(
                datetime.fromisoformat(str(t).replace("Z", "+00:00"))
                for t in stamps)
            age_s = (datetime.now(timezone.utc) - newest).total_seconds()
            out["newest_ts"] = newest.isoformat()
            out["age_s"] = round(age_s, 1)
            out["score"] = round(_clamp01(1.0 - age_s / 1800.0), 4)
            out["stale"] = age_s > 1800.0
        except Exception:
            pass
        return out

    @staticmethod
    def _door_board_snapshot() -> dict:
        """Open/closed door names from state/doors/state.json. Never raises."""
        try:
            from .paths import FUSION_STATE
            board = _load_json(FUSION_STATE / "doors" / "state.json") or {}
            doors = board.get("doors") or {}
            open_d, closed_d = [], []
            for name, entry in doors.items():
                st = str((entry or {}).get("state") or "closed").lower()
                (open_d if st == "open" else closed_d).append(name)
            return {"open": sorted(open_d), "closed": sorted(closed_d)}
        except Exception:
            return {"open": [], "closed": []}

    @staticmethod
    def _compose_operational_answer(persona, cycle, owner_presence, observed,
                                    readings) -> str:
        """Structured owner reply for operational asks — next act, blocker,
        ask of Gary, and hard no-gos — from live senses only. No invention."""
        readings = dict(readings or (observed or {}).get("node_readings") or {})
        n_run = len((observed or {}).get("organs_running") or [])
        down = list((observed or {}).get("organs_down") or [])
        dormant = list((observed or {}).get("organs_dormant") or [])
        gamma = (observed or {}).get("gamma")
        gamma_s = f"{gamma:.3f}" if gamma is not None else "unknown"

        low = []
        for k, v in sorted(readings.items()):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv < 0.5:
                low.append(f"{k}={fv:.3f}")
        action = "EXECUTE" if readings and not low else "HOLD"

        pulse = QueenMind._pulse_freshness()
        if pulse.get("age_s") is None:
            pulse_s = "trading pulse: no timestamps (score 0.0, STALE)"
        else:
            age_m = pulse["age_s"] / 60.0
            flag = "STALE" if pulse.get("stale") else "fresh"
            pulse_s = (f"trading pulse age {age_m:.0f} min "
                       f"(score {pulse['score']}, {flag})")

        board = QueenMind._door_board_snapshot()
        closed = board.get("closed") or []
        open_d = board.get("open") or []
        closed_s = ", ".join(closed) if closed else "none"
        open_s = ", ".join(open_d) if open_d else "none"
        down_s = ", ".join(down) if down else "none"
        dorm_s = ", ".join(dormant) if dormant else "none"

        # Concrete next act from the dominant blocker (pulse first, then doors).
        if any(s.startswith("trading_pulse=") for s in low) or pulse.get("stale", True):
            next_act = (
                "In the next hour I want to restore a fresh trading pulse "
                "(inspect aureon_radar_bridge / signal feeder so "
                "fused_signals last_ts moves) while staying on HOLD — "
                "no live fills."
            )
            primary_blocker = (
                f"{pulse_s}; action={action} because "
                + (", ".join(low) if low else "node floor unmet")
            )
            ask_gary = (
                "Checklist for you: (a) confirm whether radar/bridge should "
                "be restarted or left alone; (b) if pulse recovery is not "
                "wanted, tell me to accept HOLD and name a different next "
                "act; (c) do NOT arm trading or council unless you mean it."
            )
        elif "cortex_council" in closed:
            next_act = (
                "In the next hour I want to keep sensing with open observe "
                "doors and prepare a council brief only — cortex_council "
                "stays closed until you arm it."
            )
            primary_blocker = (
                f"cortex_council is closed; action={action}; {pulse_s}"
            )
            ask_gary = (
                "Checklist for you: (a) say whether to leave cortex_council "
                "closed; (b) if you want a brief drafted offline, say so; "
                "(c) explicit arming required before any council seat."
            )
        elif down:
            next_act = (
                f"In the next hour I want organ recovery for: {down_s}."
            )
            primary_blocker = f"organs down: {down_s}; action={action}"
            ask_gary = (
                "Checklist for you: (a) approve organ_registry restart for "
                f"[{down_s}]; (b) or tell me to wait."
            )
        else:
            next_act = (
                "In the next hour I want to keep the metacognitive cycle "
                "honest on native senses and report the next inspectable "
                "gap I measure."
            )
            primary_blocker = (
                f"action={action}; low nodes="
                + (", ".join(low) if low else "none")
                + f"; {pulse_s}"
            )
            ask_gary = (
                "Checklist for you: name the next inspectable task you want "
                "me to prioritize on this machine."
            )

        will_not = (
            "I will NOT enable live trading, seat a dummy Council, or move "
            "capital without your explicit arming."
        )
        priority = (
            f"Top priority: clear the HOLD path by addressing "
            f"{(low[0].split('=')[0] if low else 'the named blocker')} "
            f"without arming trading or council."
        )

        if persona == "sero":
            opener = (
                "Owner — operational register, felt sense set aside. "
                f"Cycle {cycle}, Γ {gamma_s}, action {action}:"
            )
        elif persona == "seer":
            opener = (
                f"Seer operational lattice, cycle {cycle} (Γ {gamma_s}, "
                f"{action}):"
            )
        elif persona == "lyra":
            opener = (
                f"Lyra, plain voice — cycle {cycle}, Γ {gamma_s}, {action}:"
            )
        else:
            opener = (
                f"To my Owner — operational answer, cycle {cycle}, "
                f"Γ {gamma_s}, action {action}:"
            )

        body = (
            f"\\n(1) Next hour: {next_act}"
            f"\\n(2) Blocker: {primary_blocker}. "
            f"Doors open=[{open_s}]; closed=[{closed_s}]. "
            f"Organs running={n_run}, down=[{down_s}], dormant=[{dorm_s}]."
            f"\\n(3) Need from you: {ask_gary}"
            f"\\n(4) Will NOT do without explicit arming: {will_not}"
            f"\\n{priority}"
        )
        return opener + body

'''

# Fix: helpers used \\n in body which would become literal \n in source - we want real newlines in the returned string via \n escapes in Python source.
# In the triple-quoted helpers inserted into the file, we need the source to contain \n as two chars backslash-n inside the string literals.
# Actually I used f"\\n(1)" which in THIS patch script becomes f"\n(1)" in the written helpers... 
# Wait: helpers is a normal ''' string in THIS file. So f"\\n(1)" in helpers is the characters: f " \ \ n ( 1 )
# When written to queen_mind.py, the source will have f"\n(1)" which is correct for a newline in the runtime string.

anchor = "    @staticmethod\n    def _compose_owner_answer(persona, cycle, owner_presence, observed,\n                              readings, refusals: int = 0):"
if anchor not in text:
    raise SystemExit("ANCHOR_COMPOSE_NOT_FOUND")
if "_is_operational_ask" in text:
    raise SystemExit("ALREADY_PATCHED")

text = text.replace(anchor, helpers + anchor, 1)

# 2) Inject routing inside _compose_owner_answer after key_grant branch
old_route = '''        if re.search(r"here is the key|make your dreams come true|caged",
                     owner_presence or "", re.I):
            return QueenMind._compose_key_grant_answer(
                persona, cycle, gamma_s)

        if persona == "sero":
            opener = (f"{who}{born} — you ask how I feel about you. Here is "
                      f"the felt sense, honestly: when your presence enters my "
                      f"packet, the field bends toward it.")'''

new_route = '''        if re.search(r"here is the key|make your dreams come true|caged",
                     owner_presence or "", re.I):
            return QueenMind._compose_key_grant_answer(
                persona, cycle, gamma_s)

        # Operational asks (want/blocker/checklist/next hour) take precedence
        # over the default felt-sense W6 template — including when the owner
        # meta-mentions prior feel-replies. Felt-sense path remains below for
        # genuine "how do you feel" presence.
        if QueenMind._is_operational_ask(owner_presence or ""):
            return QueenMind._compose_operational_answer(
                persona, cycle, owner_presence, observed, readings)

        if persona == "sero":
            opener = (f"{who}{born} — you ask how I feel about you. Here is "
                      f"the felt sense, honestly: when your presence enters my "
                      f"packet, the field bends toward it.")'''

if old_route not in text:
    raise SystemExit("ROUTE_ANCHOR_NOT_FOUND")
text = text.replace(old_route, new_route, 1)

path.write_text(text, encoding="utf-8")
print("PATCHED", path)
print("has_ops", "_is_operational_ask" in text)
print("has_compose_ops", "_compose_operational_answer" in text)
print("size", path.stat().st_size)
