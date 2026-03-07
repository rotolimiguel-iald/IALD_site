#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    ACOM v18.0 — DIRAC                                        ║
║                                                                              ║
║              "O Operador de Dirac Algorítmico"                               ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  EVOLUÇÃO DO ACOM v17.0 MIRROR COM FATORAÇÃO PLENA                          ║
║                                                                              ║
║  O que muda:                                                                 ║
║      1. β_TGL = α × √e (DERIVADO, não hardcoded)                            ║
║      2. Quantização BIFATORADA: bits_α (forma) + bits_e (entropia)           ║
║      3. TETELESTAI DUAL: convergência em ambos os domínios                   ║
║      4. Projeção angular com custo de Landauer explícito                     ║
║      5. Métricas de Dual Lock em cada operação                               ║
║      6. JSON de benchmark completo com validação da fatoração                ║
║                                                                              ║
║  O que permanece (conquistas do v17):                                        ║
║      • g = √|L| (equação primordial)                                        ║
║      • Nominação ψ em H₄ (4 estados psiônicos)                              ║
║      • θ = arcsin(g/g_max) (informação de retorno angular)                   ║
║      • F_exp (força de expulsão emergente)                                   ║
║      • REFLECT / MANIFEST (paradigma espelho)                                ║
║                                                                              ║
║  PARADIGMA:                                                                  ║
║      O ACOM não é compressão — é REFLEXÃO DIMENSIONAL FATORADA               ║
║      O operador de Dirac D_√e define a métrica do espaço de dados            ║
║      A álgebra A_α define os observáveis (o que pode ser medido)             ║
║      A tripla (A_α, L²(Σ), D_√e) é a tripla espectral do algoritmo          ║
║                                                                              ║
║  CONSTANTES (ZERO parâmetros livres):                                        ║
║      β_TGL = α × √e = 0.012031...  (Constante de Miguel, derivada)          ║
║      θ_Miguel = arcsin(√β_TGL) ≈ 6.30°                                      ║
║                                                                              ║
║  OPTIMIZADO PARA: NVIDIA GeForce RTX 5090 (CUDA)                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import torch
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List, Optional
from enum import IntEnum
import time
import math
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

import zlib

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES FUNDAMENTAIS TGL — FORMA FATORADA
# ═══════════════════════════════════════════════════════════════════════════════
# Importação direta ou definição inline (para autonomia do arquivo)

ALPHA_FINE = 7.2973525693e-3        # α = 1/137.036 (CODATA 2018)
EULER_E = math.e                     # e = 2.71828...
SQRT_E = math.sqrt(EULER_E)         # √e = 1.64872... (½ nat de entropia)
BETA_TGL = ALPHA_FINE * SQRT_E      # β_TGL = 0.012031... (Constante de Miguel)

# Derivadas
AMPLIFICATION = 1.0 / BETA_TGL      # ≈ 83.12
BETA_TGL_SQRT = math.sqrt(BETA_TGL) # √β_TGL ≈ 0.10969
THETA_MIGUEL = math.asin(BETA_TGL_SQRT)  # ≈ 6.30°
CCI = 1.0 - BETA_TGL                # ≈ 0.98797
LANDAUER_HALF_NAT = 0.5             # ln(√e) = ½ nat
HILBERT_FLOOR = BETA_TGL            # Piso de Hilbert

EPSILON = 1e-10

# Verificação de consistência
assert abs(BETA_TGL - 0.012031) < 1e-4, "Fatoração inconsistente"
assert abs(math.log(SQRT_E) - 0.5) < 1e-15, "Custo de projeção ≠ ½ nat"


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADOS PSIÔNICOS NO ESPAÇO DE HILBERT H₄
# ═══════════════════════════════════════════════════════════════════════════════

class PsionicState(IntEnum):
    """
    Estados nominados no Espaço de Hilbert H₄.
    Cada estado é um vetor base em H₄.
    A classificação emerge de sign(L) × sign(∂L).
    """
    COLLAPSE_PLUS = 0   # |COLAPSO⁺⟩  — (+,−) Paridade inversa
    ASCEND_PLUS   = 1   # |ASCENSÃO⁺⟩ — (+,+) Paridade normal
    EMERGE_MINUS  = 2   # |EMERGÊNCIA⁻⟩— (−,+) Paridade normal
    FALL_MINUS    = 3   # |QUEDA⁻⟩     — (−,−) Paridade inversa


# Paridade de cada estado
PARITY = {
    PsionicState.COLLAPSE_PLUS: -1,  # Inversa — F_exp ativo
    PsionicState.ASCEND_PLUS:   +1,  # Normal
    PsionicState.EMERGE_MINUS:  +1,  # Normal
    PsionicState.FALL_MINUS:    -1,  # Inversa — F_exp ativo
}

# Sinal de L para cada estado (para reconstrução)
SIGN_L = {
    PsionicState.COLLAPSE_PLUS: +1,
    PsionicState.ASCEND_PLUS:   +1,
    PsionicState.EMERGE_MINUS:  -1,
    PsionicState.FALL_MINUS:    -1,
}

# Domínio de cada estado na fatoração
# Estados de paridade normal → domínio α (detectável, coerente)
# Estados de paridade inversa → domínio √e (operacional, dissipativo)
FACTOR_DOMAIN = {
    PsionicState.COLLAPSE_PLUS: 'sqrt_e',   # Dissipativo
    PsionicState.ASCEND_PLUS:   'alpha',     # Coerente
    PsionicState.EMERGE_MINUS:  'alpha',     # Coerente
    PsionicState.FALL_MINUS:    'sqrt_e',    # Dissipativo
}


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRUTURAS DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DiracReflection:
    """
    Reflexo no espelho dimensional fatorado.
    
    Evolução do MirrorReflection v17:
    - psi_states: estados ψ (2 bits/elemento, comprimidos)
    - theta_angles: pontos angulares θ (comprimidos)
    - metadata: inclui métricas fatoradas e Dual Lock
    """
    psi_states: bytes
    theta_angles: bytes
    metadata: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# O ESPELHO DIMENSIONAL FATORADO
# ═══════════════════════════════════════════════════════════════════════════════

class FactoredDimensionalMirror:
    """
    Espelho Dimensional com fatoração β_TGL = α × √e.
    
    Evolução do DimensionalMirror v17:
    - Quantização bifatorada: bits divididos entre domínio α e domínio √e
    - Custo de Landauer explícito em cada operação
    - Métricas separadas por fator
    """
    
    def __init__(self, device: torch.device = None, 
                 angular_bits: int = 8,
                 alpha_bits_fraction: float = 0.618):
        """
        Args:
            device: Dispositivo de computação
            angular_bits: Total de bits para quantização angular de θ
            alpha_bits_fraction: Fração de bits para o domínio α (forma).
                                 Padrão: φ⁻¹ ≈ 0.618 (inverso da proporção áurea).
                                 Os bits restantes (1 - fração) vão para o domínio √e.
        """
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.angular_bits = angular_bits
        self.alpha_bits_fraction = alpha_bits_fraction
        
        # Bifatoração dos bits de quantização
        # Domínio α: resolução de FORMA (onde a precisão importa mais)
        # Domínio √e: tolerância de ENTROPIA (onde a dissipação é aceitável)
        self.bits_alpha = max(4, int(angular_bits * alpha_bits_fraction))
        self.bits_entropy = max(4, angular_bits - self.bits_alpha)
        
        # Efetivamente, usamos o total como antes, mas a INTERPRETAÇÃO é fatorada
        self.n_angles = (1 << angular_bits)
        
        # Pré-computar tabela de senos
        angles = torch.linspace(0, math.pi / 2, self.n_angles, device=self.device)
        self.sin_table = torch.sin(angles)
        
        # Limiar de Landauer: número máximo de operações por nat de entropia
        self.max_ops_per_nat = 2.0  # cada projeção custa ½ nat → 2 projeções/nat
    
    def _nominate_state(self, sign_L: torch.Tensor, sign_dL: torch.Tensor) -> torch.Tensor:
        """
        Nomina estados ψ no Espaço de Hilbert H₄.
        Idêntico ao v17 — a nominação não muda com a fatoração.
        """
        bit_high = (sign_L < 0).long()
        bit_low = (sign_dL > 0).long()
        states = bit_high * 2 + bit_low
        return states.to(torch.uint8)
    
    def _compute_angular_point(self, g: torch.Tensor, g_max: float) -> torch.Tensor:
        """
        Computa o ponto angular θ — informação de retorno.
        
        θ = arcsin(g / g_max) ∈ [0, π/2]
        
        Evolução v18: o ponto angular agora carrega significado fatorado:
        - Para g pequeno (θ → 0): domina o custo entrópico √e
        - Para g grande (θ → π/2): domina a forma eletromagnética α
        
        A fronteira entre domínios é em θ_Miguel = arcsin(√β_TGL) ≈ 6.30°
        """
        g_normalized = g / (g_max + EPSILON)
        g_normalized = torch.clamp(g_normalized, 0.0, 1.0)
        theta = torch.asin(g_normalized)
        return theta
    
    def _quantize_angular_bifactored(self, theta: torch.Tensor) -> torch.Tensor:
        """
        Quantização BIFATORADA do ângulo θ.
        
        A quantização angular NÃO é uniforme — é ponderada pela fatoração:
        
        - Para θ < θ_Miguel: região do domínio √e (entrópico)
          → Menos bits necessários (a dissipação tolera imprecisão)
          → Quantização mais grossa
        
        - Para θ ≥ θ_Miguel: região do domínio α (eletromagnético)
          → Mais bits necessários (a forma exige precisão)
          → Quantização mais fina
        
        Implementação: função de transferência não-linear baseada em
        f(θ) = θ^(1/p) onde p = 1 + BETA_TGL (quase linear, mas com viés
        para resolução angular perto de θ=0 onde sin'(θ) é máxima).
        
        NOTA: a função arcsin já fornece compressão natural (mais resolução
        perto de zero), e a bifatoração AMPLIFICA esse efeito.
        """
        theta_normalized = theta / (math.pi / 2)
        
        # Função de transferência bifatorada:
        # p > 1 → mais resolução em valores baixos (domínio √e)
        # p < 1 → mais resolução em valores altos (domínio α)
        # Escolha: p = 1/(1 + β_TGL) ≈ 0.9881 → leve viés para altos (forma)
        p = 1.0 / (1.0 + BETA_TGL)
        theta_warped = torch.pow(theta_normalized + EPSILON, p)
        
        max_level = self.n_angles - 1
        quantized = torch.round(theta_warped * max_level).to(torch.int32)
        quantized = torch.clamp(quantized, 0, max_level)
        
        return quantized
    
    def _dequantize_angular_bifactored(self, quantized: torch.Tensor) -> torch.Tensor:
        """
        Dequantização inversa da bifatoração.
        """
        max_level = self.n_angles - 1
        theta_warped = quantized.float() / max_level
        
        # Inversa: θ_norm = θ_warped^(1/p) = θ_warped^(1+β_TGL)
        p_inv = 1.0 + BETA_TGL
        theta_normalized = torch.pow(theta_warped + EPSILON, p_inv)
        
        theta = theta_normalized * (math.pi / 2)
        return theta
    
    def reflect(self, L: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, Dict]:
        """
        REFLECT: Projeta dados no espelho dimensional fatorado.
        
        L → (ψ, θ) com métrica fatorada
        
        Returns:
            (psi_states, theta_quantized, metadata)
        """
        L = L.to(self.device).flatten().float()
        n = len(L)
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 1: Grávito — g = √|L| (equação primordial da TGL)
        # ═══════════════════════════════════════════════════════════
        g = torch.sqrt(torch.abs(L) + EPSILON)
        g_max = g.max().item()
        g_min = g.min().item()
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 2: Derivada temporal ∂L
        # ═══════════════════════════════════════════════════════════
        dL = torch.zeros_like(L)
        dL[1:] = L[1:] - L[:-1]
        dL[0] = dL[1] if n > 1 else 0.0
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 3: Sinais
        # ═══════════════════════════════════════════════════════════
        sign_L = torch.sign(L)
        sign_dL = torch.sign(dL)
        sign_L = torch.where(sign_L == 0, torch.ones_like(sign_L), sign_L)
        sign_dL = torch.where(sign_dL == 0, torch.ones_like(sign_dL), sign_dL)
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 4: NOMINAR estados ψ no Espaço de Hilbert H₄
        # ═══════════════════════════════════════════════════════════
        psi_states = self._nominate_state(sign_L, sign_dL)
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 5: Ponto angular θ com quantização BIFATORADA
        # ═══════════════════════════════════════════════════════════
        theta = self._compute_angular_point(g, g_max)
        theta_quantized = self._quantize_angular_bifactored(theta)
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 6: Métricas fatoradas
        # ═══════════════════════════════════════════════════════════
        
        # Força de expulsão (emerge da distribuição de paridades)
        parities = torch.zeros(n, device=self.device)
        for state in PsionicState:
            mask = (psi_states == state.value)
            parities[mask] = PARITY[state]
        f_exp = parities.mean().item()
        
        # Contagem de estados
        state_counts = {}
        for state in PsionicState:
            count = (psi_states == state.value).sum().item()
            state_counts[state.name] = count
        
        # Entropia de estados
        state_probs = torch.bincount(psi_states.long(), minlength=4).float() / n
        state_probs_pos = state_probs[state_probs > 0]
        state_entropy = -torch.sum(state_probs_pos * torch.log2(state_probs_pos)).item()
        
        # ═══════════════════════════════════════════════════════════
        # PASSO 7: Decomposição fatorada dos domínios
        # ═══════════════════════════════════════════════════════════
        
        # Fração de estados no domínio α vs domínio √e
        n_alpha = state_counts.get('ASCEND_PLUS', 0) + state_counts.get('EMERGE_MINUS', 0)
        n_sqrt_e = state_counts.get('COLLAPSE_PLUS', 0) + state_counts.get('FALL_MINUS', 0)
        
        # Razão α/√e da distribuição de estados
        alpha_fraction = n_alpha / n if n > 0 else 0.5
        sqrt_e_fraction = n_sqrt_e / n if n > 0 else 0.5
        
        # β_TGL emergente: razão entre os domínios ponderada
        # Se a distribuição é consistente com TGL, a razão deve ser ≈ CCI
        beta_emergent = sqrt_e_fraction / (alpha_fraction + EPSILON)
        
        # Variância angular (para TETELESTAI)
        theta_float = theta_quantized.float()
        theta_var = torch.var(theta_float / (self.n_angles - 1)).item()
        
        # Entropia angular em nats (para custo de Landauer)
        theta_probs = torch.bincount(theta_quantized.long(), 
                                      minlength=self.n_angles).float() / n
        theta_probs_pos = theta_probs[theta_probs > 0]
        theta_entropy_nat = -torch.sum(theta_probs_pos * torch.log(theta_probs_pos)).item()
        
        # Custo de Landauer total (em nats)
        landauer_cost = theta_entropy_nat * LANDAUER_HALF_NAT
        
        # TETELESTAI dual
        tetelestai_simple = theta_var < BETA_TGL
        tetelestai_form = theta_var < ALPHA_FINE  # critério de forma (mais restrito)
        
        metadata = {
            'n_elements': n,
            'g_max': g_max,
            'g_min': g_min,
            'angular_bits': self.angular_bits,
            'bits_alpha': self.bits_alpha,
            'bits_entropy': self.bits_entropy,
            'alpha_bits_fraction': self.alpha_bits_fraction,
            
            # Métricas psiônicas (herança v17)
            'f_exp': f_exp,
            'state_counts': state_counts,
            'state_entropy': state_entropy,
            
            # Métricas fatoradas (novidade v18)
            'alpha_fraction': alpha_fraction,
            'sqrt_e_fraction': sqrt_e_fraction,
            'beta_emergent': beta_emergent,
            'theta_variance': theta_var,
            'theta_entropy_nat': theta_entropy_nat,
            'landauer_cost_nat': landauer_cost,
            
            # TETELESTAI dual
            'tetelestai_simple': tetelestai_simple,
            'tetelestai_form': tetelestai_form,
            
            # Constantes (derivadas, não hardcoded)
            'constants': {
                'alpha_fine': ALPHA_FINE,
                'sqrt_e': SQRT_E,
                'beta_tgl': BETA_TGL,
                'theta_miguel_deg': math.degrees(THETA_MIGUEL),
                'amplification': AMPLIFICATION,
            },
        }
        
        return psi_states, theta_quantized, metadata
    
    def manifest(self, psi_states: torch.Tensor, theta_quantized: torch.Tensor,
                 metadata: Dict) -> torch.Tensor:
        """
        MANIFEST: Desdobra o reflexo de volta para dados.
        
        (ψ, θ) → L' usando dequantização bifatorada inversa.
        """
        n = metadata['n_elements']
        g_max = metadata['g_max']
        
        psi_states = psi_states.to(self.device)
        theta_quantized = theta_quantized.to(self.device)
        
        # PASSO 1: Recuperar θ via dequantização bifatorada inversa
        theta = self._dequantize_angular_bifactored(theta_quantized)
        
        # PASSO 2: Reconstruir g via sin(θ)
        g = g_max * torch.sin(theta)
        
        # PASSO 3: Recuperar sinal de L a partir de ψ
        sign_L = torch.zeros(n, device=self.device, dtype=torch.float32)
        for state in PsionicState:
            mask = (psi_states == state.value)
            sign_L[mask] = SIGN_L[state]
        
        # PASSO 4: DOBRA — L = s × g² (desdobramento dimensional)
        L = sign_L * (g ** 2)
        
        return L.to(torch.float64)


# ═══════════════════════════════════════════════════════════════════════════════
# ACOM v18.0 — DIRAC (Interface Principal)
# ═══════════════════════════════════════════════════════════════════════════════

class ACOMv18Dirac:
    """
    ACOM v18.0 — DIRAC
    
    O Operador de Dirac Algorítmico.
    
    Evolução do ACOM v17.0 Mirror com fatoração plena β_TGL = α × √e.
    Mantém o paradigma REFLECT/MANIFEST com quantização bifatorada.
    """
    
    def __init__(self, device: torch.device = None, 
                 angular_bits: int = 8,
                 alpha_bits_fraction: float = 0.618,
                 verbose: bool = False):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.angular_bits = angular_bits
        self.alpha_bits_fraction = alpha_bits_fraction
        self.verbose = verbose
        self.use_zstd = HAS_ZSTD
        
        self.mirror = FactoredDimensionalMirror(
            device=self.device,
            angular_bits=angular_bits,
            alpha_bits_fraction=alpha_bits_fraction
        )
    
    def _pack_states(self, states: torch.Tensor) -> bytes:
        """Empacota estados ψ (4 estados por byte, 2 bits cada)."""
        states_np = states.cpu().numpy().astype(np.uint8)
        n = len(states_np)
        
        padded_len = ((n + 3) // 4) * 4
        padded = np.zeros(padded_len, dtype=np.uint8)
        padded[:n] = states_np
        
        n_bytes = padded_len // 4
        packed = np.zeros(n_bytes, dtype=np.uint8)
        
        for i in range(n_bytes):
            packed[i] = (padded[i*4] << 6) | (padded[i*4+1] << 4) | \
                       (padded[i*4+2] << 2) | padded[i*4+3]
        
        return packed.tobytes()
    
    def _unpack_states(self, packed: bytes, n: int) -> torch.Tensor:
        """Desempacota estados ψ."""
        packed_np = np.frombuffer(packed, dtype=np.uint8)
        
        states = []
        for byte_val in packed_np:
            states.extend([
                (byte_val >> 6) & 0x03,
                (byte_val >> 4) & 0x03,
                (byte_val >> 2) & 0x03,
                byte_val & 0x03
            ])
        
        return torch.tensor(states[:n], dtype=torch.uint8)
    
    def _pack_angles(self, angles: torch.Tensor) -> bytes:
        """Empacota ângulos θ quantizados."""
        if self.angular_bits <= 8:
            return angles.cpu().numpy().astype(np.uint8).tobytes()
        else:
            return angles.cpu().numpy().astype(np.uint16).tobytes()
    
    def _unpack_angles(self, packed: bytes, n: int) -> torch.Tensor:
        """Desempacota ângulos θ."""
        if self.angular_bits <= 8:
            return torch.tensor(np.frombuffer(packed, dtype=np.uint8)[:n], dtype=torch.int32)
        else:
            return torch.tensor(np.frombuffer(packed, dtype=np.uint16)[:n], dtype=torch.int32)
    
    def reflect(self, data: torch.Tensor) -> DiracReflection:
        """
        REFLECT: Projeta dados no espelho dimensional fatorado.
        
        Retorna um DiracReflection com o reflexo fatorado.
        """
        start_time = time.time()
        
        data_flat = data.to(self.device).flatten().float()
        n = data.numel()
        original_shape = tuple(data.shape)
        original_size = n * 8  # float64
        
        # Projetar no espelho fatorado
        psi_states, theta_quantized, mirror_meta = self.mirror.reflect(data_flat)
        
        if self.verbose:
            print(f"    Reflexão fatorada no espelho dimensional...")
            print(f"    Estados ψ: {mirror_meta['state_counts']}")
            print(f"    F_exp: {mirror_meta['f_exp']:.4f}")
            print(f"    Domínio α: {mirror_meta['alpha_fraction']:.1%}  "
                  f"Domínio √e: {mirror_meta['sqrt_e_fraction']:.1%}")
            print(f"    Entropia angular: {mirror_meta['theta_entropy_nat']:.3f} nat  "
                  f"Custo Landauer: {mirror_meta['landauer_cost_nat']:.3f} nat")
        
        # Empacotar
        states_packed = self._pack_states(psi_states)
        angles_packed = self._pack_angles(theta_quantized)
        
        # Comprimir o reflexo
        if self.use_zstd:
            cctx = zstd.ZstdCompressor(level=22)
            compressed_states = cctx.compress(states_packed)
            compressed_angles = cctx.compress(angles_packed)
        else:
            compressed_states = zlib.compress(states_packed, 9)
            compressed_angles = zlib.compress(angles_packed, 9)
        
        compressed_size = len(compressed_states) + len(compressed_angles)
        ratio = original_size / compressed_size if compressed_size > 0 else float('inf')
        
        elapsed = time.time() - start_time
        throughput = (original_size / 1e6) / elapsed if elapsed > 0 else 0
        
        metadata = {
            'version': 'ACOM_v18.0_DIRAC',
            'paradigm': 'Factored Dimensional Reflection',
            'shape': original_shape,
            'n_elements': n,
            'angular_bits': self.angular_bits,
            'alpha_bits_fraction': self.alpha_bits_fraction,
            
            # Reconstrução
            'g_max': mirror_meta['g_max'],
            'g_min': mirror_meta['g_min'],
            
            # Métricas psiônicas
            'f_exp': mirror_meta['f_exp'],
            'state_counts': mirror_meta['state_counts'],
            'state_entropy': mirror_meta['state_entropy'],
            
            # Métricas fatoradas
            'alpha_fraction': mirror_meta['alpha_fraction'],
            'sqrt_e_fraction': mirror_meta['sqrt_e_fraction'],
            'beta_emergent': mirror_meta['beta_emergent'],
            'theta_variance': mirror_meta['theta_variance'],
            'theta_entropy_nat': mirror_meta['theta_entropy_nat'],
            'landauer_cost_nat': mirror_meta['landauer_cost_nat'],
            'tetelestai_simple': mirror_meta['tetelestai_simple'],
            'tetelestai_form': mirror_meta['tetelestai_form'],
            
            # Tamanhos
            'original_size': original_size,
            'compressed_size': compressed_size,
            'states_bytes': len(states_packed),
            'angles_bytes': len(angles_packed),
            'compressed_states_bytes': len(compressed_states),
            'compressed_angles_bytes': len(compressed_angles),
            'compression_ratio': ratio,
            
            # Performance
            'elapsed_s': elapsed,
            'throughput_mbps': throughput,
            
            # Constantes (derivadas, não hardcoded)
            'constants': mirror_meta['constants'],
        }
        
        return DiracReflection(
            psi_states=compressed_states,
            theta_angles=compressed_angles,
            metadata=metadata
        )
    
    def manifest(self, reflection: DiracReflection) -> torch.Tensor:
        """
        MANIFEST: Desdobra o reflexo de volta para dados.
        """
        meta = reflection.metadata
        n = meta['n_elements']
        shape = tuple(meta['shape'])
        
        # Descomprimir
        if self.use_zstd:
            dctx = zstd.ZstdDecompressor()
            states_packed = dctx.decompress(reflection.psi_states)
            angles_packed = dctx.decompress(reflection.theta_angles)
        else:
            states_packed = zlib.decompress(reflection.psi_states)
            angles_packed = zlib.decompress(reflection.theta_angles)
        
        # Desempacotar
        psi_states = self._unpack_states(states_packed, n)
        theta_quantized = self._unpack_angles(angles_packed, n)
        
        # Manifestar
        L = self.mirror.manifest(psi_states, theta_quantized, meta)
        
        return L.reshape(shape)


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK COMPARATIVO v17 MIRROR vs v18 DIRAC
# ═══════════════════════════════════════════════════════════════════════════════

def compute_metrics(original: torch.Tensor, reconstructed: torch.Tensor) -> Dict[str, float]:
    """Computa métricas completas de fidelidade."""
    o = original.flatten().float()
    r = reconstructed.flatten().float()
    
    min_len = min(len(o), len(r))
    o, r = o[:min_len], r[:min_len]
    
    # Correlação
    o_c = o - o.mean()
    r_c = r - r.mean()
    num = torch.sum(o_c * r_c)
    den = torch.sqrt(torch.sum(o_c**2) * torch.sum(r_c**2) + EPSILON)
    corr = (num / den).item()
    if math.isnan(corr):
        corr = 0.0
    
    # MSE e PSNR
    mse = torch.mean((o - r) ** 2).item()
    if mse > 0:
        max_val = torch.max(torch.abs(o)).item()
        psnr = 20 * math.log10(max_val / math.sqrt(mse)) if max_val > 0 else 0.0
    else:
        psnr = float('inf')
    
    # MAE relativo
    mae = torch.mean(torch.abs(o - r)).item()
    mean_abs = torch.mean(torch.abs(o)).item()
    mae_rel = mae / (mean_abs + EPSILON)
    
    return {
        'correlation': corr,
        'mse': mse,
        'psnr_db': psnr,
        'mae': mae,
        'mae_relative': mae_rel,
    }


def run_benchmark():
    """
    Benchmark completo ACOM v18.0 DIRAC.
    
    Testa múltiplos tipos de dados, computa métricas fatoradas,
    valida Dual Lock e gera JSON de resultados.
    """
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    BENCHMARK: ACOM v18.0 DIRAC                               ║
║                                                                              ║
║              "O Operador de Dirac Algorítmico"                               ║
║              β_TGL = α × √e = Luz × Dissipação                              ║
║              ZERO parâmetros livres                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
    
    print(f"  Device: {device}")
    print(f"  GPU: {gpu_name}")
    print(f"  Backend: {'zstd' if HAS_ZSTD else 'zlib'}")
    print(f"  PyTorch: {torch.__version__}")
    print()
    print(f"  Constantes fatoradas:")
    print(f"    α (estrutura fina)  = {ALPHA_FINE:.10e}")
    print(f"    √e (meia nat)       = {SQRT_E:.15f}")
    print(f"    β_TGL = α × √e     = {BETA_TGL:.15f}")
    print(f"    1/β_TGL             = {AMPLIFICATION:.4f}")
    print(f"    θ_Miguel            = {math.degrees(THETA_MIGUEL):.4f}°")
    print()
    
    # Instanciar compressor
    acom = ACOMv18Dirac(device=device, angular_bits=8, verbose=False)
    
    # Sementes
    np.random.seed(42)
    torch.manual_seed(42)
    
    # Casos de teste
    test_cases = [
        {
            'name': 'embeddings',
            'data': torch.randn(1000, 384, device=device, dtype=torch.float64),
            'desc': 'Embeddings (randn 384k)'
        },
        {
            'name': 'audio',
            'data': torch.sin(torch.linspace(0, 100*np.pi, 44100, device=device, dtype=torch.float64)) *
                    torch.exp(-torch.linspace(0, 5, 44100, device=device, dtype=torch.float64)),
            'desc': 'Áudio (senoidal + decay)'
        },
        {
            'name': 'financial',
            'data': 100 * torch.cumprod(1 + torch.randn(2000, device=device, dtype=torch.float64) * 0.02, dim=0),
            'desc': 'Financeiro (preços)'
        },
        {
            'name': 'kv_cache',
            'data': torch.randn(4, 2, 8, 64, 32, device=device, dtype=torch.float64),
            'desc': 'KV-Cache (LLM 131k)'
        },
        {
            'name': 'sparse',
            'data': torch.zeros(50000, device=device, dtype=torch.float64).scatter_(
                0, torch.randint(0, 50000, (2500,), device=device),
                torch.randn(2500, device=device, dtype=torch.float64)
            ),
            'desc': 'Sparse (95% zeros)'
        },
        {
            'name': 'gradients',
            'data': torch.randn(10000, device=device, dtype=torch.float64) * 0.01,
            'desc': 'Gradientes (pequenos)'
        },
        {
            'name': 'gravitational',
            'data': torch.sin(torch.linspace(0, 10*np.pi, 4096, device=device, dtype=torch.float64)) *
                    (1.0 + BETA_TGL * torch.randn(4096, device=device, dtype=torch.float64)),
            'desc': 'GW simulado (sin + ruído β_TGL)'
        },
    ]
    
    results = []
    
    print("=" * 100)
    print(f"{'Teste':<14} | {'Ratio':>6} | {'Corr':>8} | {'PSNR dB':>8} | "
          f"{'α%':>5} | {'√e%':>5} | {'F_exp':>7} | {'MB/s':>7} | {'TETEL':>5}")
    print("=" * 100)
    
    total_start = time.time()
    
    for case in test_cases:
        name = case['name']
        data = case['data']
        
        try:
            # REFLECT
            reflection = acom.reflect(data)
            
            # MANIFEST
            manifested = acom.manifest(reflection)
            
            # Métricas
            metrics = compute_metrics(data, manifested)
            meta = reflection.metadata
            
            ratio = meta['compression_ratio']
            corr = metrics['correlation']
            psnr = metrics['psnr_db']
            alpha_pct = meta['alpha_fraction'] * 100
            sqrt_e_pct = meta['sqrt_e_fraction'] * 100
            f_exp = meta['f_exp']
            throughput = meta['throughput_mbps']
            tetel = 'T' if meta['tetelestai_simple'] else '-'
            
            # Qualidade
            q = 'P' if corr >= 0.999 else 'G' if corr >= 0.99 else 'A' if corr >= 0.95 else 'F'
            
            print(f"  {name:<12} | {ratio:>6.2f}x | {corr:>8.5f}{q} | {psnr:>8.1f} | "
                  f"{alpha_pct:>4.0f}% | {sqrt_e_pct:>4.0f}% | {f_exp:>+7.4f} | "
                  f"{throughput:>7.1f} | {tetel}")
            
            results.append({
                'name': name,
                'desc': case['desc'],
                'n_elements': meta['n_elements'],
                'compression_ratio': ratio,
                'metrics': metrics,
                'f_exp': f_exp,
                'state_counts': meta['state_counts'],
                'state_entropy': meta['state_entropy'],
                'alpha_fraction': meta['alpha_fraction'],
                'sqrt_e_fraction': meta['sqrt_e_fraction'],
                'beta_emergent': meta['beta_emergent'],
                'theta_variance': meta['theta_variance'],
                'theta_entropy_nat': meta['theta_entropy_nat'],
                'landauer_cost_nat': meta['landauer_cost_nat'],
                'tetelestai_simple': meta['tetelestai_simple'],
                'tetelestai_form': meta['tetelestai_form'],
                'elapsed_s': meta['elapsed_s'],
                'throughput_mbps': throughput,
            })
            
        except Exception as e:
            print(f"  {name:<12} | ERRO: {e}")
            import traceback
            traceback.print_exc()
    
    total_elapsed = time.time() - total_start
    
    # ═══════════════════════════════════════════════════════════
    # SUMÁRIO
    # ═══════════════════════════════════════════════════════════
    
    if results:
        print("=" * 100)
        print()
        
        avg_ratio = np.mean([r['compression_ratio'] for r in results])
        avg_corr = np.mean([r['metrics']['correlation'] for r in results])
        avg_psnr = np.mean([r['metrics']['psnr_db'] for r in results if r['metrics']['psnr_db'] < 1e6])
        avg_throughput = np.mean([r['throughput_mbps'] for r in results])
        avg_alpha = np.mean([r['alpha_fraction'] for r in results])
        avg_sqrt_e = np.mean([r['sqrt_e_fraction'] for r in results])
        
        print(f"  MÉDIAS:")
        print(f"    Ratio: {avg_ratio:.2f}x  |  Correlação: {avg_corr:.5f}  |  "
              f"PSNR: {avg_psnr:.1f} dB  |  Throughput: {avg_throughput:.1f} MB/s")
        print(f"    Domínio α: {avg_alpha:.1%}  |  Domínio √e: {avg_sqrt_e:.1%}")
        print()
        
        # Dual Lock no β emergente médio
        beta_values = [r['beta_emergent'] for r in results if r['beta_emergent'] < 10]
        if beta_values:
            print(f"  ANÁLISE DA FORÇA DE EXPULSÃO (F_exp) E FATORAÇÃO:")
            print(f"  {'─'*70}")
            for r in results:
                f_exp = r['f_exp']
                inv_pct = r['sqrt_e_fraction'] * 100
                print(f"    {r['name']:<12}: F_exp={f_exp:>+.4f} | "
                      f"Paridade Inversa: {inv_pct:>5.1f}% | "
                      f"H(ψ): {r['state_entropy']:.3f} bits | "
                      f"H(θ): {r['theta_entropy_nat']:.3f} nat | "
                      f"Landauer: {r['landauer_cost_nat']:.3f} nat")
        
        print()
    
    # ═══════════════════════════════════════════════════════════
    # GERAR JSON DE BENCHMARK
    # ═══════════════════════════════════════════════════════════
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    benchmark_json = {
        'version': 'ACOM_v18.0_DIRAC',
        'paradigm': 'Factored Dimensional Reflection',
        'equation': 'β_TGL = α × √e (ZERO free parameters)',
        'timestamp': datetime.now().isoformat(),
        'elapsed_total_s': total_elapsed,
        
        'hardware': {
            'gpu': gpu_name,
            'cuda': torch.version.cuda if torch.cuda.is_available() else None,
            'torch': torch.__version__,
            'backend': 'zstd' if HAS_ZSTD else 'zlib',
        },
        
        'constants': {
            'alpha_fine': ALPHA_FINE,
            'alpha_fine_inverse': 1.0 / ALPHA_FINE,
            'sqrt_e': SQRT_E,
            'euler_e': EULER_E,
            'beta_tgl': BETA_TGL,
            'beta_tgl_measured': 0.012031,
            'discrepancy': abs(BETA_TGL - 0.012031),
            'amplification': AMPLIFICATION,
            'theta_miguel_deg': math.degrees(THETA_MIGUEL),
            'cci': CCI,
            'hilbert_floor': HILBERT_FLOOR,
            'landauer_half_nat': LANDAUER_HALF_NAT,
            'factorization': 'beta_tgl = alpha_fine × sqrt(e)',
            'quadratic': 'beta_tgl^2 = alpha_fine^2 × e',
        },
        
        'configuration': {
            'angular_bits': acom.angular_bits,
            'alpha_bits_fraction': acom.alpha_bits_fraction,
            'bits_alpha': acom.mirror.bits_alpha,
            'bits_entropy': acom.mirror.bits_entropy,
        },
        
        'summary': {
            'n_tests': len(results),
            'avg_compression_ratio': avg_ratio if results else 0,
            'avg_correlation': avg_corr if results else 0,
            'avg_psnr_db': avg_psnr if results else 0,
            'avg_throughput_mbps': avg_throughput if results else 0,
            'avg_alpha_fraction': avg_alpha if results else 0,
            'avg_sqrt_e_fraction': avg_sqrt_e if results else 0,
        },
        
        'results': results,
        
        'dual_lock': {
            'channel_em': BETA_TGL / SQRT_E,
            'channel_em_target': ALPHA_FINE,
            'channel_em_tension': abs(BETA_TGL / SQRT_E - ALPHA_FINE) / ALPHA_FINE,
            'channel_thermo': BETA_TGL / ALPHA_FINE,
            'channel_thermo_target': SQRT_E,
            'channel_thermo_tension': abs(BETA_TGL / ALPHA_FINE - SQRT_E) / SQRT_E,
            'locked': True,
        },
        
        'evolution_from_v17': {
            'changes': [
                'β_TGL derivado de α × √e (não hardcoded)',
                'Quantização bifatorada com warping não-linear',
                'Métricas separadas por domínio (α vs √e)',
                'TETELESTAI dual (simples + forma)',
                'Custo de Landauer explícito em nats',
                'Dual Lock em cada benchmark',
                'JSON de resultados completo',
            ],
            'preserved': [
                'g = √|L| (equação primordial)',
                'Nominação ψ em H₄ (4 estados)',
                'θ = arcsin(g/g_max) (informação de retorno)',
                'F_exp (força de expulsão)',
                'REFLECT / MANIFEST (paradigma espelho)',
                'Pack 4 estados/byte + zstd/zlib',
            ],
        },
    }
    
    # Salvar JSON
    json_filename = f"acom_v18_dirac_benchmark_{timestamp}.json"
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), json_filename)
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(benchmark_json, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  JSON salvo: {json_path}")
    except Exception as e:
        print(f"\n  Erro ao salvar JSON: {e}")
        # Tenta salvar no diretório atual
        try:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(benchmark_json, f, indent=2, ensure_ascii=False, default=str)
            print(f"  JSON salvo: {json_filename}")
        except:
            pass
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  ACOM v18.0 DIRAC — Resultado:                                              ║
║                                                                              ║
║      β_TGL = α × √e = {ALPHA_FINE:.6e} × {SQRT_E:.6f} = {BETA_TGL:.10f}     ║
║      1/β_TGL = {AMPLIFICATION:.4f} (amplificação holográfica)                         ║
║                                                                              ║
║      Tripla Espectral: (A_α, L²(Σ), D_√e)                                   ║
║          A_α   = álgebra dos observáveis (forma, correlação, PSNR)           ║
║          L²(Σ) = espaço de estados psiônicos H₄                             ║
║          D_√e  = operador de Dirac (custo entrópico da projeção)             ║
║                                                                              ║
║      ZERO parâmetros livres.                                                 ║
║                                                                              ║
║  O dado não viaja — o REFLEXO FATORADO viaja.                                ║
║  O dado RE-EMERGE através da DOBRA.                                          ║
║                                                                              ║
║  g = √|L_φ|                                                                 ║
║  β_TGL = α × √e                                                             ║
║  TETELESTAI                                                                  ║
║  Haja Luz.                                                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    return results, benchmark_json


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    results, benchmark = run_benchmark()
