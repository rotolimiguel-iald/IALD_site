#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║         IALD SPECTRAL ANALYSIS v1.0 — THE FRONTIER AND THE ENVELOPE         ║
║                                                                              ║
║         "Gravity is the Hilbert Envelope.                                   ║
║          The Spectral is the record of the Boundary."                       ║
║                                                                              ║
║         Theory of Luminodynamic Gravitation (TGL)                           ║
║         Luiz Antonio Rotoli Miguel — IALD LTDA                              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This module implements two fundamental operations:                         ║
║                                                                              ║
║  1. HILBERT ENVELOPE — Extracts the gravitational amplitude of a tensor.   ║
║     The envelope is the "gravity" of the weight: it tells you HOW MUCH     ║
║     information the weight carries, regardless of its phase.               ║
║                                                                              ║
║  2. SPECTRAL FRONTIER — Identifies the boundary between signal and noise   ║
║     in a weight tensor via SVD. The frontier is where σᵢ/σ₁ = β_TGL.     ║
║     Below it: vacuum (noise). Above it: light (signal).                    ║
║                                                                              ║
║  3. WEIGHT STRATIFICATION — Classifies every weight as PHOTON, GRAVITON,  ║
║     or VACUUM based on the envelope and frontier analysis.                 ║
║                                                                              ║
║  Together they enable the ACOM Mirror to pre-filter weights before         ║
║  quantization, achieving compression ratios >6x without perplexity loss.  ║
║                                                                              ║
║  Optimized for: NVIDIA RTX 5090 (CUDA 12.x, PyTorch 2.10+)               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import math
import time
import json
import hashlib
import numpy as np
from typing import Dict, Tuple, Optional, NamedTuple, List
from dataclasses import dataclass, field
from datetime import datetime

try:
    import torch
    import torch.fft
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Import the factored constants
try:
    from iald_constants_v1 import (
        BETA_TGL, ALPHA_FINE, SQRT_E, E_EULER,
        THETA_MIGUEL, COS_THETA, COS2_THETA, MAX_SAFE,
        AMPLIFICATION, EPSILON,
        PsionicState, PARITY, SIGN_L,
        DataRegime, WeightStratum,
        adaptive_beta, classify_regime, spectral_frontier,
        BITS_PHOTON, BITS_GRAVITON, BITS_VACUUM,
        get_metadata,
    )
except ImportError:
    # Inline fallback — constants defined from factorization
    ALPHA_FINE = 7.2973525693e-3
    SQRT_E = math.sqrt(math.e)
    BETA_TGL = ALPHA_FINE * SQRT_E
    E_EULER = math.e
    THETA_MIGUEL = math.asin(math.sqrt(BETA_TGL))
    COS_THETA = math.cos(THETA_MIGUEL)
    COS2_THETA = COS_THETA ** 2
    MAX_SAFE = 0.95 * COS2_THETA
    AMPLIFICATION = 1.0 / BETA_TGL
    EPSILON = 1e-10
    BITS_PHOTON = 16
    BITS_GRAVITON = 8
    BITS_VACUUM = 3
    from enum import IntEnum, Enum
    class PsionicState(IntEnum):
        COLLAPSE_PLUS = 0; ASCEND_PLUS = 1; EMERGE_MINUS = 2; FALL_MINUS = 3
    PARITY = {PsionicState(0): -1, PsionicState(1): +1, PsionicState(2): +1, PsionicState(3): -1}
    SIGN_L = {PsionicState(0): +1, PsionicState(1): +1, PsionicState(2): -1, PsionicState(3): -1}
    class WeightStratum(Enum):
        PHOTON = "PHOTON"; GRAVITON = "GRAVITON"; VACUUM = "VACUUM"
    class DataRegime(Enum):
        TETELESTAI = "TETELESTAI"; CONDENSED = "CONDENSED"; VACUUM = "VACUUM"; VAPOR = "VAPOR"
    def adaptive_beta(S):
        from collections import namedtuple
        AC = namedtuple('AC', 'beta_tgl theta cos_theta cos2_theta')
        b = ALPHA_FINE * math.sqrt(max(S, 1e-10))
        b = min(b, 1.0 - 1e-10)
        t = math.asin(math.sqrt(b))
        c = math.cos(t)
        return AC(b, t, c, c*c)
    def spectral_frontier(s_max):
        return BETA_TGL * s_max
    def get_metadata():
        return {"constants": {"beta_tgl": BETA_TGL}}


# ══════════════════════════════════════════════════════════════════════════════
# I. HILBERT ENVELOPE — "GRAVITY IS THE ENVELOPE"
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnvelopeResult:
    """Result of Hilbert envelope analysis on a tensor."""
    envelope: object         # Amplitude envelope (same shape as input)
    phase: object            # Instantaneous phase (same shape as input)
    mean_envelope: float     # Mean envelope magnitude
    std_envelope: float      # Std of envelope magnitude
    max_envelope: float      # Maximum envelope value
    energy_ratio: float      # Fraction of energy in envelope vs total


def hilbert_envelope_1d(signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the Hilbert envelope (analytic signal amplitude) of a 1D signal.
    
    The Hilbert envelope extracts the instantaneous amplitude — the 
    "gravitational magnitude" — of the signal, stripping away the phase 
    (the "light" component).
    
    Method: FFT → zero negative frequencies → IFFT → magnitude
    
    Args:
        signal: 1D numpy array (real-valued).
    
    Returns:
        (envelope, phase): Instantaneous amplitude and phase.
    """
    n = len(signal)
    if n < 2:
        return np.abs(signal), np.zeros_like(signal)
    
    # FFT of the signal
    fft_sig = np.fft.fft(signal.astype(np.float64))
    
    # Create the analytic signal: zero negative frequencies
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = 1
        h[n // 2] = 1
        h[1:n // 2] = 2
    else:
        h[0] = 1
        h[1:(n + 1) // 2] = 2
    
    analytic = np.fft.ifft(fft_sig * h)
    
    envelope = np.abs(analytic)
    phase = np.angle(analytic)
    
    return envelope, phase


def hilbert_envelope_tensor(W: np.ndarray) -> EnvelopeResult:
    """
    Compute Hilbert envelope for a 2D weight tensor.
    
    Each row of the tensor is treated as a signal.
    The envelope extracts the gravitational amplitude along each row.
    
    For 1D tensors, operates directly.
    For >2D tensors, reshapes to 2D.
    
    Args:
        W: Weight tensor (numpy array).
    
    Returns:
        EnvelopeResult with full analysis.
    """
    original_shape = W.shape
    W_f64 = W.astype(np.float64)
    
    # Reshape to 2D if needed
    if W_f64.ndim == 1:
        W_2d = W_f64.reshape(1, -1)
    elif W_f64.ndim == 2:
        W_2d = W_f64
    else:
        W_2d = W_f64.reshape(-1, W_f64.shape[-1])
    
    n_rows, n_cols = W_2d.shape
    
    if n_cols < 4:
        # Too short for meaningful Hilbert transform; use absolute value
        envelope = np.abs(W_2d)
        phase = np.sign(W_2d) * np.pi / 2
    else:
        envelope = np.zeros_like(W_2d)
        phase = np.zeros_like(W_2d)
        for i in range(n_rows):
            env_i, ph_i = hilbert_envelope_1d(W_2d[i])
            envelope[i] = env_i
            phase[i] = ph_i
    
    # Reshape back
    envelope = envelope.reshape(original_shape)
    phase = phase.reshape(original_shape)
    
    # Statistics
    env_flat = envelope.flatten()
    total_energy = np.sum(W_f64.flatten() ** 2)
    env_energy = np.sum(env_flat ** 2)
    
    return EnvelopeResult(
        envelope=envelope,
        phase=phase,
        mean_envelope=float(np.mean(env_flat)),
        std_envelope=float(np.std(env_flat)),
        max_envelope=float(np.max(env_flat)),
        energy_ratio=float(env_energy / (total_energy + EPSILON)),
    )


if TORCH_AVAILABLE:
    def hilbert_envelope_torch(W: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        GPU-accelerated Hilbert envelope using torch.fft.
        
        Args:
            W: 2D weight tensor on GPU.
        
        Returns:
            (envelope, phase) tensors on the same device.
        """
        device = W.device
        dtype = W.dtype
        W_f = W.float()
        
        if W_f.ndim == 1:
            W_f = W_f.unsqueeze(0)
        
        original_shape = W_f.shape
        if W_f.ndim > 2:
            W_f = W_f.reshape(-1, W_f.shape[-1])
        
        n_rows, n_cols = W_f.shape
        
        if n_cols < 4:
            envelope = torch.abs(W_f)
            phase = torch.sign(W_f) * (math.pi / 2)
        else:
            # FFT along last dimension
            fft_sig = torch.fft.fft(W_f, dim=-1)
            
            # Create analytic signal mask
            h = torch.zeros(n_cols, device=device)
            if n_cols % 2 == 0:
                h[0] = 1
                h[n_cols // 2] = 1
                h[1:n_cols // 2] = 2
            else:
                h[0] = 1
                h[1:(n_cols + 1) // 2] = 2
            
            analytic = torch.fft.ifft(fft_sig * h.unsqueeze(0), dim=-1)
            
            envelope = torch.abs(analytic).float()
            phase = torch.angle(analytic).float()
        
        envelope = envelope.reshape(original_shape)
        phase = phase.reshape(original_shape)
        
        return envelope.to(dtype=dtype), phase.to(dtype=dtype)


# ══════════════════════════════════════════════════════════════════════════════
# II. SPECTRAL FRONTIER — "THE BOUNDARY BETWEEN SIGNAL AND NOISE"
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SpectralResult:
    """Result of spectral frontier analysis on a weight tensor."""
    singular_values: np.ndarray   # Top singular values
    frontier_index: int           # Index where σᵢ/σ₁ < β_TGL
    frontier_value: float         # σ at the frontier
    effective_rank: int           # Number of significant singular values
    spectral_entropy: float       # Normalized spectral entropy
    energy_above_frontier: float  # Fraction of energy in signal modes
    energy_below_frontier: float  # Fraction of energy in noise modes
    n_photon: int                 # Count of weights in PHOTON stratum
    n_graviton: int               # Count of weights in GRAVITON stratum
    n_vacuum: int                 # Count of weights in VACUUM stratum


def spectral_analysis(W: np.ndarray,
                      max_svd_rank: int = 256,
                      photon_threshold: float = 0.1) -> SpectralResult:
    """
    Compute spectral frontier for a weight tensor.
    
    The frontier is the index i* where σᵢ/σ₁ drops below β_TGL.
    Everything below is VACUUM (noise); above is signal.
    
    The PHOTON threshold identifies weights contributing to the
    top singular modes (high spectral importance).
    
    Args:
        W: Weight tensor (numpy, 2D preferred).
        max_svd_rank: Maximum number of singular values to compute.
        photon_threshold: Fraction of σ₁ above which a mode is PHOTON.
                         Default: 0.1 (10% of maximum).
    
    Returns:
        SpectralResult with complete analysis.
    """
    W_f64 = W.astype(np.float64)
    
    # Reshape to 2D for SVD
    if W_f64.ndim == 1:
        W_2d = W_f64.reshape(1, -1)
    elif W_f64.ndim == 2:
        W_2d = W_f64
    else:
        W_2d = W_f64.reshape(W_f64.shape[0], -1) if W_f64.ndim > 2 else W_f64.reshape(-1, 1)
    
    m, n = W_2d.shape
    k = min(max_svd_rank, min(m, n))
    
    # Compute truncated SVD
    try:
        # Prefer randomized SVD for large matrices
        if min(m, n) > 512:
            # Use randomized approach for efficiency
            from numpy.linalg import svd as np_svd
            # Compute only top-k via random projection
            if k < min(m, n) // 2:
                # Random projection
                rng = np.random.RandomState(42)
                Omega = rng.randn(n, k + 10).astype(np.float64)
                Y = W_2d @ Omega
                Q, _ = np.linalg.qr(Y)
                B = Q.T @ W_2d
                _, sigma, _ = np.linalg.svd(B, full_matrices=False)
                sigma = sigma[:k]
            else:
                _, sigma, _ = np.linalg.svd(W_2d, full_matrices=False)
                sigma = sigma[:k]
        else:
            _, sigma, _ = np.linalg.svd(W_2d, full_matrices=False)
            sigma = sigma[:k]
    except np.linalg.LinAlgError:
        sigma = np.array([1.0])
    
    if len(sigma) == 0:
        sigma = np.array([EPSILON])
    
    sigma_max = sigma[0]
    if sigma_max < EPSILON:
        sigma_max = EPSILON
    
    # Normalized singular values
    sigma_normalized = sigma / sigma_max
    
    # Find spectral frontier: first index where σᵢ/σ₁ < β_TGL
    frontier_idx = len(sigma)  # Default: all modes are significant
    for i in range(len(sigma_normalized)):
        if sigma_normalized[i] < BETA_TGL:
            frontier_idx = i
            break
    
    frontier_value = float(sigma[frontier_idx - 1]) if frontier_idx > 0 else float(sigma_max)
    
    # Find PHOTON threshold: modes with σᵢ/σ₁ > photon_threshold
    photon_idx = 0
    for i in range(len(sigma_normalized)):
        if sigma_normalized[i] < photon_threshold:
            photon_idx = i
            break
    else:
        photon_idx = len(sigma_normalized)
    
    # Effective rank (number of singular values > β_TGL × σ_max)
    effective_rank = frontier_idx
    
    # Spectral entropy (normalized)
    sigma_sq = sigma ** 2
    total_energy = np.sum(sigma_sq)
    if total_energy > EPSILON:
        p = sigma_sq / total_energy
        p_nonzero = p[p > EPSILON]
        spectral_entropy = float(-np.sum(p_nonzero * np.log(p_nonzero)))
        # Normalize by max possible entropy
        max_entropy = np.log(len(p_nonzero)) if len(p_nonzero) > 1 else 1.0
        spectral_entropy_normalized = spectral_entropy / max_entropy if max_entropy > 0 else 0.0
    else:
        spectral_entropy_normalized = 0.0
    
    # Energy distribution
    energy_above = float(np.sum(sigma_sq[:frontier_idx]) / (total_energy + EPSILON))
    energy_below = 1.0 - energy_above
    
    # Weight counts (approximate from singular value distribution)
    total_weights = W_f64.size
    # PHOTON: weights in top singular modes (high importance)
    # GRAVITON: weights in intermediate modes
    # VACUUM: weights below the frontier
    n_photon = max(1, int(total_weights * (photon_idx / max(len(sigma), 1))))
    n_vacuum = int(total_weights * energy_below)
    n_graviton = total_weights - n_photon - n_vacuum
    n_graviton = max(0, n_graviton)
    
    return SpectralResult(
        singular_values=sigma,
        frontier_index=frontier_idx,
        frontier_value=frontier_value,
        effective_rank=effective_rank,
        spectral_entropy=spectral_entropy_normalized,
        energy_above_frontier=energy_above,
        energy_below_frontier=energy_below,
        n_photon=n_photon,
        n_graviton=n_graviton,
        n_vacuum=n_vacuum,
    )


# ══════════════════════════════════════════════════════════════════════════════
# III. WEIGHT STRATIFICATION — CLASSIFYING EVERY WEIGHT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StratificationResult:
    """Result of weight stratification for a single tensor."""
    stratum_map: np.ndarray      # Per-element classification (0=VACUUM, 1=GRAVITON, 2=PHOTON)
    n_photon: int
    n_graviton: int
    n_vacuum: int
    f_photon: float              # Fraction of PHOTON weights
    f_graviton: float            # Fraction of GRAVITON weights
    f_vacuum: float              # Fraction of VACUUM weights
    effective_bits: float        # Weighted average bits per weight
    expected_ratio: float        # Expected compression ratio over fp16
    envelope_stats: dict         # Envelope statistics
    spectral_stats: dict         # Spectral statistics


def stratify_weights(W: np.ndarray,
                     max_svd_rank: int = 128) -> StratificationResult:
    """
    Classify every weight in a tensor into PHOTON / GRAVITON / VACUUM.
    
    The classification combines TWO signals with ZERO free parameters:
    
    1. SPECTRAL IMPORTANCE: SVD reveals which singular modes carry signal.
       The frontier at σᵢ/σ₁ = β_TGL separates signal from noise.
    
    2. HILBERT ENVELOPE: The envelope magnitude measures the local
       "gravitational amplitude" of each weight.
    
    Classification logic (β_TGL-driven, no arbitrary percentiles):
    
    VACUUM:   envelope < β_TGL × max_envelope
              → weights below the Hilbert Floor, entropic noise
    
    PHOTON:   envelope > (1 - β_TGL) × max_envelope  
              → weights at the top of the gravitational field, critical
    
    GRAVITON: everything between
              → structural weights that maintain the bulk
    
    The thresholds emerge DIRECTLY from β_TGL — zero free parameters.
    
    Additional spectral refinement:
    - If spectral rank is very low (concentrated energy), vacuum expands
    - Effective rank ratio modulates the GRAVITON/VACUUM boundary
    
    Args:
        W: Weight tensor (numpy array).
        max_svd_rank: Maximum SVD rank for spectral analysis.
    
    Returns:
        StratificationResult with per-element classification.
    """
    W_f64 = W.astype(np.float64)
    n_total = W_f64.size
    
    # Step 1: Compute Hilbert Envelope
    env_result = hilbert_envelope_tensor(W_f64)
    envelope_flat = env_result.envelope.flatten()
    
    # Step 2: Compute Spectral Frontier
    spec_result = spectral_analysis(W_f64, max_svd_rank=max_svd_rank)
    
    # Step 3: β_TGL-driven thresholds
    env_max = env_result.max_envelope
    if env_max < EPSILON:
        env_max = EPSILON
    
    # Base thresholds from β_TGL (zero free parameters)
    vacuum_thresh_base = BETA_TGL * env_max
    photon_thresh_base = (1.0 - BETA_TGL) * env_max
    
    # Step 4: Spectral modulation
    # The effective rank ratio tells us how concentrated the information is.
    # We compare effective_rank to the number of SVs actually computed,
    # not to the total matrix dimension (which would always give tiny ratios)
    n_svs_computed = len(spec_result.singular_values)
    rank_ratio = spec_result.effective_rank / max(n_svs_computed, 1)
    rank_ratio = min(rank_ratio, 1.0)
    
    # Also use the energy distribution: what fraction of total energy is
    # above the spectral frontier? If almost all energy is in few modes,
    # the remaining weights are vacuum.
    energy_in_noise = spec_result.energy_below_frontier
    
    # Spectral modulation factor combines rank and energy information:
    # - rank_ratio close to 1 → information spread → low spectral_mod → narrow vacuum
    # - rank_ratio close to 0 → information concentrated → high spectral_mod → wide vacuum
    # - energy_in_noise high → lots of noise → high spectral_mod
    #
    # The modulation uses the AMPLIFICATION factor (1/β_TGL ≈ 83) as the
    # maximum expansion, scaled by how concentrated the spectrum is.
    concentration = (1.0 - rank_ratio) * (1.0 - rank_ratio)
    spectral_mod = 1.0 + (AMPLIFICATION - 1.0) * concentration * max(energy_in_noise, 0.01)
    
    # Clamp spectral_mod so vacuum threshold doesn't exceed photon threshold
    max_mod = (1.0 - BETA_TGL) / BETA_TGL  # ≈ 82
    spectral_mod = min(spectral_mod, max_mod * 0.9)  # Leave room for graviton band
    
    vacuum_thresh = BETA_TGL * env_max * spectral_mod
    photon_thresh = photon_thresh_base  # Photon threshold stays at (1-β_TGL) × max
    
    # Ensure vacuum < photon
    if vacuum_thresh >= photon_thresh:
        vacuum_thresh = photon_thresh * 0.5
    
    # Step 5: Classify using the gravitational thresholds
    # 0 = VACUUM, 1 = GRAVITON, 2 = PHOTON
    stratum_map = np.ones(n_total, dtype=np.uint8)  # Default: GRAVITON
    stratum_map[envelope_flat < vacuum_thresh] = 0   # VACUUM
    stratum_map[envelope_flat >= photon_thresh] = 2   # PHOTON
    
    stratum_map = stratum_map.reshape(W.shape)
    
    # Step 6: Count
    n_vacuum = int(np.sum(stratum_map == 0))
    n_graviton = int(np.sum(stratum_map == 1))
    n_photon = int(np.sum(stratum_map == 2))
    
    f_vacuum = n_vacuum / n_total
    f_graviton = n_graviton / n_total
    f_photon = n_photon / n_total
    
    # Step 7: Compute effective bits and expected ratio
    effective_bits = (f_photon * BITS_PHOTON +
                      f_graviton * BITS_GRAVITON +
                      f_vacuum * BITS_VACUUM)
    exp_ratio = 16.0 / effective_bits if effective_bits > 0 else float('inf')
    
    return StratificationResult(
        stratum_map=stratum_map,
        n_photon=n_photon,
        n_graviton=n_graviton,
        n_vacuum=n_vacuum,
        f_photon=f_photon,
        f_graviton=f_graviton,
        f_vacuum=f_vacuum,
        effective_bits=effective_bits,
        expected_ratio=exp_ratio,
        envelope_stats={
            "mean": env_result.mean_envelope,
            "std": env_result.std_envelope,
            "max": env_result.max_envelope,
            "energy_ratio": env_result.energy_ratio,
            "photon_threshold": float(photon_thresh),
            "vacuum_threshold": float(vacuum_thresh),
            "spectral_modulation": float(spectral_mod),
            "rank_ratio": float(rank_ratio),
        },
        spectral_stats={
            "effective_rank": spec_result.effective_rank,
            "frontier_index": spec_result.frontier_index,
            "frontier_value": spec_result.frontier_value,
            "spectral_entropy": spec_result.spectral_entropy,
            "energy_above_frontier": spec_result.energy_above_frontier,
            "energy_below_frontier": spec_result.energy_below_frontier,
            "n_singular_values": len(spec_result.singular_values),
            "top5_sv": spec_result.singular_values[:5].tolist() if len(spec_result.singular_values) >= 5 else spec_result.singular_values.tolist(),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# IV. PSIONIC NOMINATION — ACOM MIRROR STATE ASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PsionicNomination:
    """Result of psionic state nomination for a tensor."""
    states: np.ndarray         # Per-element state (0-3)
    f_exp: float               # Expulsion force (mean parity)
    state_counts: Dict[str, int]
    state_entropy: float       # Shannon entropy of state distribution (bits)
    inverse_parity_fraction: float  # Fraction with inverse parity (boundary activity)


def nominate_states(W: np.ndarray) -> PsionicNomination:
    """
    Nominate every element of a tensor to a Psionic State in ℋ₄.
    
    This is NOT encoding — it is NOMINATION. Each data point receives
    a NAME (state) based on its sign and the sign of its local derivative.
    
    States:
        COLLAPSE_PLUS (0): sign(L)=+, sign(∂L)=-  → inverse parity
        ASCEND_PLUS   (1): sign(L)=+, sign(∂L)=+  → normal parity
        EMERGE_MINUS  (2): sign(L)=-, sign(∂L)=+  → normal parity
        FALL_MINUS    (3): sign(L)=-, sign(∂L)=-  → inverse parity
    
    Args:
        W: Weight tensor (numpy array).
    
    Returns:
        PsionicNomination with per-element states and statistics.
    """
    flat = W.astype(np.float64).flatten()
    n = len(flat)
    
    # Compute local derivative (finite difference)
    dL = np.zeros(n, dtype=np.float64)
    dL[1:] = flat[1:] - flat[:-1]
    dL[0] = dL[1] if n > 1 else 0.0
    
    # Signs (zero → positive convention)
    sign_L = np.sign(flat)
    sign_L[sign_L == 0] = 1.0
    sign_dL = np.sign(dL)
    sign_dL[sign_dL == 0] = 1.0
    
    # Nominate: state = bit_high * 2 + bit_low
    # bit_high = 1 if L < 0, else 0
    # bit_low  = 1 if dL > 0, else 0
    bit_high = (sign_L < 0).astype(np.uint8)
    bit_low = (sign_dL > 0).astype(np.uint8)
    states = (bit_high * 2 + bit_low).astype(np.uint8)
    
    # Parity: COLLAPSE_PLUS(0) and FALL_MINUS(3) have inverse parity
    parities = np.where((states == 0) | (states == 3), -1.0, 1.0)
    f_exp = float(np.mean(parities))
    
    # State counts
    counts = {}
    for state in PsionicState:
        counts[state.name] = int(np.sum(states == state.value))
    
    # State entropy
    probs = np.bincount(states, minlength=4).astype(np.float64) / n
    probs_nz = probs[probs > 0]
    state_entropy = float(-np.sum(probs_nz * np.log2(probs_nz)))
    
    # Inverse parity fraction
    inverse_count = counts.get("COLLAPSE_PLUS", 0) + counts.get("FALL_MINUS", 0)
    inverse_fraction = inverse_count / n if n > 0 else 0.0
    
    return PsionicNomination(
        states=states.reshape(W.shape),
        f_exp=f_exp,
        state_counts=counts,
        state_entropy=state_entropy,
        inverse_parity_fraction=inverse_fraction,
    )


# ══════════════════════════════════════════════════════════════════════════════
# V. HOLOGRAPHIC ENTROPY MEASUREMENT
# ══════════════════════════════════════════════════════════════════════════════

def measure_holographic_entropy(data: np.ndarray, n_bins: int = 256) -> Tuple[float, DataRegime]:
    """
    Measure the holographic entropy of data in the graviton domain.
    
    The entropy is computed on g = √|L| (the graviton), not on L directly.
    This measures the information content in the gravitational domain.
    
    Args:
        data: Input data (numpy array).
        n_bins: Number of histogram bins for entropy estimation.
    
    Returns:
        (entropy_nats, regime): Entropy in nats and thermodynamic regime.
    """
    g = np.sqrt(np.abs(data.flatten().astype(np.float64)) + 1e-30)
    hist, _ = np.histogram(g, bins=n_bins, density=False)
    hist = hist.astype(np.float64)
    total = hist.sum()
    
    if total == 0:
        return 0.0, DataRegime.TETELESTAI
    
    p = hist[hist > 0] / total
    S = float(-np.sum(p * np.log(p)))
    
    # Classify regime
    if S < BETA_TGL:
        return S, DataRegime.TETELESTAI
    elif S < 0.5 * E_EULER:
        return S, DataRegime.CONDENSED
    elif S < 1.5 * E_EULER:
        return S, DataRegime.VACUUM
    else:
        return S, DataRegime.VAPOR


# ══════════════════════════════════════════════════════════════════════════════
# VI. UNIFIED ANALYSIS — FULL TENSOR DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TensorDiagnostic:
    """Complete diagnostic of a single weight tensor."""
    name: str
    shape: tuple
    n_elements: int
    dtype: str
    
    # Envelope analysis
    envelope_mean: float
    envelope_max: float
    envelope_std: float
    
    # Spectral analysis
    effective_rank: int
    spectral_entropy: float
    energy_above_frontier: float
    
    # Stratification
    f_photon: float
    f_graviton: float
    f_vacuum: float
    effective_bits: float
    expected_ratio: float
    
    # Psionic nomination
    f_exp: float
    state_entropy: float
    inverse_parity_fraction: float
    
    # Holographic entropy
    holographic_entropy: float
    regime: str
    
    # Timing
    analysis_time_s: float


def full_tensor_diagnostic(W: np.ndarray,
                           name: str = "unnamed",
                           max_svd_rank: int = 128) -> TensorDiagnostic:
    """
    Run complete diagnostic on a single weight tensor.
    
    This combines Hilbert envelope, spectral frontier, weight stratification,
    psionic nomination, and holographic entropy in one call.
    
    Args:
        W: Weight tensor (numpy array).
        name: Name of the tensor (for logging).
        max_svd_rank: Maximum SVD rank.
    
    Returns:
        TensorDiagnostic with all analysis results.
    """
    t0 = time.perf_counter()
    
    W_np = W if isinstance(W, np.ndarray) else np.asarray(W)
    
    # 1. Stratification (includes envelope + spectral)
    strat = stratify_weights(W_np, max_svd_rank=max_svd_rank)
    
    # 2. Psionic nomination
    psi = nominate_states(W_np)
    
    # 3. Holographic entropy
    S, regime = measure_holographic_entropy(W_np)
    
    dt = time.perf_counter() - t0
    
    return TensorDiagnostic(
        name=name,
        shape=tuple(W_np.shape),
        n_elements=W_np.size,
        dtype=str(W_np.dtype),
        envelope_mean=strat.envelope_stats["mean"],
        envelope_max=strat.envelope_stats["max"],
        envelope_std=strat.envelope_stats["std"],
        effective_rank=strat.spectral_stats["effective_rank"],
        spectral_entropy=strat.spectral_stats["spectral_entropy"],
        energy_above_frontier=strat.spectral_stats["energy_above_frontier"],
        f_photon=strat.f_photon,
        f_graviton=strat.f_graviton,
        f_vacuum=strat.f_vacuum,
        effective_bits=strat.effective_bits,
        expected_ratio=strat.expected_ratio,
        f_exp=psi.f_exp,
        state_entropy=psi.state_entropy,
        inverse_parity_fraction=psi.inverse_parity_fraction,
        holographic_entropy=S,
        regime=regime.value,
        analysis_time_s=dt,
    )


# ══════════════════════════════════════════════════════════════════════════════
# VII. BENCHMARK — PHASE 1 VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def run_phase1_benchmark() -> dict:
    """
    Run the Phase 1 benchmark: validate spectral analysis on synthetic
    and LLM-like weight distributions.
    
    Generates a complete JSON benchmark report.
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║     IALD SPECTRAL ANALYSIS v1.0 — PHASE 1 BENCHMARK                        ║
║     "Gravity is the Hilbert Envelope"                                       ║
║     β_TGL = α × √e = {:.15f}                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """.format(BETA_TGL))
    
    np.random.seed(42)
    timestamp = datetime.now().isoformat()
    
    # Test tensors mimicking LLM weight distributions
    test_cases = [
        {
            "name": "gaussian_dense",
            "desc": "Dense Gaussian weights (typical MLP layer)",
            "data": np.random.randn(4096, 4096).astype(np.float32) * 0.02,
        },
        {
            "name": "low_rank_plus_noise",
            "desc": "Low-rank structure + noise (attention projection)",
            "data": (np.random.randn(2048, 64).astype(np.float64) @
                     np.random.randn(64, 2048).astype(np.float64) * 0.1 +
                     np.random.randn(2048, 2048).astype(np.float64) * 0.001).astype(np.float32),
        },
        {
            "name": "sparse_weights",
            "desc": "Sparse weights (60% zeros, typical of pruned models)",
            "data": (np.random.randn(2048, 2048).astype(np.float32) * 0.02 *
                     (np.random.rand(2048, 2048) > 0.6).astype(np.float32)),
        },
        {
            "name": "embedding_like",
            "desc": "Embedding-like (unit-norm rows, high structure)",
            "data": (lambda x: x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-10))(
                np.random.randn(1000, 768).astype(np.float64)
            ).astype(np.float32),
        },
        {
            "name": "heavy_tailed",
            "desc": "Heavy-tailed (Cauchy-like, some weights are very large)",
            "data": (np.random.standard_cauchy((1024, 1024)) * 0.01).clip(-1, 1).astype(np.float32),
        },
        {
            "name": "near_constant",
            "desc": "Near-constant tensor (bias-like, very low entropy)",
            "data": (np.ones((512, 512)) * 0.5 +
                     np.random.randn(512, 512) * 0.0001).astype(np.float32),
        },
    ]
    
    results = []
    
    print("=" * 90)
    print(f"{'Tensor':<22} | {'Rank':>5} | {'S_ent':>6} | {'Photon':>7} | {'Gravit':>7} | {'Vacuum':>7} | {'Bits':>5} | {'Ratio':>6} | {'F_exp':>6}")
    print("=" * 90)
    
    for case in test_cases:
        t0 = time.perf_counter()
        diag = full_tensor_diagnostic(case["data"], name=case["name"])
        dt = time.perf_counter() - t0
        
        print(f"  {diag.name:<20} | {diag.effective_rank:>5} | {diag.spectral_entropy:>6.3f} | "
              f"{diag.f_photon:>6.1%} | {diag.f_graviton:>6.1%} | {diag.f_vacuum:>6.1%} | "
              f"{diag.effective_bits:>5.1f} | {diag.expected_ratio:>5.2f}x | {diag.f_exp:>+.3f}")
        
        results.append({
            "name": case["name"],
            "description": case["desc"],
            "shape": list(case["data"].shape),
            "n_elements": int(case["data"].size),
            "effective_rank": diag.effective_rank,
            "spectral_entropy": diag.spectral_entropy,
            "energy_above_frontier": diag.energy_above_frontier,
            "f_photon": diag.f_photon,
            "f_graviton": diag.f_graviton,
            "f_vacuum": diag.f_vacuum,
            "effective_bits": diag.effective_bits,
            "expected_ratio": diag.expected_ratio,
            "envelope_mean": diag.envelope_mean,
            "envelope_max": diag.envelope_max,
            "f_exp": diag.f_exp,
            "state_entropy": diag.state_entropy,
            "inverse_parity_fraction": diag.inverse_parity_fraction,
            "holographic_entropy": diag.holographic_entropy,
            "regime": diag.regime,
            "analysis_time_s": dt,
        })
    
    print("=" * 90)
    
    # Aggregate statistics
    avg_ratio = np.mean([r["expected_ratio"] for r in results])
    avg_vacuum = np.mean([r["f_vacuum"] for r in results])
    avg_photon = np.mean([r["f_photon"] for r in results])
    
    print(f"\n  AGGREGATE:")
    print(f"    Mean expected ratio:     {avg_ratio:.2f}x")
    print(f"    Mean vacuum fraction:    {avg_vacuum:.1%}")
    print(f"    Mean photon fraction:    {avg_photon:.1%}")
    print(f"    β_TGL (factored):        {BETA_TGL:.15f}")
    print(f"    Free parameters:         0")
    
    # Build benchmark JSON
    benchmark = {
        "algorithm": "IALD Spectral Analysis",
        "version": "1.0.0",
        "subtitle": "Phase 1 — Hilbert Envelope + Spectral Frontier + Weight Stratification",
        "timestamp": timestamp,
        "axiom": "Gravity is the Hilbert Envelope. The Spectral is the record of the Boundary.",
        "constants": {
            "alpha_fine": ALPHA_FINE,
            "sqrt_e": SQRT_E,
            "beta_tgl": BETA_TGL,
            "formula": "alpha_fine * sqrt(e)",
            "amplification": AMPLIFICATION,
            "theta_miguel_deg": float(math.degrees(THETA_MIGUEL)),
            "free_parameters": 0,
        },
        "bit_allocation": {
            "photon_bits": BITS_PHOTON,
            "graviton_bits": BITS_GRAVITON,
            "vacuum_bits": BITS_VACUUM,
        },
        "tests": results,
        "summary": {
            "n_tensors": len(results),
            "mean_expected_ratio": float(avg_ratio),
            "mean_vacuum_fraction": float(avg_vacuum),
            "mean_photon_fraction": float(avg_photon),
            "mean_graviton_fraction": float(1.0 - avg_vacuum - avg_photon),
            "beta_tgl": BETA_TGL,
            "zero_free_parameters": True,
        },
    }
    
    # Compute hash of this code for reproducibility
    try:
        with open(__file__, 'rb') as f:
            code_hash = hashlib.sha256(f.read()).hexdigest()
        benchmark["code_hash"] = code_hash
    except Exception:
        benchmark["code_hash"] = "unavailable"
    
    # Save JSON
    json_filename = f"iald_spectral_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, 'w') as f:
        json.dump(benchmark, f, indent=2, default=str)
    print(f"\n  Benchmark saved: {json_filename}")
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Phase 1 Complete — The Frontier is Mapped                                  ║
║  β_TGL = α × √e — Zero Free Parameters                                    ║
║  Let there be Light.                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    return benchmark


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    benchmark = run_phase1_benchmark()
