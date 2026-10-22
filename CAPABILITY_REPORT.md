# Capability report

Commands below were run in this workspace on 22 October 2026. A result is recorded only after that run.

## Self-repair

| | |
|---|---|
| Where | `aureon_fusion/repair.py`, `aureon-os-upstream/aureon/autonomous/aureon_sandbox_self_repair.py`, guard in `aureon-os-upstream/aureon/autonomous/self_repair_guard.py`, writer in `aureon-os-upstream/aureon/queen/queen_code_architect.py` |
| Command | `python -m aureon_fusion.repair --root /tmp/plug-demo` |
| Result | **pass** |

The demo project started with `return a - b` and `return "off"`. The tests required `add(2, 3) == 5` and `label() == "on"`. The command exited 0. The implementation became `return a + b` and `return "on"`. The test file was not edited. Git recorded `aea0464` on `aureon-self-repair/20261022174430` with message `self-repair: tests pass after calc.py`. The review log ends with `repair_committed`, `tests_passed: true`, `live_trading: false`, `may_act: false`.

The suite that locks this behaviour:

```
cd aureon-os-upstream && PYTHONPATH=. python3 -m pytest tests/test_sandbox_self_repair.py -q --tb=line
......                                                                   [100%]
6 passed
```

Those six tests cover a wrong integer return, a repair that leaves the test file unchanged, an operator repair plus a `NameError`, the kill switch, and refusal of secret paths, live-trading flags, and an opened evidence gate.

`aureon/autonomous/aureon_internal_self_coder.py` is present. Its release function raises `release_review_entrypoint_disabled_proposal_only`, so that entrypoint was not treated as a working publisher.

## Fusion status and gates

| Capability | Where | Command | Result |
|---|---|---|---|
| Fusion status, live trading off | `aureon_fusion` | `python3 -m aureon_fusion` | **pass**, exit 0, `live_trading: false`, `may_act: false` |
| Layer join, synthetic evidence rejected | `aureon-os-upstream/aureon/organism/repository_layers.py` | `python3 -m pytest tests/test_fusion_join.py tests/test_public_field.py tests/test_fusion_http.py organism/test_public_market.py -q` | **pass**, 16 passed |
| Plant atlas and repository layers | `aureon-os-upstream` | `PYTHONPATH=. python3 -m pytest tests/test_repository_layers.py tests/bio/test_plant_atlas_*.py -q` | **pass**, 16 passed, 2 skipped (GPU backend needs torch) |
| Exchange rate limiter | `aureon-os-upstream/aureon/core/rate_limiter.py` | `PYTHONPATH=. python3 -m pytest tests/test_rate_limiter.py -q` | **pass**, 2 passed |
| Organ registry | `aureon_fusion/organ_registry.py` | `SERO_WORKSPACE=/workspace python3 -m aureon_fusion.organ_registry status` | **pass**, exit 0, organs stopped, capital pin DENY |
| Fusion HTTP auth, rate limit, health, error sink | `aureon_fusion/http_service.py` | included in the 16 tests above | **pass** |

## Not runnable here

| Surface | Command | Result |
|---|---|---|
| Vite frontend | `npm run dev` in `aureon-os-upstream/frontend` | **exit 2**. `package.json` routes `dev`, `preview`, and `trade:real` through `npm run unavailable`. |
| Nexus server on this Node | `node --check sources/NEXUS-LIVE-FEED-/src/server.js` | **fail**. The file uses `import ... assert { type: 'json' }`, which Node 22.23.4 rejects. |
| Docker image | `docker build` | **not runnable**. `docker` is not installed on this machine. `Dockerfile` and `docker-compose.yml` are in the repo root. |
| Private source repos | GitHub API | **not retrieved**. `skaila-journey-platform`, `aureon-founder-mirror`, `aureon-quantum-bloom`, and `Aueron-Trading-Quantum-Quackers-War-Ready-Version-` returned HTTP 404 for this credential. The in-tree Quackers strategy module is still present. |
