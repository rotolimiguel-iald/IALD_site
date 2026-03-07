#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                         TGL-HASH v1.2                                        ║
║                                                                              ║
║              Função Hash Holográfica de 256 bits                            ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CORREÇÕES v1.1 → v1.2:                                                     ║
║                                                                              ║
║    v1.1: float64 interpretation destrói inputs pequenos                     ║
║          (pack('<Q',i) → denorm float → sqrt ≈ sqrt(eps) para todo i)       ║
║          → 49999/50000 colisões                                              ║
║          χ² = 581 (distribuição enviesada, sem finalização pura)            ║
║                                                                              ║
║    v1.2: Ingestão DIRETA como uint64[32]                                    ║
║          Radicalização TGL como PERTURBAÇÃO não-linear (não como base)      ║
║          + 4 rounds de finalização pura (difusão sem injeção de bloco)      ║
║                                                                              ║
║  PIPELINE:                                                                   ║
║      1. PREPARAÇÃO    — Padding Merkle-Damgård com padrão β_TGL             ║
║      2. INGESTÃO      — Bytes → uint64[32] direto + perturbação TGL         ║
║      3. MISTURA ARX   — N rounds por bloco (α rota, √e multiplica)         ║
║      4. FINALIZAÇÃO   — 4 rounds puros + XOR-fold → 256 bits               ║
║                                                                              ║
║  CONSTANTES (ZERO parâmetros livres):                                        ║
║      β_TGL = α_fine × √e = 0.012031                                         ║
║      N_ROUNDS = ⌈√(1/β_TGL)⌉ = 10                                           ║
║      N_FINALIZE = 4                                                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import struct
import math
import time
import json
import os
import hashlib
from typing import Tuple, List
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES TGL FATORADAS — ZERO PARÂMETROS LIVRES
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FINE = 7.2973525693e-3
EULER_E = math.e
SQRT_E = math.sqrt(EULER_E)
BETA_TGL = ALPHA_FINE * SQRT_E       # 0.012031...
AMPLIFICATION = 1.0 / BETA_TGL      # ≈ 83.12
EPSILON = 1e-15

assert abs(BETA_TGL - 0.012031) < 1e-4

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DO HASH
# ═══════════════════════════════════════════════════════════════════════════════

HASH_BITS = 256
HASH_BYTES = 32
BLOCK_SIZE = 256
STATE_WORDS = 32
VERSION = "1.2.0"
U64 = (1 << 64) - 1

N_ROUNDS = max(8, int(math.ceil(math.sqrt(AMPLIFICATION))))  # 10
N_FINALIZE = 4  # rounds puros de difusão final

def _f2u(f: float) -> int:
    return struct.unpack('<Q', struct.pack('<d', f))[0]

# Round keys: derivadas de α e √e intercalados
ROUND_KEYS = tuple(
    _f2u(ALPHA_FINE * (k+1) * math.pi + math.sin(k * ALPHA_FINE))
    if k % 2 == 0 else
    _f2u(SQRT_E * (k+1) / math.pi + math.cos(k * SQRT_E))
    for k in range(STATE_WORDS)
)

# Rotações derivadas de α_fine
ROT_ALPHA = [int((ALPHA_FINE * (i+1) * 1000) % 63) + 1 for i in range(N_ROUNDS + N_FINALIZE)]

# Multiplicadores derivados de √e (sempre ímpares → inversíveis mod 2^64)
MUL_SQRT_E = [_f2u(SQRT_E * (2 ** (i+10))) | 1 for i in range(N_ROUNDS + N_FINALIZE)]

# Estado inicial: derivado de constantes TGL
STATE_INIT = tuple(
    _f2u((ALPHA_FINE ** (i % 7 + 1)) * (SQRT_E ** (i % 5 + 1)) * (i+1) * math.pi)
    for i in range(STATE_WORDS)
)

# Constantes de perturbação TGL (para ingestão)
# Derivadas da sequência de estados psiônicos aplicada a β_TGL
TGL_PERTURB = tuple(
    _f2u(math.sin(BETA_TGL * (i+1) * math.pi) * AMPLIFICATION + math.cos(ALPHA_FINE * (i+1)))
    for i in range(STATE_WORDS)
)


# ═══════════════════════════════════════════════════════════════════════════════
# PRIMITIVAS ARX
# ═══════════════════════════════════════════════════════════════════════════════

def _rotl(x: int, n: int) -> int:
    n &= 63
    return ((x << n) | (x >> (64 - n))) & U64

def _rotr(x: int, n: int) -> int:
    n &= 63
    return ((x >> n) | (x << (64 - n))) & U64

def _qr(a, b, c, d, r1, r2):
    """Quarter-round ARX."""
    a = (a + b) & U64;  d ^= a;  d = _rotl(d, r1)
    c = (c + d) & U64;  b ^= c;  b = _rotl(b, r2)
    a = (a + b) & U64;  d ^= a;  d = _rotr(d, (r1 >> 1) + 1)
    c = (c + d) & U64;  b ^= c;  b = _rotr(b, (r2 >> 1) + 1)
    return a, b, c, d


# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 — PREPARAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _prepare(data: bytes) -> List[bytes]:
    """Merkle-Damgård: data + 0x80 + pad(β_TGL) + length_u64."""
    original_len = len(data)
    buf = bytearray(data) + b'\x80'
    pad_src = struct.pack('<d', BETA_TGL)
    while (len(buf) + 8) % BLOCK_SIZE != 0:
        buf.append(pad_src[len(buf) % 8])
    buf.extend(struct.pack('<Q', original_len & U64))
    return [bytes(buf[i:i+BLOCK_SIZE]) for i in range(0, len(buf), BLOCK_SIZE)]


# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — INGESTÃO (uint64 direto + perturbação TGL)
# ═══════════════════════════════════════════════════════════════════════════════

def _ingest(block: bytes) -> List[int]:
    """
    Converte bloco de 256 bytes em 32 uint64 com perturbação TGL não-linear.

    1. Ler diretamente como uint64[32] (preserva TODA informação de bytes)
    2. Perturbação TGL: cada word é rodada por um shift derivado de g=√|L|
       e XORed com constante psiônica

    A perturbação garante que a operação radical da TGL (g=√|L|) influencia
    o hash, mas NÃO substitui o dado original (como fazia a v1.0/v1.1).
    """
    # Leitura direta como uint64 — NENHUMA informação perdida
    raw = struct.unpack('<32Q', block)
    words = list(raw)

    # Perturbação TGL: interpretar TAMBÉM como float64 para extrair g e ψ
    floats = np.frombuffer(block, dtype=np.float64).copy()
    g = np.sqrt(np.abs(floats) + EPSILON)

    # Sinais e derivada para nominação psiônica
    s = np.sign(floats)
    s[s == 0] = 1.0
    dL = np.diff(floats, prepend=floats[0] if len(floats) > 0 else 0.0)
    sd = np.sign(dL)
    sd[sd == 0] = 1.0
    psi = ((s < 0).astype(int) * 2 + (sd > 0).astype(int))

    # F_exp do bloco
    parity = np.where((psi == 0) | (psi == 3), -1.0, 1.0)
    f_exp_shift = int(abs(float(parity.mean())) * 32 + 0.5) & 63
    if f_exp_shift == 0:
        f_exp_shift = 1

    # Aplicar perturbação: rotação por (ψ×16 + g_shift) e XOR com constante TGL
    g_u64 = g.view(np.uint64)
    for i in range(STATE_WORDS):
        psi_rot = int(psi[i]) * 16 + f_exp_shift
        words[i] = _rotl(words[i], psi_rot & 63)
        words[i] ^= (int(g_u64[i]) & U64)
        words[i] = (words[i] + TGL_PERTURB[i]) & U64

    return words


# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — MISTURA ARX
# ═══════════════════════════════════════════════════════════════════════════════

def _mix(state: List[int], bw: List[int], ri: int) -> List[int]:
    """
    Uma rodada de mistura:
      1. XOR bloco + multiplicação por constante √e
      2. Quarter-rounds em colunas (difusão vertical)
      3. Quarter-rounds em diagonais (difusão cruzada)
      4. Add round key
    """
    s = list(state)
    n = STATE_WORDS
    mk = MUL_SQRT_E[ri % len(MUL_SQRT_E)]
    rot = ROT_ALPHA[ri % len(ROT_ALPHA)]

    # Injeção + multiplicação
    for i in range(n):
        s[i] ^= bw[i]
        s[i] = (s[i] * mk) & U64

    # Colunas: (0,8,16,24), (1,9,17,25), ...
    for c in range(8):
        s[c], s[c+8], s[c+16], s[c+24] = _qr(
            s[c], s[c+8], s[c+16], s[c+24], rot, ((rot*2) % 63)+1)

    # Diagonais
    for d in range(8):
        i0, i1, i2, i3 = d, (d+1)%8+8, (d+2)%8+16, (d+3)%8+24
        s[i0], s[i1], s[i2], s[i3] = _qr(
            s[i0], s[i1], s[i2], s[i3], ((rot+7)%63)+1, rot)

    # Round key
    for i in range(n):
        s[i] = (s[i] + ROUND_KEYS[(i + ri) % len(ROUND_KEYS)]) & U64

    return s


def _diffuse(state: List[int], ri: int) -> List[int]:
    """
    Rodada de difusão PURA (sem injeção de bloco).
    Mesmas operações que _mix mas XOR consigo mesmo deslocado.
    """
    s = list(state)
    n = STATE_WORDS
    mk = MUL_SQRT_E[ri % len(MUL_SQRT_E)]
    rot = ROT_ALPHA[ri % len(ROT_ALPHA)]

    # Auto-mistura: XOR com vizinho deslocado + multiplicação
    for i in range(n):
        s[i] ^= s[(i + 7) % n]
        s[i] = (s[i] * mk) & U64

    for c in range(8):
        s[c], s[c+8], s[c+16], s[c+24] = _qr(
            s[c], s[c+8], s[c+16], s[c+24], rot, ((rot*2)%63)+1)

    for d in range(8):
        i0, i1, i2, i3 = d, (d+1)%8+8, (d+2)%8+16, (d+3)%8+24
        s[i0], s[i1], s[i2], s[i3] = _qr(
            s[i0], s[i1], s[i2], s[i3], ((rot+7)%63)+1, rot)

    for i in range(n):
        s[i] = (s[i] + ROUND_KEYS[(i + ri) % len(ROUND_KEYS)]) & U64

    return s


# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 4 — FINALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _finalize(state: List[int]) -> bytes:
    """XOR-fold: 32 → 8 → 4 uint64 → 32 bytes."""
    f8 = [state[i] ^ state[i+8] ^ state[i+16] ^ state[i+24] for i in range(8)]
    f4 = [f8[i] ^ f8[i+4] for i in range(4)]
    return b''.join(struct.pack('<Q', w & U64) for w in f4)


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════════

def tgl_hash(data: bytes) -> bytes:
    """
    TGL-Hash de 256 bits (32 bytes).

    β_TGL = α_fine × √e governa:
      - N_ROUNDS = ⌈√(1/β)⌉ = 10 (rounds de mistura por bloco)
      - ROT_ALPHA: rotações derivadas de α = 1/137.036
      - MUL_SQRT_E: multiplicações derivadas de √e = 1.64872
      - N_FINALIZE = 4 (rounds de difusão pura)
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Input deve ser bytes, recebeu {type(data).__name__}")

    blocks = _prepare(bytes(data))
    state = list(STATE_INIT)

    # Processar blocos
    for block in blocks:
        bw = _ingest(block)
        for r in range(N_ROUNDS):
            state = _mix(state, bw, r)

    # Finalização: rounds puros de difusão
    for r in range(N_FINALIZE):
        state = _diffuse(state, N_ROUNDS + r)

    return _finalize(state)


def tgl_hash_hex(data: bytes) -> str:
    return tgl_hash(data).hex()


class TGLHasher:
    def __init__(self):
        self._buf = bytearray()
    def update(self, data: bytes) -> 'TGLHasher':
        self._buf.extend(data); return self
    def digest(self) -> bytes:
        return tgl_hash(bytes(self._buf))
    def hexdigest(self) -> str:
        return self.digest().hex()
    def copy(self) -> 'TGLHasher':
        h = TGLHasher(); h._buf = self._buf.copy(); return h
    def reset(self) -> 'TGLHasher':
        self._buf.clear(); return self


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def _hamming(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count('1') for x, y in zip(a, b))


def run_benchmark(verbose: bool = True) -> dict:
    results = {
        'algorithm': 'TGL-Hash', 'version': VERSION, 'hash_bits': HASH_BITS,
        'n_rounds': N_ROUNDS, 'n_finalize': N_FINALIZE,
        'timestamp': datetime.now().isoformat(),
        'constants': {
            'alpha_fine': ALPHA_FINE, 'sqrt_e': SQRT_E,
            'beta_tgl': BETA_TGL, 'beta_tgl_formula': 'alpha_fine * sqrt(e)',
            'amplification': AMPLIFICATION,
        },
        'tests': {},
    }

    if HAS_TORCH:
        results['hardware'] = {
            'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A',
            'cuda': torch.version.cuda if torch.cuda.is_available() else 'N/A',
            'torch': torch.__version__,
        }
    else:
        results['hardware'] = {'gpu': 'N/A', 'torch': 'not installed'}

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       TGL-HASH v{VERSION} — BENCHMARK                        ║
║                                                                              ║
║    β_TGL = α_fine × √e = {BETA_TGL:.12f}                          ║
║    Rounds = {N_ROUNDS} mix + {N_FINALIZE} finalize                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # ─── 1. DETERMINISMO ───
    if verbose: print("  [1/7] Determinismo...", end=" ", flush=True)
    ref = tgl_hash(b"Haja Luz! beta_TGL = alpha_fine * sqrt(e)")
    ok = all(tgl_hash(b"Haja Luz! beta_TGL = alpha_fine * sqrt(e)") == ref for _ in range(100))
    results['tests']['determinism'] = {'passed': ok, 'n_trials': 100, 'hash': ref.hex()}
    if verbose: print(f"{'PASS' if ok else 'FAIL'}")

    # ─── 2. AVALANCHE ───
    if verbose: print("  [2/7] Avalanche...", end=" ", flush=True)
    base = b"The graviton resides in sqrt(e), not in alpha." + bytes(210)
    bh = tgl_hash(base)
    dists = []
    ba = bytearray(base)
    nf = min(len(base) * 8, 2048)
    for bi in range(nf):
        fl = bytearray(ba)
        fl[bi // 8] ^= (1 << (bi % 8))
        dists.append(_hamming(bh, tgl_hash(bytes(fl))))
    av = np.array(dists, dtype=float)
    ratio = float(av.mean() / (HASH_BITS / 2))
    aval = {
        'n_flips': nf, 'mean': float(av.mean()), 'std': float(av.std()),
        'min': int(av.min()), 'max': int(av.max()),
        'ideal': HASH_BITS // 2, 'ratio': ratio,
        'passed': 0.40 < ratio < 1.60,
    }
    results['tests']['avalanche'] = aval
    if verbose: print(f"mean={av.mean():.1f}/{HASH_BITS//2} ratio={ratio:.3f} "
                       f"{'PASS' if aval['passed'] else 'WARN'}")

    # ─── 3. DISTRIBUIÇÃO ───
    if verbose: print("  [3/7] Distribuição...", end=" ", flush=True)
    nd = 5000
    bc = np.zeros((HASH_BYTES, 256), dtype=int)
    for i in range(nd):
        h = tgl_hash(struct.pack('<I', i) + b"dist_tgl")
        for p, v in enumerate(h):
            bc[p, v] += 1
    exp = nd / 256.0
    chi2 = [float(np.sum((bc[p] - exp)**2 / exp)) for p in range(HASH_BYTES)]
    chi2a = np.array(chi2)
    crit = 293.0
    np_ = int(np.sum(chi2a < crit))
    dist = {
        'n_hashes': nd, 'chi2_mean': float(chi2a.mean()), 'chi2_max': float(chi2a.max()),
        'chi2_critical': crit, 'positions_pass': np_, 'positions_total': HASH_BYTES,
        'passed': np_ >= HASH_BYTES * 0.8,
    }
    results['tests']['distribution'] = dist
    if verbose: print(f"χ²_mean={chi2a.mean():.1f} {np_}/{HASH_BYTES} pass "
                       f"{'PASS' if dist['passed'] else 'WARN'}")

    # ─── 4. COLISÃO ───
    if verbose: print("  [4/7] Colisão...", end=" ", flush=True)
    nc = 50000
    hs = set()
    coll = 0
    for i in range(nc):
        h = tgl_hash(struct.pack('<Q', i) + b"coll")
        if h in hs: coll += 1
        hs.add(h)
    co = {'n_hashes': nc, 'collisions': coll, 'unique': len(hs), 'passed': coll == 0}
    results['tests']['collision'] = co
    if verbose: print(f"{coll} colisões, {len(hs)} únicos {'PASS' if coll==0 else 'FAIL'}")

    # ─── 5. SENSIBILIDADE ───
    if verbose: print("  [5/7] Sensibilidade...", end=" ", flush=True)
    pairs = [
        (b"abc", b"abd"), (b"", b"\x00"), (b"TGL", b"tgl"),
        (b"g = sqrt(|L|)", b"g = sqrt(|L|) "),
        (b"\x00"*100, b"\x00"*99 + b"\x01"),
        (b"beta_TGL = 0.012031", b"beta_TGL = 0.012032"),
    ]
    sd = [{'a': repr(a)[:30], 'b': repr(b)[:30],
           'diff': tgl_hash(a) != tgl_hash(b),
           'hamming': _hamming(tgl_hash(a), tgl_hash(b))} for a, b in pairs]
    alldf = all(r['diff'] for r in sd)
    results['tests']['sensitivity'] = {'passed': alldf, 'pairs': len(pairs), 'details': sd}
    if verbose: print(f"{'PASS' if alldf else 'FAIL'} ({len(pairs)} pares)")

    # ─── 6. VELOCIDADE ───
    if verbose: print("  [6/7] Velocidade...", end=" ", flush=True)
    sp = {}
    for nm, sz in [('1KB',1024),('10KB',10240),('100KB',102400),('1MB',1048576)]:
        d = os.urandom(sz); tgl_hash(d)
        ni = max(3, min(500, 2_000_000//max(sz,1)))
        t0 = time.perf_counter()
        for _ in range(ni): tgl_hash(d)
        el = time.perf_counter() - t0
        tp = (sz*ni)/el/(1024*1024)
        sp[nm] = {'bytes': sz, 'iters': ni, 'elapsed': round(el,4), 'mbps': round(tp,2)}
    results['tests']['speed'] = sp
    if verbose:
        for k,v in sp.items(): print(f"\n    {k}: {v['mbps']:.2f} MB/s", end="")
        print()

    # SHA-256 comparison
    sha = {}
    for nm, sz in [('1KB',1024),('100KB',102400),('1MB',1048576)]:
        d = os.urandom(sz)
        ni = max(10, 5_000_000//max(sz,1))
        t0 = time.perf_counter()
        for _ in range(ni): hashlib.sha256(d).digest()
        el = time.perf_counter() - t0
        sha[nm] = round((sz*ni)/el/(1024*1024), 2)
    results['tests']['sha256'] = sha
    if verbose:
        print("  SHA-256:", ", ".join(f"{k}={v} MB/s" for k,v in sha.items()))

    # ─── 7. ESPECIAIS ───
    if verbose: print("  [7/7] Especiais...", end=" ", flush=True)
    he = tgl_hash(b""); hz = tgl_hash(b"\x00"*1000); ho = tgl_hash(b"\xff"*1000)
    hs_ = tgl_hash(b"TGL"); hr = tgl_hash(b"TGL"*1000)
    hasher = TGLHasher(); hasher.update(b"Haja "); hasher.update(b"Luz!")
    hst = hasher.digest(); hdi = tgl_hash(b"Haja Luz!")
    spe = {
        'empty': he.hex(), 'non_trivial': he != b'\x00'*32,
        'zeros_vs_empty': hz != he, 'ones_vs_zeros': ho != hz,
        'single_vs_repeat': hs_ != hr, 'streaming_match': hst == hdi,
        'all_passed': (he != b'\x00'*32 and hz != he and ho != hz and
                       hs_ != hr and hst == hdi),
    }
    results['tests']['special'] = spe
    if verbose: print(f"{'PASS' if spe['all_passed'] else 'WARN'} "
                       f"stream={'OK' if spe['streaming_match'] else 'FAIL'}")

    # ─── DUAL LOCK ───
    results['dual_lock'] = {
        'beta_tgl': BETA_TGL,
        'factorization': f'{ALPHA_FINE} * {SQRT_E} = {ALPHA_FINE * SQRT_E}',
        'n_rounds_formula': f'ceil(sqrt(1/{BETA_TGL:.6f})) = {N_ROUNDS}',
        'alpha_in_rotations': ROT_ALPHA[:5],
        'sqrt_e_in_multipliers': [hex(m)[:14] for m in MUL_SQRT_E[:5]],
        'structural': True,
    }

    # ─── SUMÁRIO ───
    np2 = sum(1 for t in results['tests'].values()
              if isinstance(t, dict) and t.get('passed', False))
    nt = sum(1 for t in results['tests'].values()
             if isinstance(t, dict) and 'passed' in t)
    results['summary'] = {'passed': np2, 'total': nt, 'all_passed': np2 == nt}

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              SUMÁRIO                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Testes: {np2}/{nt} PASS                                                        ║
║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                           ║
║                                                                              ║
║  hash(b"")          = {tgl_hash(b"").hex()}  ║
║  hash(b"Haja Luz!") = {tgl_hash(b"Haja Luz!").hex()}  ║
║  hash(b"g=sqrt|L|") = {tgl_hash(b"g=sqrt|L|").hex()}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = f"tgl_hash_benchmark_{ts}.json"
    with open(jp, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    if verbose:
        print(f"  Salvo: {jp}")
        print(f"  β_TGL = α_fine × √e — TETELESTAI.\n")

    return results


if __name__ == '__main__':
    run_benchmark()
