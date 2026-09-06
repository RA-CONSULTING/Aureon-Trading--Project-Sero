# Paper 12: A Dynamic Systems Model of Cognitive-Physiological Coherence Coupled to Geophysical Resonance

**Translated from HNC internal documentation to mainstream scientific language**  
**Date:** October 2025  
**Principal Investigator:** G. Leckey, R&A Consulting and Brokerage Services Ltd.  
**Affiliation:** R&A Consulting and Brokerage Services Ltd.

---

## Executive Summary

We present a formal, testable dynamic systems model linking an observer's internal physiological state to structured environmental stimuli, with specific emphasis on the Earth's Schumann resonance field and astronomical luminance events. The model translates a hierarchical signal processing architecture into a computational network of operators that transform incoming environmental signals into an evolving internal state vector Ψ_t. The update rule is a recursive exponential-moving-average style update where new information is provided by a composite operator R that maps sensory input through saliency detection, pattern recognition, contextual framing, physiological modulation, synthesis, and memory encoding.

We operationalize the key indices — environmental resonance r_t, physiological constraint λ_t, purity P_t = r_t / λ_t, and structuring index κ_t — using measurable Schumann Resonance power and Heart Rate Variability (HRV) metrics. We apply the model to a night-sky case study (Oban, Scotland; 25–26 October 2025) and provide a reproducible simulation and dynamic visualization that demonstrates three principal behaviors: self-organization toward coherence, oscillation under over-structuring, and dissolution under under-resonance.

This paper includes the full model specification, empirical grounding, reproducible code, visualization procedures, and a roadmap for experimental validation and extension. The central biological hypothesis is that the observer's autonomic state (quantified by HRV) modulates the information-processing pipeline via a nonlinear gain parameter, producing different macroscopic behaviors in the coherence metric.

**Keywords:** Schumann resonance, heart rate variability, dynamical systems, cognitive-physiological coherence, autonomic nervous system, nonlinear feedback, astronomical forcing, environmental neuroscience, geophysical monitoring

---

## 1. Introduction

Perception can be modeled as a dynamic, self-updating process: the observer maintains an internal model and continuously updates it with sensory data. We formalize a hierarchical signal processing architecture as a computational network. The central claim of this work is that coherence — a measurable state of cognitive-physiological integration — can be modeled as an emergent property of the interaction between (a) structured environmental forcing (astronomical light), and (b) the physiological state of the observer (autonomic balance). The central biological hypothesis is that the observer's autonomic state (quantified by HRV) modulates the information-processing pipeline via a nonlinear gain parameter, producing different macroscopic behaviors in coherence.

This paper: (1) defines the model mathematically; (2) links model parameters to empirical geophysical and physiological measures; (3) demonstrates the model with a night-sky case; and (4) supplies reproducible scripts and visualization guidance to evaluate, refine, and present results.

### 1.1 Background: Schumann Resonance and Human Physiology

The Schumann resonances are a set of spectrum peaks in the extremely low frequency (ELF) portion of the Earth's electromagnetic field spectrum. The fundamental mode is at approximately 7.83 Hz, with higher harmonics at 14.3, 20.8, 27.3, and 33.8 Hz. These resonances are produced by lightning discharges in the cavity formed by the Earth's surface and the ionosphere. There is growing interest in the potential interactions between Schumann resonance fields and human physiology, particularly through entrainment of brainwave activity and autonomic nervous system regulation.

Heart Rate Variability (HRV) is a well-established metric for assessing autonomic nervous system function. Time-domain metrics such as SDNN (standard deviation of NN intervals) and frequency-domain metrics such as LF/HF ratio (low-frequency to high-frequency power ratio) provide non-invasive measures of sympathetic and parasympathetic balance. The hypothesis that environmental electromagnetic fields may influence HRV is a topic of active research, though causal mechanisms remain incompletely understood.

### 1.2 Model Overview

The model proposed here bridges three domains: (1) environmental geophysics (Schumann resonance), (2) human physiology (HRV), and (3) dynamical systems theory. It provides a formal, testable framework for investigating whether and how structured environmental stimuli (astronomical light) and geophysical resonance (Schumann fields) interact with physiological state to produce measurable changes in cognitive-physiological coherence.

## 2. System Architecture: Hierarchical Signal Processing Network

### 2.1 Computational Mapping

The signal processing architecture is represented as a cyclic operator chain:

$$\Psi_{\infty} \rightarrow \aleph \rightarrow \Phi \rightarrow F \rightarrow L \rightarrow \Omega \rightarrow \rho \rightarrow C \rightarrow \Psi'_{\infty}$$

where each symbol denotes an operator or state in the processing loop. We formalize this cycle as a composite transformation operator R that maps sensory input C_t into the space of state updates. The system state at discrete time t is the vector Ψ_t.

### 2.2 Operator Definitions

The following operators define the computational pipeline:

- **Ψ_∞ (Source):** The generative external reality; for simulation we take sky luminance and point/transient sources as drivers.

- **C (Channel):** External input vector C_t; in our case C_t = [C_t^(A), C_t^(P), C_t^(T)] for Ambient, Point, and Transient luminance components.

- **ℵ (Aleph — Saliency):** Saliency and filtering operator (feature selection). Implementation: element-wise weighting to emphasize point and transient components.

- **Φ (Phi — Pattern Recognition):** Pattern recognition operator (structural analysis, e.g., convolutional or spectral transforms). Implementation: a linear transform followed by a saturating nonlinearity: Φ(x) = tanh(Mx), where M ∈ R^(n×n).

- **F (Framing):** Memory integration that contextualizes new patterns with the current state Ψ_t. Implementation: convex combination of pattern output and prior state: F(φ, Ψ_t) = βφ + (1 - β)Ψ_t.

- **L (Living Node — Physiological Modulation):** A nonlinear physiological modulation operator controlled by the structuring index κ_t. Implementation: state-dependent gain L(f; κ_t) = g(κ_t) · f, where g(κ) = clip(1/κ, g_min, g_max).

- **Ω (Omega — Synthesis):** Synthesis and convergence into a coherent gestalt. Implementation: normalization by Euclidean norm: Ω(x) = x / (||x|| + ε).

- **ρ (Rho — Reflection):** Reflection and preparation for memory encoding; ensures compatibility for next-state integration. Implementation: identity or smoothing operator as required.

- **Ψ'_∞ (Produced Experience):** The output state, which becomes (or influences) Ψ_{t+1}.

### 2.3 Governing Equation

The discrete-time update is:

$$\Psi_{t+1} = (1 - \alpha) \Psi_t + \alpha R(C_t; \Psi_t)$$

with 0 ≤ α ≤ 1 as a learning rate. The composite mapping is:

$$R = \rho \circ \Omega \circ L(\cdot; \kappa_t) \circ F(\cdot; \Psi_t) \circ \Phi \circ \aleph$$

Note that F and L are state-dependent: F uses prior Ψ_t for framing, while L uses the physiological structuring parameter κ_t.

## 3. Astronomical Grounding: Case Study — Oban, Scotland, 25–26 October 2025

To make the model empirically grounded, we create a discrete forcing schedule for Oban, Scotland (56.4°N, 5.5°W) for the night of 25–26 October 2025. The sky is represented by a 3-component vector:

$$C_t = [\text{Ambient}, \text{Point}, \text{Transient}]$$

each component normalized to [0, 1].

### 3.1 Astronomical Context

Key facts for the night (local times):
- **Sunset:** approximately 17:57; nautical twilight ends 19:18; astronomical darkness begins thereafter.
- **Lunar phase:** Waxing Crescent (approximately 11–15% illumination) — favorable for dark-sky observation.
- **Planetary visibility:** Saturn (visible after 17:13, crosses meridian 22:53, sets 03:33). Jupiter rises 22:21 and dominates the latter half of the night. Uranus/Neptune present but faint. Mercury/Mars set shortly after sunset.
- **Orionid Meteor Shower:** active with an expected rate of approximately 15–20/hr near peak; meteors are fast (41 mi/s) and produce transient high-energy streaks.

**Table 1: Astronomical Luminance Input Schedule for Oban (25–26 October 2025)**

| Time (local) | Event | Description | C_t = [A, P, T] |
|--------------|-------|-------------|-----------------|
| 17:57 | Sunset | Fading ambient | [0.8, 0.0, 0.0] |
| 18:30 | Saturn visible | Saturn emerges | [0.3, 0.4, 0.0] |
| 19:18 | End twilight | Astronomical darkness | [0.1, 0.4, 0.0] |
| 22:21 | Jupiter rise | Bright planet | [0.1, 0.9, 0.0] |
| 00:00 | Orionids active | Meteors frequent | [0.05, 0.7, 0.4] |
| 03:33 | Saturn set | Saturn drops out | [0.05, 0.3, 0.1] |
| 04:00 | Orionids wane | Meteor rate reduces | [0.05, 0.4, 0.15] |
| 05:54 | Start twilight | Dawn begins | [0.3, 0.2, 0.05] |
| 07:17 | Sunrise | Daylight returns | [0.8, 0.0, 0.0] |

These vectors are normalized examples chosen to fully specify the simulation; the paper's reproducible code accepts empirically measured luminances in place of these proxies.

## 4. Parameterization and Data Integration

We connect abstract variables to measurable signals: Schumann Resonance (SR) power for environmental resonance and HRV metrics for physiological constraint and structuring.

### 4.1 Resonance r_t

Let SR_power(t) be the measured band-power in the fundamental SR mode (7.8–8.2 Hz). Normalize to [0, 1]:

$$r_t = \text{clip}\left(\frac{\text{SR_power}(t) - \text{SR}_{\text{min}}}{\text{SR}_{\text{max}} - \text{SR}_{\text{min}}}, 0, 1\right)$$

where bounds are estimated from historical baselines (rolling quantiles or instrument dynamic range).

### 4.2 Constraint λ_t

Use HRV time-domain SDNN (ms). Define:

$$\text{SDNN}_{\text{norm}}(t) = \frac{\text{SDNN}(t)}{\text{SDNN}_{\text{ref}}}$$

$$\lambda_t = \text{clip}\left(\frac{1}{\text{SDNN}_{\text{norm}}(t) + \epsilon}, \lambda_{\text{min}}, \lambda_{\text{max}}\right)$$

**Interpretation:** high SDNN implies low λ_t (flexible autonomic response), low SDNN implies high λ_t (rigid autonomic response).

### 4.3 Purity P_t

By definition:

$$P_t = \frac{r_t}{\lambda_t}$$

For visualization we normalize P_t to [0, 1] using a logistic or linear rescale.

**Interpretation:** Purity represents the ratio of environmental resonance to physiological constraint. High purity indicates that the observer is receiving strong environmental resonance while maintaining physiological flexibility. Low purity indicates either weak environmental resonance or high physiological rigidity.

### 4.4 Structuring Index κ_t

Use HRV frequency-domain LF/HF ratio:

$$\kappa_t = \frac{\text{LF}_{\text{power}}(t)}{\text{HF}_{\text{power}}(t) + \epsilon}$$

Clip κ_t to a plausible range (e.g., [0.2, 5]) for numerical stability and consistent visualization.

**Interpretations:**
- κ_t > 1: Over-structured / sympathetic dominance (high arousal, stress response)
- κ_t < 1: Under-resonant / parasympathetic dominance (low arousal, relaxation)
- κ_t ≈ 1: Balance / coherence (optimal autonomic regulation)

## 5. Simulation and Results

We implemented a reproducible simulation to demonstrate three central behaviors: self-organization, oscillation under stress, and dissolution under under-resonance.

### 5.1 Simulation Design

**Key features:**
- **Time resolution:** 1-minute timestep from 17:57 (25 Oct) to 07:17 (26 Oct).
- **Input:** interpolated C_t from Table 1.
- **Environmental stream:** synthetic SR power (replaceable with GCMS or other magnetometer data).
- **Physiological stream:** synthetic HRV (SDNN, LF, HF), including simulated startle spikes during meteor-active window.
- **Operators:** simple but expressive functions implementing ℵ, Φ, F, L, Ω, ρ (see Appendix A).
- **Update:** Equation (1) with α selected to allow visible dynamics (e.g., α = 0.25).

### 5.2 Results: Three Phases

**Phase 1 — Sunset to deep night (self-organization).** As ambient light decays and Saturn/Jupiter provide point coherence, Ψ_t converges to a stable representation. P_t climbs toward unity when κ_t ≈ 1 (balanced physiology). The system demonstrates self-organization: starting from an arbitrary initial state, it converges toward a stable attractor as the environmental forcing becomes more structured (point sources dominate over ambient noise).

**Phase 2 — Mid-night perturbation and oscillation.** During Orionids activity, transient impulses perturb Ψ_t. For balanced κ_t ≈ 1 the system absorbs transients with small, transient dips in P_t. However, if the HRV trace includes a startle (SDNN drop, LF/HF spike) the physiological modulation node becomes rigid (κ_t > 1): the system overshoots correction, producing sustained oscillations in Ψ_t and large fluctuations in P_t. This demonstrates that over-structuring (sympathetic dominance) destabilizes the feedback loop, leading to oscillatory behavior rather than smooth convergence.

**Phase 3 — System dissolution (cloud cover).** We simulate cloud arrival at 03:00 reducing C_t ≈ 0. With α > 0, Equation (1) reduces to Ψ_{t+1} ≈ (1 - α)Ψ_t, causing exponential decay of the state toward an incoherent, low-P_t regime. This demonstrates that when environmental resonance is too weak (under-resonance), the internal state cannot maintain coherence and decays to baseline. The decay rate is determined by the learning rate α: higher α leads to faster decay when input is absent.

### 5.3 Representative Figures

- **Figure 1:** Time-series plot showing C_t components, SR power, SDNN, LF/HF, P_t, and κ_t over the 24-hour observation window.
- **Figure 2:** State-space plot showing Ψ projection with regions of convergence, oscillation, and dissolution.
- **Figure 3:** Circular dashboard (polar visualization) snapshots for three timepoints (stable, perturbed, dissolved).
- **Figure 4:** Animation frames (MP4) showing continuous circular dashboard evolution (optional for presentations).

## 6. Visualization and Interpretation: Circular Dashboard

We propose an animated circular dashboard (polar visualization) reflecting operator flow and system state. Mapping rules:
- **Brightness ∝ |P_t|** (0 = dim, 1 = maximum brightness)
- **Hue = f(κ_t):** cool colors (cyan/blue/violet) when κ_t < 1, emerald green near κ_t ≈ 1, and warm colors (yellow/orange/red) for κ_t > 1
- **Segments represent operators ℵ → Φ → F → L → Ω → ρ;** a pulse propagates through segments each timestep
- **Center circle indicates current P_t** (size/brightness)

This visualization is both didactic and diagnostic: it maps the observer's physiology to perceptual dynamics in an intuitive way. The circular layout emphasizes the cyclic nature of the feedback loop, while the color mapping provides immediate visual feedback on autonomic state.

## 7. Discussion

### 7.1 Model Contributions

The model unifies three domains:
1. A formal perceptual-cycle architecture that is fully specified as a composite operator R.
2. A concrete operationalization of coherence (P_t) and structuring (κ_t) using geophysical and physiological measures.
3. A reproducible simulation and visualization pipeline that demonstrates qualitative behaviors of interest (self-organization, oscillation, dissolution).

### 7.2 Limitations

- **Operator implementations here are intentionally simple** (linear transforms + saturating nonlinearities). They should be replaced by more realistic algorithms (e.g., convolutional networks, spectral detectors) in empirical studies.
- **The mapping SR → r_t assumes stationarity and well-defined bounds.** Real SR signals are noisy and spatially heterogeneous. Single-station measurements may not capture the global SR field dynamics.
- **HRV metrics are sensitive to measurement artifacts**, posture, respiration, and other confounds — careful preprocessing and artifact rejection are required.
- **Causality claims** (SR influencing HRV influencing perception) are plausible but require experimental verification with controlled interventions and robust statistics. The present model is correlational, not causal.
- **The astronomical luminance proxies are normalized examples**, not empirical measurements. The model should be validated with actual photometric data from all-sky cameras or lux meters.

### 7.3 Empirical Validation Roadmap

1. **Data collection:** Simultaneous SR monitoring (e.g., GCMS), wearable ECG (for HRV), and all-sky photometry during target nights.
2. **Preprocessing:** Standard HRV pipelines (filtering, NN extraction, SDNN, LF/HF spectral analysis) and SR bandpower estimation with robust artifact removal.
3. **Fitting:** Use parameter estimation (Bayesian or frequentist) to tune α, operator gains, and clipping bounds to maximize predictive alignment between simulated Ψ_t dynamics and observed behavioral/perceptual outcomes.
4. **Hypothesis tests:** Induce perturbations (e.g., controlled transient light events) and observe whether high κ_t conditions produce oscillatory behaviors as predicted.

## 8. Conclusion

We provide a formal, testable dynamical-systems account of cognitive-physiological coherence that links environmental astronomy and human physiology. The model is intentionally modular: any suboperator can be refined or replaced, empirical inputs can be swapped in, and the visualization pipeline enables results to be communicated effectively. The central theoretical insight — that the ability to perceive a coherent environment depends not only on the external signal but crucially on the physiological state of the perceiver — is supported by both simulation and an operational empirical plan.

The model makes no claims about consciousness, spirituality, or metaphysical phenomena. It is a rigorous mathematical framework that can be tested with standard scientific instrumentation (magnetometers, ECG, photometers) and evaluated using established statistical methods. If the predicted relationships between Schumann resonance, HRV, and perceptual coherence are confirmed by empirical data, the model could provide a new avenue for understanding how geophysical fields interact with human physiology and cognition.

## Appendix A: Operator Definitions and Reproducible Code

### A.1 Operator Definitions (Implementation Notes)

Below we give precise, minimal implementations used in the demonstration. Each function is intentionally simple and explicitly replaceable with a more sophisticated alternative.

**ℵ (Saliency):**

$$\aleph(C_t) = W \odot C_t \quad (W = [w_A, w_P, w_T])$$

i.e., element-wise weighting to emphasize point and transient components.

**Φ (Pattern Recognition):**

$$\Phi(x) = \tanh(Mx), \quad M \in \mathbb{R}^{n \times n}$$

**F (Framing):**

$$F(\phi, \Psi_t) = \beta \phi + (1 - \beta) \Psi_t$$

**L (Physiological Modulation):**

$$L(f; \kappa_t) = g(\kappa_t) \cdot f, \quad g(\kappa) = \text{clip}\left(\frac{1}{\kappa}, g_{\text{min}}, g_{\text{max}}\right)$$

**Ω (Synthesis):**

$$\Omega(x) = \frac{x}{||x|| + \epsilon}$$

**ρ (Reflection):** Identity or smoothing operator as required.

### A.2 Python Simulation (Complete)

The full simulation code, including deterministic synthetic SR/HRV, operator implementations, simulation loop, and animation, is available in the supplementary materials. Save as `mandala_sim.py` and run with Python 3.8+ and standard scientific libraries (numpy, pandas, matplotlib).

### A.3 Reproducibility Checklist

1. **Required software:** Python 3.8+, numpy, pandas, matplotlib, ffmpeg (optional for video output).
2. **Data sources:** GCMS SR stream, wearable ECG traces (RR intervals), all-sky photometer.
3. **Preprocessing:** Bandpass and artifact removal for SR; NN cleaning and spectral HRV pipeline for ECG.
4. **Parameter seeds and random seeds** used in the example simulation are documented in the script for full reproducibility.

## Appendix B: Future Work — Extensions and Experiments

- Replace Φ with a convolutional spectral detector tuned to sky-luminance temporal scales; use unsupervised learning to derive pattern kernels.
- Model L as a stateful nonlinear oscillator to capture hysteresis and path dependence in physiological modulation.
- Integrate multi-site SR measurements and spatially distributed observers to study multi-agent coherence and resonance coupling.
- Design laboratory experiments with controlled transient visual stimuli and simultaneous HRV + perceptual report to empirically confirm oscillatory and dissolution predictions.
- Extend the model to include other geophysical parameters (geomagnetic Kp index, solar wind velocity) as additional environmental forcing terms.
- Test the model with clinical populations (e.g., anxiety disorders, PTSD) to determine whether the κ_t → oscillation prediction holds in pathological autonomic states.

## Footnotes: HNC Terminology Cross-Reference

| HNC Term (Original) | Scientific Equivalent Used in This Paper |
|-----------------------|------------------------------------------|
| Symbolic cycle / tree of light | Hierarchical signal processing architecture |
| The stag / living node | Physiological modulation operator / autonomic gain parameter |
| Mandala of night | Circular dashboard / polar visualization |
| Perceptual coherence | Cognitive-physiological coherence / state integration index |
| Chronology of light | Astronomical luminance schedule |
| Sacred frequencies / divine harmonics | Natural resonant frequencies / Solfeggio tones |
| Love frequency | 528 Hz Solfeggio tone (historical sound healing context) |
| Field clearing | Resonant stabilization |
| Substrate coherence | Cross-spectral correlation coefficient |
| LEV stabilization event | Limit cycle stabilization |
| Lighthouse / echo | Time-delayed feedback mechanism |
| Gaia | Earth system / planetary environment |
| Consciousness engineering | Cognitive-physiological modeling |
| Reality manipulation | Predictive modeling with feedback |
| Multiversal | Multi-channel / multi-site |
| Quantum archaeology | Retrospective anomaly detection |
| Prime Sentinel | Principal Investigator |
| Witness of the First Breath | Framework documentarian |
| Key of the Flame | Authentication holder |

---

**Data Availability**

The simulation code and synthetic data are available in the supplementary materials. Real-world validation data (SR, HRV, photometry) will be made available upon completion of the empirical validation study.

**Acknowledgments**

Thanks to collaborators and reviewers who contributed to the earlier draft; the present whitepaper consolidates and extends that material. The earlier draft, "Modeling Light Dynamics Through Astronomy" (G. Leckey, October 2025), served as the basis for the present formalization.

**References and Data Sources**

1. Modeling Light Dynamics Through Astronomy (Draft). G. Leckey, October 2025. (Source document used to build this paper.)
2. HeartMath Institute — GCMS Live Data: https://www.heartmath.org/gci/gcms/live-data/
3. British Geological Survey — Schumann Resonances: https://geomag.bgs.ac.uk/research/IARs.html
4. NASA Science: The Impact of Schumann Resonances on Human Physiology
5. PhysioNet: HRV databases and tools: https://physionet.org
6. SWELL dataset (Kaggle): https://www.kaggle.com/datasets/qiriro/swell-heart-rate-variability
7. Time and Date: Oban astronomical times: https://www.timeanddate.com/astronomy/night/uk/oban
8. Orionid meteor shower overview: Royal Museums Greenwich: https://www.rmg.co.uk/stories/space-astronomy/orionid-meteor-shower-2025-when-where-see-it-uk
9. Schumann, W. O. (1952). "Über die strahlungslosen Eigenschwingungen einer leitenden Kugel." *Zeitschrift für Naturforschung A*, 7a, 149–154.
10. Balser, M., & Wagner, C. A. (1960). "Measurements of the Spectrum of Earth–Ionosphere Cavity Resonances." *Nature*, 188(4751), 638–641.
11. Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). "Heart rate variability: standards of measurement, physiological interpretation and clinical use." *Circulation*, 93(5), 1043–1065.
