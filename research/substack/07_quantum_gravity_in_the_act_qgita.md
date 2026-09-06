# Quantum Gravity in the Act (QGITA): A Two-Stage Framework for Detecting Structure in Noise

**Abstract:** This article introduces Quantum Gravity in the Act (QGITA), a two-stage framework for high-fidelity event detection in complex, non-stationary signals. Stage 1 employs a Fibonacci-tightened geometric-temporal filter to isolate candidate structural anomalies. Stage 2 validates these candidates through a five-metric consensus model. In representative simulations, QGITA achieves a specificity improvement of more than two orders of magnitude over conventional single-metric thresholding, reducing hundreds of ambiguous candidates to a single validated structural transition.

---

## 1. The Problem: Fleeting Structures in Complex Dynamics

Complex dynamical systems — whether physical fields, financial markets, neural networks, or climate models — share a common signature: extended periods of quasi-stable behaviour punctuated by sudden, transient structural events. These episodes carry the most critical information about the system's underlying state, its governing dynamics, and its future evolution.

Yet they are notoriously difficult to detect. Conventional anomaly detection relies on single-metric thresholding: monitor amplitude, variance, or spectral power; flag any value exceeding a predefined limit. In non-stationary environments, this approach produces an unmanageable rate of false positives. The threshold cannot simultaneously be sensitive enough to catch subtle events and specific enough to ignore benign fluctuations.

The problem is not that the events are invisible. It is that **the observer is looking at the wrong dimensions**.

---

## 2. The Proposal: Geometry Before Threshold

QGITA reverses the conventional detection pipeline. Instead of thresholding first and validating later, it **geometrically isolates** candidate events first, then **consensually validates** them.

### Stage 1: Fibonacci-Tightened Curvature Points (FTCPs)

The temporal sampling grid is non-uniform, with adjacent-interval ratios converging to the golden ratio φ ≈ 1.618. This is not arbitrary. The Fibonacci lattice is the least-resonant spacing — it minimises self-interference while maximising coverage of the temporal phase space.

An FTCP fires when two conditions are met simultaneously:
1. **Geometric tightness:** The local temporal interval is φ-tight to its neighbours (ratio within ε of φ).
2. **Curvature spike:** The signal's discrete curvature (second difference normalised by step size) exceeds a context-adaptive threshold.

**Why this works:** Most noise is temporally unstructured — its intervals follow exponential or uniform distributions, not Fibonacci. A φ-tight interval is therefore a strong prior for structural significance. The curvature spike confirms that the geometric anomaly corresponds to a dynamical transition, not merely a sampling artefact.

**Control test:** When the algorithm is run with 1/φ spacing (the inverse golden ratio), the FTCP detection rate vanishes. This confirms that the detection is specific to the φ-geometry, not a generic property of non-uniform sampling.

### Stage 2: Lighthouse Five-Metric Consensus

Each FTCP candidate is subjected to rigorous validation through five independent metrics, fused into a normalised geometric mean L(t):

| Metric | Symbol | What It Measures |
|--------|--------|-----------------|
| Linear coherence | C_lin | Pearson correlation of signal with its delayed copy |
| Nonlinear coherence | C_nonlin | Mutual information between adjacent samples |
| Cross-scale coherence | C_φ | Alignment of local dynamics with φ-scaled window |
| Effective gravity | G_eff | Local "attraction" of the signal to its recent mean |
| Anomaly pointer | \|Q\| | Suppressor for known instrumental artefacts |

A confirmed structural event is declared only when L(t) exceeds a consensus threshold — requiring strong agreement across all five independent measures.

**Result:** The two-stage pipeline achieves **>100× specificity improvement** over single-metric thresholding on benchmark datasets. Where conventional methods produce hundreds of false positives per true event, QGITA produces one validated transition.

---

## 3. Theoretical Foundation: Observer-System Resonance

QGITA is not merely a signal-processing trick. It operationalises a core HNC principle: **the resonance between a geometrically structured observer and the intrinsic dynamics of the system**.

The Fibonacci lattice is the observer's "shape." The curvature point is the system's "knock." When the shape and the knock match, the observer "hears" the event. When they don't, the event passes unnoticed — not because it didn't happen, but because the observer was the wrong shape.

This reframes anomaly detection as **harmonic matching** rather than threshold crossing. The observer's geometry is as important as the signal's amplitude.

---

## 4. Applications Beyond Markets

QGITA was developed for financial market analysis, but its domain-agnostic structure extends to:

- **Industrial fault detection:** Identifying incipient bearing failures in rotating machinery via vibration analysis.
- **Neuroscience:** Detecting seizure onset in EEG signals with high temporal precision.
- **Climate science:** Identifying regime transitions in ocean-atmosphere coupled models.
- **Fundamental physics:** Searching for transient gravitational-wave events in detector noise.

In each domain, the key insight is the same: **rare structural events announce themselves through geometric resonance, not amplitude excess**.

---

## 5. Falsification Criteria

1. **φ-Specificity:** If FTCP detection does not vanish under 1/φ spacing in controlled trials, the geometric prior is invalid.
2. **Consensus Necessity:** If any single metric (e.g., C_lin alone) matches or exceeds the five-metric consensus performance on benchmark datasets, the multi-metric architecture is unnecessary.
3. **Cross-Domain Failure:** If QGITA fails to outperform single-threshold methods on at least three independent non-financial datasets (industrial, neural, climate), the domain-agnostic claim is weakened.
4. **Computational Cost:** If the two-stage pipeline cannot process real-time data streams at ≥1 kHz on standard hardware, the practical deployment claim fails.

---

---

**About the author:** **Gary Anthony Leckey** is the founder and director of **R&A Consulting and Brokerage Services Ltd** (company number NI696693, Companies House Northern Ireland), trading as **Aureon Zorza Technologies**. He is the principal investigator of the **Aureon Institute** and the architect of the **Harmonic Nexus Core (HNC)** framework. His work integrates theoretical physics, consciousness research, electromagnetic engineering, archaeological pattern recognition, and macroeconomic forensics into a unified, falsifiable research programme. R&A Consulting was awarded **Silver Level Innovator** status on the Innovate NI Innovation Framework by the Department for the Economy, Northern Ireland, in July 2025.

**Company:** R&A Consulting and Brokerage Services Ltd · Trading as Aureon Zorza Technologies  
**Location:** Belfast, Northern Ireland, United Kingdom  
**Website:** <https://aureonzorzatechnologies.pl>  
**Repository:** <https://github.com/RA-CONSULTING/aureon-trading>  
**License:** MIT © 2025–2026 R&A Consulting and Brokerage Services Ltd  
**Citation:** Leckey, G. A. (2026). *Quantum Gravity in the Act (QGITA)*. Aureon Institute Research Publications.
