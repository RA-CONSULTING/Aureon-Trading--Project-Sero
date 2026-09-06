import os, sys, threading
os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"
sys.path.insert(0, r"C:\Users\user\.kimi_openclaw\workspace\aureon-os-upstream")
import time
t0 = time.time()
before = set(t.name for t in threading.enumerate())
target = sys.argv[1]
if target == "maeshowe":
    from aureon.wisdom.maeshowe_seer_decode import get_oracle_maeshowe
    o = get_oracle_maeshowe()
    print("oracle:", type(o).__name__)
elif target == "seer":
    import aureon.intelligence.aureon_seer as m
    print("module loaded, get_seer present:", hasattr(m, "get_seer"), "ephem:", m._EPHEM_AVAILABLE)
elif target == "lyra":
    import aureon.trading.aureon_lyra as m
    print("module loaded, get_lyra present:", hasattr(m, "get_lyra"))
after = set(t.name for t in threading.enumerate())
new_threads = after - before
print("new threads:", new_threads or "none")
assert not new_threads, "threads spawned at import!"
print(f"PROBE {target} OK in {time.time()-t0:.1f}s")
