# Capability report

Commands below were run in this workspace on 22 October 2026. A result is recorded only after that run.

## Self-repair

| | |
|---|---|
| Where | `aureon_fusion/repair.py`, `aureon-os-upstream/aureon/autonomous/aureon_sandbox_self_repair.py`, guard in `aureon-os-upstream/aureon/autonomous/self_repair_guard.py`, writer in `aureon-os-upstream/aureon/queen/queen_code_architect.py` |
| Command | `python -m aureon_fusion.repair --root /tmp/plug-demo` |
| Result | **pass** |

The repair changes the implementation the tests name. That includes trading size and evidence gates. The Queen writer can also write `AUREON_LIVE_TRADING=1`, `may_act = True`, `gate = "RELEASE"`, and a local `.env`. `AUREON_SELF_REPAIR_KILL=1` is the operator stop and is off unless set.

A desk module that returned `0` and `"HOLD"` was repaired to `return 1` and `return "RELEASE"` because `position_qty(100) == 1` and `evidence_gate() == "RELEASE"`. The test file was not edited. An earlier command-line run repaired `return a - b` to `return a + b` and `return "off"` to `return "on"`, commit `aea0464` on `aureon-self-repair/20261022174430`.

```
cd aureon-os-upstream && PYTHONPATH=. python3 -m pytest tests/test_sandbox_self_repair.py -q --tb=line
.......                                                                  [100%]
7 passed
```

`aureon/autonomous/aureon_internal_self_coder.py` remains the model-backed coder. With `AUREON_CODE_AUTO_APPROVE=1` it applies an approved patch and runs the checks. Its senior release review still raises `release_review_entrypoint_disabled_proposal_only` until a durable proposal vault exists. The command above is the repair that runs without that vault.

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
