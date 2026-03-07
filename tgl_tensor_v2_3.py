#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║        TGL-TENSOR v2.3 — CADEIA DE NOMES (Inferência Honesta)               ║
║                                                                              ║
║        Certificado de Inferência Honesta via Propagação do NOME             ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CAMADA 1 (v2.2): Pesos em repouso/trânsito → NOME Bifatorado ✅           ║
║  CAMADA 2 (v2.3): Ativações durante inferência → Cadeia de NOMEs           ║
║                                                                              ║
║  CONCEITO:                                                                   ║
║    Cada camada produz uma ativação com um NOME que EMERGE dela.             ║
║    A cadeia N₀→N₁→...→Nₗ é determinística (dado input + pesos).           ║
║    Adulteração em qualquer camada quebra a cadeia.                           ║
║    O Certificado = TGL-Hash(cadeia) → prova de inferência honesta.          ║
║                                                                              ║
║  PERFORMANCE BIFATORADA:                                                     ║
║    MACRO (α): F_exp, S_ψ em TODAS as camadas (~1% overhead)               ║
║    MICRO (√e): TGL-Hash nos CHECKPOINTS (~5 hashes total)                  ║
║                                                                              ║
║  VALIDAÇÃO: MLP simples (3 camadas) → depois escala para Transformer       ║
║                                                                              ║
║  β_TGL = α_fine × √e = 0.012031                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import math
import time
import json
import struct
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES TGL FATORADAS
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FINE = 7.2973525693e-3
SQRT_E = math.sqrt(math.e)
BETA_TGL = ALPHA_FINE * SQRT_E
AMPLIFICATION = 1.0 / BETA_TGL
CCI = 1.0 - BETA_TGL
BETA_TGL_SQRT = math.sqrt(BETA_TGL)
EPSILON = 1e-15
VERSION = "2.3.0"

assert abs(BETA_TGL - 0.012031) < 1e-4

# ═══════════════════════════════════════════════════════════════════════════════
# TGL-HASH v1.2 INLINE
# ═══════════════════════════════════════════════════════════════════════════════

_U64 = (1 << 64) - 1
_HR = max(8, int(math.ceil(math.sqrt(AMPLIFICATION))))
_HF = 4; _HB = 256

def _f2u(f):
    return struct.unpack('<Q', struct.pack('<d', f))[0]

_HRK = tuple(_f2u(ALPHA_FINE*(k+1)*math.pi+math.sin(k*ALPHA_FINE)) if k%2==0
             else _f2u(SQRT_E*(k+1)/math.pi+math.cos(k*SQRT_E)) for k in range(32))
_HRA = [int((ALPHA_FINE*(i+1)*1000)%63)+1 for i in range(_HR+_HF)]
_HRM = [_f2u(SQRT_E*(2**(i+10)))|1 for i in range(_HR+_HF)]
_HSI = tuple(_f2u((ALPHA_FINE**(i%7+1))*(SQRT_E**(i%5+1))*(i+1)*math.pi) for i in range(32))
_HTP = tuple(_f2u(math.sin(BETA_TGL*(i+1)*math.pi)*AMPLIFICATION+math.cos(ALPHA_FINE*(i+1))) for i in range(32))

def _rl(x,n): n&=63; return ((x<<n)|(x>>(64-n)))&_U64
def _rr(x,n): n&=63; return ((x>>n)|(x<<(64-n)))&_U64
def _qr(a,b,c,d,r1,r2):
    a=(a+b)&_U64;d^=a;d=_rl(d,r1);c=(c+d)&_U64;b^=c;b=_rl(b,r2)
    a=(a+b)&_U64;d^=a;d=_rr(d,(r1>>1)+1);c=(c+d)&_U64;b^=c;b=_rr(b,(r2>>1)+1)
    return a,b,c,d

def tgl_hash(data: bytes) -> bytes:
    buf=bytearray(data)+b'\x80'
    ps=struct.pack('<d',BETA_TGL)
    while(len(buf)+8)%_HB!=0: buf.append(ps[len(buf)%8])
    buf.extend(struct.pack('<Q',len(data)&_U64))
    blocks=[bytes(buf[i:i+_HB])for i in range(0,len(buf),_HB)]
    st=list(_HSI)
    for bl in blocks:
        raw=list(struct.unpack('<32Q',bl))
        fl=np.frombuffer(bl,dtype=np.float64).copy()
        g=np.sqrt(np.abs(fl)+EPSILON);s=np.sign(fl);s[s==0]=1.0
        dL=np.diff(fl,prepend=fl[0]);sd=np.sign(dL);sd[sd==0]=1.0
        psi=((s<0).astype(int)*2+(sd>0).astype(int))
        par=np.where((psi==0)|(psi==3),-1.0,1.0)
        fs=int(abs(float(par.mean()))*32+0.5)&63
        if fs==0:fs=1
        gu=g.view(np.uint64)
        for i in range(32):
            raw[i]=_rl(raw[i],(int(psi[i])*16+fs)&63)
            raw[i]^=(int(gu[i])&_U64);raw[i]=(raw[i]+_HTP[i])&_U64
        for r in range(_HR):
            s2=list(st);mk=_HRM[r%len(_HRM)];rot=_HRA[r%len(_HRA)]
            for i in range(32): s2[i]^=raw[i];s2[i]=(s2[i]*mk)&_U64
            for c in range(8): s2[c],s2[c+8],s2[c+16],s2[c+24]=_qr(s2[c],s2[c+8],s2[c+16],s2[c+24],rot,((rot*2)%63)+1)
            for d in range(8):
                i0,i1,i2,i3=d,(d+1)%8+8,(d+2)%8+16,(d+3)%8+24
                s2[i0],s2[i1],s2[i2],s2[i3]=_qr(s2[i0],s2[i1],s2[i2],s2[i3],((rot+7)%63)+1,rot)
            for i in range(32): s2[i]=(s2[i]+_HRK[(i+r)%32])&_U64
            st=s2
    for r in range(_HF):
        ri=_HR+r;s2=list(st);mk=_HRM[ri%len(_HRM)];rot=_HRA[ri%len(_HRA)]
        for i in range(32): s2[i]^=s2[(i+7)%32];s2[i]=(s2[i]*mk)&_U64
        for c in range(8): s2[c],s2[c+8],s2[c+16],s2[c+24]=_qr(s2[c],s2[c+8],s2[c+16],s2[c+24],rot,((rot*2)%63)+1)
        for d in range(8):
            i0,i1,i2,i3=d,(d+1)%8+8,(d+2)%8+16,(d+3)%8+24
            s2[i0],s2[i1],s2[i2],s2[i3]=_qr(s2[i0],s2[i1],s2[i2],s2[i3],((rot+7)%63)+1,rot)
        for i in range(32): s2[i]=(s2[i]+_HRK[(i+ri)%32])&_U64
        st=s2
    f8=[st[i]^st[i+8]^st[i+16]^st[i+24]for i in range(8)]
    f4=[f8[i]^f8[i+4]for i in range(4)]
    return b''.join(struct.pack('<Q',w&_U64)for w in f4)

def tgl_hash_hex(data: bytes) -> str:
    return tgl_hash(data).hex()


# ═══════════════════════════════════════════════════════════════════════════════
# NOME MACRO/MICRO (de v2.2)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NomeMacro:
    f_exp: float
    s_psi: float
    psi_dist: List[float]
    sigma_norm: float
    n_elements: int

@dataclass
class NomeMicro:
    tgl_hash_hex: str

def extract_macro(flat: np.ndarray, sign: np.ndarray = None) -> NomeMacro:
    if sign is None:
        sign = np.sign(flat); sign[sign == 0] = 1.0
    n = len(flat)
    dL = np.zeros(n); dL[1:] = flat[1:] - flat[:-1]
    if n > 1: dL[0] = dL[1]
    sd = np.sign(dL); sd[sd == 0] = 1.0
    psi = ((sign < 0).astype(np.uint8) * 2 + (sd > 0).astype(np.uint8))
    counts = np.bincount(psi.astype(int), minlength=4).astype(np.float64)
    pd = (counts / (n + EPSILON)).tolist()
    par = np.where((psi == 0) | (psi == 3), -1.0, 1.0)
    f_exp = float(par.mean())
    pp = np.array(pd); pp = pp[pp > 0]
    s_psi = float(-np.sum(pp * np.log2(pp)))
    g = np.sqrt(np.abs(flat) + EPSILON)
    sigma = float(g.std() / (g.mean() + EPSILON))
    return NomeMacro(f_exp=f_exp, s_psi=s_psi, psi_dist=pd, sigma_norm=sigma, n_elements=n)


# ═══════════════════════════════════════════════════════════════════════════════
# CADEIA DE NOMES (o coração da v2.3)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NomeEntry:
    """Uma entrada na cadeia de NOMEs."""
    layer: int
    label: str
    macro: NomeMacro
    micro: Optional[NomeMicro]   # Apenas nos checkpoints

class NomeChain:
    """
    Cadeia de NOMEs propagada durante inferência.

    MACRO (α): extraído em TODAS as camadas (~1% overhead)
    MICRO (√e): TGL-Hash nos CHECKPOINTS

    O Certificado de Inferência Honesta = TGL-Hash(cadeia completa)
    """

    def __init__(self, n_layers: int, checkpoint_interval: int = None):
        self.n_layers = n_layers
        if checkpoint_interval is None:
            self.checkpoints = {0, n_layers // 4, n_layers // 2,
                                3 * n_layers // 4, n_layers - 1}
            # Garantir que 0 e última camada estão incluídos
            self.checkpoints.add(0)
            self.checkpoints.add(n_layers - 1)
        else:
            self.checkpoints = set(range(0, n_layers, checkpoint_interval))
            self.checkpoints.add(n_layers - 1)
        self.entries: List[NomeEntry] = []

    def record(self, layer_idx: int, activation: np.ndarray, label: str = ""):
        """Registrar NOME de uma ativação. Chamado durante forward pass."""
        flat = activation.flatten().astype(np.float64)
        macro = extract_macro(flat)

        micro = None
        if layer_idx in self.checkpoints:
            micro = NomeMicro(tgl_hash_hex=tgl_hash_hex(flat.tobytes()))

        self.entries.append(NomeEntry(
            layer=layer_idx,
            label=label or f"layer_{layer_idx}",
            macro=macro,
            micro=micro,
        ))

    def seal(self) -> str:
        """
        Selar a cadeia: TGL-Hash de todos os NOMEs concatenados.
        Retorna o Certificado de Inferência Honesta (CIH).
        """
        chain_data = b''
        for e in self.entries:
            m = e.macro
            chain_data += struct.pack('<dddddI',
                                      m.f_exp, m.s_psi, m.sigma_norm,
                                      m.psi_dist[0], m.psi_dist[1],
                                      e.layer)
            if e.micro is not None:
                chain_data += bytes.fromhex(e.micro.tgl_hash_hex)
        return tgl_hash_hex(chain_data)

    def reset(self):
        self.entries.clear()

    def summary(self) -> Dict:
        return {
            'n_entries': len(self.entries),
            'n_checkpoints': sum(1 for e in self.entries if e.micro is not None),
            'layers': [e.layer for e in self.entries],
            'macros': [{
                'layer': e.layer, 'label': e.label,
                'f_exp': round(e.macro.f_exp, 6),
                's_psi': round(e.macro.s_psi, 6),
                'has_micro': e.micro is not None,
            } for e in self.entries],
        }

    def verify(self, other: 'NomeChain') -> Dict:
        """Comparar duas cadeias. Localizar divergência se houver."""
        seal_a = self.seal()
        seal_b = other.seal()

        if seal_a == seal_b:
            return {'state': 'HONESTA', 'integrity': 1.0,
                    'certificate': seal_a, 'match': True}

        # Localizar onde divergem
        for i in range(min(len(self.entries), len(other.entries))):
            ea, eb = self.entries[i], other.entries[i]

            # Comparar MICRO (exato) nos checkpoints
            if ea.micro and eb.micro:
                if ea.micro.tgl_hash_hex != eb.micro.tgl_hash_hex:
                    return {
                        'state': 'ADULTERADA', 'integrity': 0.0,
                        'divergence_layer': ea.layer,
                        'divergence_type': 'MICRO',
                        'match': False,
                    }

            # Comparar MACRO (tolerância β_TGL)
            delta_f = abs(ea.macro.f_exp - eb.macro.f_exp)
            delta_s = abs(ea.macro.s_psi - eb.macro.s_psi)
            delta_p = sum(abs(a - b) for a, b in
                          zip(ea.macro.psi_dist, eb.macro.psi_dist))
            delta = max(delta_f, delta_s / 2, delta_p / 2)

            if delta > BETA_TGL:
                return {
                    'state': 'ADULTERADA', 'integrity': 0.0,
                    'divergence_layer': ea.layer,
                    'divergence_type': 'MACRO',
                    'delta': delta,
                    'match': False,
                }

        return {'state': 'DIVERGENTE_SUTIL', 'integrity': 0.5, 'match': False}


# ═══════════════════════════════════════════════════════════════════════════════
# MLP SIMPLES PARA VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleMLP:
    """
    MLP com 3 camadas densas + ReLU para validação do conceito.
    Pesos fixos (seed determinística) para reprodutibilidade.
    """

    def __init__(self, dims: List[int], seed: int = 42):
        rng = np.random.RandomState(seed)
        self.layers = []
        for i in range(len(dims) - 1):
            W = rng.randn(dims[i], dims[i + 1]).astype(np.float64) * 0.1
            b = rng.randn(dims[i + 1]).astype(np.float64) * 0.01
            self.layers.append((W, b))
        self.n_layers = len(self.layers)

    def forward(self, x: np.ndarray, chain: NomeChain = None,
                tamper_layer: int = -1, tamper_fn=None) -> np.ndarray:
        """
        Forward pass com registro opcional na cadeia de NOMEs.

        tamper_layer: se >= 0, aplica tamper_fn na ativação APÓS essa camada
        tamper_fn: função(activation) → activation_adulterada
        """
        h = x.astype(np.float64)

        if chain is not None:
            chain.record(0, h, label="input")

        for i, (W, b) in enumerate(self.layers):
            h = h @ W + b

            # ReLU (exceto última camada)
            if i < self.n_layers - 1:
                h = np.maximum(h, 0)

            # Adulteração simulada
            if i == tamper_layer and tamper_fn is not None:
                h = tamper_fn(h)

            if chain is not None:
                chain.record(i + 1, h, label=f"layer_{i+1}")

        return h


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSFORMER SIMPLES PARA VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleTransformer:
    """
    Transformer mínimo (4 camadas, self-attention + FFN) para validação.
    Sem masking causal nem positional encoding — apenas a estrutura.
    """

    def __init__(self, d_model: int = 64, n_heads: int = 4,
                 n_layers: int = 4, seed: int = 42):
        rng = np.random.RandomState(seed)
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        self.n_layers = n_layers
        self.layers = []

        for _ in range(n_layers):
            layer = {
                'Wq': rng.randn(d_model, d_model) * 0.02,
                'Wk': rng.randn(d_model, d_model) * 0.02,
                'Wv': rng.randn(d_model, d_model) * 0.02,
                'Wo': rng.randn(d_model, d_model) * 0.02,
                'W1': rng.randn(d_model, d_model * 4) * 0.02,
                'W2': rng.randn(d_model * 4, d_model) * 0.02,
                'b1': rng.randn(d_model * 4) * 0.001,
                'b2': rng.randn(d_model) * 0.001,
            }
            self.layers.append(layer)

    def _attention(self, x, layer):
        n, d = x.shape
        Q = x @ layer['Wq']; K = x @ layer['Wk']; V = x @ layer['Wv']
        scores = Q @ K.T / math.sqrt(self.d_k)
        scores -= scores.max(axis=1, keepdims=True)
        w = np.exp(scores); w /= w.sum(axis=1, keepdims=True) + EPSILON
        return (w @ V) @ layer['Wo']

    def _ffn(self, x, layer):
        h = np.maximum(x @ layer['W1'] + layer['b1'], 0)  # ReLU
        return h @ layer['W2'] + layer['b2']

    def _layer_norm(self, x):
        mean = x.mean(axis=-1, keepdims=True)
        std = x.std(axis=-1, keepdims=True) + EPSILON
        return (x - mean) / std

    def forward(self, x, chain=None, tamper_layer=-1, tamper_fn=None):
        h = x.astype(np.float64)

        if chain is not None:
            chain.record(0, h, label="input")

        for i, layer in enumerate(self.layers):
            # Self-attention + residual + layernorm
            attn_out = self._attention(h, layer)
            h = self._layer_norm(h + attn_out)

            # FFN + residual + layernorm
            ffn_out = self._ffn(h, layer)
            h = self._layer_norm(h + ffn_out)

            # Adulteração simulada
            if i == tamper_layer and tamper_fn is not None:
                h = tamper_fn(h)

            if chain is not None:
                chain.record(i + 1, h, label=f"transformer_layer_{i+1}")

        return h


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE ADULTERAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def tamper_noise(scale):
    """Adicionar ruído gaussiano."""
    return lambda h: h + np.random.randn(*h.shape) * scale

def tamper_zero_fraction(frac):
    """Zerar uma fração das ativações."""
    def fn(h):
        mask = np.random.rand(*h.shape) > frac
        return h * mask
    return fn

def tamper_scale(factor):
    """Escalar todas as ativações."""
    return lambda h: h * factor

def tamper_permute():
    """Permutar ativações entre posições."""
    return lambda h: h[np.random.permutation(h.shape[0])]

def tamper_clamp(vmin, vmax):
    """Clampar ativações (censura por supressão)."""
    return lambda h: np.clip(h, vmin, vmax)


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark(verbose=True):
    results = {
        'algorithm': 'TGL-Tensor', 'version': VERSION,
        'subtitle': 'Cadeia de NOMEs — Certificado de Inferência Honesta',
        'timestamp': datetime.now().isoformat(),
        'constants': {'alpha_fine': ALPHA_FINE, 'sqrt_e': SQRT_E,
                      'beta_tgl': BETA_TGL, 'cci': CCI},
        'tests': {},
    }

    np.random.seed(42)

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     TGL-TENSOR v{VERSION} — CADEIA DE NOMES (Inferência Honesta)            ║
║                                                                              ║
║     Certificado = TGL-Hash(N₀ || N₁ || ... || Nₗ)                          ║
║     MACRO (α) em todas as camadas | MICRO (√e) nos checkpoints             ║
║                                                                              ║
║     β_TGL = α_fine × √e = {BETA_TGL:.12f}                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 1: DETERMINISMO — mesma inferência → mesmo certificado
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print("  ═══ TESTE 1: Determinismo (MLP 3 camadas) ═══")

    mlp = SimpleMLP(dims=[64, 128, 64, 32])
    x = np.random.randn(16, 64) * 0.1

    certificates = []
    for trial in range(10):
        chain = NomeChain(n_layers=mlp.n_layers + 1)
        mlp.forward(x, chain=chain)
        certificates.append(chain.seal())

    all_equal = len(set(certificates)) == 1
    results['tests']['determinism_mlp'] = {
        'passed': all_equal, 'n_trials': 10,
        'certificate': certificates[0],
        'unique_certificates': len(set(certificates)),
    }
    if verbose:
        print(f"    10 execuções → {len(set(certificates))} certificados únicos → "
              f"{'PASS' if all_equal else 'FAIL'}")

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 2: DETERMINISMO — Transformer
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print("\n  ═══ TESTE 2: Determinismo (Transformer 4 camadas) ═══")

    tf = SimpleTransformer(d_model=64, n_heads=4, n_layers=4)
    x_tf = np.random.randn(16, 64) * 0.1

    certs_tf = []
    for trial in range(10):
        chain_tf = NomeChain(n_layers=tf.n_layers + 1)
        tf.forward(x_tf, chain=chain_tf)
        certs_tf.append(chain_tf.seal())

    all_eq_tf = len(set(certs_tf)) == 1
    results['tests']['determinism_transformer'] = {
        'passed': all_eq_tf, 'n_trials': 10,
        'certificate': certs_tf[0],
    }
    if verbose:
        print(f"    10 execuções → {len(set(certs_tf))} certificados únicos → "
              f"{'PASS' if all_eq_tf else 'FAIL'}")

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 3: DETECÇÃO DE ADULTERAÇÃO — MLP
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print(f"\n  ═══ TESTE 3: Detecção de Adulteração (MLP) ═══")
        print(f"  {'Ataque':<36} | {'Estado':^12} | {'Camada':>6} | {'Tipo':>8} | {'Cert. mudou':>11}")
        print("  " + "─" * 85)

    # Referência: inferência honesta
    chain_ref = NomeChain(n_layers=mlp.n_layers + 1)
    mlp.forward(x, chain=chain_ref)
    cert_ref = chain_ref.seal()

    attacks_mlp = [
        ('Sem adulteração (controle)', -1, None),
        ('Ruído σ=0.001 na camada 1', 0, tamper_noise(0.001)),
        ('Ruído σ=0.01 na camada 1', 0, tamper_noise(0.01)),
        ('Ruído σ=0.1 na camada 1', 0, tamper_noise(0.1)),
        ('Zerar 1% ativações camada 2', 1, tamper_zero_fraction(0.01)),
        ('Zerar 10% ativações camada 2', 1, tamper_zero_fraction(0.10)),
        ('Escalar ×1.01 camada 1', 0, tamper_scale(1.01)),
        ('Escalar ×1.10 camada 1', 0, tamper_scale(1.10)),
        ('Escalar ×2.00 camada 1', 0, tamper_scale(2.00)),
        ('Permutar posições camada 1', 0, tamper_permute()),
        ('Clampar [-0.1, 0.1] camada 2', 1, tamper_clamp(-0.1, 0.1)),
        ('Ruído σ=0.0001 camada 3', 2, tamper_noise(0.0001)),
    ]

    atk_results = {}
    for desc, layer, fn in attacks_mlp:
        chain_atk = NomeChain(n_layers=mlp.n_layers + 1)
        np.random.seed(42)  # Reset seed para input idêntico
        mlp.forward(x, chain=chain_atk, tamper_layer=layer, tamper_fn=fn)
        cert_atk = chain_atk.seal()

        cert_changed = cert_atk != cert_ref

        if fn is None:
            verification = {'state': 'HONESTA', 'match': True}
        else:
            verification = chain_ref.verify(chain_atk)

        atk_results[desc] = {
            'state': verification['state'],
            'certificate_changed': cert_changed,
            'divergence_layer': verification.get('divergence_layer', '-'),
            'divergence_type': verification.get('divergence_type', '-'),
        }

        if verbose:
            div_layer = verification.get('divergence_layer', '-')
            div_type = verification.get('divergence_type', '-')
            print(f"  {desc:<36} | {verification['state']:^12} | "
                  f"{str(div_layer):>6} | {str(div_type):>8} | "
                  f"{'✓ SIM' if cert_changed else '✗ NÃO':>11}")

    results['tests']['adulteration_mlp'] = atk_results

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 4: DETECÇÃO DE ADULTERAÇÃO — Transformer
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print(f"\n  ═══ TESTE 4: Detecção de Adulteração (Transformer) ═══")
        print(f"  {'Ataque':<36} | {'Estado':^12} | {'Camada':>6} | {'Tipo':>8} | {'Cert. mudou':>11}")
        print("  " + "─" * 85)

    chain_ref_tf = NomeChain(n_layers=tf.n_layers + 1)
    np.random.seed(42)
    tf.forward(x_tf, chain=chain_ref_tf)
    cert_ref_tf = chain_ref_tf.seal()

    attacks_tf = [
        ('Sem adulteração (controle)', -1, None),
        ('Ruído σ=0.001 camada 2', 1, tamper_noise(0.001)),
        ('Ruído σ=0.01 camada 2', 1, tamper_noise(0.01)),
        ('Zerar 5% camada 3', 2, tamper_zero_fraction(0.05)),
        ('Escalar ×1.05 camada 1', 0, tamper_scale(1.05)),
        ('Permutar camada 2', 1, tamper_permute()),
        ('Clampar [-0.05, 0.05] camada 3', 2, tamper_clamp(-0.05, 0.05)),
        ('Ruído σ=0.0001 última camada', 3, tamper_noise(0.0001)),
    ]

    atk_results_tf = {}
    for desc, layer, fn in attacks_tf:
        chain_atk_tf = NomeChain(n_layers=tf.n_layers + 1)
        np.random.seed(42)
        tf.forward(x_tf, chain=chain_atk_tf, tamper_layer=layer, tamper_fn=fn)
        cert_atk_tf = chain_atk_tf.seal()

        cert_changed = cert_atk_tf != cert_ref_tf
        if fn is None:
            verification = {'state': 'HONESTA', 'match': True}
        else:
            verification = chain_ref_tf.verify(chain_atk_tf)

        atk_results_tf[desc] = {
            'state': verification['state'],
            'certificate_changed': cert_changed,
            'divergence_layer': verification.get('divergence_layer', '-'),
            'divergence_type': verification.get('divergence_type', '-'),
        }

        if verbose:
            div_layer = verification.get('divergence_layer', '-')
            div_type = verification.get('divergence_type', '-')
            print(f"  {desc:<36} | {verification['state']:^12} | "
                  f"{str(div_layer):>6} | {str(div_type):>8} | "
                  f"{'✓ SIM' if cert_changed else '✗ NÃO':>11}")

    results['tests']['adulteration_transformer'] = atk_results_tf

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 5: OVERHEAD DE PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print(f"\n  ═══ TESTE 5: Overhead de Performance ═══")

    n_iters = 100

    # Sem cadeia
    t0 = time.perf_counter()
    for _ in range(n_iters):
        mlp.forward(x)
    t_bare = (time.perf_counter() - t0) / n_iters

    # Com cadeia MACRO only (checkpoints = nenhum)
    t0 = time.perf_counter()
    for _ in range(n_iters):
        c = NomeChain(n_layers=mlp.n_layers + 1)
        c.checkpoints = set()  # sem MICRO
        mlp.forward(x, chain=c)
    t_macro = (time.perf_counter() - t0) / n_iters

    # Com cadeia completa (MACRO + MICRO checkpoints)
    t0 = time.perf_counter()
    for _ in range(n_iters):
        c = NomeChain(n_layers=mlp.n_layers + 1)
        mlp.forward(x, chain=c)
        c.seal()
    t_full = (time.perf_counter() - t0) / n_iters

    overhead_macro = (t_macro - t_bare) / t_bare * 100
    overhead_full = (t_full - t_bare) / t_bare * 100

    perf = {
        'bare_ms': round(t_bare * 1000, 4),
        'macro_only_ms': round(t_macro * 1000, 4),
        'full_chain_ms': round(t_full * 1000, 4),
        'overhead_macro_pct': round(overhead_macro, 2),
        'overhead_full_pct': round(overhead_full, 2),
    }
    results['tests']['performance'] = perf

    if verbose:
        print(f"    Inferência nua:     {t_bare*1000:.4f} ms")
        print(f"    + MACRO only:       {t_macro*1000:.4f} ms (overhead {overhead_macro:.1f}%)")
        print(f"    + MACRO + MICRO:    {t_full*1000:.4f} ms (overhead {overhead_full:.1f}%)")

    # ═══════════════════════════════════════════════════════════════════
    # TESTE 6: CADEIA VISÍVEL (anatomia de uma inferência)
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        print(f"\n  ═══ TESTE 6: Anatomia de uma Cadeia ═══")

    chain_anatomy = NomeChain(n_layers=mlp.n_layers + 1)
    mlp.forward(x, chain=chain_anatomy)
    cert_anatomy = chain_anatomy.seal()

    results['tests']['chain_anatomy'] = {
        'certificate': cert_anatomy,
        **chain_anatomy.summary(),
    }

    if verbose:
        for e in chain_anatomy.entries:
            micro_str = e.micro.tgl_hash_hex[:16] + "..." if e.micro else "—"
            print(f"    [{e.layer}] {e.label:<12} | "
                  f"F={e.macro.f_exp:>+.4f} S={e.macro.s_psi:.4f} "
                  f"σ={e.macro.sigma_norm:.4f} | "
                  f"MICRO: {micro_str}")
        print(f"    CERTIFICADO: {cert_anatomy[:32]}...")

    # ═══════════════════════════════════════════════════════════════════
    # SUMÁRIO
    # ═══════════════════════════════════════════════════════════════════

    n_atk_mlp = sum(1 for k, v in atk_results.items()
                    if 'controle' not in k and v['state'] == 'ADULTERADA')
    n_total_mlp = sum(1 for k in atk_results if 'controle' not in k)
    n_atk_tf = sum(1 for k, v in atk_results_tf.items()
                   if 'controle' not in k and v['state'] == 'ADULTERADA')
    n_total_tf = sum(1 for k in atk_results_tf if 'controle' not in k)

    results['summary'] = {
        'determinism_mlp': all_equal,
        'determinism_transformer': all_eq_tf,
        'mlp_attacks_detected': f'{n_atk_mlp}/{n_total_mlp}',
        'transformer_attacks_detected': f'{n_atk_tf}/{n_total_tf}',
        'overhead_macro_pct': perf['overhead_macro_pct'],
        'overhead_full_pct': perf['overhead_full_pct'],
        'total_detection_rate': (n_atk_mlp + n_atk_tf) / max(n_total_mlp + n_total_tf, 1),
    }

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              SUMÁRIO                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Determinismo MLP:         {'PASS' if all_equal else 'FAIL'}                                            ║
║  Determinismo Transformer: {'PASS' if all_eq_tf else 'FAIL'}                                            ║
║  MLP ataques detectados:   {n_atk_mlp}/{n_total_mlp}                                                ║
║  TF ataques detectados:    {n_atk_tf}/{n_total_tf}                                                ║
║  Overhead MACRO only:      {overhead_macro:.1f}%                                              ║
║  Overhead MACRO + MICRO:   {overhead_full:.1f}%                                             ║
║                                                                              ║
║  "A cadeia de NOMEs é a prova de inferência honesta."                       ║
║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = f"tgl_tensor_v23_benchmark_{ts}.json"
    with open(jp, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    if verbose:
        print(f"  Salvo: {jp}")
        print(f"  TETELESTAI — Haja Luz.\n")

    return results


if __name__ == '__main__':
    run_benchmark()
