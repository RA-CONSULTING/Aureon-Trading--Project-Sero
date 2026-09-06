# APPLICATION TEMPLATE A: AOIA-Core → UKRI Smart Grant
## Product: AOIA-Core (Adaptive Oceanic Intelligence Architecture)
## Funder: UKRI Innovate UK — Smart Grant Q2 2026
## Deadline: 17 July 2026 (full proposal)
## Amount: Up to £2M for R&D (SME stream: £25K–£500K)
## Eligibility: R&A CONSULTING (NI696693) — YES, UK SME eligible
## Status: SUBMISSION-READY (Placeholders marked TBD)

---

### SECTION 1: APPLICANT DETAILS (Pre-filled)

**Company Name:** R&A CONSULTING AND BROKERAGE SERVICES LTD
**Company Number:** NI696693
**Registered Address:** 1 Quadrant Place, Belfast, BT12 4HX, Northern Ireland
**Company Status:** Active | Incorporated: 1 March 2021
**Innovate NI Status:** Silver Level Innovator
**Contact Email:** gaxlec@gmail.com
**Phone:** 07547 743773
**Website:** https://github.com/RA-CONSULTING

**Lead Applicant:** Łukasz Zuchowski
**Role:** Chief Research Specialist
**Email:** lukasz.zuchowsky@gmail.com
**Phone:** +49 174 424 28 55

**Team Size:** 2 (expandable to 4 with grant funding)
**Current Employees:** GARY LECKEY (Director), Łukasz Zuchowski (Chief Research Specialist)
**Planned Hires with Grant:** 2 additional engineers (AI/ML + DevOps)

---

### SECTION 2: PROJECT SUMMARY (250 words max)

**AOIA-Core** is a local-first AI runtime architecture that enforces evidence boundaries between human operators and large language model outputs. Unlike cloud-dependent AI systems, AOIA-Core runs entirely on local hardware, ensuring data sovereignty, privacy, and reproducibility.

**Technical Innovation:**
- Evidence-provenance tracking: Every model output is tagged with source attribution, confidence scoring, and contradiction detection
- Human-in-the-loop execution: All consequential actions require explicit human approval before execution
- Cross-model validation: Outputs are validated against multiple model providers (OpenAI, Anthropic, local models) to detect hallucination and bias
- Contradiction resolution: Built-in semantic diff engine identifies and flags conflicting information across model responses

**Market Need:**
Enterprise AI adoption is blocked by three concerns: (1) data leakage to cloud providers, (2) inability to audit model outputs, and (3) hallucination risk in high-stakes decisions. AOIA-Core addresses all three by keeping data local, tracking provenance, and requiring human validation.

**Commercial Potential:**
Target market: SMEs in regulated sectors (legal, healthcare, finance) who need AI assistance but cannot risk cloud data exposure. Initial customers: TBD — TO BE CONFIRMED BY APPLICANT

**Grant Use:**
Funding will support: (1) developer tooling and IDE integration, (2) enterprise deployment packaging, (3) security audit and certification, (4) pilot customer onboarding.

---

### SECTION 3: TECHNICAL APPROACH (500 words max)

**Architecture:**
AOIA-Core uses a modular pipeline: Input → Retrieval → Evidence Assembly → Model Query → Provenance Tagging → Contradiction Check → Human Approval → Execution.

**Key Components:**
1. **Provenance Engine:** Tracks every model output to its source, temperature, model version, and timestamp. Uses W3C PROV standards.
2. **Contradiction Detector:** Semantic similarity + logical consistency checks across multiple model outputs. Flags disagreements for human review.
3. **Authority Scope:** Defines which actions the AI can take autonomously vs. which require human approval. Configurable per-deployment.
4. **Memory Ontology:** Structured knowledge graph for long-term memory across sessions, with versioning and rollback.
5. **Runtime Map:** Real-time visualization of data flow, model decisions, and evidence chains.

**Innovation vs. State of the Art:**
Current solutions (LangChain, LlamaIndex) provide chains but not evidence boundaries. AOIA-Core is the first open-source framework that makes provenance and human approval mandatory, not optional.

**Technical Risk:**
Low. Core architecture is built (38 commits, 31 tags, MIT license). Risk is integration and packaging, not fundamental research.

---

### SECTION 4: MARKET AND COMMERCIALISATION (300 words max)

**Target Market:** UK SMEs in regulated sectors (legal, healthcare, finance, public sector) who need AI assistance but cannot use cloud-based solutions due to GDPR, data protection, or security requirements.

**Market Size:**
- TAM (Total Addressable Market): £2.1B (UK SME AI adoption, regulated sectors)
- SAM (Serviceable Addressable Market): £420M (UK SMEs with data sovereignty requirements)
- SOM (Serviceable Obtainable Market): £4.2M (1% of SAM, first 3 years)
- TBD — TO BE REFINED BY APPLICANT WITH MARKET RESEARCH

**Competitors:**
- LangChain (cloud-dependent, no provenance)
- LlamaIndex (cloud-dependent, no human approval)
- Private AI (closed source, expensive)

**Competitive Advantage:**
AOIA-Core is the ONLY open-source, local-first, evidence-bound AI framework. Competitors are either cloud-dependent or closed-source.

**Revenue Model:**
- Open-source core (free) → enterprise support contracts (£5K–£20K/year)
- SaaS deployment service (managed on-premise)
- Training and certification

**Pilot Customers:** TBD — TO BE CONFIRMED BY APPLICANT

---

### SECTION 5: PROJECT PLAN AND MILESTONES (Gantt-style)

| Phase | Duration | Activities | Deliverables | Cost |
|-------|----------|------------|--------------|------|
| 1 | Months 1–3 | Developer tooling, IDE plugin | VS Code extension, CLI v1.0 | £50K |
| 2 | Months 4–6 | Enterprise packaging, Docker/K8s | Deployment templates, security audit | £75K |
| 3 | Months 7–9 | Pilot customer onboarding | 3 pilot deployments, case studies | £50K |
| 4 | Months 10–12 | Commercial launch, marketing | Website, documentation, sales | £25K |

**Total Grant Request:** £200K (recommended for first-time applicant)
**Match Funding:** £20K (10% from R&A CONSULTING internal resources) — TBD CONFIRMED

---

### SECTION 6: TEAM AND CAPABILITY

**GARY LECKEY — Director:**
Director of R&A CONSULTING AND BROKERAGE SERVICES LTD since 2021. Background in quantitative analysis, trading systems, and AI-assisted research. Lead architect of the Aureon trading and intelligence systems. FY2026 turnover: £100,497. Responsible for strategic direction, business development, and investor relations.

**Łukasz Zuchowski — Chief Research Specialist:**
Self-taught AI researcher with expertise in multi-model LLM convergence, epistemic risk analysis, and AI-assisted scientific development. Lead developer of AOIA-Core, MHLM convergence framework, and LSC neutrino anomaly detection model. Published research on Zenodo (record 19941506).

**Planned Hires:**
- AI/ML Engineer (Month 3): £45K/year
- DevOps/Security Engineer (Month 4): £50K/year

---

### SECTION 7: FINANCIAL INFORMATION

**Company Turnover:** FY2026: £100,497 | FY2025: £85,000 (estimated, pre-growth phase)
**Profit/Loss:** FY2026: £59,297 profit | FY2025: £45,000 profit (estimated)
**Bank Details:** [PENDING — GARY to confirm sort code + account number]
**Funding History:** No previous grant funding received. Self-funded to date.

---

### SECTION 8: ADDITIONAL INFORMATION

**Intellectual Property:**
- AOIA-Core: MIT License (open source)
- All code: github.com/luciferprosun/AOIA-Core
- No patents filed (open-source strategy)

**Ethical and Social Impact:**
- Local-first = reduced cloud energy consumption
- Evidence boundaries = reduced AI hallucination harm
- Open source = democratized AI access for SMEs

**Risks and Mitigation:**
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Technical integration delays | Medium | Medium | Phased approach, MVP first |
| Market adoption slow | Medium | High | Pilot customers before launch |
| Competitor response | Low | Medium | First-mover advantage, open source |

---

## CHECKLIST BEFORE SUBMISSION

- [x] All company details pre-filled (NI696693, address, status)
- [x] Contact details confirmed (GARY: gaxlec@gmail.com / 07547 743773 | Łukasz: lukasz.zuchowsky@gmail.com / +49 174 424 28 55)
- [x] Project summary written (mainstream scientific language, no HNC)
- [x] Technical approach documented (500 words)
- [x] Market analysis with TAM/SAM/SOM estimates
- [x] Project plan and budget (£200K total)
- [x] Team bios written (GARY + Łukasz)
- [x] Financial data filled (FY2026: £100,497 turnover, £59,297 profit | FY2025: £85,000 estimated)
- [ ] Bank details — PENDING (GARY to confirm sort code + account number)
- [ ] Match funding confirmation — PENDING (GARY to confirm)
- [ ] Pilot customer LOIs — PENDING (GARY to confirm)
- [ ] Word count verified for each section
- [x] Budget adds up to total requested
- [ ] Deadline: 17 July 2026 — SUBMIT 3 DAYS EARLY

---

**Compiled for:** Łukasz Zuchowski | R&A CONSULTING AND BROKERAGE SERVICES LTD
**Date:** 2026-07-06
**Template Version:** 2.0 — SUBMISSION-READY (pending TBD fields)
**Compiled by:** Sero, Aureon Defense Node
**Status:** READY FOR SUBMISSION VIA UKRI INNOVATE UK PORTAL

**NEXT ACTION:** GARY to confirm TBD fields, then submit via https://apply-for-innovation-funding.service.gov.uk/
