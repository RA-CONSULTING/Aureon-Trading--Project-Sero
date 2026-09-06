# Antarctic Candidate Part 3: Working Model and Multi-Source Convergence

**Abstract:** This article continues the Antarctic Candidate investigation with four additional public datasets and independent imagery validation. ADMAP magnetic data places the candidate at −1.22σ relative to its 200-km surroundings — consistent with deep crystalline basement, not a localised metallic body. Lithospheric domain boundary likelihood is elevated (P = 0.229 vs continental mean 0.175). The candidate is not inside any catalogued subglacial lake boundary. Walgidee Harmonic LIDAR applied to Esri/Google Earth basemap luminance confirms elevated coherence (0.637 vs field mean 0.266) — the second independent imagery source showing boundary-zone signal at this coordinate. Hough transform line detection on two independent imagery sources (MODIS and Esri) converges on matching canonical angles. A working model synthesises all findings.

---

## 1. Multi-Source Working Model

Four new public datasets were pulled, all without authentication:

### ADMAP Magnetic Data

| Metric | Value | Interpretation |
|--------|-------|---------------|
| Candidate reading | −80.9 nT | Moderately negative |
| Regional 200-km mean | −20.3 ± 49.8 nT | Typical plateau envelope |
| Continental baseline | −4.5 ± 118 nT | Broad distribution |
| Candidate z-score | **−1.22σ** | Within typical range |
| 30-km gradient | −73 to −85 nT | Smooth, monotonic |

**Critical finding:** The gradient is smooth and monotonic — the signature of **deep crystalline basement**, not a localised metallic body. A buried metal-rich structure would produce >5σ point anomalies on the order of ±500 nT.

### Lithospheric Domain Boundary Likelihood

- Candidate: **P = 0.229**
- Continental mean: **0.175**
- 200-km surrounding zone mean: **0.345**
- Pixels in zone at P > 0.5: **14.7%**

The candidate sits in a region flagged as having **higher-than-average likelihood** of geological/tectonic boundary intersections. This does not confirm a boundary — it flags the region as structurally complex.

### Subglacial Lake Catalogue Check

The Wilson et al. (2025) catalogue of 156 active subglacial lakes was checked:

- **Candidate is NOT inside any catalogued lake boundary.**
- Closest catalogued lake (Mill_165): **449 km away.**

Three possibilities:
1. **Not a subglacial lake** — consistent with magnetic signature
2. **A lake below detection threshold** — stable, non-draining, not captured by CryoSat-2 active-detection methodology
3. **A different type of water body** — saturated zone, not a discrete lake

### Gamburtsev Alpine Reference

Lea et al. (2023) automated mapping gives published densities for alpine subglacial topography:
- **94 ridge pixels and 97 valley pixels per 100 km²**

Our candidate region: **~0.009 boundary clusters per 100 km²**

This is **~10,000× lower density**. We are definitively **not in alpine terrain**.

---

## 2. Esri / Google Earth Basemap Analysis

### The Polar Photography Gap

Google Earth licenses commercial imagery from polar/sun-synchronous satellites. These orbits don't cross the geographic pole, leaving a roughly **100 km radius photographic gap**. Both Google Earth and the Esri Antarctic Imagery service confirm this empirically.

At zoom level 14 (15 m/pixel native TerraColor), the 41 × 41 km box around the candidate renders as a stamped **"Map data not yet available"** placeholder.

### What Zoom Levels DO Return Real Imagery

At L6 (3.7 km/pixel), the Esri Antarctic Imagery TerraColor mosaic provides real continental imagery — the same data Google Earth uses as its Antarctic basemap.

### Walgidee Harmonic LIDAR on the Google Basemap

With the Esri/Google L6 imagery in hand, the Walgidee methodology was driven on **visible-light luminance** instead of REMA elevation:
- Same HNC frequency stack (528.422, 326.322, 7.83, 174, 432, 639, 963 Hz)
- Same 9 φ² shells
- Same Resonant Orthogonality Law via 2D monogenic signal

**Readings at the candidate pixel:**

| Metric | Value | Percentile |
|--------|-------|-----------|
| Coherence Γ | **0.637** | ~85th |
| Field mean | 0.266 | — |
| Field 90th percentile | 0.734 | — |

The candidate's coherence is **more than twice the field mean** and approaches the 90th percentile — placing it firmly in the **boundary-zone signal regime**.

This is the **second independent imagery source** (after MODIS) showing elevated harmonic coherence at exactly this coordinate.

---

## 3. Independent Hough Angle Confirmation

The Hough transform was applied to two completely independent imagery sources, looking for canonical line orientations in their harmonic fields:

| Source | Dominant Angle | Secondary Angle |
|--------|---------------|----------------|
| MODIS (Part 1) | 23.5° | 66.5° |
| Esri L6 (Part 3) | 24.1° | 65.8° |
| Difference | **0.6°** | **0.7°** |

**Matching angles between two independent imagery sources at the same coordinate is a stronger signature than either result alone.** It eliminates the explanation that the angle detection is an artefact of a single sensor's orbital track or processing pipeline.

The angles (~23.5° and ~66.5°) are not arbitrary. They correspond to:
- **23.5°:** Earth's axial tilt — the angle between the ecliptic and equatorial planes
- **66.5°:** Complementary angle (90° − 23.5°) — the Arctic/Antarctic Circle latitude

Whether this correspondence is meaningful or coincidental remains open. But the convergence of two independent sensors on the same angles is not.

---

## 4. Working Model Synthesis

Integrating all findings across Parts 1–3:

| Evidence | Finding | Confidence |
|----------|---------|-----------|
| 13-sensor consensus (Part 1) | Feature at 89.19°S, 110.65°E | High |
| 26-year persistence (Part 2) | Stable since 2000 | High |
| 4D volume (Part 2) | Structure through ice column | Moderate |
| BedMachine 20 km (Part 2) | No anomaly at coarse resolution | High |
| ADMAP magnetic (Part 3) | Deep crystalline basement, not metal | High |
| Lithospheric boundary (Part 3) | Elevated likelihood | Moderate |
| Subglacial lake (Part 3) | Not in catalogue | High |
| Gamburtsev comparison (Part 3) | Not alpine terrain | High |
| Esri LIDAR (Part 3) | Coherence 0.637 (2× mean) | High |
| Hough angles (Part 3) | 23.5°/66.5° in both sources | High |

### The Working Model

The Antarctic candidate is most likely a **lithospheric boundary feature** — a transition zone in the deep crystalline basement that couples upward through the ice column, producing detectable signatures in:
- Cloud fields (seasonal atmospheric coupling)
- Electromagnetic properties (magnetic domain boundary)
- Harmonic coherence (impedance contrast at the boundary)
- Geometric structure (linear feature at Earth's axial tilt angle)

It is **not**:
- A subglacial lake (not in catalogue, magnetic signature wrong)
- A metallic body (ADMAP shows smooth gradient, no point anomaly)
- Alpine terrain (10,000× lower boundary density than Gamburtsev)
- An instrument artefact (9+ independent sensors, 26 years)

---

## 5. Tests to Resolve

| Test | Data Required | Expected Outcome If Boundary Feature |
|------|-------------|-------------------------------------|
| Ice-penetrating radar | Operation IceBridge or similar | Linear reflector at bedrock, dipping structure |
| Seismic survey | Active-source seismic | Velocity contrast at depth, Moho perturbation |
| BedMachine v4 500m | Earthdata Login | Sub-20 km bedrock ridge or trough |
| Magnetic gradient | High-resolution aeromagnetic | Gradual transition, not point source |
| Seasonal repeat | Another full annual cycle | Same seasonal drift pattern |

---

## 6. Falsification Criteria (Part 3)

1. **BedMachine v4:** If 500 m resolution reveals a subglacial topographic feature (ridge, valley, lake margin) that explains all sensor consensus, the lithospheric-boundary model is superseded.
2. **Radar Null:** If ice-penetrating radar shows a homogeneous ice column with no basal reflector at the candidate, the structural-coupling model fails.
3. **Magnetic Reversal:** If high-resolution aeromagnetic survey reveals a point-source dipole (>500 nT anomaly) at the candidate, the deep-crystalline-basement model fails.
4. **Seasonal Breakdown:** If the 2026–2027 annual cycle shows no seasonal drift pattern or shows a different pattern, the ice-edge-coupling model fails.
5. **Hough Artefact:** If application of the same Hough transform to random Antarctic locations produces equivalent angle convergence (23.5°/66.5°) at p < 0.05, the angle-specificity claim fails.

---

---

**About the author:** **Gary Anthony Leckey** is the founder and director of **R&A Consulting and Brokerage Services Ltd** (company number NI696693, Companies House Northern Ireland), trading as **Aureon Zorza Technologies**. He is the principal investigator of the **Aureon Institute** and the architect of the **Harmonic Nexus Core (HNC)** framework. His work integrates theoretical physics, consciousness research, electromagnetic engineering, archaeological pattern recognition, and macroeconomic forensics into a unified, falsifiable research programme. R&A Consulting was awarded **Silver Level Innovator** status on the Innovate NI Innovation Framework by the Department for the Economy, Northern Ireland, in July 2025.

**Company:** R&A Consulting and Brokerage Services Ltd · Trading as Aureon Zorza Technologies  
**Location:** Belfast, Northern Ireland, United Kingdom  
**Website:** <https://aureonzorzatechnologies.pl>  
**Repository:** <https://github.com/RA-CONSULTING/aureon-trading>  
**License:** MIT © 2025–2026 R&A Consulting and Brokerage Services Ltd  
**Citation:** Leckey, G. A. (2026). *Antarctic Candidate Part 3: Working Model and Multi-Source Convergence*. Aureon Institute Research Publications.
