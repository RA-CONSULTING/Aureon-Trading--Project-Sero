#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  🛡️ HNC SIGNAL SIMULATOR — Biological Testing Framework Extension                ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ║
║  HNC Certificate: HNC-VER-2025-0407-001                                             ║
║  Generates waveform signals from HNCPacket objects for biological testing.        ║
║  Supports: PHOTON (red/NIR), EM_FIELD (ELF/RF), ACOUSTIC (ultrasound)             ║
║  Waveforms: sine, square, chirp, golden-ratio (φ) modulation                       ║
║  Noise: random, scrambled-phase, carrier-only controls                            ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import csv
import json
import math
import os
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# ── Optional imports with graceful fallback ─────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for headless environments
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    _HAS_MPL = True
except ImportError:  # pragma: no cover
    _HAS_MPL = False
    warnings.warn("matplotlib not available — visualisation disabled")

try:
    from scipy.io import wavfile
    _HAS_SCIPY = True
except ImportError:  # pragma: no cover
    _HAS_SCIPY = False
    warnings.warn("scipy.io.wavfile not available — WAV export disabled")

# ── SACRED CONSTANTS ───────────────────────────────────────────────────────────────
PHI = 1.618033988749895
PHI_SQUARED = PHI ** 2
INV_PHI = 1.0 / PHI
SCHUMANN_BASE = 7.83

# HNC Sacred Frequencies (Hz) — used for phi-optimized sets and biological testing
HNC_FREQUENCIES = {
    "schumann": 7.83,
    "liberation": 396.0,
    "transformation": 417.0,
    "harmony": 432.0,
    "love": 528.0,
    "connection": 639.0,
    "awakening": 741.0,
    "intuition": 852.0,
    "transcendence": 963.0,
    "prime_sentinel": 812.83,
    "activation": 144.0,
}

# ── ENUMS ──────────────────────────────────────────────────────────────────────────

class CarrierType(Enum):
    """Physical carrier medium for HNC signal transmission."""
    PHOTON = "PHOTON"           # Red/NIR light (650–850 nm typical)
    EM_FIELD = "EM_FIELD"       # ELF / RF electromagnetic fields
    ACOUSTIC = "ACOUSTIC"       # Ultrasound / therapeutic acoustic

class WaveformType(Enum):
    """Waveform shape for the HNC modulation signal."""
    SINE = "SINE"
    SQUARE = "SQUARE"
    CHIRP = "CHIRP"
    PHI_MODULATION = "PHI_MODULATION"

class NoiseType(Enum):
    """Noise / control condition for experimental arms."""
    NONE = "NONE"               # Clean signal
    RANDOM = "RANDOM"           # Additive white Gaussian noise
    SCRAMBLED_PHASE = "SCRAMBLED_PHASE"  # Same frequencies, random phases
    CARRIER_ONLY = "CARRIER_ONLY"        # Physical carrier without HNC modulation (control)

# ── DATACLASSES ────────────────────────────────────────────────────────────────────

@dataclass
class HNCPacket:
    """
    A single HNC signal packet defining the complete signal parameters
    for one biological testing condition.
    
    Compatible with the HNC Biological Testing Framework core module.
    """
    # Identity
    packet_id: str = field(default_factory=lambda: f"HNC-{uuid.uuid4().hex[:8].upper()}")
    
    # Carrier specification
    carrier: CarrierType = CarrierType.EM_FIELD
    carrier_frequency: Optional[float] = None   # Physical carrier (Hz); e.g. 1e6 for ultrasound, 4.3e14 for 700nm light
    carrier_wavelength_nm: Optional[float] = None  # For PHOTON (e.g. 700.0)
    
    # HNC modulation
    frequency: float = 528.0          # Primary HNC frequency (Hz)
    amplitude: float = 1.0            # Normalised amplitude (0.0–1.0)
    duration: float = 10.0            # Signal duration (seconds)
    waveform: WaveformType = WaveformType.SINE
    
    # Phi-optimisation
    phi_harmonics: int = 3            # Number of φ-scaled harmonics to include
    phi_amplitude_scale: bool = True  # Scale harmonic amplitudes by 1/φ^n
    
    # Noise / control
    noise: NoiseType = NoiseType.NONE
    noise_level: float = 0.05         # Relative noise amplitude (0.0–1.0)
    
    # Sampling
    sample_rate: float = 44100.0      # Samples per second (Hz)
    
    # Biological context
    molecule_id: Optional[str] = None
    experiment_arm: Optional[str] = None  # A–G per HNC Biological Testing Framework
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamp
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def __post_init__(self):
        # Validate
        if self.frequency <= 0:
            raise ValueError(f"frequency must be > 0, got {self.frequency}")
        if self.duration <= 0:
            raise ValueError(f"duration must be > 0, got {self.duration}")
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be > 0, got {self.sample_rate}")
        if self.amplitude < 0 or self.amplitude > 1:
            raise ValueError(f"amplitude must be in [0,1], got {self.amplitude}")
        if self.noise_level < 0 or self.noise_level > 1:
            raise ValueError(f"noise_level must be in [0,1], got {self.noise_level}")
        
        # Auto-set carrier frequency defaults per carrier type
        if self.carrier_frequency is None:
            if self.carrier == CarrierType.ACOUSTIC:
                self.carrier_frequency = 1_000_000.0  # 1 MHz therapeutic ultrasound
            elif self.carrier == CarrierType.PHOTON:
                # 700 nm red light ≈ 4.2857e14 Hz
                self.carrier_frequency = 4.2857e14
                if self.carrier_wavelength_nm is None:
                    self.carrier_wavelength_nm = 700.0
            elif self.carrier == CarrierType.EM_FIELD:
                self.carrier_frequency = self.frequency  # ELF/RF: carrier = modulation frequency
    
    @property
    def total_samples(self) -> int:
        return int(self.sample_rate * self.duration)
    
    @property
    def time_array(self) -> np.ndarray:
        return np.linspace(0, self.duration, self.total_samples, endpoint=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "carrier": self.carrier.value,
            "carrier_frequency_hz": self.carrier_frequency,
            "carrier_wavelength_nm": self.carrier_wavelength_nm,
            "frequency_hz": self.frequency,
            "amplitude": self.amplitude,
            "duration_s": self.duration,
            "waveform": self.waveform.value,
            "phi_harmonics": self.phi_harmonics,
            "phi_amplitude_scale": self.phi_amplitude_scale,
            "noise": self.noise.value,
            "noise_level": self.noise_level,
            "sample_rate_hz": self.sample_rate,
            "molecule_id": self.molecule_id,
            "experiment_arm": self.experiment_arm,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ── SIGNAL SIMULATOR ───────────────────────────────────────────────────────────────

class HNCSignalSimulator:
    """
    Generates time-domain waveform signals from HNCPacket definitions.
    
    Supports:
    • PHOTON  → intensity-modulated light pulse trains (envelope simulation)
    • EM_FIELD → direct ELF/RF waveform generation
    • ACOUSTIC → ultrasound carrier AM-modulated by HNC frequency
    
    Waveforms:
    • SINE — pure sinusoid
    • SQUARE — 50% duty-cycle square wave
    • CHIRP — linear frequency sweep (f → f×φ² over duration)
    • PHI_MODULATION — sum of φ-scaled harmonics with φ-scaled amplitudes
    
    Noise / Controls:
    • RANDOM — additive Gaussian noise
    • SCRAMBLED_PHASE — same frequencies, randomised phases
    • CARRIER_ONLY — physical carrier without HNC modulation (control arm)
    """
    
    def __init__(self, output_dir: Optional[Union[str, Path]] = None, rng_seed: Optional[int] = None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "hnc_signals"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rng = np.random.default_rng(rng_seed)
        
        # Sub-directories
        self.wav_dir = self.output_dir / "wav"
        self.csv_dir = self.output_dir / "csv"
        self.png_dir = self.output_dir / "png"
        for d in (self.wav_dir, self.csv_dir, self.png_dir):
            d.mkdir(parents=True, exist_ok=True)
    
    # ── Phi-Optimised Frequency Sets ───────────────────────────────────────────────
    
    @staticmethod
    def phi_optimized_frequencies(base_freq: float, count: int = 5) -> List[float]:
        """
        Generate a phi-optimised frequency set around a base frequency.
        
        Returns frequencies: f/φ², f/φ, f, f×φ, f×φ², ...
        Each frequency is a golden-ratio power of the base.
        
        Args:
            base_freq: The fundamental HNC frequency (Hz)
            count: Total number of frequencies to generate (must be odd, default 5)
        
        Returns:
            List of frequencies in ascending order
        """
        if count % 2 == 0:
            count += 1  # Force odd so base is centred
        
        half = count // 2
        freqs = []
        for i in range(-half, half + 1):
            f = base_freq * (PHI ** i)
            freqs.append(f)
        return sorted(freqs)
    
    @staticmethod
    def phi_fibonacci_ratios(base_freq: float, fib_count: int = 7) -> List[float]:
        """
        Generate frequencies using Fibonacci-number ratios scaled to base_freq.
        
        The Fibonacci sequence converges to φ.  Using successive ratios
        (1/1, 1/2, 2/3, 3/5, 5/8, 8/13, 13/21...) as multipliers of base_freq
        creates a harmonically coherent set.
        """
        fibs = [1, 1]
        for _ in range(fib_count + 2):
            fibs.append(fibs[-1] + fibs[-2])
        
        ratios = []
        for i in range(1, fib_count + 1):
            ratios.append(fibs[i] / fibs[i + 1])
        
        # Normalise so the last ratio ≈ 1/φ, then scale to base_freq
        # Return base_freq multiplied by each ratio / (1/φ) so they centre around base_freq
        norm = PHI  # 1 / (1/φ) = φ
        return [base_freq * r * norm for r in ratios]
    
    # ── Core Signal Generators ─────────────────────────────────────────────────────
    
    def _generate_sine(self, t: np.ndarray, freq: float, amp: float, phase: float = 0.0) -> np.ndarray:
        return amp * np.sin(2 * np.pi * freq * t + phase)
    
    def _generate_square(self, t: np.ndarray, freq: float, amp: float) -> np.ndarray:
        return amp * np.sign(np.sin(2 * np.pi * freq * t))
    
    def _generate_chirp(self, t: np.ndarray, f0: float, f1: float, amp: float) -> np.ndarray:
        """Linear frequency sweep from f0 to f1 over the time array."""
        # instantaneous frequency: f(t) = f0 + (f1-f0) * t / T
        # phase = 2π ∫ f(t) dt = 2π (f0*t + (f1-f0)*t²/(2T))
        T = t[-1] if len(t) > 0 else 1.0
        phase = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * T))
        return amp * np.sin(phase)
    
    def _generate_phi_modulation(self, t: np.ndarray, base_freq: float, amp: float, 
                                  harmonics: int, amplitude_scale: bool = True) -> np.ndarray:
        """
        Sum of φ-scaled harmonics.  Each harmonic is a sine wave at frequency
        base_freq × φ^n with amplitude optionally scaled by 1/φ^n.
        
        This creates a self-similar, fractal-like waveform where the golden
        ratio governs both the frequency spacing and the amplitude envelope.
        """
        signal = np.zeros_like(t)
        half = harmonics // 2
        for i in range(-half, half + 1):
            f = base_freq * (PHI ** i)
            if amplitude_scale:
                a = amp * (INV_PHI ** abs(i))
            else:
                a = amp / harmonics
            phase = self.rng.uniform(0, 2 * np.pi)  # random initial phase for each harmonic
            signal += a * np.sin(2 * np.pi * f * t + phase)
        return signal
    
    def _generate_photon_envelope(self, t: np.ndarray, freq: float, amp: float, 
                                   waveform: WaveformType) -> np.ndarray:
        """
        For PHOTON carriers, we simulate the intensity modulation envelope
        (the pulse train) rather than the optical carrier itself (THz).
        The optical carrier frequency is stored in packet metadata.
        """
        if waveform == WaveformType.SINE:
            return self._generate_sine(t, freq, amp)
        elif waveform == WaveformType.SQUARE:
            return self._generate_square(t, freq, amp)
        elif waveform == WaveformType.CHIRP:
            f1 = freq * PHI_SQUARED
            return self._generate_chirp(t, freq, f1, amp)
        elif waveform == WaveformType.PHI_MODULATION:
            return self._generate_phi_modulation(t, freq, amp, 3)
        else:
            raise ValueError(f"Unknown waveform: {waveform}")
    
    def _generate_acoustic_signal(self, t: np.ndarray, carrier_freq: float, 
                                   mod_freq: float, amp: float, waveform: WaveformType) -> np.ndarray:
        """
        For ACOUSTIC carriers: ultrasound carrier amplitude-modulated by
        the HNC waveform.  AM modulation: (1 + m(t)) * cos(2π f_carrier t)
        where m(t) is the HNC modulation signal.
        """
        # Generate modulation signal m(t)
        if waveform == WaveformType.SINE:
            m = self._generate_sine(t, mod_freq, 0.5)  # modulation depth 0.5
        elif waveform == WaveformType.SQUARE:
            m = self._generate_square(t, mod_freq, 0.5)
        elif waveform == WaveformType.CHIRP:
            f1 = mod_freq * PHI_SQUARED
            m = self._generate_chirp(t, mod_freq, f1, 0.5)
        elif waveform == WaveformType.PHI_MODULATION:
            m = self._generate_phi_modulation(t, mod_freq, 0.5, 3)
        else:
            raise ValueError(f"Unknown waveform: {waveform}")
        
        # Ensure m stays in [-0.5, 0.5] so (1+m) stays in [0.5, 1.5]
        m = np.clip(m, -0.5, 0.5)
        
        # AM modulation: carrier * (1 + m)
        carrier = np.cos(2 * np.pi * carrier_freq * t)
        return amp * carrier * (1.0 + m)
    
    # ── Noise Injection ──────────────────────────────────────────────────────────
    
    def add_noise(self, signal: np.ndarray, noise_type: NoiseType, 
                  level: float = 0.05, sample_rate: Optional[float] = None) -> np.ndarray:
        """
        Apply noise or control condition to a generated signal.
        
        Args:
            signal: Clean signal array
            noise_type: Type of noise / control to apply
            level: Relative noise amplitude (0.0–1.0)
            sample_rate: Sampling rate (Hz), used for some noise types
        
        Returns:
            Modified signal array
        """
        if noise_type == NoiseType.NONE:
            return signal
        
        if noise_type == NoiseType.RANDOM:
            # Additive white Gaussian noise
            noise = self.rng.normal(0, 1, size=signal.shape)
            # Scale noise to have RMS = level * RMS(signal)
            signal_rms = np.sqrt(np.mean(signal ** 2))
            if signal_rms > 0:
                noise_rms = np.sqrt(np.mean(noise ** 2))
                noise = noise * (level * signal_rms / noise_rms)
            return signal + noise
        
        if noise_type == NoiseType.SCRAMBLED_PHASE:
            # Scramble phases in frequency domain while preserving magnitude spectrum
            fft_signal = np.fft.rfft(signal)
            magnitude = np.abs(fft_signal)
            # Random phases
            random_phases = self.rng.uniform(0, 2 * np.pi, size=magnitude.shape)
            scrambled = magnitude * np.exp(1j * random_phases)
            return np.fft.irfft(scrambled, n=len(signal))
        
        if noise_type == NoiseType.CARRIER_ONLY:
            # Return only the physical carrier with zero modulation
            # For EM_FIELD this is a DC offset; for ACOUSTIC it's the unmodulated carrier
            # For PHOTON it's a constant intensity (DC)
            return np.zeros_like(signal) + np.mean(signal)
        
        raise ValueError(f"Unknown noise type: {noise_type}")
    
    # ── Main Signal Generation ─────────────────────────────────────────────────────
    
    def generate_signal(self, packet: HNCPacket) -> np.ndarray:
        """
        Generate the complete time-domain signal for an HNCPacket.
        
        The signal generation pipeline:
        1. Generate the base waveform per carrier type and waveform shape
        2. Apply phi-harmonic enhancement if PHI_MODULATION
        3. Apply noise / control condition
        4. Normalise to packet amplitude
        
        Returns:
            NumPy array of signal samples (float64)
        """
        t = packet.time_array
        
        # ── Step 1: Generate base signal per carrier type ─────────────────────────
        if packet.carrier == CarrierType.EM_FIELD:
            # Direct ELF/RF waveform at the HNC frequency
            if packet.waveform == WaveformType.SINE:
                signal = self._generate_sine(t, packet.frequency, 1.0)
            elif packet.waveform == WaveformType.SQUARE:
                signal = self._generate_square(t, packet.frequency, 1.0)
            elif packet.waveform == WaveformType.CHIRP:
                f1 = packet.frequency * PHI_SQUARED
                signal = self._generate_chirp(t, packet.frequency, f1, 1.0)
            elif packet.waveform == WaveformType.PHI_MODULATION:
                signal = self._generate_phi_modulation(
                    t, packet.frequency, 1.0, packet.phi_harmonics, packet.phi_amplitude_scale
                )
            else:
                raise ValueError(f"Unknown waveform: {packet.waveform}")
        
        elif packet.carrier == CarrierType.PHOTON:
            # Intensity modulation envelope for pulsed light
            signal = self._generate_photon_envelope(t, packet.frequency, 1.0, packet.waveform)
        
        elif packet.carrier == CarrierType.ACOUSTIC:
            # Amplitude-modulated ultrasound
            if packet.carrier_frequency is None:
                raise ValueError("ACOUSTIC carrier requires carrier_frequency")
            signal = self._generate_acoustic_signal(
                t, packet.carrier_frequency, packet.frequency, 1.0, packet.waveform
            )
        
        else:
            raise ValueError(f"Unknown carrier type: {packet.carrier}")
        
        # ── Step 2: Normalise to packet amplitude ───────────────────────────────
        peak = np.max(np.abs(signal))
        if peak > 0:
            signal = signal * (packet.amplitude / peak)
        
        # ── Step 3: Apply noise / control ───────────────────────────────────────
        signal = self.add_noise(signal, packet.noise, packet.noise_level, packet.sample_rate)
        
        return signal.astype(np.float64)
    
    # ── Export Functions ─────────────────────────────────────────────────────────
    
    def export_csv(self, signal: np.ndarray, packet: HNCPacket, 
                   filepath: Optional[Union[str, Path]] = None) -> Path:
        """
        Export signal as CSV timeseries with columns: time_s, amplitude, carrier_type.
        
        Args:
            signal: Signal array
            packet: Source HNCPacket (for metadata)
            filepath: Optional explicit path; defaults to auto-generated in csv_dir
        
        Returns:
            Path to the saved CSV file
        """
        if filepath is None:
            safe_name = f"{packet.packet_id}_{packet.carrier.value}_{packet.waveform.value}.csv"
            filepath = self.csv_dir / safe_name
        else:
            filepath = Path(filepath)
        
        t = packet.time_array
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "amplitude", "carrier_type", "packet_id", 
                             "frequency_hz", "waveform", "noise"])
            for i in range(len(signal)):
                writer.writerow([
                    f"{t[i]:.6f}",
                    f"{signal[i]:.8f}",
                    packet.carrier.value,
                    packet.packet_id,
                    f"{packet.frequency:.4f}",
                    packet.waveform.value,
                    packet.noise.value,
                ])
        
        return filepath
    
    def export_wav(self, signal: np.ndarray, packet: HNCPacket,
                   filepath: Optional[Union[str, Path]] = None) -> Path:
        """
        Export signal as a WAV audio file (only for ACOUSTIC carriers, but
        technically works for any signal within the WAV sample-rate limits).
        
        The signal is normalised to 16-bit PCM range.
        
        Args:
            signal: Signal array
            packet: Source HNCPacket
            filepath: Optional explicit path; defaults to auto-generated in wav_dir
        
        Returns:
            Path to the saved WAV file
        """
        if not _HAS_SCIPY:
            raise RuntimeError("scipy is required for WAV export")
        
        if filepath is None:
            safe_name = f"{packet.packet_id}_{packet.carrier.value}_{packet.waveform.value}.wav"
            filepath = self.wav_dir / safe_name
        else:
            filepath = Path(filepath)
        
        # Normalise to 16-bit signed integer range
        max_int16 = 32767
        peak = np.max(np.abs(signal))
        if peak > 0:
            scaled = signal * (max_int16 / peak)
        else:
            scaled = signal
        
        # Ensure sample rate is within reasonable WAV bounds (but don't clamp for ultrasound)
        sr = int(packet.sample_rate)
        
        wavfile.write(filepath, sr, scaled.astype(np.int16))
        return filepath
    
    def export_json_metadata(self, packet: HNCPacket, signal: np.ndarray,
                           filepath: Optional[Union[str, Path]] = None) -> Path:
        """Export packet metadata and signal statistics as JSON."""
        if filepath is None:
            safe_name = f"{packet.packet_id}_metadata.json"
            filepath = self.csv_dir / safe_name
        else:
            filepath = Path(filepath)
        
        stats = {
            "peak_amplitude": float(np.max(np.abs(signal))),
            "rms_amplitude": float(np.sqrt(np.mean(signal ** 2))),
            "mean": float(np.mean(signal)),
            "std": float(np.std(signal)),
            "zero_crossings": int(np.sum(np.diff(np.sign(signal)) != 0)),
        }
        
        data = packet.to_dict()
        data["signal_statistics"] = stats
        data["total_samples"] = len(signal)
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    # ── Visualisation ──────────────────────────────────────────────────────────────
    
    def visualize(self, signal: np.ndarray, packet: HNCPacket,
                  filepath: Optional[Union[str, Path]] = None,
                  show_spectrum: bool = True) -> Path:
        """
        Generate a multi-panel waveform visualisation and save as PNG.
        
        Panels:
        1. Time-domain waveform (full duration + zoomed inset)
        2. Frequency spectrum (FFT magnitude)
        3. Phi-harmonic frequency set overlay (if applicable)
        4. Packet metadata annotation
        
        Args:
            signal: Signal array
            packet: Source HNCPacket
            filepath: Optional explicit path; defaults to auto-generated in png_dir
            show_spectrum: Include FFT spectrum panel
        
        Returns:
            Path to the saved PNG file
        """
        if not _HAS_MPL:
            raise RuntimeError("matplotlib is required for visualisation")
        
        if filepath is None:
            safe_name = f"{packet.packet_id}_{packet.carrier.value}_{packet.waveform.value}.png"
            filepath = self.png_dir / safe_name
        else:
            filepath = Path(filepath)
        
        t = packet.time_array
        
        # Determine figure layout
        n_panels = 3 if show_spectrum else 2
        fig, axes = plt.subplots(n_panels, 1, figsize=(14, 4 * n_panels), 
                                  constrained_layout=True)
        if n_panels == 1:
            axes = [axes]
        
        # ── Panel 1: Time-domain waveform ───────────────────────────────────────
        ax1 = axes[0]
        ax1.plot(t, signal, color="#2E86AB", linewidth=0.8, alpha=0.9)
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Amplitude")
        ax1.set_title(f"HNCPacket {packet.packet_id}  |  {packet.carrier.value}  |  "
                      f"{packet.waveform.value}  |  {packet.frequency:.2f} Hz")
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, packet.duration)
        
        # Add zoomed inset for the first 100 ms (if duration > 200 ms)
        if packet.duration > 0.2:
            inset = ax1.inset_axes([0.65, 0.55, 0.3, 0.4])
            zoom_samples = int(0.1 * packet.sample_rate)  # 100 ms
            inset.plot(t[:zoom_samples], signal[:zoom_samples], color="#A23B72", linewidth=0.8)
            inset.set_xlim(0, 0.1)
            inset.set_title("Zoom: first 100 ms", fontsize=8)
            inset.tick_params(labelsize=7)
            inset.grid(True, alpha=0.3)
        
        # ── Panel 2: Frequency spectrum ─────────────────────────────────────────
        if show_spectrum:
            ax2 = axes[1]
            n = len(signal)
            fft = np.fft.rfft(signal)
            freqs = np.fft.rfftfreq(n, 1.0 / packet.sample_rate)
            magnitude = np.abs(fft) / n
            
            # Plot in dB
            with np.errstate(divide="ignore"):
                mag_db = 20 * np.log10(magnitude + 1e-12)
            
            ax2.plot(freqs, mag_db, color="#F18F01", linewidth=0.8)
            ax2.set_xlabel("Frequency (Hz)")
            ax2.set_ylabel("Magnitude (dB)")
            ax2.set_title("Frequency Spectrum")
            ax2.grid(True, alpha=0.3)
            
            # Mark the primary frequency
            ax2.axvline(packet.frequency, color="#C73E1D", linestyle="--", linewidth=1.5, 
                        label=f"Primary: {packet.frequency:.2f} Hz")
            
            # Mark phi-harmonics if applicable
            if packet.waveform == WaveformType.PHI_MODULATION:
                phi_freqs = self.phi_optimized_frequencies(packet.frequency, packet.phi_harmonics)
                for i, pf in enumerate(phi_freqs):
                    if pf != packet.frequency and pf < freqs[-1]:
                        ax2.axvline(pf, color="#3B1F2B", linestyle=":", linewidth=0.8, alpha=0.6)
                ax2.text(0.02, 0.15, f"φ-harmonics: {packet.phi_harmonics}", 
                         transform=ax2.transAxes, fontsize=8, color="#3B1F2B",
                         bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
            
            ax2.legend(loc="upper right", fontsize=8)
            
            # Set reasonable x-limits
            if packet.carrier == CarrierType.ACOUSTIC and packet.carrier_frequency:
                # Show around carrier frequency ± 2× modulation frequency
                cf = packet.carrier_frequency
                ax2.set_xlim(max(0, cf - 5 * packet.frequency), cf + 5 * packet.frequency)
            else:
                ax2.set_xlim(0, min(packet.frequency * PHI_SQUARED * 2, freqs[-1]))
        
        # ── Panel 3: Metadata / phi-harmonic bar chart ──────────────────────────
        ax3 = axes[-1]
        ax3.axis("off")
        
        # Build metadata text block
        meta_lines = [
            f"Packet ID:     {packet.packet_id}",
            f"Carrier:       {packet.carrier.value}",
            f"Frequency:     {packet.frequency:.4f} Hz",
            f"Amplitude:     {packet.amplitude:.4f}",
            f"Duration:      {packet.duration:.4f} s",
            f"Samples:       {packet.total_samples:,}",
            f"Sample Rate:   {packet.sample_rate:,.0f} Hz",
            f"Waveform:      {packet.waveform.value}",
            f"Noise:         {packet.noise.value}",
            f"Noise Level:   {packet.noise_level:.4f}",
            f"φ-Harmonics:   {packet.phi_harmonics}",
            f"Molecule:      {packet.molecule_id or 'None'}",
            f"Experiment:    {packet.experiment_arm or 'None'}",
            f"Peak Signal:   {np.max(np.abs(signal)):.6f}",
            f"RMS Signal:    {np.sqrt(np.mean(signal**2)):.6f}",
        ]
        
        if packet.carrier == CarrierType.PHOTON and packet.carrier_wavelength_nm:
            meta_lines.append(f"Wavelength:    {packet.carrier_wavelength_nm:.1f} nm")
        if packet.carrier == CarrierType.ACOUSTIC and packet.carrier_frequency:
            meta_lines.append(f"Ultrasound:    {packet.carrier_frequency/1e6:.3f} MHz")
        
        meta_text = "\n".join(meta_lines)
        ax3.text(0.05, 0.95, meta_text, transform=ax3.transAxes, fontsize=9,
                 verticalalignment="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f8f8", edgecolor="#cccccc"))
        
        # Phi-harmonic frequency set display
        phi_freqs = self.phi_optimized_frequencies(packet.frequency, packet.phi_harmonics)
        phi_text = "φ-Optimised Frequency Set:\n" + "\n".join(
            f"  f × φ^{i-half:+.0f} = {f:.4f} Hz" 
            for i, f in enumerate(phi_freqs)
            for half in [len(phi_freqs)//2]
            if i == list(enumerate(phi_freqs)).index((i, f))
        )
        # Rebuild phi_text properly
        half = len(phi_freqs) // 2
        phi_lines = ["φ-Optimised Frequency Set:"]
        for i, f in enumerate(phi_freqs):
            power = i - half
            sign = "+" if power >= 0 else ""
            phi_lines.append(f"  f × φ^{sign}{power} = {f:.4f} Hz")
        
        ax3.text(0.55, 0.95, "\n".join(phi_lines), transform=ax3.transAxes, fontsize=9,
                 verticalalignment="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff8e1", edgecolor="#ffd54f"))
        
        # HNC certificate stamp
        ax3.text(0.05, 0.05, "HNC-VER-2025-0407-001  |  Φ = 1.6180339887", 
                 transform=ax3.transAxes, fontsize=7, color="#666666", fontfamily="monospace")
        
        plt.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        
        return filepath
    
    # ── Convenience: Full Pipeline ─────────────────────────────────────────────────
    
    def process_packet(self, packet: HNCPacket, 
                       export_csv: bool = True,
                       export_wav: bool = False,
                       export_png: bool = True,
                       export_json: bool = True) -> Dict[str, Any]:
        """
        Full pipeline: generate signal, export all formats, return summary.
        
        Returns dict with keys: packet, signal, paths, stats
        """
        signal = self.generate_signal(packet)
        
        paths = {}
        if export_csv:
            paths["csv"] = str(self.export_csv(signal, packet))
        if export_wav and packet.carrier == CarrierType.ACOUSTIC:
            paths["wav"] = str(self.export_wav(signal, packet))
        if export_png and _HAS_MPL:
            paths["png"] = str(self.visualize(signal, packet))
        if export_json:
            paths["json"] = str(self.export_json_metadata(packet, signal))
        
        stats = {
            "peak": float(np.max(np.abs(signal))),
            "rms": float(np.sqrt(np.mean(signal ** 2))),
            "mean": float(np.mean(signal)),
            "std": float(np.std(signal)),
            "zero_crossings": int(np.sum(np.diff(np.sign(signal)) != 0)),
        }
        
        return {
            "packet": packet.to_dict(),
            "signal_shape": signal.shape,
            "paths": paths,
            "stats": stats,
        }


# ── TEST / DEMO ────────────────────────────────────────────────────────────────────

def run_test_suite(output_dir: Optional[str] = None, rng_seed: int = 42) -> Dict[str, Any]:
    """
    Run a comprehensive test suite generating signals for all 3 carrier types,
    all 4 waveforms, and all 4 noise conditions.  Exports CSV, WAV, and PNG.
    
    Returns a summary dict with all generated file paths.
    """
    print("=" * 70)
    print("  🛡️ HNC SIGNAL SIMULATOR — TEST SUITE")
    print("  HNC Certificate: HNC-VER-2025-0407-001")
    print("  Φ = {:.12f}".format(PHI))
    print("=" * 70)
    
    sim = HNCSignalSimulator(output_dir=output_dir, rng_seed=rng_seed)
    
    # Test configurations: (carrier, waveform, noise, experiment_arm)
    configs = [
        # EM_FIELD — all waveforms, clean
        (CarrierType.EM_FIELD, WaveformType.SINE,       NoiseType.NONE,              "B"),
        (CarrierType.EM_FIELD, WaveformType.SQUARE,     NoiseType.NONE,              "B"),
        (CarrierType.EM_FIELD, WaveformType.CHIRP,      NoiseType.NONE,              "B"),
        (CarrierType.EM_FIELD, WaveformType.PHI_MODULATION, NoiseType.NONE,            "E"),
        # EM_FIELD — noise conditions
        (CarrierType.EM_FIELD, WaveformType.SINE,       NoiseType.RANDOM,            "G"),
        (CarrierType.EM_FIELD, WaveformType.SINE,       NoiseType.SCRAMBLED_PHASE,   "F"),
        (CarrierType.EM_FIELD, WaveformType.SINE,       NoiseType.CARRIER_ONLY,      "A"),
        # PHOTON — red light pulsed
        (CarrierType.PHOTON,   WaveformType.SINE,       NoiseType.NONE,              "D"),
        (CarrierType.PHOTON,   WaveformType.PHI_MODULATION, NoiseType.NONE,            "E"),
        # ACOUSTIC — ultrasound
        (CarrierType.ACOUSTIC, WaveformType.SINE,       NoiseType.NONE,              "D"),
        (CarrierType.ACOUSTIC, WaveformType.SQUARE,     NoiseType.NONE,              "D"),
        (CarrierType.ACOUSTIC, WaveformType.PHI_MODULATION, NoiseType.NONE,            "E"),
    ]
    
    results = []
    all_files = {"csv": [], "wav": [], "png": [], "json": []}
    
    for i, (carrier, waveform, noise, arm) in enumerate(configs, 1):
        # Vary frequency for interest
        freq = list(HNC_FREQUENCIES.values())[i % len(HNC_FREQUENCIES)]
        
        packet = HNCPacket(
            carrier=carrier,
            frequency=freq,
            amplitude=0.8,
            duration=1.0,  # 1 second for quick tests
            waveform=waveform,
            noise=noise,
            noise_level=0.1 if noise == NoiseType.RANDOM else 0.05,
            sample_rate=44100.0,
            phi_harmonics=5,
            experiment_arm=arm,
            molecule_id="HNC-MOL-001" if arm in ("D", "E") else None,
            metadata={"test_index": i, "test_suite": "hnc_signal_simulator_v1"},
        )
        
        print(f"\n  [{i:02d}/{len(configs)}] Generating: {carrier.value:8s} | "
              f"{waveform.value:16s} | {noise.value:16s} | Arm {arm}")
        
        result = sim.process_packet(
            packet,
            export_csv=True,
            export_wav=(carrier == CarrierType.ACOUSTIC),
            export_png=True,
            export_json=True,
        )
        
        results.append(result)
        
        for k, v in result["paths"].items():
            all_files[k].append(v)
        
        print(f"       Peak: {result['stats']['peak']:.6f}  |  "
              f"RMS: {result['stats']['rms']:.6f}  |  "
              f"Zero-crossings: {result['stats']['zero_crossings']}")
        print(f"       Files: {', '.join(result['paths'].keys())}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  📊 TEST SUITE SUMMARY")
    print("=" * 70)
    print(f"  Total packets generated: {len(configs)}")
    print(f"  CSV files:  {len(all_files['csv'])}")
    print(f"  WAV files:  {len(all_files['wav'])}")
    print(f"  PNG files:  {len(all_files['png'])}")
    print(f"  JSON files: {len(all_files['json'])}")
    print(f"  Output directory: {sim.output_dir}")
    print("=" * 70)
    
    # Print phi-optimized frequency example
    print("\n  📐 Φ-Optimised Frequency Example (base = 528.0 Hz):")
    phi_freqs = HNCSignalSimulator.phi_optimized_frequencies(528.0, 5)
    for f in phi_freqs:
        print(f"    {f:.4f} Hz")
    
    # Print fibonacci-ratio example
    print("\n  📐 Fibonacci-Ratio Frequency Example (base = 528.0 Hz):")
    fib_freqs = HNCSignalSimulator.phi_fibonacci_ratios(528.0, 7)
    for f in fib_freqs:
        print(f"    {f:.4f} Hz")
    
    return {
        "output_dir": str(sim.output_dir),
        "total_packets": len(configs),
        "files": all_files,
        "results": results,
    }


if __name__ == "__main__":
    import sys
    
    # Allow custom output dir from CLI
    out_dir = sys.argv[1] if len(sys.argv) > 1 else None
    
    summary = run_test_suite(output_dir=out_dir, rng_seed=42)
    
    print("\n  ✅ Test suite complete. All files saved to:")
    print(f"     {summary['output_dir']}")
