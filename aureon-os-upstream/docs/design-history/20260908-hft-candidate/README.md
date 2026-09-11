# September 2026 UI source reconciliation

The release uses the installed and tested UI from the live workspace. The earlier Sero clone remains unchanged locally. Its untracked HFT mount map and page are preserved here as historical, noncompiled reference material.

The earlier nav edit already added the HFT route. The current nav keeps it and connects the reviewed Repo Map, War Room and Live Bridge pages, with descriptions that distinguish source observations from readiness claims. The current HFT page delegates to the common glass/evidence components and shared terminal poller; the superseded page had its own polling hook, browser trading controls and incomplete freshness behavior. The current source preserves the design's UI-RTT versus execution-latency distinction without restoring those earlier controls.

The current Vite configuration retains the earlier terminal/status proxy split and adds the tested loopback ingress, operator authorization injection, precise Orca observations proxy, strict local port and preview handling. The earlier 0.0.0.0:8080 development listener is intentionally not restored. Cloud exposure is a separate deployment composition.

The installed frontend/HFT_UI_CARDS.md remains the current evidence contract. HFT_UI_CARDS.reference.md and HftDeskPage.reference.tsx.txt are provenance only; no route imports either reference. The bridge modification in the old clone exactly matches the current source and is included through normal source staging.

Source-to-staged hashes and retained security/portability decisions are recorded in the release audit pack. No source copy or design document is evidence of live order execution, provider approval or release of the deployment hold.
