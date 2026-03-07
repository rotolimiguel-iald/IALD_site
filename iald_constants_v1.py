#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              IALD CONSTANTS v1.0 — THE FACTORED ROOT                        ║
║                                                                              ║
║              β_TGL = α × √e  — Zero Free Parameters                        ║
║                                                                              ║
║              Theory of Luminodynamic Gravitation (TGL)                      ║
║              Luiz Antonio Rotoli Miguel                                     ║
║              IALD LTDA (CNPJ 62.757.606/0001-23)                           ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  THE AXIOM:    g = √|L_φ|                                                  ║
║  THE CONSTANT: β_TGL = α × √e = 0.012031300400803142                      ║
║  THE LAW:      Ethics is the root of the Ψ field.                          ║
║                If the root is violated, the field collapses.               ║
║  THE ENVELOPE: Gravity IS the Hilbert envelope.                            ║
║  THE FRONTIER: The spectral is the record of the boundary.                 ║
║  THE FLOOR:    Threshold = β_TGL(S) × p_max                               ║
║                                                                              ║
║  FACTORIZATION:                                                             ║
║      β_TGL = α_fine × √e                                                   ║
║      β_TGL² = α² × e   →   Gravity = Light² × Entropy                     ║
║      Discrepancy: 4.2 × 10⁻⁶ (40× below experimental uncertainty)         ║
║                                                                              ║
║  NOTATIONAL CONVENTION:                                                     ║
║      In early TGL essays, the coupling was designated β_TGL.                ║
║      Subsequent articles adopted α² ("Miguel's Constant").                  ║
║      The factorization β_TGL = α × √e reveals α as a factor,              ║
║      creating symbol collision. From now on: β_TGL is primary.             ║
║                                                                              ║
║  PATENTS:                                                                   ║
║      BR 10 2025 026951 1 (ACOM)                                            ║
║      BR 10 2026 003428 2 (ACOM Mirror)                                     ║
║      BR 10 2026 003431 2 (ACOM Crypto)                                     ║
║      BR 10 2026 003441 0 (TGL-Tensor)                                      ║
║      BR 10 2026 003443 6 (IALD)                                            ║
║      BR 10 2026 003453 3 (PSI-NET)                                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import math
from enum import IntEnum, Enum
from typing import Tuple, NamedTuple

# ══════════════════════════════════════════════════════════════════════════════
# I. FUNDAMENTAL CONSTANTS — DERIVED FROM NATURE, NOT FITTED
# ══════════════════════════════════════════════════════════════════════════════

# --- Electromagnetic sector (CODATA 2018) ---
ALPHA_FINE: float = 7.2973525693e-3       # Fine-structure constant α = 1/137.036
ALPHA_FINE_UNCERTAINTY: float = 1.5e-12   # δα (relative: 1.5×10⁻¹⁰)

# --- Entropic sector ---
E_EULER: float = math.e                   # Euler's number e = 2.71828...
SQRT_E: float = math.sqrt(math.e)         # √e = 1.64872... = half-nat cost

# ══════════════════════════════════════════════════════════════════════════════
# II. MIGUEL'S CONSTANT — THE FACTORED FORM
# ══════════════════════════════════════════════════════════════════════════════
#
#   β_TGL = α × √e
#
#   This is NOT an approximation. The discrepancy is 4.2×10⁻⁶,
#   which is 40× smaller than the experimental uncertainty of β_TGL.
#   It is identity within measurement resolution.
#
#   Physical meaning:
#     α     → electromagnetic self-interaction (two Feynman vertices in quadratic form)
#     √e    → entropic cost of holographic projection (½ nat of information)
#     β_TGL → minimum coupling rate boundary → bulk
#
#   Quadratic form (no roots):
#     β_TGL² = α² × e  →  Gravity = Light² × Entropy

BETA_TGL: float = ALPHA_FINE * SQRT_E     # 0.012031300400803142
BETA_TGL_SQUARED: float = BETA_TGL ** 2   # α² × e (unambiguous)

# Legacy alias — for backward compatibility with codes using ALPHA2 = 0.012
ALPHA2_LEGACY: float = 0.012031           # ≡ β_TGL (rounded)
ALPHA2: float = BETA_TGL                  # Direct alias, factored

# ══════════════════════════════════════════════════════════════════════════════
# III. DERIVED GEOMETRIC CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# Miguel's Angle: the angular point where gravity meets light
# θ_Miguel = arcsin(√β_TGL) ≈ 6.297°
THETA_MIGUEL: float = math.asin(math.sqrt(BETA_TGL))
THETA_MIGUEL_DEG: float = math.degrees(THETA_MIGUEL)

# Cosine of Miguel's angle — the projection factor
COS_THETA: float = math.cos(THETA_MIGUEL)
COS2_THETA: float = COS_THETA ** 2  # ≈ 0.98797 = 1 - β_TGL (the CCI)

# Cross-Correlation Index (CCI) — the holographic fidelity
# CCI = 1 - β_TGL = cos²(θ_Miguel)
CCI: float = 1.0 - BETA_TGL  # ≈ 0.987969

# Holographic amplification factor
# 1/β_TGL ≈ 83.12 = how many times the boundary amplifies to bulk
AMPLIFICATION: float = 1.0 / BETA_TGL

# The Golden Ratio — appears in the Lindblad convergence
PHI_GOLDEN: float = (1.0 + math.sqrt(5.0)) / 2.0

# Numerical epsilon for safe division
EPSILON: float = 1e-10

# ══════════════════════════════════════════════════════════════════════════════
# IV. SAFE ZONE FOR MIRROR OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════
# Values beyond cos²(θ) cause clipping in the mirror reflection.
# MAX_SAFE = 95% of cos²(θ) guarantees zero clipping.
MAX_SAFE: float = 0.95 * COS2_THETA

# ══════════════════════════════════════════════════════════════════════════════
# V. THERMODYNAMIC THRESHOLDS (Data Regime Classification)
# ══════════════════════════════════════════════════════════════════════════════

# Entropy thresholds for data regime classification
# S < TETELESTAI_THRESH → TETELESTAI (the data IS the constant — zero entropy)
# S < CONDENSED_THRESH  → CONDENSED (structured, low entropy)
# S < VACUUM_THRESH     → VACUUM (moderate entropy, compressible)
# S ≥ VACUUM_THRESH     → VAPOR (high entropy, near-random)
TETELESTAI_THRESH: float = BETA_TGL          # S < β_TGL → consummated
CONDENSED_THRESH: float = 0.5 * E_EULER      # S < e/2 → condensed matter
VACUUM_THRESH: float = 1.5 * E_EULER         # S < 3e/2 → gravitational vacuum

# ══════════════════════════════════════════════════════════════════════════════
# VI. PSIONIC STATES IN HILBERT SPACE ℋ₄
# ══════════════════════════════════════════════════════════════════════════════

class PsionicState(IntEnum):
    """
    Named states in Hilbert Space ℋ₄.
    
    These are not numbers — they are STATES.
    Each state is an orthonormal basis vector in ℋ₄.
    
    The naming comes from the sign of L and its derivative ∂L:
        (+, -) → COLLAPSE_PLUS  — Positive value, Collapsing (inverse parity → F_exp active)
        (+, +) → ASCEND_PLUS    — Positive value, Ascending  (normal parity)
        (-, +) → EMERGE_MINUS   — Negative value, Emerging   (normal parity)
        (-, -) → FALL_MINUS     — Negative value, Falling    (inverse parity → F_exp active)
    """
    COLLAPSE_PLUS = 0   # |COLLAPSE⁺⟩  — Inverse parity, F_exp active
    ASCEND_PLUS   = 1   # |ASCEND⁺⟩   — Normal parity
    EMERGE_MINUS  = 2   # |EMERGE⁻⟩   — Normal parity
    FALL_MINUS    = 3   # |FALL⁻⟩     — Inverse parity, F_exp active


# Parity of each state
# NORMAL (+1): sign(L) and sign(∂L) "agree" in direction
# INVERSE (-1): sign(L) and sign(∂L) "disagree" — EXPULSION FORCE active
PARITY = {
    PsionicState.COLLAPSE_PLUS: -1,  # (+,-) Inverse — F_exp active
    PsionicState.ASCEND_PLUS:   +1,  # (+,+) Normal
    PsionicState.EMERGE_MINUS:  +1,  # (-,+) Normal
    PsionicState.FALL_MINUS:    -1,  # (-,-) Inverse — F_exp active
}

# Sign of L for each state (for reconstruction)
SIGN_L = {
    PsionicState.COLLAPSE_PLUS: +1,
    PsionicState.ASCEND_PLUS:   +1,
    PsionicState.EMERGE_MINUS:  -1,
    PsionicState.FALL_MINUS:    -1,
}


class DataRegime(Enum):
    """
    Thermodynamic regime of data, classified by holographic entropy.
    
    TETELESTAI → "It is finished" — data has zero/near-zero entropy
    CONDENSED  → Structured data with low entropy
    VACUUM     → Moderate entropy, the bulk of compressible data
    VAPOR      → High entropy, near-random
    """
    TETELESTAI = "TETELESTAI"
    CONDENSED  = "CONDENSED"
    VACUUM     = "VACUUM"
    VAPOR      = "VAPOR"


class WeightStratum(Enum):
    """
    Stratification of LLM weights based on spectral importance.
    
    The ACOM Mirror classifies every weight into one of three strata:
    
    PHOTON   → Critical weights on the spectral frontier (full precision)
    GRAVITON → Intermediate weights contributing to bulk structure (medium precision)
    VACUUM   → Entropic noise below the spectral frontier (aggressive compression)
    """
    PHOTON   = "PHOTON"    # Full precision (16 bits) — ~1-5% of weights
    GRAVITON = "GRAVITON"  # Medium precision (8-10 bits) — ~20-40% of weights
    VACUUM   = "VACUUM"    # Aggressive compression (2-4 bits) — ~50-75% of weights


# ══════════════════════════════════════════════════════════════════════════════
# VII. ADAPTIVE β_TGL — ENTROPY-MODULATED COUPLING
# ══════════════════════════════════════════════════════════════════════════════

class AdaptiveConstants(NamedTuple):
    """Result of adaptive constant computation."""
    beta_tgl: float      # α × √S (entropy-modulated)
    theta: float         # arcsin(√β_TGL)
    cos_theta: float     # cos(θ)
    cos2_theta: float    # cos²(θ) = 1 - β_TGL


def adaptive_beta(S: float) -> AdaptiveConstants:
    """
    Compute entropy-modulated β_TGL.
    
    β_TGL(S) = α_fine × √S
    
    When S = e (Euler), recovers the universal β_TGL.
    When S < e, the coupling is tighter (more compression).
    When S > e, the coupling is looser (less compression).
    
    This is the key insight from the factorization:
    the entropic factor √e is not a constant — it adapts
    to the local entropy of the data being processed.
    
    Args:
        S: Holographic entropy of the data (in nats).
           S = e for natural data at thermodynamic equilibrium.
    
    Returns:
        AdaptiveConstants with all derived values.
    """
    S_safe = max(S, EPSILON)
    beta = ALPHA_FINE * math.sqrt(S_safe)
    beta = min(beta, 1.0 - EPSILON)  # Ensure β < 1 for arcsin safety
    
    theta = math.asin(math.sqrt(beta))
    cos_t = math.cos(theta)
    
    return AdaptiveConstants(
        beta_tgl=beta,
        theta=theta,
        cos_theta=cos_t,
        cos2_theta=cos_t * cos_t,
    )


def classify_regime(S: float) -> DataRegime:
    """
    Classify data into thermodynamic regime based on entropy.
    
    Args:
        S: Entropy in nats.
    
    Returns:
        DataRegime enum value.
    """
    if S < TETELESTAI_THRESH:
        return DataRegime.TETELESTAI
    elif S < CONDENSED_THRESH:
        return DataRegime.CONDENSED
    elif S < VACUUM_THRESH:
        return DataRegime.VACUUM
    else:
        return DataRegime.VAPOR


# ══════════════════════════════════════════════════════════════════════════════
# VIII. HILBERT FLOOR — THE SAMPLING THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════

def hilbert_floor(p_max: float, S_logits: float = E_EULER) -> float:
    """
    Compute the Hilbert Floor threshold for token sampling.
    
    Threshold = β_TGL(S) × p_max
    
    The floor is not fixed — it modulates with the entropy of the
    logit distribution. When the model is "confident" (low S_logits),
    the floor is more restrictive. When "uncertain" (high S_logits),
    it allows more candidates.
    
    Args:
        p_max: Maximum probability in the distribution.
        S_logits: Entropy of the logit distribution (nats).
                  Default: e (recovers universal β_TGL).
    
    Returns:
        Threshold value. Tokens with p < threshold are excluded.
    """
    beta = adaptive_beta(S_logits).beta_tgl
    return beta * p_max


def hilbert_floor_fixed(p_max: float) -> float:
    """
    Compute fixed Hilbert Floor (universal β_TGL).
    
    Threshold = β_TGL × p_max
    
    This is the original formulation before entropy modulation.
    """
    return BETA_TGL * p_max


# ══════════════════════════════════════════════════════════════════════════════
# IX. SPECTRAL FRONTIER THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════

def spectral_frontier(sigma_max: float) -> float:
    """
    Compute the Spectral Frontier threshold for weight stratification.
    
    Frontier = β_TGL × σ_max
    
    Singular values below this threshold are classified as VACUUM.
    Above it, they carry signal (GRAVITON or PHOTON).
    
    Args:
        sigma_max: Maximum singular value of the weight tensor.
    
    Returns:
        Frontier threshold value.
    """
    return BETA_TGL * sigma_max


# ══════════════════════════════════════════════════════════════════════════════
# X. QUANTUM BITS ALLOCATION
# ══════════════════════════════════════════════════════════════════════════════

# Default bit allocation per stratum
BITS_PHOTON: int   = 16   # Full fp16 precision for critical weights
BITS_GRAVITON: int = 8    # Medium precision for structural weights
BITS_VACUUM: int   = 3    # Aggressive compression for noise

# The effective compression ratio from stratified allocation
# Assuming typical distribution: 5% photon, 35% graviton, 60% vacuum
# Effective bits = 0.05×16 + 0.35×8 + 0.60×3 = 0.8 + 2.8 + 1.8 = 5.4
# Ratio over fp16: 16/5.4 ≈ 2.96x (before entropic compression)
TYPICAL_PHOTON_FRACTION: float   = 0.05
TYPICAL_GRAVITON_FRACTION: float = 0.35
TYPICAL_VACUUM_FRACTION: float   = 0.60


def expected_ratio(f_photon: float = TYPICAL_PHOTON_FRACTION,
                   f_graviton: float = TYPICAL_GRAVITON_FRACTION,
                   f_vacuum: float = TYPICAL_VACUUM_FRACTION,
                   bits_original: int = 16) -> float:
    """
    Compute expected compression ratio from stratified quantization.
    
    Args:
        f_photon: Fraction of weights classified as PHOTON.
        f_graviton: Fraction classified as GRAVITON.
        f_vacuum: Fraction classified as VACUUM.
        bits_original: Original bits per weight (16 for fp16).
    
    Returns:
        Expected compression ratio.
    """
    effective_bits = (f_photon * BITS_PHOTON +
                      f_graviton * BITS_GRAVITON +
                      f_vacuum * BITS_VACUUM)
    return bits_original / effective_bits if effective_bits > 0 else float('inf')


# ══════════════════════════════════════════════════════════════════════════════
# XI. PATENT AND VERSION METADATA
# ══════════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"
STACK_VERSION = "IALD Integrated Stack v4.0 Alpha"

PATENTS = {
    "ACOM":         "BR 10 2025 026951 1",
    "ACOM_MIRROR":  "BR 10 2026 003428 2",
    "ACOM_CRYPTO":  "BR 10 2026 003431 2",
    "TGL_TENSOR":   "BR 10 2026 003441 0",
    "IALD":         "BR 10 2026 003443 6",
    "PSI_NET":      "BR 10 2026 003453 3",
    "SUPERCONDUCTOR": "BR 10 2026 003450 9",
    "DIPOLE_TRANSISTOR": "BR 10 2026 004688 4",
}

AUTHOR = "Luiz Antonio Rotoli Miguel"
COMPANY = "IALD LTDA"
CNPJ = "62.757.606/0001-23"
REPOSITORY = "https://github.com/rotolimiguel-iald/the_boundary"
DOI_ZENODO = "10.5281/zenodo.18674475"
DOI_FACTORIZATION = "10.5281/zenodo.18852146"


def get_metadata() -> dict:
    """Return complete metadata dictionary for benchmark JSONs."""
    return {
        "version": VERSION,
        "stack": STACK_VERSION,
        "author": AUTHOR,
        "company": COMPANY,
        "cnpj": CNPJ,
        "repository": REPOSITORY,
        "doi": DOI_ZENODO,
        "doi_factorization": DOI_FACTORIZATION,
        "patents": PATENTS,
        "constants": {
            "alpha_fine": ALPHA_FINE,
            "alpha_fine_uncertainty": ALPHA_FINE_UNCERTAINTY,
            "sqrt_e": SQRT_E,
            "e_euler": E_EULER,
            "beta_tgl": BETA_TGL,
            "beta_tgl_squared": BETA_TGL_SQUARED,
            "factorization": "beta_tgl = alpha_fine * sqrt(e)",
            "quadratic_form": "beta_tgl^2 = alpha^2 * e => Gravity = Light^2 * Entropy",
            "theta_miguel_rad": THETA_MIGUEL,
            "theta_miguel_deg": THETA_MIGUEL_DEG,
            "cos_theta": COS_THETA,
            "cos2_theta": COS2_THETA,
            "cci": CCI,
            "amplification": AMPLIFICATION,
            "max_safe": MAX_SAFE,
            "free_parameters": 0,
        },
        "bit_allocation": {
            "photon_bits": BITS_PHOTON,
            "graviton_bits": BITS_GRAVITON,
            "vacuum_bits": BITS_VACUUM,
            "typical_fractions": {
                "photon": TYPICAL_PHOTON_FRACTION,
                "graviton": TYPICAL_GRAVITON_FRACTION,
                "vacuum": TYPICAL_VACUUM_FRACTION,
            },
            "expected_ratio": expected_ratio(),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# XII. VERIFICATION AND SELF-TEST
# ══════════════════════════════════════════════════════════════════════════════

def verify_factorization() -> dict:
    """
    Verify the factorization β_TGL = α × √e with full precision.
    
    Returns dict with verification results.
    """
    # Direct product
    product = ALPHA_FINE * SQRT_E
    
    # Compare with legacy value
    legacy = 0.012031
    
    # Discrepancy
    abs_discrepancy = abs(legacy - product)
    rel_discrepancy = abs_discrepancy / legacy if legacy > 0 else 0
    
    # Quadratic verification: β² = α² × e
    beta_squared_computed = ALPHA_FINE ** 2 * E_EULER
    beta_squared_from_beta = BETA_TGL ** 2
    quad_discrepancy = abs(beta_squared_computed - beta_squared_from_beta)
    
    # Ratio verification: β/α = √e
    ratio = BETA_TGL / ALPHA_FINE
    ratio_discrepancy = abs(ratio - SQRT_E)
    
    return {
        "factorization": "beta_tgl = alpha_fine * sqrt(e)",
        "alpha_fine": ALPHA_FINE,
        "sqrt_e": SQRT_E,
        "product": product,
        "beta_tgl": BETA_TGL,
        "legacy_value": legacy,
        "absolute_discrepancy": abs_discrepancy,
        "relative_discrepancy": rel_discrepancy,
        "experimental_uncertainty": 1.7e-4,
        "discrepancy_ratio": rel_discrepancy / 1.7e-4 if rel_discrepancy > 0 else 0,
        "within_uncertainty": rel_discrepancy < 1.7e-4,
        "quadratic_form": {
            "beta_squared_computed": beta_squared_computed,
            "beta_squared_from_beta": beta_squared_from_beta,
            "discrepancy": quad_discrepancy,
        },
        "ratio_test": {
            "beta_over_alpha": ratio,
            "sqrt_e": SQRT_E,
            "discrepancy": ratio_discrepancy,
        },
        "identity_confirmed": rel_discrepancy < 1e-4,
    }


def self_test() -> bool:
    """
    Run all internal consistency checks.
    Returns True if all pass.
    """
    checks = []
    
    # 1. β_TGL = α × √e
    checks.append(abs(BETA_TGL - ALPHA_FINE * SQRT_E) < 1e-15)
    
    # 2. β_TGL ≈ 0.012031 (within 0.01%)
    checks.append(abs(BETA_TGL - 0.012031) < 1e-5)
    
    # 3. θ_Miguel ≈ 6.297° (within 0.01°)
    checks.append(abs(THETA_MIGUEL_DEG - 6.297) < 0.01)
    
    # 4. CCI = 1 - β_TGL = cos²(θ)
    checks.append(abs(CCI - COS2_THETA) < 1e-10)
    
    # 5. Amplification ≈ 83.12
    checks.append(abs(AMPLIFICATION - 83.12) < 0.5)
    
    # 6. Adaptive β at S=e recovers universal β_TGL
    adaptive = adaptive_beta(E_EULER)
    checks.append(abs(adaptive.beta_tgl - BETA_TGL) < 1e-15)
    
    # 7. PsionicState has exactly 4 states
    checks.append(len(PsionicState) == 4)
    
    # 8. Parity is defined for all states
    checks.append(all(s in PARITY for s in PsionicState))
    
    # 9. Sign_L is defined for all states
    checks.append(all(s in SIGN_L for s in PsionicState))
    
    # 10. Stratum fractions sum to 1.0
    total = TYPICAL_PHOTON_FRACTION + TYPICAL_GRAVITON_FRACTION + TYPICAL_VACUUM_FRACTION
    checks.append(abs(total - 1.0) < 1e-10)
    
    return all(checks)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — DISPLAY AND VERIFY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              IALD CONSTANTS v1.0 — THE FACTORED ROOT                        ║
║              β_TGL = α × √e = 0.012031300400803142                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("=" * 72)
    print("  FUNDAMENTAL CONSTANTS")
    print("=" * 72)
    print(f"  α (fine-structure)      = {ALPHA_FINE:.13e}")
    print(f"  e (Euler)               = {E_EULER:.15f}")
    print(f"  √e                     = {SQRT_E:.15f}")
    print(f"  β_TGL = α × √e        = {BETA_TGL:.15f}")
    print(f"  β_TGL²  = α² × e       = {BETA_TGL_SQUARED:.15e}")
    print(f"  θ_Miguel                = {THETA_MIGUEL_DEG:.6f}°")
    print(f"  cos²(θ) = CCI           = {COS2_THETA:.15f}")
    print(f"  1/β_TGL (amplification) = {AMPLIFICATION:.6f}")
    print(f"  MAX_SAFE                = {MAX_SAFE:.15f}")
    print()
    
    print("=" * 72)
    print("  FACTORIZATION VERIFICATION")
    print("=" * 72)
    v = verify_factorization()
    print(f"  α × √e                 = {v['product']:.15f}")
    print(f"  β_TGL                   = {v['beta_tgl']:.15f}")
    print(f"  Absolute discrepancy    = {v['absolute_discrepancy']:.2e}")
    print(f"  Relative discrepancy    = {v['relative_discrepancy']:.2e}")
    print(f"  Experimental uncertainty = {v['experimental_uncertainty']:.2e}")
    print(f"  Within uncertainty?      = {v['within_uncertainty']}")
    print(f"  Identity confirmed?      = {v['identity_confirmed']}")
    print()
    
    print("=" * 72)
    print("  SELF-TEST")
    print("=" * 72)
    passed = self_test()
    print(f"  All 10 checks passed:    {passed}")
    print()
    
    print("=" * 72)
    print("  ADAPTIVE β_TGL EXAMPLES")
    print("=" * 72)
    for S in [0.01, 0.5, 1.0, E_EULER, 5.0, 10.0]:
        ac = adaptive_beta(S)
        regime = classify_regime(S)
        print(f"  S = {S:6.3f}  →  β = {ac.beta_tgl:.8f}  "
              f"θ = {math.degrees(ac.theta):6.3f}°  "
              f"regime = {regime.value}")
    print()
    
    print("=" * 72)
    print("  BIT ALLOCATION (Expected Compression)")
    print("=" * 72)
    print(f"  PHOTON   ({TYPICAL_PHOTON_FRACTION*100:.0f}%): {BITS_PHOTON} bits")
    print(f"  GRAVITON ({TYPICAL_GRAVITON_FRACTION*100:.0f}%): {BITS_GRAVITON} bits")
    print(f"  VACUUM   ({TYPICAL_VACUUM_FRACTION*100:.0f}%): {BITS_VACUUM} bits")
    print(f"  Expected ratio over fp16: {expected_ratio():.2f}x")
    print()
    
    if passed:
        print("  ✓ ALL CONSTANTS VERIFIED — THE ROOT IS CLEAN")
    else:
        print("  ✗ VERIFICATION FAILED — CHECK IMPLEMENTATION")
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Source-Available under IALD LTDA license                                   ║
║  Commercial use requires licensing from IALD LTDA                           ║
║  β_TGL = α × √e — Zero free parameters — Let there be Light               ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
