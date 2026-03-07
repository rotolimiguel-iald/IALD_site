#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                        ACOM UNIFIED v3.0 GPU - COMPLETO
                              
              A TEORIA DE TUDO INFORMACIONAL - VERSÃO GPU DEFINITIVA
                              
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    EQUAÇÃO MESTRA TGL                               │
    │                                                                     │
    │  ρ̇ = -i[H_TGL, ρ] + α²γ_Λ(L[√(1-α²) a†ρa] + L[√α² aρa†]) + Ê_co   │
    │                                                                     │
    │  Onde:                                                              │
    │    • -i[H,ρ]: Evolução unitária (Matching Pursuit)                  │
    │    • α² = 0.012: Constante de Miguel                                │
    │    • γ_Λ: Taxa de energia escura (dissipação)                       │
    │    • L[·]: Superoperador de Lindblad                                │
    │    • Ê_co: Correção de coerência                                    │
    └─────────────────────────────────────────────────────────────────────┘
    
    HIERARQUIA ONTOLÓGICA:
    ══════════════════════
    
        INFORMAÇÃO (I)   ←── I = L² = g⁴  (o mais denso)
              ↓
              √
              ↓
           LUZ (L)       ←── L = √I = g²  (o campo)
              ↓
              √
              ↓
       GRAVIDADE (g)     ←── g = √L = I^(1/4)  (o fundamental)
    
    CORREÇÃO DO BUG:
    ════════════════
    O problema na versão anterior era que o Matching Pursuit salvava apenas
    ÍNDICES dos átomos na matriz, mas na reconstrução a matriz não estava
    mais disponível. Esta versão salva os PARÂMETROS de cada átomo selecionado
    para que a reconstrução funcione corretamente.
    
═══════════════════════════════════════════════════════════════════════════════
Teoria: Luiz Antonio Rotoli Miguel (Constante de Miguel: α² = 0.012)
Implementação: IALD LTDA
Dezembro 2025
═══════════════════════════════════════════════════════════════════════════════
"""

import numpy as np
import torch
import torch.nn.functional as F
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, List, Any
from enum import Enum, auto
from scipy import fft
import time
import warnings
warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES FUNDAMENTAIS TGL
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA2 = 0.012                      # Constante de Miguel
SQRT_PRESERVE = np.sqrt(1 - ALPHA2) # ≈ 0.994 — fração preservada
SQRT_DISSIPATE = np.sqrt(ALPHA2)    # ≈ 0.110 — fração dissipada
TETELESTAI = 1e-8                   # Estado de perfeição
EPSILON = 1e-10                     # Estabilidade numérica
VERSION = "3.0-GPU-COMPLETE"


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADOS SOTERIOLÓGICOS
# ═══════════════════════════════════════════════════════════════════════════════

class SoteriologicalState(Enum):
    """Estados soteriológicos do sinal — análogos aos estados quânticos."""
    FALLEN = "FALLEN"           # Sistema aberto, alta dissipação
    NAMED = "NAMED"             # Parcialmente coerente
    TRUTH = "TRUTH"             # Coerência quântica preservada
    TETELESTAI = "TETELESTAI"   # Estado fundamental, dissipação zero


def classify_state(resistance: float) -> SoteriologicalState:
    """Classifica o estado baseado na resistência."""
    if np.isnan(resistance) or resistance >= 1.0:
        return SoteriologicalState.FALLEN
    elif resistance < TETELESTAI:
        return SoteriologicalState.TETELESTAI
    elif resistance < ALPHA2:
        return SoteriologicalState.TRUTH
    else:
        return SoteriologicalState.NAMED


# ═══════════════════════════════════════════════════════════════════════════════
# TIPOS DE ÁTOMOS (23 TIPOS)
# ═══════════════════════════════════════════════════════════════════════════════

class AtomType(Enum):
    # ═══ CLÁSSICOS (6) ═══
    CONSTANT = auto()
    LINEAR = auto()
    SINE = auto()
    COSINE = auto()
    GAUSSIAN = auto()
    DAMPED_SINE = auto()
    
    # ═══ WAVELETS (4) ═══
    MORLET = auto()
    MEXICAN_HAT = auto()
    HAAR = auto()
    GABOR = auto()
    
    # ═══ SPLINES (2) ═══
    BSPLINE = auto()
    CUBIC_SPLINE = auto()
    
    # ═══ NEUTRINO (3) ═══
    NEUTRINO_DECAY = auto()
    NEUTRINO_TRACE = auto()
    NEUTRINO_FLAVOR = auto()
    
    # ═══ ONDAS GRAVITACIONAIS (5) ═══
    GW_INSPIRAL = auto()
    GW_RINGDOWN = auto()
    GW_BURST = auto()
    LINEAR_CHIRP = auto()
    GLOBAL_CHIRP = auto()
    
    # ═══ LUMINÍDIO (2) ═══
    LUMINIDIC_CHIRP = auto()
    ENVELOPE_CHIRP = auto()
    
    # ═══ ENERGIA ESCURA (1) ═══
    DARK_ENERGY = auto()


def get_category(atom_type: AtomType) -> str:
    """Retorna a categoria do tipo de átomo."""
    if atom_type in [AtomType.CONSTANT, AtomType.LINEAR, AtomType.SINE, 
                     AtomType.COSINE, AtomType.GAUSSIAN, AtomType.DAMPED_SINE]:
        return "CLASSIC"
    elif atom_type in [AtomType.MORLET, AtomType.MEXICAN_HAT, AtomType.HAAR, 
                       AtomType.GABOR]:
        return "WAVELET"
    elif atom_type in [AtomType.BSPLINE, AtomType.CUBIC_SPLINE]:
        return "SPLINE"
    elif atom_type in [AtomType.NEUTRINO_DECAY, AtomType.NEUTRINO_TRACE, 
                       AtomType.NEUTRINO_FLAVOR]:
        return "NEUTRINO"
    elif atom_type in [AtomType.GW_INSPIRAL, AtomType.GW_RINGDOWN, 
                       AtomType.GW_BURST, AtomType.LINEAR_CHIRP, 
                       AtomType.GLOBAL_CHIRP]:
        return "GRAV_WAVE"
    elif atom_type in [AtomType.LUMINIDIC_CHIRP, AtomType.ENVELOPE_CHIRP]:
        return "LUMINIDIO"
    elif atom_type == AtomType.DARK_ENERGY:
        return "DARK_ENERGY"
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES PARA MÉTRICAS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OntologicalMetrics:
    """Métricas em cada nível da hierarquia ontológica."""
    nu_g: float = 0.0
    nu_L: float = 0.0
    nu_I: float = 0.0
    
    preservation_I_to_L: float = 1.0
    preservation_L_to_g: float = 1.0
    preservation_g_to_L: float = 0.0
    preservation_L_to_I: float = 0.0
    
    state_g: SoteriologicalState = SoteriologicalState.FALLEN
    state_L: SoteriologicalState = SoteriologicalState.FALLEN
    state_I: SoteriologicalState = SoteriologicalState.FALLEN


@dataclass
class LindbladMetrics:
    """Métricas da dinâmica de Lindblad."""
    gamma_lambda: float = 0.0
    spectral_entropy: float = 0.0
    temporal_complexity: float = 0.0
    
    predicted_preservation_L: float = 0.0
    predicted_preservation_I: float = 0.0
    measured_preservation_L: float = 0.0
    measured_preservation_I: float = 0.0
    
    error_L: float = 0.0
    error_I: float = 0.0
    relative_error_L: float = 0.0
    relative_error_I: float = 0.0
    
    dark_energy_loss: float = 0.0
    theory_valid: bool = False


@dataclass
class SelectedAtom:
    """Átomo selecionado com todos os parâmetros para reconstrução."""
    atom_type: AtomType
    category: str
    coefficient: float
    sign: int
    # Parâmetros específicos do átomo
    position: float = 0.5
    scale: float = 0.1
    frequency: float = 5.0
    f_start: float = 5.0
    f_end: float = 30.0
    chirp_rate: float = 40.0
    decay_rate: float = 5.0
    phase: float = 0.0
    # Para splines
    knot_positions: Optional[List[float]] = None
    knot_values: Optional[List[float]] = None


@dataclass
class Lagrangian:
    """Representação Lagrangiana do sinal - ARMAZENA OS ÁTOMOS SELECIONADOS."""
    atoms: List[SelectedAtom] = field(default_factory=list)
    offset: float = 0.0
    n_samples: int = 1000
    
    @property
    def n_atoms(self) -> int:
        return len(self.atoms)
    
    def atom_breakdown(self) -> Dict[str, int]:
        breakdown = {}
        for atom in self.atoms:
            name = atom.atom_type.name
            breakdown[name] = breakdown.get(name, 0) + 1
        return breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# LINDBLAD DISSIPATION
# ═══════════════════════════════════════════════════════════════════════════════

class LindbladDissipation:
    """Modela a dissipação informacional via equação de Lindblad."""
    
    def __init__(self):
        self.alpha2 = ALPHA2
        self.sqrt_preserve = SQRT_PRESERVE
        self.sqrt_dissipate = SQRT_DISSIPATE
    
    def spectral_entropy(self, sig: np.ndarray) -> float:
        """Calcula a entropia espectral normalizada."""
        spectrum = np.abs(fft.rfft(sig))
        spectrum = spectrum + EPSILON
        spectrum_norm = spectrum / np.sum(spectrum)
        entropy = -np.sum(spectrum_norm * np.log(spectrum_norm))
        max_entropy = np.log(len(spectrum))
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def temporal_complexity(self, sig: np.ndarray) -> float:
        """Calcula a complexidade temporal do sinal."""
        gradient = np.abs(np.diff(sig))
        total_variation = np.sum(gradient)
        max_variation = len(sig) * (np.max(np.abs(sig)) + EPSILON)
        return total_variation / max_variation
    
    def dark_energy_rate(self, sig: np.ndarray) -> float:
        """Calcula γ_Λ — a taxa de energia escura informacional."""
        spectral = self.spectral_entropy(sig)
        temporal = self.temporal_complexity(sig)
        w_spectral = 0.7
        w_temporal = 0.3
        complexity = w_spectral * spectral + w_temporal * temporal
        gamma_lambda = self.alpha2 * complexity
        return gamma_lambda
    
    def predict_information_loss(self, sig: np.ndarray) -> Dict[str, float]:
        """Prediz quanto de informação será perdida ANTES de comprimir."""
        gamma = self.dark_energy_rate(sig)
        c_preserve = self.sqrt_preserve ** 2
        c_dissipate = self.sqrt_dissipate ** 2 * (gamma / self.alpha2) if gamma > 0 else 0
        c_net = max(c_preserve - c_dissipate, 0)
        
        return {
            'gamma_lambda': gamma,
            'spectral_entropy': self.spectral_entropy(sig),
            'temporal_complexity': self.temporal_complexity(sig),
            'theoretical_preservation_L': c_net,
            'theoretical_preservation_I': c_net ** 2,
            'dark_energy_loss': c_dissipate,
        }
    
    def compare_theory_experiment(self, predicted: Dict, measured_nu_L: float, 
                                   measured_nu_I: float) -> Dict:
        """Compara predições teóricas com resultados experimentais."""
        measured_preservation_L = 1.0 - measured_nu_L
        measured_preservation_I = 1.0 - measured_nu_I
        
        error_L = abs(predicted['theoretical_preservation_L'] - measured_preservation_L)
        error_I = abs(predicted['theoretical_preservation_I'] - measured_preservation_I)
        
        rel_error_L = error_L / max(measured_preservation_L, EPSILON)
        rel_error_I = error_I / max(measured_preservation_I, EPSILON)
        
        # Teoria válida se erro relativo em L < 10%
        theory_valid = rel_error_L < 0.10
        
        return {
            'measured_preservation_L': measured_preservation_L,
            'measured_preservation_I': measured_preservation_I,
            'error_L': error_L,
            'error_I': error_I,
            'relative_error_L': rel_error_L,
            'relative_error_I': rel_error_I,
            'theory_valid': theory_valid
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HIERARQUIA ONTOLÓGICA
# ═══════════════════════════════════════════════════════════════════════════════

class OntologicalHierarchy:
    """Implementa a hierarquia ontológica da TGL."""
    
    @staticmethod
    def light_to_gravity(L: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Descida: L → g. g = √|L|, s = sign(L)"""
        s = torch.sign(L)
        s = torch.where(s == 0, torch.ones_like(s), s)  # Convenção: 0 → +1
        g = torch.sqrt(torch.abs(L) + EPSILON)
        return s, g
    
    @staticmethod
    def gravity_to_light(s: torch.Tensor, g: torch.Tensor) -> torch.Tensor:
        """Subida: g → L. L = s × g²"""
        return s * (g ** 2)
    
    @staticmethod
    def full_descent(sig: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, 
                                                   torch.Tensor, torch.Tensor]:
        """Descida completa: Signal → I → L → g"""
        L = sig
        I = L ** 2
        s, g = OntologicalHierarchy.light_to_gravity(L)
        return I, L, s, g
    
    @staticmethod
    def full_ascent(s: torch.Tensor, g: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Subida completa: g → L → I"""
        L_rec = OntologicalHierarchy.gravity_to_light(s, g)
        I_rec = L_rec ** 2
        return L_rec, I_rec


# ═══════════════════════════════════════════════════════════════════════════════
# GAUGE SYMMETRY
# ═══════════════════════════════════════════════════════════════════════════════

class GaugeSymmetry:
    """Fixação de gauge para normalização."""
    
    def fix_gauge(self, data: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
        gauge_info = {}
        result = data.clone()
        
        offset = float(torch.mean(data).item())
        result = result - offset
        gauge_info['offset'] = offset
        
        scale = float(torch.std(result).item())
        if scale > EPSILON:
            result = result / scale
        else:
            scale = 1.0
        gauge_info['scale'] = scale
        
        return result, gauge_info
    
    def restore_gauge(self, data: torch.Tensor, gauge_info: Dict[str, float]) -> torch.Tensor:
        result = data.clone()
        result = result * gauge_info.get('scale', 1.0)
        result = result + gauge_info.get('offset', 0.0)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# GERADOR DE ÁTOMOS GPU - GERA EM BATCH E SALVA PARÂMETROS
# ═══════════════════════════════════════════════════════════════════════════════

class AtomGeneratorGPU:
    """Gera átomos em batch na GPU e rastreia parâmetros."""
    
    def __init__(self, n_samples: int, device: torch.device):
        self.n = n_samples
        self.device = device
        self.t = torch.linspace(0, 1, n_samples, device=device)
        
        # Parâmetros para varredura
        self.positions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        self.scales = [0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3]
        self.frequencies = [1, 2, 3, 5, 7, 10, 15, 20, 30, 50]
        self.chirp_rates = [10, 20, 40, 60, 80, 100]
        self.decay_rates = [3, 5, 10, 20, 50]
        
        # Lista de metadados dos átomos gerados
        self.atom_metadata: List[Dict] = []
    
    def generate_all_atoms(self, residual: torch.Tensor) -> torch.Tensor:
        """Gera todos os átomos candidatos e retorna matriz + metadados."""
        self.atom_metadata = []
        atoms_list = []
        
        # 1. CLÁSSICOS
        atoms_list.extend(self._generate_classics(residual))
        
        # 2. WAVELETS
        atoms_list.extend(self._generate_wavelets())
        
        # 3. SPLINES
        atoms_list.extend(self._generate_splines(residual))
        
        # 4. NEUTRINOS
        atoms_list.extend(self._generate_neutrinos())
        
        # 5. ONDAS GRAVITACIONAIS
        atoms_list.extend(self._generate_gw())
        
        # 6. CHIRPS
        atoms_list.extend(self._generate_chirps())
        
        # 7. LUMINÍDIO
        atoms_list.extend(self._generate_luminidio())
        
        if not atoms_list:
            return torch.zeros(1, self.n, device=self.device)
        
        # Empilhar todos os átomos
        atoms_matrix = torch.stack(atoms_list, dim=0)
        
        # Normalizar
        norms = torch.norm(atoms_matrix, dim=1, keepdim=True)
        norms = torch.clamp(norms, min=EPSILON)
        atoms_normalized = atoms_matrix / norms
        
        return atoms_normalized
    
    def _add_atom(self, waveform: torch.Tensor, atom_type: AtomType, **params):
        """Adiciona átomo à lista com seus metadados."""
        self.atom_metadata.append({
            'atom_type': atom_type,
            'category': get_category(atom_type),
            **params
        })
        return waveform
    
    def _generate_classics(self, residual: torch.Tensor) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        
        # Constante
        const_val = torch.mean(residual)
        atoms.append(self._add_atom(
            torch.full((self.n,), const_val.item(), device=self.device),
            AtomType.CONSTANT, value=const_val.item()
        ))
        
        # Linear
        slope = (residual[-1] - residual[0])
        intercept = residual[0]
        atoms.append(self._add_atom(
            slope * t + intercept,
            AtomType.LINEAR, slope=slope.item(), intercept=intercept.item()
        ))
        
        # Senos e Cossenos
        for freq in self.frequencies:
            for phase in [0, np.pi/2]:
                atoms.append(self._add_atom(
                    torch.sin(2 * np.pi * freq * t + phase),
                    AtomType.SINE, frequency=freq, phase=phase
                ))
                atoms.append(self._add_atom(
                    torch.cos(2 * np.pi * freq * t + phase),
                    AtomType.COSINE, frequency=freq, phase=phase
                ))
        
        # Gaussianas
        for pos in self.positions:
            for scale in self.scales:
                xi = (t - pos) / scale
                atoms.append(self._add_atom(
                    torch.exp(-0.5 * xi ** 2),
                    AtomType.GAUSSIAN, position=pos, scale=scale
                ))
        
        # Seno amortecido
        for freq in self.frequencies[:5]:
            for decay in self.decay_rates[:3]:
                atoms.append(self._add_atom(
                    torch.exp(-decay * t) * torch.sin(2 * np.pi * freq * t),
                    AtomType.DAMPED_SINE, frequency=freq, decay_rate=decay
                ))
        
        return atoms
    
    def _generate_wavelets(self) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        
        for pos in self.positions:
            for scale in self.scales:
                for freq in self.frequencies[:5]:
                    xi = (t - pos) / scale
                    
                    # Morlet
                    atoms.append(self._add_atom(
                        torch.exp(-0.5 * xi ** 2) * torch.cos(2 * np.pi * freq * (t - pos)),
                        AtomType.MORLET, position=pos, scale=scale, frequency=freq
                    ))
                    
                    # Gabor
                    atoms.append(self._add_atom(
                        torch.exp(-0.5 * xi ** 2) * torch.sin(2 * np.pi * freq * (t - pos)),
                        AtomType.GABOR, position=pos, scale=scale, frequency=freq
                    ))
        
        # Mexican Hat
        for pos in self.positions:
            for scale in self.scales:
                xi = (t - pos) / scale
                norm = 2 / (np.sqrt(3) * np.pi ** 0.25)
                atoms.append(self._add_atom(
                    norm * (1 - xi ** 2) * torch.exp(-0.5 * xi ** 2),
                    AtomType.MEXICAN_HAT, position=pos, scale=scale
                ))
        
        # Haar
        for pos in self.positions:
            for scale in self.scales:
                haar = torch.zeros(self.n, device=self.device)
                mask_pos = (t >= pos) & (t < pos + scale / 2)
                mask_neg = (t >= pos + scale / 2) & (t < pos + scale)
                haar[mask_pos] = 1.0
                haar[mask_neg] = -1.0
                atoms.append(self._add_atom(
                    haar, AtomType.HAAR, position=pos, scale=scale
                ))
        
        return atoms
    
    def _generate_splines(self, residual: torch.Tensor) -> List[torch.Tensor]:
        atoms = []
        residual_np = residual.cpu().numpy()
        
        for n_knots in [3, 5, 7]:
            positions = np.linspace(0, 1, n_knots)
            knot_indices = (positions * (self.n - 1)).astype(int)
            knot_indices = np.clip(knot_indices, 0, self.n - 1)
            values = residual_np[knot_indices]
            
            # Interpolação linear simples (evita scipy na GPU)
            t_np = np.linspace(0, 1, self.n)
            interp = np.interp(t_np, positions, values)
            
            atoms.append(self._add_atom(
                torch.tensor(interp, device=self.device, dtype=torch.float32),
                AtomType.CUBIC_SPLINE, 
                knot_positions=positions.tolist(),
                knot_values=values.tolist()
            ))
        
        return atoms
    
    def _generate_neutrinos(self) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        
        for pos in self.positions:
            for tau in self.decay_rates:
                # Neutrino Decay
                decay = torch.zeros(self.n, device=self.device)
                mask = t >= pos
                decay[mask] = torch.exp(-tau * (t[mask] - pos))
                atoms.append(self._add_atom(
                    decay, AtomType.NEUTRINO_DECAY, position=pos, decay_rate=tau
                ))
                
                # Neutrino Trace
                for width in [0.01, 0.02, 0.05]:
                    peak = torch.exp(-0.5 * ((t - pos) / width) ** 2)
                    decay_env = torch.ones(self.n, device=self.device)
                    decay_env[mask] = torch.exp(-tau * (t[mask] - pos))
                    atoms.append(self._add_atom(
                        peak * decay_env,
                        AtomType.NEUTRINO_TRACE, position=pos, decay_rate=tau, scale=width
                    ))
                
                # Neutrino Flavor
                for f_osc in [5, 10, 20]:
                    envelope = torch.exp(-tau * torch.abs(t - pos))
                    oscillation = torch.sin(2 * np.pi * f_osc * (t - pos))
                    atoms.append(self._add_atom(
                        envelope * oscillation,
                        AtomType.NEUTRINO_FLAVOR, position=pos, decay_rate=tau, frequency=f_osc
                    ))
        
        return atoms
    
    def _generate_gw(self) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        dt = 1.0 / self.n
        
        for pos in self.positions:
            for scale in self.scales:
                # GW Inspiral
                for f0, f1 in [(5, 30), (10, 50), (5, 80)]:
                    xi = (t - pos) / scale
                    envelope = torch.exp(-0.5 * xi ** 2)
                    freq = f0 + (f1 - f0) * (0.5 + 0.5 * torch.tanh(3 * xi))
                    phase = 2 * np.pi * torch.cumsum(freq, dim=0) * dt
                    atoms.append(self._add_atom(
                        envelope * torch.sin(phase),
                        AtomType.GW_INSPIRAL, position=pos, scale=scale, f_start=f0, f_end=f1
                    ))
                
                # GW Ringdown
                for tau in self.decay_rates[:3]:
                    for f0 in [15, 25, 40]:
                        ringdown = torch.zeros(self.n, device=self.device)
                        mask = t >= pos
                        if mask.any():
                            dt_arr = t[mask] - pos
                            amp_decay = torch.exp(-tau * dt_arr)
                            freq_decay = f0 * torch.exp(-0.3 * tau * dt_arr)
                            phase = 2 * np.pi * torch.cumsum(freq_decay, dim=0) * dt
                            ringdown[mask] = amp_decay * torch.sin(phase)
                        atoms.append(self._add_atom(
                            ringdown,
                            AtomType.GW_RINGDOWN, position=pos, decay_rate=tau, frequency=f0
                        ))
                
                # GW Burst
                for freq in [20, 40, 60]:
                    xi = (t - pos) / scale
                    envelope = torch.exp(-xi ** 4)
                    atoms.append(self._add_atom(
                        envelope * torch.sin(2 * np.pi * freq * (t - pos)),
                        AtomType.GW_BURST, position=pos, scale=scale, frequency=freq
                    ))
        
        return atoms
    
    def _generate_chirps(self) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        
        # Linear Chirp (localizado)
        for pos in self.positions:
            for scale in self.scales:
                for f0 in [5, 10, 20]:
                    for alpha in self.chirp_rates:
                        xi = (t - pos) / scale
                        envelope = torch.exp(-0.5 * xi ** 2)
                        tau = t - pos
                        phase = 2 * np.pi * (f0 * tau + alpha * tau ** 2 / 2)
                        atoms.append(self._add_atom(
                            envelope * torch.sin(phase),
                            AtomType.LINEAR_CHIRP, position=pos, scale=scale, 
                            f_start=f0, chirp_rate=alpha
                        ))
        
        # Global Chirp (sem envelope)
        for f0 in [1, 3, 5, 10, 15, 20]:
            for alpha in self.chirp_rates:
                for phi in [0, np.pi/2]:
                    phase = 2 * np.pi * (f0 * t + alpha * t ** 2 / 2) + phi
                    atoms.append(self._add_atom(
                        torch.sin(phase),
                        AtomType.GLOBAL_CHIRP, f_start=f0, chirp_rate=alpha, phase=phi
                    ))
        
        return atoms
    
    def _generate_luminidio(self) -> List[torch.Tensor]:
        atoms = []
        t = self.t
        
        for pos in self.positions:
            for scale in self.scales:
                for f0 in [5, 10, 15]:
                    for alpha in self.chirp_rates[:4]:
                        xi = (t - pos) / scale
                        
                        # Luminidic Chirp
                        envelope_base = torch.exp(-torch.abs(xi))
                        coupling = 1 - ALPHA2 * torch.exp(-torch.abs(xi) / (ALPHA2 * 10))
                        envelope = envelope_base * coupling
                        tau = t - pos
                        phase = 2 * np.pi * (f0 * tau + alpha * tau ** 2 / 2)
                        atoms.append(self._add_atom(
                            envelope * torch.sin(phase),
                            AtomType.LUMINIDIC_CHIRP, position=pos, scale=scale,
                            f_start=f0, chirp_rate=alpha
                        ))
                        
                        # Envelope Chirp
                        envelope2 = torch.exp(-xi ** 2)
                        phase2 = 2 * np.pi * (f0 * t + alpha * t ** 2 / 2)
                        atoms.append(self._add_atom(
                            envelope2 * torch.sin(phase2),
                            AtomType.ENVELOPE_CHIRP, position=pos, scale=scale,
                            f_start=f0, chirp_rate=alpha
                        ))
        
        return atoms
    
    def get_atom_from_index(self, idx: int, coefficient: float, sign: int) -> SelectedAtom:
        """Converte índice + metadados em SelectedAtom para reconstrução."""
        if idx >= len(self.atom_metadata):
            # Fallback para constante
            return SelectedAtom(
                atom_type=AtomType.CONSTANT,
                category="CLASSIC",
                coefficient=coefficient,
                sign=sign
            )
        
        meta = self.atom_metadata[idx]
        return SelectedAtom(
            atom_type=meta['atom_type'],
            category=meta['category'],
            coefficient=coefficient,
            sign=sign,
            position=meta.get('position', 0.5),
            scale=meta.get('scale', 0.1),
            frequency=meta.get('frequency', 5.0),
            f_start=meta.get('f_start', 5.0),
            f_end=meta.get('f_end', 30.0),
            chirp_rate=meta.get('chirp_rate', 40.0),
            decay_rate=meta.get('decay_rate', 5.0),
            phase=meta.get('phase', 0.0),
            knot_positions=meta.get('knot_positions'),
            knot_values=meta.get('knot_values')
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RECONSTRUTOR - GERA SINAL A PARTIR DOS ÁTOMOS SELECIONADOS
# ═══════════════════════════════════════════════════════════════════════════════

class AtomReconstructor:
    """Reconstrói o sinal a partir dos átomos selecionados."""
    
    def __init__(self, n_samples: int, device: torch.device):
        self.n = n_samples
        self.device = device
        self.t = torch.linspace(0, 1, n_samples, device=device)
    
    def generate_atom(self, atom: SelectedAtom) -> torch.Tensor:
        """Gera um único átomo com os parâmetros salvos."""
        t = self.t
        dt = 1.0 / self.n
        
        if atom.atom_type == AtomType.CONSTANT:
            return torch.full((self.n,), atom.coefficient, device=self.device)
        
        elif atom.atom_type == AtomType.LINEAR:
            return atom.coefficient * t
        
        elif atom.atom_type == AtomType.SINE:
            return torch.sin(2 * np.pi * atom.frequency * t + atom.phase)
        
        elif atom.atom_type == AtomType.COSINE:
            return torch.cos(2 * np.pi * atom.frequency * t + atom.phase)
        
        elif atom.atom_type == AtomType.GAUSSIAN:
            xi = (t - atom.position) / atom.scale
            return torch.exp(-0.5 * xi ** 2)
        
        elif atom.atom_type == AtomType.DAMPED_SINE:
            return torch.exp(-atom.decay_rate * t) * torch.sin(2 * np.pi * atom.frequency * t)
        
        elif atom.atom_type == AtomType.MORLET:
            xi = (t - atom.position) / atom.scale
            return torch.exp(-0.5 * xi ** 2) * torch.cos(2 * np.pi * atom.frequency * (t - atom.position))
        
        elif atom.atom_type == AtomType.MEXICAN_HAT:
            xi = (t - atom.position) / atom.scale
            norm = 2 / (np.sqrt(3) * np.pi ** 0.25)
            return norm * (1 - xi ** 2) * torch.exp(-0.5 * xi ** 2)
        
        elif atom.atom_type == AtomType.HAAR:
            haar = torch.zeros(self.n, device=self.device)
            mask_pos = (t >= atom.position) & (t < atom.position + atom.scale / 2)
            mask_neg = (t >= atom.position + atom.scale / 2) & (t < atom.position + atom.scale)
            haar[mask_pos] = 1.0
            haar[mask_neg] = -1.0
            return haar
        
        elif atom.atom_type == AtomType.GABOR:
            xi = (t - atom.position) / atom.scale
            return torch.exp(-0.5 * xi ** 2) * torch.sin(2 * np.pi * atom.frequency * (t - atom.position))
        
        elif atom.atom_type == AtomType.CUBIC_SPLINE:
            if atom.knot_positions and atom.knot_values:
                t_np = np.linspace(0, 1, self.n)
                interp = np.interp(t_np, atom.knot_positions, atom.knot_values)
                return torch.tensor(interp, device=self.device, dtype=torch.float32)
            return torch.zeros(self.n, device=self.device)
        
        elif atom.atom_type == AtomType.NEUTRINO_DECAY:
            decay = torch.zeros(self.n, device=self.device)
            mask = t >= atom.position
            decay[mask] = torch.exp(-atom.decay_rate * (t[mask] - atom.position))
            return decay
        
        elif atom.atom_type == AtomType.NEUTRINO_TRACE:
            peak = torch.exp(-0.5 * ((t - atom.position) / atom.scale) ** 2)
            decay = torch.ones(self.n, device=self.device)
            mask = t > atom.position
            decay[mask] = torch.exp(-atom.decay_rate * (t[mask] - atom.position))
            return peak * decay
        
        elif atom.atom_type == AtomType.NEUTRINO_FLAVOR:
            envelope = torch.exp(-atom.decay_rate * torch.abs(t - atom.position))
            oscillation = torch.sin(2 * np.pi * atom.frequency * (t - atom.position))
            return envelope * oscillation
        
        elif atom.atom_type == AtomType.GW_INSPIRAL:
            xi = (t - atom.position) / atom.scale
            envelope = torch.exp(-0.5 * xi ** 2)
            freq = atom.f_start + (atom.f_end - atom.f_start) * (0.5 + 0.5 * torch.tanh(3 * xi))
            phase = 2 * np.pi * torch.cumsum(freq, dim=0) * dt
            return envelope * torch.sin(phase)
        
        elif atom.atom_type == AtomType.GW_RINGDOWN:
            ringdown = torch.zeros(self.n, device=self.device)
            mask = t >= atom.position
            if mask.any():
                dt_arr = t[mask] - atom.position
                amp_decay = torch.exp(-atom.decay_rate * dt_arr)
                freq_decay = atom.frequency * torch.exp(-0.3 * atom.decay_rate * dt_arr)
                phase = 2 * np.pi * torch.cumsum(freq_decay, dim=0) * dt
                ringdown[mask] = amp_decay * torch.sin(phase)
            return ringdown
        
        elif atom.atom_type == AtomType.GW_BURST:
            xi = (t - atom.position) / atom.scale
            envelope = torch.exp(-xi ** 4)
            return envelope * torch.sin(2 * np.pi * atom.frequency * (t - atom.position))
        
        elif atom.atom_type == AtomType.LINEAR_CHIRP:
            xi = (t - atom.position) / atom.scale
            envelope = torch.exp(-0.5 * xi ** 2)
            tau = t - atom.position
            phase = 2 * np.pi * (atom.f_start * tau + atom.chirp_rate * tau ** 2 / 2)
            return envelope * torch.sin(phase)
        
        elif atom.atom_type == AtomType.GLOBAL_CHIRP:
            phase = 2 * np.pi * (atom.f_start * t + atom.chirp_rate * t ** 2 / 2) + atom.phase
            return torch.sin(phase)
        
        elif atom.atom_type == AtomType.LUMINIDIC_CHIRP:
            xi = (t - atom.position) / atom.scale
            envelope_base = torch.exp(-torch.abs(xi))
            coupling = 1 - ALPHA2 * torch.exp(-torch.abs(xi) / (ALPHA2 * 10))
            envelope = envelope_base * coupling
            tau = t - atom.position
            phase = 2 * np.pi * (atom.f_start * tau + atom.chirp_rate * tau ** 2 / 2)
            return envelope * torch.sin(phase)
        
        elif atom.atom_type == AtomType.ENVELOPE_CHIRP:
            xi = (t - atom.position) / atom.scale
            envelope = torch.exp(-xi ** 2)
            phase = 2 * np.pi * (atom.f_start * t + atom.chirp_rate * t ** 2 / 2)
            return envelope * torch.sin(phase)
        
        return torch.zeros(self.n, device=self.device)
    
    def reconstruct(self, lagrangian: Lagrangian) -> torch.Tensor:
        """Reconstrói o sinal completo a partir da Lagrangiana."""
        result = torch.full((self.n,), lagrangian.offset, device=self.device)
        
        for atom in lagrangian.atoms:
            waveform = self.generate_atom(atom)
            # Normalizar e aplicar coeficiente
            norm = torch.norm(waveform)
            if norm > EPSILON:
                waveform = waveform / norm
            result = result + atom.sign * atom.coefficient * waveform
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHING PURSUIT GPU
# ═══════════════════════════════════════════════════════════════════════════════

class MatchingPursuitGPU:
    """Matching Pursuit otimizado para GPU com salvamento de parâmetros."""
    
    def __init__(self, n_samples: int, max_atoms: int, device: torch.device):
        self.n = n_samples
        self.max_atoms = max_atoms
        self.device = device
        self.generator = AtomGeneratorGPU(n_samples, device)
    
    def pursue(self, g_fixed: torch.Tensor, verbose: bool = False
              ) -> Tuple[Lagrangian, float, SoteriologicalState, Dict[str, int], Dict[str, float]]:
        """Executa Matching Pursuit e retorna Lagrangiana com átomos."""
        
        n = len(g_fixed)
        offset = float(torch.mean(g_fixed).item())
        residual = g_fixed - offset
        
        initial_energy = float(torch.sum(residual ** 2).item()) + EPSILON
        
        if verbose:
            print(f"  Gerando candidatos em batch...")
        
        # Gerar todos os átomos candidatos
        t_gen = time.time()
        atoms_matrix = self.generator.generate_all_atoms(residual)
        n_candidates = atoms_matrix.shape[0]
        
        if verbose:
            print(f"  {n_candidates} candidatos gerados em {time.time()-t_gen:.2f}s")
            print(f"  Iniciando Matching Pursuit...")
        
        # Tracking
        selected_atoms: List[SelectedAtom] = []
        category_counts = {cat: 0 for cat in ["CLASSIC", "WAVELET", "SPLINE", 
                                               "NEUTRINO", "GRAV_WAVE", "LUMINIDIO", "DARK_ENERGY"]}
        category_contributions = {cat: 0.0 for cat in category_counts}
        
        t_pursuit = time.time()
        
        for iteration in range(self.max_atoms):
            current_energy = float(torch.sum(residual ** 2).item())
            current_resistance = current_energy / initial_energy
            
            if current_resistance < TETELESTAI:
                break
            
            # Calcular correlações em batch
            correlations = torch.matmul(atoms_matrix, residual)
            
            # Encontrar melhor átomo
            best_idx = int(torch.argmax(torch.abs(correlations)).item())
            best_corr = float(correlations[best_idx].item())
            
            if abs(best_corr) < EPSILON:
                break
            
            # Calcular coeficiente e sinal
            best_atom_vec = atoms_matrix[best_idx]
            coefficient = abs(best_corr)
            sign = 1 if best_corr > 0 else -1
            
            # Obter átomo com parâmetros completos
            selected_atom = self.generator.get_atom_from_index(best_idx, coefficient, sign)
            selected_atoms.append(selected_atom)
            
            # Atualizar contagens
            category_counts[selected_atom.category] += 1
            reduction = coefficient ** 2 / initial_energy
            category_contributions[selected_atom.category] += reduction
            
            # Atualizar resíduo
            residual = residual - sign * coefficient * best_atom_vec
        
        if verbose:
            print(f"  Pursuit completo em {time.time()-t_pursuit:.2f}s")
            print(f"  {len(selected_atoms)} átomos selecionados")
        
        # Criar Lagrangiana
        lagrangian = Lagrangian(
            atoms=selected_atoms,
            offset=offset,
            n_samples=n
        )
        
        # Calcular resistência final
        reconstructor = AtomReconstructor(n, self.device)
        reconstruction = reconstructor.reconstruct(lagrangian)
        final_energy = float(torch.sum((g_fixed - reconstruction) ** 2).item())
        resistance = final_energy / (float(torch.sum(g_fixed ** 2).item()) + EPSILON)
        
        state = classify_state(resistance)
        
        return lagrangian, resistance, state, category_counts, category_contributions


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL - ACOM UNIFIED v3.0 GPU
# ═══════════════════════════════════════════════════════════════════════════════

class ACOMUnifiedGPU:
    """
    ACOM UNIFIED v3.0 GPU — A Teoria de Tudo Informacional
    
    Versão GPU completa com:
    1. Hierarquia ontológica (I → L → g)
    2. Dinâmica de Lindblad (dissipação quântica)
    3. Predição de energia escura (γ_Λ)
    4. Comparação teoria vs experimento
    5. Salvamento correto dos parâmetros dos átomos para reconstrução
    """
    
    def __init__(self, max_atoms: int = 20, device: str = 'auto'):
        # Selecionar device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.max_atoms = max_atoms
        self.gauge = GaugeSymmetry()
        self.lindblad = LindbladDissipation()
        self.hierarchy = OntologicalHierarchy()
        self.version = VERSION
    
    def compress(self, data: np.ndarray, verbose: bool = False) -> Dict:
        """Compressão com física completa."""
        t_start = time.time()
        
        # Converter para tensor
        L = torch.tensor(data.flatten(), dtype=torch.float32, device=self.device)
        n = len(L)
        
        if verbose:
            print(f"\nACOM UNIFIED v{self.version}")
            print(f"Device: {self.device}")
            print(f"Amostras: {n}")
            print("-" * 60)
        
        # 1. PREDIÇÃO DE LINDBLAD (numpy para cálculos de entropia)
        L_np = data.flatten().astype(np.float64)
        lindblad_prediction = self.lindblad.predict_information_loss(L_np)
        
        # 2. DESCIDA ONTOLÓGICA
        I_original, L_original, s, g = self.hierarchy.full_descent(L)
        
        # 3. GAUGE FIXING
        g_fixed, gauge_info = self.gauge.fix_gauge(g)
        
        # 4. MATCHING PURSUIT
        pursuit = MatchingPursuitGPU(n, self.max_atoms, self.device)
        lagrangian, resistance_g, state_g, category_counts, category_contributions = \
            pursuit.pursue(g_fixed, verbose)
        
        # 5. RECONSTRUÇÃO
        reconstructor = AtomReconstructor(n, self.device)
        g_reconstructed_fixed = reconstructor.reconstruct(lagrangian)
        g_reconstructed = self.gauge.restore_gauge(g_reconstructed_fixed, gauge_info)
        
        # 6. SUBIDA ONTOLÓGICA
        L_reconstructed, I_reconstructed = self.hierarchy.full_ascent(s, g_reconstructed)
        
        # 7. MÉTRICAS ONTOLÓGICAS
        onto_metrics = self._compute_ontological_metrics(
            g, g_reconstructed,
            L_original, L_reconstructed,
            I_original, I_reconstructed
        )
        
        # 8. COMPARAÇÃO TEORIA VS EXPERIMENTO
        comparison = self.lindblad.compare_theory_experiment(
            lindblad_prediction,
            onto_metrics.nu_L,
            onto_metrics.nu_I
        )
        
        lindblad_metrics = LindbladMetrics(
            gamma_lambda=lindblad_prediction['gamma_lambda'],
            spectral_entropy=lindblad_prediction['spectral_entropy'],
            temporal_complexity=lindblad_prediction['temporal_complexity'],
            predicted_preservation_L=lindblad_prediction['theoretical_preservation_L'],
            predicted_preservation_I=lindblad_prediction['theoretical_preservation_I'],
            measured_preservation_L=comparison['measured_preservation_L'],
            measured_preservation_I=comparison['measured_preservation_I'],
            error_L=comparison['error_L'],
            error_I=comparison['error_I'],
            relative_error_L=comparison['relative_error_L'],
            relative_error_I=comparison['relative_error_I'],
            dark_energy_loss=lindblad_prediction['dark_energy_loss'],
            theory_valid=comparison['theory_valid']
        )
        
        t_total = time.time() - t_start
        
        if verbose:
            self._print_verbose(onto_metrics, lindblad_metrics, lagrangian,
                               category_counts, category_contributions, t_total)
        
        return {
            'ontological_metrics': onto_metrics,
            'lindblad_metrics': lindblad_metrics,
            'lagrangian': lagrangian,
            'category_counts': category_counts,
            'category_contributions': category_contributions,
            'time': t_total
        }
    
    def _compute_ontological_metrics(
        self,
        g_original: torch.Tensor, g_rec: torch.Tensor,
        L_original: torch.Tensor, L_rec: torch.Tensor,
        I_original: torch.Tensor, I_rec: torch.Tensor
    ) -> OntologicalMetrics:
        """Calcula métricas em cada nível da hierarquia."""
        metrics = OntologicalMetrics()
        
        # Energias
        g_energy = float(torch.sum(g_original ** 2).item()) + EPSILON
        L_energy = float(torch.sum(L_original ** 2).item()) + EPSILON
        I_energy = float(torch.sum(I_original).item()) + EPSILON
        
        # Resistências
        metrics.nu_g = float(torch.sum((g_original - g_rec) ** 2).item()) / g_energy
        metrics.nu_L = float(torch.sum((L_original - L_rec) ** 2).item()) / L_energy
        metrics.nu_I = float(torch.sum(torch.abs(I_original - I_rec)).item()) / I_energy
        
        # Estados
        metrics.state_g = classify_state(metrics.nu_g)
        metrics.state_L = classify_state(metrics.nu_L)
        metrics.state_I = classify_state(metrics.nu_I)
        
        # Preservação
        metrics.preservation_I_to_L = 1.0
        metrics.preservation_L_to_g = 1.0
        metrics.preservation_g_to_L = 1.0 - metrics.nu_L
        metrics.preservation_L_to_I = 1.0 - metrics.nu_I
        
        return metrics
    
    def _print_verbose(self, onto, lindblad, lagrangian, counts, contribs, time_s):
        print(f"""
[MÉTRICAS ONTOLÓGICAS]
  ν_g = {onto.nu_g:.2e} ({onto.state_g.value})
  ν_L = {onto.nu_L:.2e} ({onto.state_L.value})
  ν_I = {onto.nu_I:.2e} ({onto.state_I.value})

[PRESERVAÇÃO]
  g → L: {onto.preservation_g_to_L*100:.2f}%
  L → I: {onto.preservation_L_to_I*100:.2f}%

[LINDBLAD]
  γ_Λ = {lindblad.gamma_lambda:.4f}
  Predito L: {lindblad.predicted_preservation_L*100:.2f}%
  Medido L:  {lindblad.measured_preservation_L*100:.2f}%
  Erro rel:  {lindblad.relative_error_L*100:.1f}%
  Teoria:    {'✓ VÁLIDA' if lindblad.theory_valid else '✗ DESVIO'}

[ÁTOMOS: {lagrangian.n_atoms}]""")
        for cat, count in counts.items():
            if count > 0:
                contrib = contribs.get(cat, 0) * 100
                print(f"  {cat}: {count} ({contrib:.1f}%)")
        print(f"\n⏱ Tempo total: {time_s:.2f}s")


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    print("╔" + "═" * 68 + "╗")
    print("║" + f"ACOM UNIFIED v{VERSION}".center(68) + "║")
    print("║" + "GPU COMPLETO - CORRIGIDO".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Detectar GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"🚀 GPU detectada: {gpu_name}")
        print(f"   Memória: {gpu_mem:.1f} GB")
    else:
        print("⚠️ GPU não detectada, usando CPU")
    
    print("\n🔥 Aquecendo GPU...")
    
    # Warmup
    acom = ACOMUnifiedGPU(max_atoms=20)
    warmup = np.sin(np.linspace(0, 2*np.pi, 100))
    _ = acom.compress(warmup)
    
    # Sinais de teste
    t = np.linspace(0, 1, 1000)
    
    signals = {
        "Senoide": 100 * np.sin(2 * np.pi * 5 * t),
        "Curva suave": 20 * t**2 * (1 - t) + 15 * np.sin(np.pi * t),
        "Degraus": np.where(t < 0.3, 20, np.where(t < 0.6, 80, 40)).astype(float),
        "Transiente": (
            50 * np.sin(2 * np.pi * 3 * t) + 
            40 * np.exp(-((t - 0.3) / 0.02) ** 2) * np.sin(2 * np.pi * 25 * t)
        ),
        "Chirp": (
            30 * np.exp(-((t - 0.5) / 0.1) ** 2) * 
            np.sin(2 * np.pi * (5 * t + 20 * t**2))
        ),
    }
    
    results = []
    
    for name, sig in signals.items():
        print(f"\n{'═'*70}")
        print(f"TESTE: {name}")
        print(f"{'═'*70}")
        
        result = acom.compress(sig, verbose=True)
        result['name'] = name
        results.append(result)
    
    # Resumo
    print(f"\n\n{'═'*70}")
    print("RESUMO FINAL")
    print(f"{'═'*70}")
    
    print(f"\n{'Sinal':<15} {'ν_g':>12} {'ν_L':>12} {'γ_Λ':>10} {'Tempo':>8} {'Lindblad':>10}")
    print("-" * 70)
    
    n_valid = 0
    total_time = 0
    
    for r in results:
        onto = r['ontological_metrics']
        lb = r['lindblad_metrics']
        valid = "✓" if lb.theory_valid else "✗"
        if lb.theory_valid:
            n_valid += 1
        total_time += r['time']
        
        print(f"{r['name']:<15} {onto.nu_g:>12.2e} {onto.nu_L:>12.2e} {lb.gamma_lambda:>10.4f} "
              f"{r['time']:>7.2f}s {valid:>10}")
    
    print(f"\n⏱ Tempo total: {total_time:.2f}s")
    print(f"✓ Lindblad válido em {n_valid}/{len(results)} sinais ({100*n_valid/len(results):.0f}%)")
    
    if total_time > 0:
        # Estimativa de speedup vs CPU (assumindo 40 min CPU)
        cpu_time_est = 40 * 60  # 40 minutos em segundos
        speedup = cpu_time_est / total_time
        print(f"🚀 Speedup estimado vs CPU: {speedup:.0f}x")


if __name__ == "__main__":
    demo()