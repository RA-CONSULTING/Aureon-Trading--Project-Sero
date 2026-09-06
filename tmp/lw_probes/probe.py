"""Unit probes for aureon_fusion.learning_will in an isolated temp workspace.

usage: probe.py <scenario> <temp_workspace> <real_workspace>
"""
import json
import os
import sys
from types import SimpleNamespace

scenario = sys.argv[1]
WS = sys.argv[2]
REAL = sys.argv[3]

os.environ["SERO_WORKSPACE"] = WS
os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"
if REAL not in sys.path:
    sys.path.insert(0, REAL)

from aureon_fusion import learning_will as lw  # noqa: E402

INTENT = {
    "id": "lw_testintent1", "kind": "domain_curiosity",
    "question": "What evidence would raise my confidence in the 'ethics' domain?",
    "domain": "ethics", "source": "probe", "url": None, "desire_score": 0.7,
}

ok = True

def check(name, cond, extra=""):
    global ok
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        ok = False

def fake_mycelium():
    class Net:
        domains = {"ethics": {"confidence": 0.4, "signal_weight": 1.0,
                              "count": 3}}
        def get_domain_confidence(self, d):
            return 0.4
    return Net()

if scenario == "gate_veto":
    lw._CACHE["mycelium"] = fake_mycelium()
    from aureon_fusion import conscience_hook
    conscience_hook.evaluate = lambda desc, ctx=None: {
        "verdict": "VETO", "reasoning": "probe veto", "conditions": [],
        "sls_score": 0.1}
    gate = lw.LearningGate().check(INTENT)
    check("outcome==vetoed", gate["outcome"] == "vetoed", gate["outcome"])
    check("passed False", gate["passed"] is False)
    res = lw.LearningWill().consider_once(dry_run=True)
    check("consider_once vetoed", res["outcome"] == "vetoed", res["outcome"])

elif scenario == "gate_incoherent":
    # hnc state written by runner with gamma 0.1
    gate = lw.LearningGate().check(INTENT)
    check("outcome==held_incoherent", gate["outcome"] == "held_incoherent",
          gate["outcome"])
    check("gamma recorded", gate["coherence"]["gamma"] == 0.1)

elif scenario == "gate_missing_row":
    # matrix written by runner WITHOUT the network_access row
    gate = lw.LearningGate().check(INTENT)
    check("outcome==deferred", gate["outcome"] == "deferred", gate["outcome"])
    check("missing_row flagged", gate["authorization"].get("missing_row") is True)
    check("never crashed", True)

elif scenario == "gate_missing_state":
    gate = lw.LearningGate().check(INTENT)  # runner: no hnc file at all
    check("missing state holds", gate["outcome"] == "held_incoherent",
          gate["coherence"]["status"])

elif scenario == "discernment":
    SENT_DUP = ("The mycelium network grows confidence in the ethics domain "
                "through careful evidence feeding over long cycles.")
    SENT_NEW = ("A previously unobserved harmonic coupling between the "
                "Schumann baseline and the temporal coherence phase emerges "
                "during quiet solar wind intervals.")
    SENT_CONTRA = ("The ethics domain confidence is high and never needs "
                   "further evidence feeding.")

    class FakeFrag:
        def __init__(self, text):
            self.text = text

    ECHO = ("harmonic coupling schumann baseline temporal phase")
    INTENT_LOCAL = {
        "id": "lw_testintent2", "kind": "unanswered_question",
        "question": ("What coupling exists between the Schumann baseline "
                     "and the temporal coherence phase?"),
        "domain": "schumann", "source": "probe", "url": None,
        "desire_score": 0.7,
    }

    class FakeKD:
        def find_similar(self, text, n=5):
            toks = set(lw._content_tokens(text))
            if lw._jaccard(toks, set(lw._content_tokens(SENT_DUP))) > 0.5:
                return [FakeFrag(SENT_DUP)]
            if lw._jaccard(toks, set(lw._content_tokens(ECHO))) >= 0.25:
                return [FakeFrag(ECHO)]
            return []
        def absorb(self, *a, **k):
            return 1
        def save(self):
            pass

    class FakeNode:
        def __init__(self, content, nid="mem_x"):
            self.content = content
            self.id = nid
    class FakeWeb:
        def __init__(self):
            self.recalled = 0
        def recall(self, query, **k):
            self.recalled += 1
            toks = set(lw._content_tokens(query))
            if "confidence" in toks and "ethics" in toks:
                return [FakeNode("ethics domain confidence is high and stable")]
            return []
        def remember(self, *a, **k):
            return FakeNode("")
        def save(self):
            pass

    lw._CACHE["knowledge_dataset"] = FakeKD()
    web = FakeWeb()
    lw._CACHE["memory_web"] = web
    lw._CACHE["mycelium"] = None

    d = lw.Discernment()
    text = " ".join([SENT_DUP, SENT_NEW, SENT_CONTRA])
    cands = d.distill(text, INTENT_LOCAL)
    by_verdict = {}
    for c in cands:
        by_verdict.setdefault(c.get("verdict"), []).append(c)
    check("near-dup rejected", "near_dup_rejected" in by_verdict,
          str({k: len(v) for k, v in by_verdict.items()}))
    check("contested tagged", "contested" in by_verdict)
    if "contested" in by_verdict:
        c = by_verdict["contested"][0]
        check("conflict recorded", c.get("conflict_with") == "mem_x",
              str(c.get("conflict_with")))
    check("novel sentence survived", "absorb" in by_verdict,
          str({k: len(v) for k, v in by_verdict.items()}))
    if "absorb" in by_verdict:
        check("corroboration boosted",
              by_verdict["absorb"][0].get("corroborated") is True)

elif scenario == "mind_augment_spy":
    calls = {"learn": []}
    class SpyAugment:
        available = True
        def learn(self, coherence, action="HOLD"):
            calls["learn"].append((float(coherence), action))
    class FakeKD:
        def __init__(self): self.pockets = []
        def find_similar(self, text, n=5): return []
        def absorb(self, pocket, interpretations=None):
            self.pockets.append((pocket, interpretations)); return 1
        def save(self): pass
    class FakeWeb:
        def remember(self, *a, **k): return SimpleNamespace(id="m1")
        def save(self): pass
    class FakeNet:
        def __init__(self): self.fed = []
        def feed_evidence(self, domain, signal, outcome):
            self.fed.append((domain, signal, outcome)); return 0.5
        def get_domain_confidence(self, d): return 0.5

    lw._CACHE["knowledge_dataset"] = FakeKD()
    lw._CACHE["memory_web"] = FakeWeb()
    net = FakeNet()
    lw._CACHE["mycelium"] = net
    lw._CACHE["mind_augment"] = SpyAugment()

    cand = {"text": "A novel signal pattern in the ethics pathway was observed.",
            "quality": 0.8, "novelty": 0.9, "max_similarity": 0.1,
            "contested": False, "corroborated": True, "domain": "ethics",
            "domain_confidence": 0.5, "coherence_fit": 0.5,
            "score": 0.85, "verdict": "absorb"}
    contested = dict(cand, text="A conflicting claim about the pathway.",
                     contested=True, verdict="contested", score=0.4)
    absb = lw.Absorber(dry_run=False)
    batch = absb.absorb_batch([cand, contested], INTENT,
                              {"url": "https://example.test/x", "stale": False},
                              gamma=0.5)
    check("batch absorbed 1", batch["absorbed"] == 1, str(batch))
    check("contested stored", batch["contested_stored"] == 1)
    check("mind_augment.learn invoked", len(calls["learn"]) == 1,
          str(calls["learn"]))
    if calls["learn"]:
        check("learn got EXECUTE", calls["learn"][0][1] == "EXECUTE",
              str(calls["learn"]))
        check("learn got gamma", calls["learn"][0][0] == 0.5)
    check("mycelium fed per candidate", len(net.fed) == 2, str(net.fed))
    check("absorbed outcome 1.0", net.fed[0][2] == 1.0)
    check("contested outcome 0.0", net.fed[1][2] == 0.0)
    kd = lw._CACHE["knowledge_dataset"]
    check("kd absorb called", len(kd.pockets) == 2)
    tags2 = kd.pockets[1][0].entries[0].tags
    check("contested tagged in bank", "contested" in tags2, str(tags2))
    interp = kd.pockets[1][1]
    check("contested not fact", interp is not None and
          interp[0].data_type == "contested_claim")

else:
    print("unknown scenario", scenario)
    sys.exit(2)

sys.exit(0 if ok else 1)
