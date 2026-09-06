"""One-shot verification probes for aureon_fusion.outbound_messenger.

Run by the build agent; not part of any suite. Each probe is independent;
nothing here touches the real allowlist file or the network.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ.get("AUREON_WORKSPACE",
                                  r"C:\Users\user\.kimi_openclaw\workspace"))

import aureon_fusion.outbound_messenger as m

failures = []


def check(name, cond, info=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name} {info}")
    if not cond:
        failures.append(name)


# ── Probe 2: approval flag absent → refused before anything else ──────────
real_approval = m._approval
m._approval = lambda: {"ok": False, "flag_file": str(m.APPROVAL_FLAG),
                       "flag_present": False, "authorized": False}
r = m.send("anyone@example.com", "s", "b")
check("flag-absent refuses", r["sent"] is False and r["reason"] == "not_approved",
      json.dumps({k: r[k] for k in ("sent", "reason")}))
m._approval = real_approval

# ── Probe 3: conscience VETO is absolute ──────────────────────────────────
real_conscience = m._conscience_evaluate
m._conscience_evaluate = lambda d, c: {"ok": False, "verdict": "VETO",
                                       "reasoning": "probe veto"}
r = m.send("anyone@example.com", "s", "b")
check("conscience VETO refuses", r["sent"] is False and r["reason"] == "conscience_veto",
      json.dumps({k: r[k] for k in ("sent", "reason")}))
m._conscience_evaluate = real_conscience

# ── Probe 4: success path — fake SMTP + allowlisted recipient + approve ───
tmpdir = Path(tempfile.mkdtemp(prefix="outbound_probe_"))
allow_file = tmpdir / "allowlist.json"
allow_file.write_text(json.dumps({"recipients": ["Gary@Example.com"]}),
                      encoding="utf-8")
real_allowlist_file = m.ALLOWLIST_FILE
m.ALLOWLIST_FILE = allow_file

m._conscience_evaluate = lambda d, c: {"ok": True, "verdict": "ALLOW",
                                       "reasoning": "probe approve"}

sent_log = []


class FakeSMTP:
    def __init__(self, host, port):
        sent_log.append({"host": host, "port": port})

    def starttls(self, context=None):
        sent_log[-1]["tls"] = True

    def login(self, user, password):
        sent_log[-1]["login"] = True

    def send_message(self, msg):
        sent_log[-1]["to"] = msg["To"]
        sent_log[-1]["from"] = msg["From"]
        sent_log[-1]["subject"] = msg["Subject"]
        sent_log[-1]["body"] = msg.get_content()

    def quit(self):
        sent_log[-1]["quit"] = True


m.SMTP_FACTORY = lambda host, port: FakeSMTP(host, port)
os.environ["OUTBOUND_SMTP_HOST"] = "smtp.probe.test"
os.environ["OUTBOUND_SMTP_PORT"] = "587"
os.environ["OUTBOUND_SMTP_USER"] = "probe-user"
os.environ["OUTBOUND_SMTP_PASSWORD"] = "probe-secret-value"
os.environ["OUTBOUND_SMTP_FROM"] = "organism@probe.test"

r = m.send("gary@example.com", "Decree probe subject", "probe body text",
           source="probe")
check("success path sends", r["sent"] is True and r["reason"] is None,
      json.dumps({k: r.get(k) for k in ("sent", "reason", "transport")}))
check("fake SMTP received message",
      sent_log and sent_log[-1].get("to") == "gary@example.com"
      and sent_log[-1].get("subject") == "Decree probe subject"
      and str(sent_log[-1].get("body", "")).strip() == "probe body text"
      and sent_log[-1].get("login") is True,
      json.dumps({k: v for k, v in sent_log[-1].items()
                  if k not in ("body",)}))

# ── Probe 5: journal integrity — last line matches the send, no body/creds ─
lines = m.JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
last = json.loads(lines[-1])
check("journal records success send",
      last.get("recipient") == "gary@example.com" and last.get("sent") is True
      and last.get("source") == "probe",
      json.dumps({k: last.get(k) for k in ("recipient", "sent", "source")}))
blob = m.JOURNAL_FILE.read_text(encoding="utf-8")
check("journal has no body/secret leakage",
      "probe body text" not in blob and "probe-secret-value" not in blob
      and "Decree probe subject" not in blob)
check("journal subject is hashed",
      last.get("subject_sha256") ==
      __import__("hashlib").sha256("Decree probe subject".encode()).hexdigest())

# ── Probe 6: non-allowlisted still refused even with everything armed ─────
r = m.send("stranger@example.com", "s", "b")
check("armed rail still refuses non-allowlisted",
      r["sent"] is False and r["reason"] == "recipient_not_allowlisted")
check("no SMTP connection opened for refused send", len(sent_log) == 1,
      f"smtp_calls={len(sent_log)}")

# ── cleanup ────────────────────────────────────────────────────────────────
m.ALLOWLIST_FILE = real_allowlist_file
m.SMTP_FACTORY = None
m._conscience_evaluate = real_conscience
for k in ("OUTBOUND_SMTP_HOST", "OUTBOUND_SMTP_PORT", "OUTBOUND_SMTP_USER",
          "OUTBOUND_SMTP_PASSWORD", "OUTBOUND_SMTP_FROM"):
    os.environ.pop(k, None)

print("\n%d probe(s) failed" % len(failures) if failures else "\nALL PROBES PASS")
sys.exit(1 if failures else 0)
