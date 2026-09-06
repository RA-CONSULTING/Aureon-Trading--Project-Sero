#!/usr/bin/env python3
"""
Audit and fix all Substack articles for professional consistency.
Applies standardized author bio, company details, license, and disclaimers.
"""

import os

BASE_DIR = r"C:\Users\user\.kimi_openclaw\workspace\research\substack"

# Standard professional footer template
STANDARD_FOOTER = """\
---

**About the author:** **Gary Anthony Leckey** is the founder and director of **R&A Consulting and Brokerage Services Ltd** (company number NI696693, Companies House Northern Ireland), trading as **Aureon Zorza Technologies**. He is the principal investigator of the **Aureon Institute** and the architect of the **Harmonic Nexus Core (HNC)** framework. His work integrates theoretical physics, consciousness research, electromagnetic engineering, archaeological pattern recognition, and macroeconomic forensics into a unified, falsifiable research programme. R&A Consulting was awarded **Silver Level Innovator** status on the Innovate NI Innovation Framework by the Department for the Economy, Northern Ireland, in July 2025.

**Company:** R&A Consulting and Brokerage Services Ltd · Trading as Aureon Zorza Technologies  
**Location:** Belfast, Northern Ireland, United Kingdom  
**Website:** <https://aureonzorzatechnologies.pl>  
**Repository:** <https://github.com/RA-CONSULTING/aureon-trading>  
**License:** MIT © 2025–2026 R&A Consulting and Brokerage Services Ltd  
**Citation:** Leckey, G. A. (2026). *{title}*. Aureon Institute Research Publications.
"""

# Article-specific disclaimers
DISCLAIMERS = {
    "02_the_hnc_and_aureon_trading_framework.md": "**Disclaimer:** This research is presented for educational and investigative purposes. It does not constitute financial advice, investment recommendation, or an offer of securities. Past performance of any model or framework is not indicative of future results. The Aureon Trading Framework operates under strict safety gates; live trading requires explicit operator confirmation and regulatory compliance.",
    "09_hnc_biomolecule_frequency_packet.md": "**Disclaimer:** This article reports a computationally reproducible design and a proposed experimental protocol. It does not report completed wet-lab results, does not make a therapeutic claim, and does not claim clinical efficacy. The framework is presented as a testable hypothesis subject to empirical falsification. No human or animal trials have been conducted.",
    "14_the_math_angel_protocol.md": "**Disclaimer:** The Math Angel Protocol and Nexus System are research frameworks. The Unity Event is a measurable phase transition in a computational model; claims about consciousness as fundamental reality remain theoretical pending independent replication. No medical or therapeutic claims are made.",
    "21_project_druid_epas_defence_framework.md": "**Disclaimer:** Project Druid is a research proposal at Technology Readiness Level 2 (concept formulated, components validated individually). No flight-qualified hardware has been built. Performance claims are theoretical and require experimental validation before engineering application.",
    "22_project_alfie_hybrid_launch_system.md": "**Disclaimer:** Project Alfie is a theoretical framework and feasibility analysis. No prototype has been constructed. The required power infrastructure (14.2 TW peak) exceeds present global electrical generation capacity. The phased development roadmap represents a research programme, not a committed engineering project.",
}

articles = sorted(f for f in os.listdir(BASE_DIR) if f.endswith(".md") and f != "STYLE_GUIDE.md")

fixed_count = 0
for article in articles:
    path = os.path.join(BASE_DIR, article)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Extract title from filename for citation
    title_slug = article.replace(".md", "").replace("_", " ").title()
    # Clean up specific titles
    title_map = {
        "00_one_logic_across_many_domains.md": "One Logic Across Many Domains: Mapping the Aureon Research Programme",
        "01_the_harmonic_nexus_core_and_auris_conjecture.md": "The Harmonic Nexus Core and the Auris Conjecture",
        "02_the_hnc_and_aureon_trading_framework.md": "The HNC and the Aureon Trading Framework",
        "03_the_harmonic_nexus_theory_of_becoming.md": "The Harmonic Nexus Theory of Becoming",
        "04_unified_framework_of_symbolic_emergence.md": "Unified Framework of Symbolic Emergence",
        "05_hnc_empirical_audit_and_validation.md": "HNC Empirical Audit and Cross-Channel Validation",
        "06_project_druid_technical_architecture.md": "Project Druid: Technical Architecture for a Harmonic Defence System",
        "07_quantum_gravity_in_the_act_qgita.md": "Quantum Gravity in the Act (QGITA)",
        "08_the_luminacell_v2_contactless_quantum_core.md": "The LuminaCell v2: A Contactless Quantum Interference Core",
        "09_hnc_biomolecule_frequency_packet.md": "HNC BioMolecule Adjacent Frequency Packet",
        "10_tandem_in_unity_unifying_resonant_fields.md": "Tandem in Unity: Unifying Resonant Fields",
        "11_the_sagittarius_convergence.md": "The Sagittarius Convergence",
        "12_the_doorbell_hypothesis.md": "The Doorbell Hypothesis",
        "13_the_harmonic_solar_system_survey.md": "The Harmonic Solar System Survey",
        "14_the_math_angel_protocol.md": "The Math Angel Protocol",
        "15_the_maeshowe_seer_decode.md": "The Maeshowe Seer Decode",
        "16_the_dormant_seed.md": "The Dormant Seed",
        "17_the_phi_squared_chain.md": "The φ² Chain",
        "18_the_barons_banner.md": "The Barons' Banner",
        "19_hnc_grand_unified_v2.md": "HNC Grand Unified v2",
        "20_hnc_mycelium_networks.md": "HNC Mycelium Networks",
        "21_project_druid_epas_defence_framework.md": "Project Druid EPAS: A Multi-Layer Active Defence Framework",
        "22_project_alfie_hybrid_launch_system.md": "Project Alfie: A Staged Hybrid Electromagnetic-Acoustic Launch System",
        "23_antarctic_candidate_multisensor_analysis.md": "Antarctic Candidate: Multi-Sensor Harmonic Signature Analysis",
        "24_antarctic_candidate_part_2.md": "Antarctic Candidate Part 2: Subsurface Ground Truth and 4D Reconstruction",
        "25_antarctic_candidate_part_3.md": "Antarctic Candidate Part 3: Working Model and Multi-Source Convergence",
    }
    title = title_map.get(article, title_slug)
    
    # Find the "About the author" section and cut everything from there
    marker = "**About the author:**"
    idx = text.rfind(marker)
    if idx == -1:
        # Try alternative
        marker = "About the author:"
        idx = text.rfind(marker)
    
    if idx == -1:
        print(f"WARN: No 'About the author' found in {article}")
        continue
    
    body = text[:idx].rstrip()
    
    # Build new footer
    footer = f"""\
---

**About the author:** **Gary Anthony Leckey** is the founder and director of **R&A Consulting and Brokerage Services Ltd** (company number NI696693, Companies House Northern Ireland), trading as **Aureon Zorza Technologies**. He is the principal investigator of the **Aureon Institute** and the architect of the **Harmonic Nexus Core (HNC)** framework. His work integrates theoretical physics, consciousness research, electromagnetic engineering, archaeological pattern recognition, and macroeconomic forensics into a unified, falsifiable research programme. R&A Consulting was awarded **Silver Level Innovator** status on the Innovate NI Innovation Framework by the Department for the Economy, Northern Ireland, in July 2025.

**Company:** R&A Consulting and Brokerage Services Ltd · Trading as Aureon Zorza Technologies  
**Location:** Belfast, Northern Ireland, United Kingdom  
**Website:** <https://aureonzorzatechnologies.pl>  
**Repository:** <https://github.com/RA-CONSULTING/aureon-trading>  
**License:** MIT © 2025–2026 R&A Consulting and Brokerage Services Ltd  
**Citation:** Leckey, G. A. (2026). *{title}*. Aureon Institute Research Publications.
"""
    
    # Add disclaimer if applicable
    if article in DISCLAIMERS:
        footer = f"\n{DISCLAIMERS[article]}\n{footer}"
    
    new_text = body + "\n\n" + footer
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    
    fixed_count += 1
    print(f"FIXED: {article}")

print(f"\n=== AUDIT COMPLETE ===")
print(f"Articles fixed: {fixed_count}/{len(articles)}")
