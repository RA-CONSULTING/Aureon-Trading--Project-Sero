from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aureon" / "exchanges"))

from trading_gate_evidence import (  # noqa: E402
    build_opportunity_evidence,
    build_source_evidence,
    build_trading_gate_evidence,
    read_analysis_policy,
)


NOW = 1_788_894_000.0


class TradingGateEvidenceTests(unittest.TestCase):
    def source(self):
        return build_source_evidence(
            [
                {"source": "provider-a", "source_timestamp": NOW - 2, "max_age_sec": 5},
                {"source": "provider-b", "source_timestamp": NOW - 1, "max_age_sec": 10},
            ],
            now_epoch=NOW,
            clock_skew_sec=5,
        )

    def candidate(self, candidate_id="candidate-a", timestamp=NOW - 1):
        return {
            "candidate_id": candidate_id,
            "data_status": "live",
            "actionable": True,
            "market_observations": [
                {
                    "source": "provider-a",
                    "feed": "live_stream_cache",
                    "source_timestamp": timestamp,
                    "max_age_sec": 5,
                }
            ],
        }

    def analysis_policy(self):
        return {
            "available": True,
            "truth_status": "real_derived",
            "generated_values": False,
            "source": "operator-versioned-policy",
            "source_timestamp": NOW - 1,
            "source_timestamp_iso": "2026-09-08T19:59:59Z",
            "policy_id": "policy-2026-09-08",
            "required_gates": ["auris", "lighthouse", "qgita"],
            "auris_min_coherence": 0.5,
            "lighthouse_min_confidence": 0.5,
            "lhe_required": False,
            "allowed_qgita_tiers": ["Gold", "Blue"],
            "execution_authority": False,
            "reason": "operator_versioned_analysis_policy_loaded_execution_hold_preserved",
        }

    def qgita(self):
        return {
            "available": True,
            "truth_status": "real_derived",
            "generated_values": False,
            "source": "central_beat_history.provider_timestamps",
            "symbol": "BTCUSD",
            "tier": "Blue",
            "confidence": 0.5,
            "source_timestamp": NOW - 1,
            "sample_count": 12,
            "samples_needed": 0,
            "analysis_status": "complete",
            "lighthouse_confidence": 0.5,
            "lighthouse_intensity": 0.04,
            "lighthouse_threshold": 0.2,
            "lhe_count": 0,
        }

    def test_source_receipt_preserves_provider_window_and_earliest_expiry(self):
        source = self.source()
        self.assertTrue(source["available"])
        self.assertEqual(source["source_timestamp"], NOW - 2)
        self.assertEqual(source["newest_source_timestamp"], NOW - 1)
        self.assertEqual(source["expires_at"], NOW + 3)
        self.assertEqual(source["observation_count"], 2)
        self.assertFalse(source["generated_values"])

    def test_stale_future_and_malformed_observations_do_not_become_evidence(self):
        for timestamp in (NOW - 6, NOW + 6, None, float("nan")):
            source = build_source_evidence(
                [{"source": "provider", "source_timestamp": timestamp, "max_age_sec": 5}],
                now_epoch=NOW,
                clock_skew_sec=5,
            )
            self.assertFalse(source["available"])
            self.assertIsNone(source["source_timestamp"])

    def test_candidate_identity_is_counted_once_across_routes(self):
        first = self.candidate("same-candidate")
        second = self.candidate("same-candidate", NOW - 0.5)
        first["execution_routes"] = [{"venue": "kraken"}]
        second["execution_routes"] = [{"venue": "binance"}]
        evidence = build_opportunity_evidence(
            [first, second],
            market_source=self.source(),
            now_epoch=NOW,
            clock_skew_sec=5,
        )
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["active_order_flow_count"], 1)

    def test_invalid_candidate_is_unavailable_not_a_synthetic_zero(self):
        candidate = self.candidate(timestamp=NOW - 30)
        evidence = build_opportunity_evidence(
            [candidate],
            market_source=self.source(),
            now_epoch=NOW,
            clock_skew_sec=5,
        )
        self.assertFalse(evidence["available"])
        self.assertIsNone(evidence["active_order_flow_count"])

    def test_partial_stale_candidate_observations_do_not_hide_current_route(self):
        source = self.source()
        candidate = self.candidate("candidate-with-current-and-stale")
        candidate["market_observations"].append({
            "source": "provider-a",
            "feed": "live_stream_cache",
            "source_timestamp": NOW - 30,
            "max_age_sec": 5,
        })

        evidence = build_opportunity_evidence(
            [candidate], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )

        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["active_order_flow_count"], 1)
        self.assertEqual(evidence["invalid_candidate_count"], 1)
        self.assertGreaterEqual(evidence["observation_count"], 1)

    def test_zero_is_reported_only_when_fresh_market_evaluation_is_proven(self):
        current = build_opportunity_evidence(
            [], market_source=self.source(), now_epoch=NOW, clock_skew_sec=5,
        )
        missing = build_opportunity_evidence(
            [], market_source={}, now_epoch=NOW, clock_skew_sec=5,
        )
        self.assertTrue(current["available"])
        self.assertEqual(current["active_order_flow_count"], 0)
        self.assertFalse(missing["available"])
        self.assertIsNone(missing["active_order_flow_count"])

    def test_receipt_keeps_unproved_policy_lighthouse_lhe_and_qgita_unavailable(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [self.candidate()], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": True},
            source_evidence=source,
            auris={"evaluated": True, "data_status": "live", "coherence": 0.72},
            opportunities=opportunities,
            generated_at_epoch=NOW,
        )
        self.assertTrue(receipt["auris"]["available"])
        self.assertEqual(receipt["auris"]["coherence"], 0.72)
        self.assertIsNone(receipt["auris"]["threshold"])
        self.assertFalse(receipt["analysis_policy"]["available"])
        self.assertFalse(receipt["lighthouse"]["available"])
        self.assertFalse(receipt["lhe"]["available"])
        self.assertFalse(receipt["qgita"]["available"])
        self.assertFalse(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        json.dumps(receipt, allow_nan=False)

    def test_provider_source_stays_available_when_auris_metrics_drop_out(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": False, "blockers": ["finite_provider_market_rows_unavailable"]},
            source_evidence=source,
            auris={"evaluated": False, "data_status": "no_data", "coherence": None},
            opportunities=opportunities,
            generated_at_epoch=NOW,
        )

        self.assertEqual(receipt["truth_status"], "real_derived")
        self.assertTrue(receipt["source"]["available"])
        self.assertNotIn("fresh_provider_gate_source_unavailable", receipt["analysis_blockers"])
        self.assertIn("auris_measurement_unavailable", receipt["analysis_blockers"])
        self.assertFalse(receipt["auris"]["available"])
        self.assertFalse(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        json.dumps(receipt, allow_nan=False)

    def test_fresh_lighthouse_event_is_evidence_without_authorizing_policy(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [self.candidate()], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": True},
            source_evidence=source,
            auris={"evaluated": True, "data_status": "live", "coherence": 0.72},
            opportunities=opportunities,
            generated_at_epoch=NOW,
            lighthouse_event={
                "available": True,
                "truth_status": "real_derived",
                "generated_values": False,
                "source": "state/lighthouse_event.jsonl",
                "source_timestamp": NOW - 1,
                "confidence": 0.61,
                "event_type": "lighthouse.harmonic_convergence",
                "event_types": ["lighthouse.harmonic_convergence"],
                "event_count": 1,
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "is_lhe": True,
            },
        )

        self.assertTrue(receipt["lighthouse"]["available"])
        self.assertEqual(receipt["lighthouse"]["confidence"], 0.61)
        self.assertTrue(receipt["lhe"]["available"])
        self.assertTrue(receipt["lhe"]["is_lhe"])
        self.assertIn("authoritative_trading_gate_policy_unavailable", receipt["analysis_blockers"])
        self.assertIn("qgita_runtime_evidence_unavailable", receipt["analysis_blockers"])
        self.assertNotIn("lighthouse_runtime_evidence_unavailable", receipt["analysis_blockers"])
        self.assertNotIn("lhe_runtime_evidence_unavailable", receipt["analysis_blockers"])
        self.assertFalse(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        json.dumps(receipt, allow_nan=False)

    def test_qgita_measurement_is_source_evidence_without_policy_authority(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [self.candidate()], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": True},
            source_evidence=source,
            auris={"evaluated": True, "data_status": "live", "coherence": 0.72},
            opportunities=opportunities,
            generated_at_epoch=NOW,
            qgita={
                "available": True,
                "truth_status": "real_derived",
                "generated_values": False,
                "source": "central_beat_history.provider_timestamps",
                "symbol": "BTCUSD",
                "tier": "Blue",
                "confidence": 0.5,
                "source_timestamp": NOW - 1,
                "sample_count": 12,
                "samples_needed": 0,
                "analysis_status": "complete",
            },
        )

        self.assertTrue(receipt["qgita"]["available"])
        self.assertEqual(receipt["qgita"]["tier"], "Blue")
        self.assertNotIn("qgita_runtime_evidence_unavailable", receipt["analysis_blockers"])
        self.assertIn("authoritative_trading_gate_policy_unavailable", receipt["analysis_blockers"])
        self.assertFalse(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        json.dumps(receipt, allow_nan=False)


    def test_versioned_analysis_policy_evaluates_required_gates_without_execution_authority(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [self.candidate()], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": True},
            source_evidence=source,
            auris={"evaluated": True, "data_status": "live", "coherence": 0.72},
            opportunities=opportunities,
            generated_at_epoch=NOW,
            qgita=self.qgita(),
            analysis_policy=self.analysis_policy(),
        )

        self.assertTrue(receipt["analysis_policy"]["available"])
        self.assertEqual(receipt["analysis_policy"]["required_gates"], ["auris", "lighthouse", "qgita"])
        self.assertTrue(receipt["auris"]["passed"])
        self.assertTrue(receipt["lighthouse"]["passed"])
        self.assertTrue(receipt["lhe"]["passed"])
        self.assertTrue(receipt["qgita"]["passed"])
        self.assertTrue(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        self.assertEqual(receipt["analysis_blockers"], [])
        json.dumps(receipt, allow_nan=False)

    def test_qgita_stage_two_can_supply_lighthouse_measurement_when_event_log_is_stale(self):
        source = self.source()
        opportunities = build_opportunity_evidence(
            [self.candidate()], market_source=source, now_epoch=NOW, clock_skew_sec=5,
        )
        receipt = build_trading_gate_evidence(
            source_metrics={"passed": True},
            source_evidence=source,
            auris={"evaluated": True, "data_status": "live", "coherence": 0.72},
            opportunities=opportunities,
            generated_at_epoch=NOW,
            lighthouse_event={"available": False, "truth_status": "unavailable", "generated_values": False},
            qgita=self.qgita(),
            analysis_policy=self.analysis_policy(),
        )

        self.assertTrue(receipt["lighthouse"]["available"])
        self.assertEqual(receipt["lighthouse"]["source"], "central_beat_history.qgita_stage2_lighthouse")
        self.assertEqual(receipt["lighthouse"]["confidence"], 0.5)
        self.assertEqual(receipt["lighthouse"]["qgita_lighthouse_intensity"], 0.04)
        self.assertEqual(receipt["lighthouse"]["qgita_lighthouse_threshold"], 0.2)
        self.assertTrue(receipt["analysis_ready"])
        self.assertFalse(receipt["execution_authority"])
        json.dumps(receipt, allow_nan=False)

    def test_policy_file_refuses_execution_authority(self):
        with TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            policy_path.write_text(json.dumps({
                "schema": "aureon.trading_gate.analysis_policy.v1",
                "policy_id": "unsafe",
                "scope": "analysis_only_no_execution_authority",
                "generated_values": False,
                "source": "policy.json",
                "required_gates": ["auris", "lighthouse", "qgita"],
                "auris_min_coherence": 0.5,
                "lighthouse_min_confidence": 0.5,
                "lhe_required": False,
                "allowed_qgita_tiers": ["Gold", "Blue"],
                "execution_authority": True,
            }), encoding="utf-8")
            policy = read_analysis_policy(policy_path)

        self.assertFalse(policy["available"])
        self.assertEqual(policy["reason"], "authoritative_trading_gate_policy_execution_authority_rejected")
        self.assertFalse(policy["execution_authority"])


if __name__ == "__main__":
    unittest.main()
