"""Truth-preserving evidence contracts for the read-only War Room gate surface.

This module never authorizes execution.  It only describes provider-timestamped
observations that were still current when a runtime cycle evaluated them.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

_ALLOWED_POLICY_GATES = {"auris", "lighthouse", "lhe", "qgita"}


def _finite_number(value: Any, *, positive: bool = False) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or (positive and number <= 0.0):
        return None
    return number


def _utc_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(value: Any) -> Optional[List[str]]:
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        text = _text(item)
        if text is None:
            return None
        result.append(text)
    return result


def _unavailable_source(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "truth_status": "unavailable",
        "generated_values": False,
        "reason": reason,
        "source_timestamp": None,
        "source_timestamp_iso": None,
        "newest_source_timestamp": None,
        "newest_source_timestamp_iso": None,
        "expires_at": None,
        "expires_at_iso": None,
        "freshness_limit_sec": None,
        "observation_count": 0,
        "source_names": [],
    }


def _unavailable_policy(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "truth_status": "unavailable",
        "generated_values": False,
        "source": None,
        "source_timestamp": None,
        "source_timestamp_iso": None,
        "policy_id": None,
        "required_gates": None,
        "auris_min_coherence": None,
        "lighthouse_min_confidence": None,
        "lhe_required": None,
        "allowed_qgita_tiers": None,
        "execution_authority": False,
        "reason": reason,
    }


def read_analysis_policy(path: Optional[Any] = None) -> Dict[str, Any]:
    """Read the operator-versioned analysis policy without granting execution authority."""
    policy_path = Path(path) if path is not None else Path(__file__).with_name("trading_gate_analysis_policy.json")
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
        source_timestamp = policy_path.stat().st_mtime
    except FileNotFoundError:
        return _unavailable_policy("authoritative_trading_gate_policy_unavailable")
    except (OSError, json.JSONDecodeError):
        return _unavailable_policy("authoritative_trading_gate_policy_unreadable")

    if not isinstance(raw, Mapping):
        return _unavailable_policy("authoritative_trading_gate_policy_malformed")
    if raw.get("generated_values") is not False:
        return _unavailable_policy("authoritative_trading_gate_policy_generated_values_rejected")
    if raw.get("execution_authority") is not False:
        return _unavailable_policy("authoritative_trading_gate_policy_execution_authority_rejected")

    policy_id = _text(raw.get("policy_id"))
    source = _text(raw.get("source")) or policy_path.as_posix()
    required_gates = _string_list(raw.get("required_gates"))
    auris_min_coherence = _finite_number(raw.get("auris_min_coherence"))
    lighthouse_min_confidence = _finite_number(raw.get("lighthouse_min_confidence"))
    allowed_qgita_tiers = _string_list(raw.get("allowed_qgita_tiers"))
    lhe_required = raw.get("lhe_required")

    if policy_id is None or required_gates is None or not required_gates:
        return _unavailable_policy("authoritative_trading_gate_policy_malformed")
    if any(gate not in _ALLOWED_POLICY_GATES for gate in required_gates):
        return _unavailable_policy("authoritative_trading_gate_policy_unknown_gate")
    if auris_min_coherence is None or not 0.0 <= auris_min_coherence <= 1.0:
        return _unavailable_policy("authoritative_trading_gate_policy_bad_auris_threshold")
    if lighthouse_min_confidence is None or not 0.0 <= lighthouse_min_confidence <= 1.0:
        return _unavailable_policy("authoritative_trading_gate_policy_bad_lighthouse_threshold")
    if not isinstance(lhe_required, bool):
        return _unavailable_policy("authoritative_trading_gate_policy_bad_lhe_required")
    if allowed_qgita_tiers is None or not allowed_qgita_tiers:
        return _unavailable_policy("authoritative_trading_gate_policy_bad_qgita_tiers")

    return {
        "available": True,
        "truth_status": "real_derived",
        "generated_values": False,
        "source": source,
        "source_timestamp": source_timestamp,
        "source_timestamp_iso": _utc_iso(source_timestamp),
        "policy_id": policy_id,
        "required_gates": required_gates,
        "auris_min_coherence": auris_min_coherence,
        "lighthouse_min_confidence": lighthouse_min_confidence,
        "lhe_required": lhe_required,
        "allowed_qgita_tiers": allowed_qgita_tiers,
        "execution_authority": False,
        "reason": str(raw.get("reason") or "operator_versioned_analysis_policy_loaded_execution_hold_preserved"),
    }


def build_source_evidence(
    observations: Iterable[Mapping[str, Any]],
    *,
    now_epoch: float,
    clock_skew_sec: float,
) -> Dict[str, Any]:
    """Build a receipt from original provider clocks, never assembly time."""
    accepted: List[Dict[str, Any]] = []
    for observation in observations:
        timestamp = _finite_number(observation.get("source_timestamp"), positive=True)
        max_age_sec = _finite_number(observation.get("max_age_sec"), positive=True)
        source = str(observation.get("source") or observation.get("feed") or "").strip()
        if timestamp is None or max_age_sec is None or not source:
            continue
        age_sec = now_epoch - timestamp
        if age_sec < -clock_skew_sec or age_sec > max_age_sec:
            continue
        accepted.append({
            "source_timestamp": timestamp,
            "max_age_sec": max_age_sec,
            "source": source,
        })

    if not accepted:
        return _unavailable_source("fresh_provider_observations_unavailable")

    oldest = min(row["source_timestamp"] for row in accepted)
    newest = max(row["source_timestamp"] for row in accepted)
    expires_at = min(row["source_timestamp"] + row["max_age_sec"] for row in accepted)
    return {
        "available": True,
        "truth_status": "real_derived",
        "generated_values": False,
        "reason": "fresh_original_provider_timestamps_verified",
        "source_timestamp": oldest,
        "source_timestamp_iso": _utc_iso(oldest),
        "newest_source_timestamp": newest,
        "newest_source_timestamp_iso": _utc_iso(newest),
        "expires_at": expires_at,
        "expires_at_iso": _utc_iso(expires_at),
        # Informational only. Consumers use expires_at because observations can
        # have different source-specific limits.
        "freshness_limit_sec": min(row["max_age_sec"] for row in accepted),
        "observation_count": len(accepted),
        "source_names": sorted({row["source"] for row in accepted}),
    }


def build_opportunity_evidence(
    candidates: Iterable[Mapping[str, Any]],
    *,
    market_source: Mapping[str, Any],
    now_epoch: float,
    clock_skew_sec: float,
) -> Dict[str, Any]:
    """Count current candidate identities once, even when routed to many venues."""
    candidates = [candidate for candidate in candidates if isinstance(candidate, Mapping)]
    if not candidates:
        if market_source.get("available") is True:
            return {
                **dict(market_source),
                "reason": "live_order_flow_evaluated_no_candidates",
                "active_order_flow_count": 0,
            }
        return {
            **_unavailable_source("order_flow_and_fresh_market_source_unavailable"),
            "active_order_flow_count": None,
        }

    identities = set()
    candidate_observations: List[Mapping[str, Any]] = []
    invalid_candidate_count = 0
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        observations = candidate.get("market_observations")
        if (
            not candidate_id
            or candidate.get("data_status") != "live"
            or candidate.get("actionable") is not True
            or not isinstance(observations, list)
            or not observations
        ):
            invalid_candidate_count += 1
            continue
        evidence = build_source_evidence(
            [row for row in observations if isinstance(row, Mapping)],
            now_epoch=now_epoch,
            clock_skew_sec=clock_skew_sec,
        )
        accepted_count = int(evidence.get("observation_count", 0) or 0)
        if evidence.get("available") is not True or accepted_count <= 0:
            invalid_candidate_count += 1
            continue
        if accepted_count < len([row for row in observations if isinstance(row, Mapping)]):
            invalid_candidate_count += 1
        identities.add(candidate_id)
        candidate_observations.extend(row for row in observations if isinstance(row, Mapping))

    source = build_source_evidence(
        candidate_observations,
        now_epoch=now_epoch,
        clock_skew_sec=clock_skew_sec,
    )
    if not identities or source.get("available") is not True:
        return {
            **_unavailable_source("current_candidate_market_observations_unavailable"),
            "active_order_flow_count": None,
            "invalid_candidate_count": invalid_candidate_count,
        }
    return {
        **source,
        "reason": "unique_current_order_flow_candidates",
        "active_order_flow_count": len(identities),
        "invalid_candidate_count": invalid_candidate_count,
    }


def _qgita_lighthouse_event(qgita: Mapping[str, Any]) -> Dict[str, Any]:
    confidence = _finite_number(qgita.get("lighthouse_confidence"))
    timestamp = _finite_number(qgita.get("source_timestamp"), positive=True)
    if (
        qgita.get("available") is not True
        or qgita.get("truth_status") != "real_derived"
        or qgita.get("generated_values") is not False
        or confidence is None
        or not 0.0 <= confidence <= 1.0
        or timestamp is None
    ):
        return {}
    lhe_count = qgita.get("lhe_count")
    event_count = int(lhe_count) if isinstance(lhe_count, int) and not isinstance(lhe_count, bool) and lhe_count >= 0 else 0
    symbol = _text(qgita.get("symbol"))
    return {
        "available": True,
        "truth_status": "real_derived",
        "generated_values": False,
        "source": "central_beat_history.qgita_stage2_lighthouse",
        "source_timestamp": timestamp,
        "confidence": confidence,
        "event_type": "qgita_stage2.lighthouse",
        "event_types": ["qgita_stage2.lighthouse"],
        "event_count": event_count,
        "symbols": [symbol] if symbol else [],
        "is_lhe": event_count > 0,
    }


def build_trading_gate_evidence(
    *,
    source_metrics: Mapping[str, Any],
    source_evidence: Mapping[str, Any],
    auris: Mapping[str, Any],
    opportunities: Mapping[str, Any],
    generated_at_epoch: float,
    lighthouse_event: Optional[Mapping[str, Any]] = None,
    qgita: Optional[Mapping[str, Any]] = None,
    analysis_policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a fail-closed gate receipt without inventing policy or signals."""
    source_available = bool(source_evidence.get("available") is True)
    source_metrics_available = bool(source_metrics.get("passed") is True)
    coherence = _finite_number(auris.get("coherence"))
    auris_available = bool(
        source_available
        and source_metrics_available
        and auris.get("evaluated") is True
        and auris.get("data_status") == "live"
        and coherence is not None
        and 0.0 <= coherence <= 1.0
    )

    qgita = qgita if isinstance(qgita, Mapping) else {}
    qgita_tier = str(qgita.get("tier") or "").strip()
    qgita_confidence = _finite_number(qgita.get("confidence"))
    qgita_timestamp = _finite_number(qgita.get("source_timestamp"), positive=True)
    qgita_lighthouse_confidence = _finite_number(qgita.get("lighthouse_confidence"))
    qgita_lighthouse_intensity = _finite_number(qgita.get("lighthouse_intensity"))
    qgita_lighthouse_threshold = _finite_number(qgita.get("lighthouse_threshold"), positive=True)
    qgita_lhe_count = qgita.get("lhe_count")
    qgita_lhe_count_value = (
        int(qgita_lhe_count)
        if isinstance(qgita_lhe_count, int) and not isinstance(qgita_lhe_count, bool) and qgita_lhe_count >= 0
        else None
    )
    qgita_available = bool(
        qgita.get("available") is True
        and qgita.get("truth_status") == "real_derived"
        and qgita.get("generated_values") is False
        and qgita_tier
        and qgita_confidence is not None
        and 0.0 <= qgita_confidence <= 1.0
        and qgita_timestamp is not None
    )

    lighthouse_event = lighthouse_event if isinstance(lighthouse_event, Mapping) else {}
    lighthouse_confidence = _finite_number(lighthouse_event.get("confidence"))
    lighthouse_timestamp = _finite_number(lighthouse_event.get("source_timestamp"), positive=True)
    lighthouse_available = bool(
        lighthouse_event.get("available") is True
        and lighthouse_event.get("truth_status") == "real_derived"
        and lighthouse_event.get("generated_values") is False
        and lighthouse_confidence is not None
        and 0.0 <= lighthouse_confidence <= 1.0
        and lighthouse_timestamp is not None
    )
    if not lighthouse_available:
        fallback_event = _qgita_lighthouse_event(qgita)
        if fallback_event:
            lighthouse_event = fallback_event
            lighthouse_confidence = _finite_number(lighthouse_event.get("confidence"))
            lighthouse_timestamp = _finite_number(lighthouse_event.get("source_timestamp"), positive=True)
            lighthouse_available = True
    is_lhe_value = lighthouse_event.get("is_lhe")
    lhe_available = bool(lighthouse_available and isinstance(is_lhe_value, bool))

    policy = analysis_policy if isinstance(analysis_policy, Mapping) else _unavailable_policy("authoritative_trading_gate_policy_unavailable")
    required_gates = _string_list(policy.get("required_gates"))
    allowed_qgita_tiers = _string_list(policy.get("allowed_qgita_tiers"))
    auris_min_coherence = _finite_number(policy.get("auris_min_coherence"))
    lighthouse_min_confidence = _finite_number(policy.get("lighthouse_min_confidence"))
    lhe_required = policy.get("lhe_required") if isinstance(policy.get("lhe_required"), bool) else None
    policy_available = bool(
        policy.get("available") is True
        and policy.get("truth_status") == "real_derived"
        and policy.get("generated_values") is False
        and policy.get("execution_authority") is False
        and _text(policy.get("source")) is not None
        and _text(policy.get("policy_id")) is not None
        and _finite_number(policy.get("source_timestamp"), positive=True) is not None
        and required_gates is not None
        and required_gates
        and all(gate in _ALLOWED_POLICY_GATES for gate in required_gates)
        and allowed_qgita_tiers is not None
        and bool(allowed_qgita_tiers)
        and auris_min_coherence is not None
        and 0.0 <= auris_min_coherence <= 1.0
        and lighthouse_min_confidence is not None
        and 0.0 <= lighthouse_min_confidence <= 1.0
        and lhe_required is not None
    )
    if not policy_available:
        policy = _unavailable_policy(str(policy.get("reason") or "authoritative_trading_gate_policy_unavailable"))
        required_gates = None
        allowed_qgita_tiers = None
        auris_min_coherence = None
        lighthouse_min_confidence = None
        lhe_required = None

    auris_passed = bool(auris_available and policy_available and coherence is not None and coherence >= auris_min_coherence) if policy_available else None
    lighthouse_passed = bool(
        lighthouse_available
        and policy_available
        and lighthouse_confidence is not None
        and lighthouse_confidence >= lighthouse_min_confidence
    ) if policy_available else None
    lhe_passed = bool(policy_available and (lhe_required is False or (lhe_available and is_lhe_value is True))) if policy_available else None
    qgita_passed = bool(qgita_available and policy_available and qgita_tier in allowed_qgita_tiers) if policy_available else None
    pass_by_gate = {
        "auris": auris_passed is True,
        "lighthouse": lighthouse_passed is True,
        "lhe": lhe_passed is True,
        "qgita": qgita_passed is True,
    }
    analysis_ready = bool(policy_available and required_gates is not None and all(pass_by_gate.get(gate) is True for gate in required_gates))

    analysis_blockers: List[str] = []
    if not source_available:
        analysis_blockers.append("fresh_provider_gate_source_unavailable")
    if not auris_available:
        analysis_blockers.append("auris_measurement_unavailable")
    if not policy_available:
        analysis_blockers.append(str(policy.get("reason") or "authoritative_trading_gate_policy_unavailable"))
    if not lighthouse_available:
        analysis_blockers.append("lighthouse_runtime_evidence_unavailable")
    elif policy_available and "lighthouse" in (required_gates or []) and lighthouse_passed is not True:
        analysis_blockers.append("lighthouse_below_policy_threshold")
    if policy_available and lhe_required is False:
        pass
    elif not lhe_available:
        analysis_blockers.append("lhe_runtime_evidence_unavailable")
    elif policy_available and "lhe" in (required_gates or []) and lhe_passed is not True:
        analysis_blockers.append("lhe_policy_required_event_absent")
    if not qgita_available:
        analysis_blockers.append("qgita_runtime_evidence_unavailable")
    elif policy_available and "qgita" in (required_gates or []) and qgita_passed is not True:
        analysis_blockers.append("qgita_tier_outside_policy")
    if policy_available and "auris" in (required_gates or []) and auris_passed is not True and auris_available:
        analysis_blockers.append("auris_below_policy_threshold")

    policy_timestamp = _finite_number(policy.get("source_timestamp"), positive=True)
    return {
        "schema_version": 1,
        "generated_at": _utc_iso(generated_at_epoch),
        "truth_status": "real_derived" if source_available else "unavailable",
        "generated_values": False,
        "source": dict(source_evidence),
        "analysis_policy": {
            "available": policy_available,
            "truth_status": "real_derived" if policy_available else "unavailable",
            "generated_values": False,
            "source": policy.get("source") if policy_available else None,
            "source_timestamp": policy_timestamp if policy_available else None,
            "source_timestamp_iso": _utc_iso(policy_timestamp) if policy_available and policy_timestamp is not None else None,
            "policy_id": policy.get("policy_id") if policy_available else None,
            "required_gates": list(required_gates) if policy_available and required_gates is not None else None,
            "auris_min_coherence": auris_min_coherence if policy_available else None,
            "lighthouse_min_confidence": lighthouse_min_confidence if policy_available else None,
            "lhe_required": lhe_required if policy_available else None,
            "allowed_qgita_tiers": list(allowed_qgita_tiers) if policy_available and allowed_qgita_tiers is not None else None,
            "execution_authority": False,
            "reason": policy.get("reason"),
        },
        "auris": {
            "available": auris_available,
            "truth_status": "real_derived" if auris_available else "unavailable",
            "generated_values": False,
            "coherence": coherence if auris_available else None,
            "threshold": auris_min_coherence if policy_available else None,
            "passed": auris_passed,
            "source_timestamp": source_evidence.get("source_timestamp") if auris_available else None,
            "source_timestamp_iso": source_evidence.get("source_timestamp_iso") if auris_available else None,
            "reason": "provider_market_texture_evaluated" if auris_available else "fresh_complete_market_texture_unavailable",
        },
        "lighthouse": {
            "available": lighthouse_available,
            "truth_status": "real_derived" if lighthouse_available else "unavailable",
            "generated_values": False,
            "confidence": lighthouse_confidence if lighthouse_available else None,
            "threshold": lighthouse_min_confidence if policy_available else None,
            "passed": lighthouse_passed,
            "source": lighthouse_event.get("source") if lighthouse_available else None,
            "source_timestamp": lighthouse_timestamp if lighthouse_available else None,
            "source_timestamp_iso": _utc_iso(lighthouse_timestamp) if lighthouse_available and lighthouse_timestamp is not None else None,
            "event_type": lighthouse_event.get("event_type") if lighthouse_available else None,
            "event_types": list(lighthouse_event.get("event_types") or []) if lighthouse_available else [],
            "event_count": lighthouse_event.get("event_count") if lighthouse_available else 0,
            "symbols": list(lighthouse_event.get("symbols") or []) if lighthouse_available else [],
            "qgita_lighthouse_intensity": qgita_lighthouse_intensity if qgita_available else None,
            "qgita_lighthouse_threshold": qgita_lighthouse_threshold if qgita_available else None,
            "reason": "fresh_lighthouse_runtime_evidence_observed" if lighthouse_available else "lighthouse_runtime_evidence_unavailable",
        },
        "lhe": {
            "available": lhe_available,
            "truth_status": "real_derived" if lhe_available else "unavailable",
            "generated_values": False,
            "required": lhe_required if policy_available else None,
            "is_lhe": bool(is_lhe_value) if lhe_available else None,
            "passed": lhe_passed,
            "source": lighthouse_event.get("source") if lhe_available else None,
            "source_timestamp": lighthouse_timestamp if lhe_available else None,
            "source_timestamp_iso": _utc_iso(lighthouse_timestamp) if lhe_available and lighthouse_timestamp is not None else None,
            "event_types": list(lighthouse_event.get("event_types") or []) if lhe_available else [],
            "event_count": qgita_lhe_count_value if qgita_lhe_count_value is not None else lighthouse_event.get("event_count", 0),
            "reason": "lhe_optional_by_policy" if policy_available and lhe_required is False else ("fresh_lighthouse_runtime_evidence_observed" if lhe_available else "lhe_runtime_evidence_unavailable"),
        },
        "qgita": {
            "available": qgita_available,
            "truth_status": "real_derived" if qgita_available else "unavailable",
            "generated_values": False,
            "tier": qgita_tier if qgita_available else None,
            "confidence": qgita_confidence if qgita_available else None,
            "passed": qgita_passed,
            "source": qgita.get("source") if qgita_available else qgita.get("source"),
            "source_timestamp": qgita_timestamp if qgita_available else None,
            "source_timestamp_iso": _utc_iso(qgita_timestamp) if qgita_available and qgita_timestamp is not None else None,
            "symbol": qgita.get("symbol") if qgita_available else qgita.get("symbol"),
            "sample_count": qgita.get("sample_count") if isinstance(qgita.get("sample_count"), int) else None,
            "samples_needed": qgita.get("samples_needed") if isinstance(qgita.get("samples_needed"), int) else None,
            "analysis_status": qgita.get("analysis_status") if qgita_available else qgita.get("analysis_status"),
            "regime": qgita.get("regime") if qgita_available else None,
            "direction": qgita.get("direction") if qgita_available else None,
            "spread_proxy": qgita.get("spread_proxy") if qgita_available else None,
            "lighthouse_confidence": qgita_lighthouse_confidence if qgita_available else None,
            "lighthouse_intensity": qgita_lighthouse_intensity if qgita_available else None,
            "lighthouse_threshold": qgita_lighthouse_threshold if qgita_available else None,
            "lhe_count": qgita_lhe_count_value if qgita_available else None,
            "reason": (
                "provider_price_history_qgita_analyzed_policy_evaluated"
                if qgita_available and policy_available
                else "provider_price_history_qgita_analyzed_policy_unavailable"
                if qgita_available
                else str(qgita.get("reason") or "qgita_runtime_evidence_unavailable")
            ),
        },
        "opportunities": dict(opportunities),
        "analysis_ready": analysis_ready,
        "analysis_blockers": analysis_blockers,
        "execution_authority": False,
    }
