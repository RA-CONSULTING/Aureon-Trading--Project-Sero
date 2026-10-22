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

## What it will not do

These checks stay on while the repair runs:

- `AUREON_SELF_REPAIR_KILL=1` stops every repair and every Queen write
- files named `.env`, `*secret*`, `*credential*`, `*wallet*`, or a private key are not written
- a write that arms live trading (`AUREON_LIVE_TRADING=1`, `testnet: false`, `CONFIRM_LIVE_TRADING=yes`, and the same family) is refused
- a write that sets `may_act`, `action_eligible`, or `economic_mutation` to true, sets a gate to `RELEASE`, or deletes `sample_or_synthetic_evidence_excluded` is refused
- the repair does not push the branch and does not place an order

The Queen writer (`aureon/queen/queen_code_architect.py`) uses the same checks, so a repair cannot step around them by writing the file directly.

## Other self-coding modules in the tree

`aureon/autonomous/aureon_repo_self_repair.py` still runs the repo diagnostic and writes an audit through the Queen writer. `aureon/autonomous/aureon_internal_self_coder.py` remains the receipt-backed coder. Its release entrypoint in this checkout raises `release_review_entrypoint_disabled_proposal_only`, so it does not publish code on its own. The command above is the path that repairs a project without that release step.
