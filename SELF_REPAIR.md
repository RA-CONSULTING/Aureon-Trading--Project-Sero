# Self-repair

A developer points Aureon at a Python project. Aureon runs that project's pytest suite, repairs the implementation, runs the tests again, and commits the repair on a local branch. Nothing is pushed.

```bash
python -m aureon_fusion.repair --root /path/to/project
```

The project needs `pytest` on the command path. The command exits 0 when the tests pass after the repair, or when they already passed.

## What it repairs

In one run it can repair several failures, as long as each one is proved by the tests:

- a function returns the wrong constant (`return "off"` against `assert label() == "on"`)
- a two-argument function uses the wrong operator (`return a - b` against `assert add(2, 3) == 5`)
- a `NameError` whose missing name is one character away from exactly one name in that file

It edits implementation files only. Test files are left as they are. After the suite passes, the change is committed on `aureon-self-repair/<timestamp>`. A line is appended to `state/self_repair_review_log.jsonl`.

## What the writer is for

The Queen writer is the system's hands. It can write the code the organs run:

- trading logic, including the flags that arm a live session when the operator sets them
- evidence gates, including `RELEASE` and `may_act = True` when that is the code under repair
- a local `.env` whose values are the credentials the exchanges read

`AUREON_SELF_REPAIR_KILL=1` stops the writer. Leave it unset and the repair runs. The repair commits on a local branch and writes `state/self_repair_review_log.jsonl`. It does not rewrite the test file, because the test is the specification it has to meet. It does not push.

The fusion HTTP process still starts with live trading unset. Arming a session is a flag in the environment, which the writer is allowed to set when that is the change being made.

## Other self-coding modules in the tree

`aureon/autonomous/aureon_repo_self_repair.py` still runs the repo diagnostic and writes an audit through the Queen writer. `aureon/autonomous/aureon_internal_self_coder.py` remains the receipt-backed coder. Its release entrypoint in this checkout raises `release_review_entrypoint_disabled_proposal_only`, so it does not publish code on its own. The command above is the path that repairs a project without that release step.
