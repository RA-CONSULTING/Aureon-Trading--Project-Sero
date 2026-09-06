#!/usr/bin/env bash
set -u
REAL="C:/Users/user/.kimi_openclaw/workspace"
export AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS=1 AUREON_AUDIT_MODE=1
overall=0
run() {
  local scen="$1" gamma="$2" matrix="$3"
  local ws
  ws=$(mktemp -d /tmp/lwprobe.XXXXXX)
  mkdir -p "$ws/aureon_fusion/state" "$ws/sero_autonomous_state" "$ws/sero_mycelium" "$ws/sero_memory_web" "$ws/aureon-os-upstream"
  if [ "$gamma" != "none" ]; then
    printf '{"coherence_gamma": %s}\n' "$gamma" > "$ws/aureon_fusion/state/hnc_core_state.json"
  fi
  echo "$matrix" > "$ws/sero_autonomous_state/capability_matrix.json"
  echo "=== $scen (ws=$ws) ==="
  python "$REAL/tmp/lw_probes/probe.py" "$scen" "$ws" "$REAL"
  rc=$?
  rm -rf "$ws"
  [ $rc -ne 0 ] && overall=1
  return $rc
}

WITH_ROW='{"gates":{"network_access:fetch_public_data":{"status":"active","level":"OBSERVE"}}}'
NO_ROW='{"gates":{"file_system:read_files":{"status":"active"}}}'

run gate_veto        0.9  "$WITH_ROW"
run gate_incoherent  0.1  "$WITH_ROW"
run gate_missing_row 0.9  "$NO_ROW"
run gate_missing_state none "$WITH_ROW"
run discernment      0.9  "$WITH_ROW"
run mind_augment_spy 0.9  "$WITH_ROW"
exit $overall
