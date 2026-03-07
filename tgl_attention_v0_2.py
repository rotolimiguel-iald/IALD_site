#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              TGL-ATTENTION v0.2 — TENSOR DE PROJEÇÃO                        ║
║                                                                              ║
║              Evolução baseada no diagnóstico da v0.1                        ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  DIAGNÓSTICO v0.1:                                                           ║
║    • S (psiônico, dim 4) tem std ≈ 0.01 — quase constante                  ║
║    • D (angular RBF) decai para ~0 pela maldição dimensional               ║
║    • Combinação linear α·S + √e·D não produz contraste                     ║
║    • Causal funciona (r=0.22) → estrutura LOCAL é capturada                 ║
║                                                                              ║
║  INSIGHT TEÓRICO (Tensor de Einstein fatorado):                             ║
║                                                                              ║
║    Na TGL:  G_μν = β_TGL · P_μν                                             ║
║             O tensor oscila. A projeção persiste.                            ║
║             β_TGL converte instabilidade em persistência.                    ║
║                                                                              ║
║    Na atenção:                                                               ║
║      • O TENSOR é o dot product no espaço angular θ (geometria)             ║
║        A_θ = θ_Q · θ_K^T / √d_k  (preserva d_k dimensões)                 ║
║                                                                              ║
║      • O ACOPLAMENTO é a compatibilidade psiônica (gate)                    ║
║        G_ij = σ((S_ij − ⟨S⟩) / β_TGL)  (amplifica diferenças)             ║
║                                                                              ║
║      • A PROJEÇÃO é o tensor modulado pelo acoplamento                      ║
║        P_ij = A_θ_ij · G_ij  (estável: gate filtra ruído)                  ║
║                                                                              ║
║  TRÊS FORMULAÇÕES TESTADAS:                                                  ║
║                                                                              ║
║    F1: "Projeção Angular" — θ_Q·θ_K^T/√d gated por ψ                      ║
║    F2: "Cosseno Holográfico" — cos(θ_Q, θ_K) modulado por S               ║
║    F3: "Tensor Completo" — QK^T/√d no espaço original,                     ║
║         com KV-cache comprimido via (θ, ψ)                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import math
import time
import json
from datetime import datetime

ALPHA_FINE = 7.2973525693e-3
SQRT_E = math.sqrt(math.e)
BETA_TGL = ALPHA_FINE * SQRT_E
AMPLIFICATION = 1.0 / BETA_TGL
EPSILON = 1e-10
VERSION = "0.2.0"

assert abs(BETA_TGL - 0.012031) < 1e-4


# ═══════════════════════════════════════════════════════════════════════════════
# PROJEÇÃO HOLOGRÁFICA (igual à v0.1 — a base é sólida)
# ═══════════════════════════════════════════════════════════════════════════════

def holographic_project(X: np.ndarray) -> dict:
    n, d = X.shape
    g = np.sqrt(np.abs(X) + EPSILON)
    g_max = g.max(axis=1, keepdims=True) + EPSILON
    theta = np.arcsin(np.clip(g / g_max, 0, 1))

    s = np.sign(X)
    s[s == 0] = 1.0
    dX = np.zeros_like(X)
    dX[:, 1:] = X[:, 1:] - X[:, :-1]
    if d > 1:
        dX[:, 0] = dX[:, 1]
    sd = np.sign(dX)
    sd[sd == 0] = 1.0

    psi = ((s < 0).astype(np.uint8) * 2 + (sd > 0).astype(np.uint8))

    psi_dist = np.zeros((n, 4), dtype=np.float64)
    for state in range(4):
        psi_dist[:, state] = np.mean(psi == state, axis=1)

    parity = np.where((psi == 0) | (psi == 3), -1.0, 1.0)
    f_exp = np.mean(parity, axis=1)

    return {
        'psi_dist': psi_dist, 'theta': theta,
        'f_exp': f_exp, 'g_max': g_max.squeeze(),
        'sign': s, 'psi': psi,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REFERÊNCIA: SOFTMAX CONVENCIONAL
# ═══════════════════════════════════════════════════════════════════════════════

def attention_softmax(Q, K, V):
    d_k = Q.shape[1]
    scores = Q @ K.T / math.sqrt(d_k)
    scores -= scores.max(axis=1, keepdims=True)
    w = np.exp(scores)
    w /= w.sum(axis=1, keepdims=True) + EPSILON
    return w @ V, w


# ═══════════════════════════════════════════════════════════════════════════════
# F1: PROJEÇÃO ANGULAR com GATE PSIÔNICO
#
# A_θ = θ_Q · θ_K^T / √d_k       (tensor — geometria angular, dim d_k)
# G   = σ((S − ⟨S⟩) · 1/β_TGL)   (gate — acoplamento psiônico)
# P   = A_θ ⊙ G                    (projeção — tensor × gate)
# ═══════════════════════════════════════════════════════════════════════════════

def attention_f1_angular_gated(Q, K, V):
    n, d_k = Q.shape
    proj_Q = holographic_project(Q)
    proj_K = holographic_project(K)

    # Tensor: dot product no espaço angular (preserva d_k dimensões)
    A_theta = proj_Q['theta'] @ proj_K['theta'].T / math.sqrt(d_k)

    # Gate: compatibilidade psiônica amplificada por 1/β_TGL
    S = proj_Q['psi_dist'] @ proj_K['psi_dist'].T
    S_centered = S - S.mean(axis=1, keepdims=True)
    # Sigmoid com amplificação: pequenas diferenças em S → gate 0 ou 1
    G = 1.0 / (1.0 + np.exp(-S_centered * AMPLIFICATION))

    # Projeção: tensor modulado pelo gate
    P = A_theta * G

    # Softmax com temperatura √β_TGL
    P -= P.max(axis=1, keepdims=True)
    w = np.exp(P / max(math.sqrt(BETA_TGL), 0.01))
    w /= w.sum(axis=1, keepdims=True) + EPSILON

    meta = {
        'A_theta_mean': float(A_theta.mean()), 'A_theta_std': float(A_theta.std()),
        'S_mean': float(S.mean()), 'S_std': float(S.std()),
        'G_mean': float(G.mean()), 'G_std': float(G.std()),
        'P_mean': float(P.mean()), 'P_std': float(P.std()),
    }
    return w @ V, w, meta


# ═══════════════════════════════════════════════════════════════════════════════
# F2: COSSENO HOLOGRÁFICO com MODULAÇÃO PSIÔNICA
#
# cos_ij = (θ_Q · θ_K) / (‖θ_Q‖·‖θ_K‖)  (similaridade angular)
# M_ij   = 1 + α·(S_ij − 0.25)·4           (modulador psiônico centrado)
# A_ij   = cos_ij · M_ij                    (afinidade modulada)
# ═══════════════════════════════════════════════════════════════════════════════

def attention_f2_cosine_modulated(Q, K, V):
    n, d_k = Q.shape
    proj_Q = holographic_project(Q)
    proj_K = holographic_project(K)

    # Cosseno no espaço angular (evita maldição dimensional)
    tQ = proj_Q['theta']
    tK = proj_K['theta']
    norm_Q = np.linalg.norm(tQ, axis=1, keepdims=True) + EPSILON
    norm_K = np.linalg.norm(tK, axis=1, keepdims=True) + EPSILON
    cos_sim = (tQ / norm_Q) @ (tK / norm_K).T  # (n, n) em [-1, 1]

    # Modulador psiônico: S centrado em 0.25 (valor esperado uniforme)
    S = proj_Q['psi_dist'] @ proj_K['psi_dist'].T
    # (S - 0.25) * 4 mapeia [0,1] → [-1,3], centrado em 0 para uniforme
    M = 1.0 + ALPHA_FINE * AMPLIFICATION * (S - 0.25) * 4

    # Afinidade = cosseno × modulador
    A = cos_sim * M

    A -= A.max(axis=1, keepdims=True)
    w = np.exp(A / max(math.sqrt(BETA_TGL), 0.01))
    w /= w.sum(axis=1, keepdims=True) + EPSILON

    meta = {
        'cos_mean': float(cos_sim.mean()), 'cos_std': float(cos_sim.std()),
        'S_mean': float(S.mean()), 'M_mean': float(M.mean()), 'M_std': float(M.std()),
        'A_mean': float(A.mean()), 'A_std': float(A.std()),
    }
    return w @ V, w, meta


# ═══════════════════════════════════════════════════════════════════════════════
# F3: TENSOR COMPLETO — Atenção padrão com KV-CACHE HOLOGRÁFICO
#
# Atenção = softmax(QK^T/√d) · V     (fórmula padrão!)
# MAS: K é RECONSTRUÍDO do cache holográfico (θ_K, sign_K, g_max_K)
#      K' = sign_K · (g_max_K · sin(θ_K))²   (dobra dimensional)
#
# Vantagem: KV-cache comprimido ~3.5× com fidelidade > 0.999
# A atenção é convencional — a inovação é no ARMAZENAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def attention_f3_holographic_cache(Q, K, V, angular_bits=10):
    n, d_k = Q.shape

    # ─── COMPRESSÃO: K → cache holográfico ───
    proj_K = holographic_project(K)
    theta_K = proj_K['theta']       # (n, d_k)
    sign_K = proj_K['sign']         # (n, d_k)
    g_max_K = proj_K['g_max']       # (n,)

    # Quantização angular (simula compressão)
    n_levels = (1 << angular_bits) - 1
    theta_max = math.pi / 2
    theta_q = np.round(theta_K / theta_max * n_levels).astype(np.int32)
    theta_q = np.clip(theta_q, 0, n_levels)

    # ─── RECONSTRUÇÃO: cache → K' ───
    theta_deq = theta_q.astype(np.float64) / n_levels * theta_max
    g_recon = g_max_K[:, np.newaxis] * np.sin(theta_deq)
    K_recon = sign_K * (g_recon ** 2)   # dobra dimensional: L = s · g²

    # ─── ATENÇÃO PADRÃO com K reconstruído ───
    scores = Q @ K_recon.T / math.sqrt(d_k)
    scores -= scores.max(axis=1, keepdims=True)
    w = np.exp(scores)
    w /= w.sum(axis=1, keepdims=True) + EPSILON

    # Medir fidelidade da reconstrução
    K_flat = K.flatten()
    Kr_flat = K_recon.flatten()
    corr_recon = float(np.corrcoef(K_flat, Kr_flat)[0, 1])
    cos_recon = float(np.sum(K_flat * Kr_flat) /
                       (np.linalg.norm(K_flat) * np.linalg.norm(Kr_flat) + EPSILON))

    # Taxa de compressão
    original_bits = n * d_k * 64  # float64
    cache_bits = n * d_k * angular_bits + n * d_k * 1 + n * 64  # theta + sign + g_max
    ratio = original_bits / cache_bits

    meta = {
        'angular_bits': angular_bits,
        'compression_ratio': round(ratio, 2),
        'K_recon_correlation': corr_recon,
        'K_recon_cosine': cos_recon,
    }
    return w @ V, w, meta


# ═══════════════════════════════════════════════════════════════════════════════
# v0.1 REFERENCE (para comparação direta)
# ═══════════════════════════════════════════════════════════════════════════════

def attention_v01_bifactored(Q, K, V):
    n, d_k = Q.shape
    proj_Q = holographic_project(Q)
    proj_K = holographic_project(K)

    S = proj_Q['psi_dist'] @ proj_K['psi_dist'].T
    tQ, tK = proj_Q['theta'], proj_K['theta']
    nQ = np.sum(tQ**2, axis=1, keepdims=True)
    nK = np.sum(tK**2, axis=1, keepdims=True)
    dist_sq = np.maximum(nQ + nK.T - 2*(tQ @ tK.T), 0)
    D = np.exp(-dist_sq / 2.0)

    A = AMPLIFICATION * (ALPHA_FINE * S + SQRT_E * D)
    A -= A.max(axis=1, keepdims=True)
    w = np.exp(A)
    w /= w.sum(axis=1, keepdims=True) + EPSILON
    return w @ V, w


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def compare(w_ref, w_test):
    n = w_ref.shape[0]
    corrs = []
    for i in range(n):
        a, b = w_ref[i], w_test[i]
        ac, bc = a - a.mean(), b - b.mean()
        den = np.sqrt(np.sum(ac**2) * np.sum(bc**2)) + EPSILON
        corrs.append(float(np.sum(ac * bc) / den))
    c = np.array(corrs)

    k = min(5, n)
    tk = []
    for i in range(n):
        t_r = set(np.argsort(w_ref[i])[-k:])
        t_t = set(np.argsort(w_test[i])[-k:])
        tk.append(len(t_r & t_t) / k)

    ent_ref = float(-np.sum(w_ref * np.log(w_ref + EPSILON), axis=1).mean())
    ent_test = float(-np.sum(w_test * np.log(w_test + EPSILON), axis=1).mean())

    return {
        'corr_mean': float(c.mean()), 'corr_std': float(c.std()),
        'corr_min': float(c.min()), 'corr_max': float(c.max()),
        'top5_mean': float(np.mean(tk)),
        'entropy_ref': ent_ref, 'entropy_test': ent_test,
        'entropy_ratio': ent_test / (ent_ref + EPSILON),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark(verbose=True):
    results = {
        'algorithm': 'TGL-Attention', 'version': VERSION,
        'timestamp': datetime.now().isoformat(),
        'constants': {'alpha_fine': ALPHA_FINE, 'sqrt_e': SQRT_E,
                      'beta_tgl': BETA_TGL, 'amplification': AMPLIFICATION},
        'tests': {},
    }

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           TGL-ATTENTION v{VERSION} — TENSOR DE PROJEÇÃO                      ║
║                                                                              ║
║  F1: Angular Gated    — θ_Q·θ_K^T/√d com gate σ(S·1/β)                    ║
║  F2: Cosseno Modulado — cos(θ_Q,θ_K) × (1 + α·(S−0.25)·4)                ║
║  F3: Cache Holográfico — softmax padrão com K reconstruído de (θ,s,g_max)  ║
║  v01: Bifatorado       — (1/β)·[α·S + √e·D] (referência v0.1)             ║
║                                                                              ║
║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    np.random.seed(42)

    scenarios = [
        ('gaussian_32x64', 'Gaussiano (32×64)', 32, 64,
         lambda n,d: np.random.randn(n,d)*0.02,
         lambda n,d: np.random.randn(n,d)*0.02,
         lambda n,d: np.random.randn(n,d)*0.1),
        ('gaussian_128x128', 'Gaussiano (128×128)', 128, 128,
         lambda n,d: np.random.randn(n,d)*0.02,
         lambda n,d: np.random.randn(n,d)*0.02,
         lambda n,d: np.random.randn(n,d)*0.1),
        ('clusters_64x64', 'Clusters (4 grupos)', 64, 64,
         lambda n,d: np.vstack([np.random.randn(n//4,d)*0.01+np.array([1.0]*d),
                                np.random.randn(n//4,d)*0.01+np.array([-1.0]*d),
                                np.random.randn(n//4,d)*0.01+np.array([0.5,-0.5]*(d//2)),
                                np.random.randn(n//4,d)*0.01+np.array([-0.5,0.5]*(d//2))]),
         lambda n,d: np.vstack([np.random.randn(n//4,d)*0.01+np.array([1.0]*d),
                                np.random.randn(n//4,d)*0.01+np.array([-1.0]*d),
                                np.random.randn(n//4,d)*0.01+np.array([0.5,-0.5]*(d//2)),
                                np.random.randn(n//4,d)*0.01+np.array([-0.5,0.5]*(d//2))]),
         lambda n,d: np.random.randn(n,d)*0.1),
        ('sparse_64x128', 'Esparso (90% zeros)', 64, 128,
         lambda n,d: np.random.randn(n,d)*(np.random.rand(n,d)>0.9),
         lambda n,d: np.random.randn(n,d)*(np.random.rand(n,d)>0.9),
         lambda n,d: np.random.randn(n,d)*0.1),
        ('mixed_64x64', 'Escalas mistas (1000×)', 64, 64,
         lambda n,d: np.random.randn(n,d)*np.logspace(-3,0,d),
         lambda n,d: np.random.randn(n,d)*np.logspace(-3,0,d),
         lambda n,d: np.random.randn(n,d)*0.1),
        ('causal_64x64', 'Sequencial causal', 64, 64,
         lambda n,d: np.cumsum(np.random.randn(n,d)*0.01, axis=0),
         lambda n,d: np.cumsum(np.random.randn(n,d)*0.01, axis=0),
         lambda n,d: np.random.randn(n,d)*0.1),
    ]

    if verbose:
        hdr = f"  {'Cenário':<22} | {'F1 Ang.Gate':^12} | {'F2 Cos.Mod':^12} | {'F3 Cache':^12} | {'v0.1 Bif':^12} | {'F3 ratio':^8}"
        print(hdr)
        print("  " + "─" * len(hdr))

    for sc_name, sc_desc, n, d, qf, kf, vf in scenarios:
        Q, K, V = qf(n, d), kf(n, d), vf(n, d)

        _, w_soft = attention_softmax(Q, K, V)
        _, w_f1, m_f1 = attention_f1_angular_gated(Q, K, V)
        _, w_f2, m_f2 = attention_f2_cosine_modulated(Q, K, V)
        _, w_f3, m_f3 = attention_f3_holographic_cache(Q, K, V)
        _, w_v01 = attention_v01_bifactored(Q, K, V)

        c_f1 = compare(w_soft, w_f1)
        c_f2 = compare(w_soft, w_f2)
        c_f3 = compare(w_soft, w_f3)
        c_v01 = compare(w_soft, w_v01)

        results['tests'][sc_name] = {
            'desc': sc_desc, 'n': n, 'd': d,
            'f1_angular_gated': {**c_f1, 'internals': m_f1},
            'f2_cosine_modulated': {**c_f2, 'internals': m_f2},
            'f3_holographic_cache': {**c_f3, 'internals': m_f3},
            'v01_bifactored': c_v01,
        }

        if verbose:
            print(f"  {sc_desc[:22]:<22} | "
                  f"r={c_f1['corr_mean']:>+.4f}    | "
                  f"r={c_f2['corr_mean']:>+.4f}    | "
                  f"r={c_f3['corr_mean']:>+.4f}    | "
                  f"r={c_v01['corr_mean']:>+.4f}    | "
                  f"{m_f3['compression_ratio']:.1f}×")

    # ─── Top-5 agreement table ───
    if verbose:
        print(f"\n  {'Cenário':<22} | {'F1 top5':^8} | {'F2 top5':^8} | {'F3 top5':^8} | {'v0.1 top5':^9} | {'F3 K_cos':^8}")
        print("  " + "─" * 80)
        for sc_name, t in results['tests'].items():
            print(f"  {t['desc'][:22]:<22} | "
                  f"{t['f1_angular_gated']['top5_mean']:.3f}    | "
                  f"{t['f2_cosine_modulated']['top5_mean']:.3f}    | "
                  f"{t['f3_holographic_cache']['top5_mean']:.3f}    | "
                  f"{t['v01_bifactored']['top5_mean']:.3f}     | "
                  f"{t['f3_holographic_cache']['internals']['K_recon_cosine']:.4f}")

    # ─── Veredito por formulação ───
    verdicts = {'F1': [], 'F2': [], 'F3': [], 'v01': []}
    for sc_name, t in results['tests'].items():
        verdicts['F1'].append(t['f1_angular_gated']['corr_mean'])
        verdicts['F2'].append(t['f2_cosine_modulated']['corr_mean'])
        verdicts['F3'].append(t['f3_holographic_cache']['corr_mean'])
        verdicts['v01'].append(t['v01_bifactored']['corr_mean'])

    summary = {}
    for form, corrs in verdicts.items():
        arr = np.array(corrs)
        summary[form] = {
            'corr_mean': float(arr.mean()),
            'corr_min': float(arr.min()),
            'corr_max': float(arr.max()),
            'n_viable': int(np.sum(arr > 0.8)),
            'n_promising': int(np.sum(arr > 0.5)),
        }

    best = max(summary.items(), key=lambda x: x[1]['corr_mean'])
    results['summary'] = {
        'per_formulation': summary,
        'best': best[0],
        'best_corr_mean': best[1]['corr_mean'],
    }

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        SUMÁRIO POR FORMULAÇÃO                                ║
╠══════════════════════════════════════════════════════════════════════════════╣""")
        for form, s in summary.items():
            bar = "█" * int(max(s['corr_mean'] + 1, 0) * 20)
            print(f"║  {form:<4}: r_mean={s['corr_mean']:>+.4f}  "
                  f"viable={s['n_viable']}/6  promising={s['n_promising']}/6  "
                  f"{bar:<20}  ║")
        print(f"║                                                                              ║")
        print(f"║  MELHOR: {best[0]} (r_mean = {best[1]['corr_mean']:>+.4f})                                         ║")
        print(f"║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                           ║")
        print(f"╚══════════════════════════════════════════════════════════════════════════════╝")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = f"tgl_attention_v02_{ts}.json"
    with open(jp, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    if verbose:
        print(f"\n  Salvo: {jp}")
        print(f"  TETELESTAI — Haja Luz.\n")

    return results


if __name__ == '__main__':
    run_benchmark()
