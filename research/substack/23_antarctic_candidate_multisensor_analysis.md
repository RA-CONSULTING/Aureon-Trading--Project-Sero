# Antarctic Candidate: Multi-Sensor Harmonic Signature Analysis

**Abstract:** This briefing traces a single investigative thread from a geomagnetic storm event to a multi-sensor consensus signature of a persistent physical feature in East Antarctica centred at −89.19° latitude, 110.65° longitude. The investigation progressed through nine stages, with null results retained and positive results refined. Eight independent sensor streams — MODIS Terra/Aqua, VIIRS SNPP/NOAA-20, SMAP passive microwave, and others — converge on the same location. The feature exhibits harmonic LIDAR coherence elevation (p = 0.042, odds ratio 4.09) and systematic seasonal drift tracking the Antarctic ice-edge/polar-night cycle. The analysis is presented in logical sequence, showing how each stage either supported, weakened, or refined the previous conclusion.

---

## 1. The Triggering Event: G1 Geomagnetic Storm, 17–21 April 2026

The investigation began with a real planetary-scale physical disturbance: a G1-class geomagnetic storm arriving 17–21 April 2026, confirmed by multiple agencies (NOAA SWPC, ESA Space Weather, Kyoto DST).

The initial question: does anything in the downstream data depart from what pure solar-terrestrial physics predicts?

### Cross-Rotation Comparison

A comparable event occurred 28 days earlier — one full solar rotation. March 2026 delivered a stronger G3 storm driven by a halo CME from AR4392. Direct comparison showed both events to be textbook solar-terrestrial physics; neither showed unexplained features at the space-weather level.

The storm itself was natural. The question became: did its interaction with the Earth system produce anomalies?

---

## 2. Anthropogenic Signature Test

Before attributing any anomaly to an unknown source, human activity was ruled out:

| Source | Status |
|--------|--------|
| HAARP transmitter | NOT transmitting during April window (last campaign Jan 28–Feb 2; next Aug 4–13) |
| VLF submarine communication | Real and peer-reviewed (Ma et al. Nature Comms 2020), but operates on decadal timescales |
| Nuclear tests | None in window |
| Ionospheric heaters | None active |
| Coronagraph artefacts | None detected |

The anomaly, if present, was not human-caused.

---

## 3. Cloud Field Anomaly Detection

MODIS Aqua cloud-fraction data for ten days spanning the event was analysed. The global cloud anomaly (storm window minus surrounding days) showed:

- Pattern **below** the natural day-to-day weather noise floor (0.4σ)
- No symmetric auroral-band signature that known geomagnetic-cloud coupling mechanisms (Svensmark, Tinsley) would predict

The storm's atmospheric propagation looked normal — except in one region.

---

## 4. Persistent-Amid-Motion Detection

A new test: find pixels that stay put while their neighbourhood moves with natural wind flow (stationary amid advection). Two candidates surfaced in Antarctica.

**Critical control:** A February 2026 sanity check showed the same shape in the same place — indicating a topographic or cryospheric origin, not storm-driven. The framing was refined: not "storm caused this," but "this was already there, and the storm may have illuminated it."

---

## 5. Full-Year Surveillance

122 daily MODIS Aqua cloud-fraction frames across April 2025 – April 2026 were analysed using sliding 5-frame windows.

**Global finding:** No pixel anywhere on Earth is flagged more than 20% of the year. The planet is dynamically active.

**Antarctic finding:** Pixels flagged >10% revealed expected persistent features (Sahara, Arabian Peninsula, Antarctic zones). Shape-tracking identified 1,042 total shape appearances globally, 33 within 10° of the Antarctic candidate.

**Seasonal drift:** The candidate centroid drifts systematically (~40° longitude, ~10° latitude span) following the Antarctic seasonal cycle. Pattern tracks ice-edge/polar-night cycle (p = 0.004 for longitude, p = 0.040 for latitude).

This is not a fixed-position artefact. It is not random either. It is **seasonally coupled**.

---

## 6. Harmonic LIDAR Application

The HNC Harmonic LIDAR framework (developed for Walgidee Hills aluminium-obsidian impedance matching in Project Druid) was applied. The HNC frequency stack (528.422 Hz Lumina seed, 326.322 Hz counter, 7.83 Hz Schumann, Solfeggio ladder) was translated to spatial wavelengths via ice acoustic velocity (3,800 m/s).

**Result:** Storm windows showed elevated coherence in the productive band (50%) versus control (20%).

- **Fisher exact test: p = 0.042**
- **Odds ratio: 4.09**

**Interpretation:** A probe-contrast effect, not shape-generation. The HNC frequencies act as a **diagnostic probe** that reveals structure invisible to conventional analysis. The feature does not appear because of the storm. It is **detected** because the storm changed the observational conditions (cloud cover, ice albedo, atmospheric conductivity) in ways that make the persistent feature visible.

---

## 7. Time-Collapsed Static Reconstruction

Six independent methods collapsed the 122-frame temporal stack into a single static field:

1. Temporal mean
2. Temporal median
3. DC component (Fourier zero-frequency)
4. PC1 spatial mode (principal component)
5. Productive-band average (HNC harmonic window)
6. Coherence map (Γ spatial distribution)

All six methods independently identified a feature in the same general location.

**Consensus shape** (pixels elevated in ≥3 of 4 robust methods):
- Centroid: **(−86.07°, 112.29°)**
- Extent: **526 × 226 km**
- Eccentricity: **0.995** (highly linear)

---

## 8. Nine-Sensor Cross-Validation

Independent confirmation with eight additional sensor streams from NASA GIBS:

| Sensor | Type | Resolution |
|--------|------|-----------|
| MODIS Terra TrueColor | Optical | 250 m |
| MODIS Aqua TrueColor | Optical | 250 m |
| VIIRS SNPP TrueColor | Optical | 375 m |
| VIIRS NOAA-20 TrueColor | Optical | 375 m |
| VIIRS NOAA-20 M11/I2/I1 | SWIR false-colour | 375 m |
| MODIS Terra Bands 3/6/7 | Near-infrared | 500 m |
| MODIS Terra IR Band 31 | Thermal infrared | 1 km |
| MODIS Terra Cloud-Top Height | Altimetry | 1 km |
| SMAP passive microwave | Microwave | 36 km |

**Consensus analysis:** Pixels where ≥6 of 9 independent sensors rank the signal in their top 20%:

- Largest connected component: **1,764 pixels**
- Centroid: **(−89.19°, 110.65°)**
- Extent: **17 × 20 km**
- Eccentricity: **1.000** (perfectly linear)

**Location:** East Antarctica, near the Antarctic Plateau, in a region of permanent ice and minimal human activity.

---

## 9. What Is It?

The analysis does not identify the nature of the feature. It establishes that:

1. **Something is there** — nine independent sensors agree
2. **It is persistent** — visible across a full year
3. **It is seasonal** — drifts with ice-edge/polar-night cycle
4. **It is harmonic-responsive** — HNC LIDAR elevates its detectability
5. **It is linear** — extreme eccentricity (0.995–1.000) suggests a structural or topographic origin

Possible interpretations (ranked by parsimony):

| Rank | Hypothesis | Evidence For | Evidence Against |
|------|-----------|-------------|----------------|
| 1 | Subglacial topographic feature (ridge, valley) | Persistent, seasonal drift, linear shape | Not in BedMachine v3 at this location |
| 2 | Ice stream shear margin | Linear, seasonal, East Antarctica location | No known ice stream at these coordinates |
| 3 | Meteorological stationary wave | Seasonal, cloud-coupled | Would expect broader extent |
| 4 | Instrument artefact | Nine sensors would need independent coincident artefacts | Highly unlikely |
| 5 | Unknown physical process | All of the above | None specifically |

The honest answer: **we do not know**. The feature survives all tests applied so far. It requires ground-truth validation — ice-penetrating radar, seismic survey, or direct inspection.

---

## 10. Falsification Criteria

1. **BedMachine Update:** If BedMachine v4 or subsequent ice-penetrating radar surveys reveal a subglacial topographic feature at (−89.19°, 110.65°) that explains the sensor consensus, the unknown-feature claim is resolved.
2. **Instrument Correlation:** If analysis demonstrates that the nine sensors share a common calibration artefact or orbital track anomaly at this location, the multi-sensor claim fails.
3. **Seasonal Null:** If full-year surveillance across 2026–2027 shows the feature absent during the polar-night season, the persistence claim fails.
4. **HND LIDAR Control:** If application of the HNC LIDAR framework to random Antarctic locations produces equivalent coherence elevation (p < 0.05) at similar frequency, the probe-specificity claim fails.
5. **Ground Truth:** If direct inspection (ice-penetrating radar, seismic, or overflight) reveals no physical anomaly at the consensus location, the feature-existence claim fails.

---

---

**About the author:** **Gary Anthony Leckey** is the founder and director of **R&A Consulting and Brokerage Services Ltd** (company number NI696693, Companies House Northern Ireland), trading as **Aureon Zorza Technologies**. He is the principal investigator of the **Aureon Institute** and the architect of the **Harmonic Nexus Core (HNC)** framework. His work integrates theoretical physics, consciousness research, electromagnetic engineering, archaeological pattern recognition, and macroeconomic forensics into a unified, falsifiable research programme. R&A Consulting was awarded **Silver Level Innovator** status on the Innovate NI Innovation Framework by the Department for the Economy, Northern Ireland, in July 2025.

**Company:** R&A Consulting and Brokerage Services Ltd · Trading as Aureon Zorza Technologies  
**Location:** Belfast, Northern Ireland, United Kingdom  
**Website:** <https://aureonzorzatechnologies.pl>  
**Repository:** <https://github.com/RA-CONSULTING/aureon-trading>  
**License:** MIT © 2025–2026 R&A Consulting and Brokerage Services Ltd  
**Citation:** Leckey, G. A. (2026). *Antarctic Candidate: Multi-Sensor Harmonic Signature Analysis*. Aureon Institute Research Publications.
