# Aureon Ollama Cognitive Bridge

- status: ollama_cognitive_bridge_blocked_by_cognitive_sources
- generated_at: 2026-09-04T18:01:03.693720+00:00
- ollama_reachable: True
- resolved_model: kimi-k2.7-code
- hnc_auris_ready: False
- metacognitive_ready: False
- hand_in_hand_ready: False

## Crew
- Phi Chat Steward: Accept the human message, redact context, and keep the dashboard conversation live.
- Aureon Metacognitive Context Builder: Gather HNC/Auris, cognitive, voice, role, and skill evidence before the model answers.
- Ollama Language Worker: Generate local language responses through the installed Ollama model when reachable.
- Aureon Brain Fallback: Keep reasoning available when the local model is offline, slow, or blocked by audit mode.
- HNC/Auris Drift Inspector: Hold claims when harmonic, node, or cognitive proof is missing or stale.
- ThoughtBus Evidence Clerk: Publish chat and bridge status evidence without leaking secrets.

## Proof Checklist
- pass: Configured Ollama local/cloud endpoint is reachable (https://ollama.com)
- pass: Ollama model catalog is visible (glm-5.2, minimax-m2.7, minimax-m3, qwen3.5:397b, nemotron-3-super, deepseek-v4-pro:0813)
- pass: A chat model is resolved for Aureon (kimi-k2.7-code)
- hold: HNC/Auris context is ready for guarded conversation (sources=2)
- hold: Aureon metacognitive evidence is present (sources=2)
- hold: Agent roles can declare who, what, where, when, how, and act (agent company / creative guardian)
- pass: Aureon Brain fallback is declared when Ollama is unavailable (AureonHybridAdapter falls back to AureonBrainAdapter)
- pass: Existing live-action and credential gates remain authoritative (no bypass introduced)

## Next Actions
- refresh_cognitive_proof: Refresh HNC/Auris, cognitive evidence, and creative-process guardian reports.
- use_hybrid_backend: Use the hand-in-hand voice backend for the dashboard chat lane.
