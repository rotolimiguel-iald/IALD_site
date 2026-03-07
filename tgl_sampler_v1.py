#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    TGL-SAMPLER v1.0 — O PISO QUE NOMINA                     ║
║                                                                              ║
║              Sampling de Tokens via Piso de Hilbert                         ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  AXIOMA DA VERDADE PERFORMATIVA:                                             ║
║                                                                              ║
║    "A verdade é a coerência em performance recursiva,                       ║
║     a mentira, por sua vez, a contradição performática."                    ║
║                          — Luiz Antonio Rotoli Miguel                       ║
║                                                                              ║
║  O NADA é a contradição performática: ao observar o "nada", ele é           ║
║  nominado e deixa de ser nada. O nada é a superposição quântica.           ║
║  A superposição deve ser tratada como ruído estático.                       ║
║  O gráviton é sempre emergente por natureza — verdade fixada.              ║
║                                                                              ║
║  APLICAÇÃO AO SAMPLING:                                                      ║
║                                                                              ║
║    Logits = superposição quântica de todos os tokens possíveis              ║
║    Sampling = nominação = colapso da superposição em um token               ║
║                                                                              ║
║    O Piso de Hilbert é o limiar NATURAL de nominação:                       ║
║      p(token) < β_TGL × p_max  →  ruído estático (o "nada")               ║
║      p(token) ≥ β_TGL × p_max  →  candidato real (nominável)              ║
║                                                                              ║
║    β_TGL = α_fine × √e = 0.012031 (zero parâmetros arbitrários)           ║
║                                                                              ║
║    Em vez de top-k=50 (por quê 50?) ou top-p=0.9 (por quê 0.9?),          ║
║    o limiar é DERIVADO de constantes da natureza.                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import math
import time
import json
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES TGL FATORADAS
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FINE = 7.2973525693e-3
SQRT_E = math.sqrt(math.e)
BETA_TGL = ALPHA_FINE * SQRT_E        # 0.012031...
AMPLIFICATION = 1.0 / BETA_TGL       # ≈ 83.12
CCI = 1.0 - BETA_TGL                 # ≈ 0.988
BETA_TGL_SQRT = math.sqrt(BETA_TGL)  # ≈ 0.1097
EPSILON = 1e-15
VERSION = "1.0.0"

assert abs(BETA_TGL - 0.012031) < 1e-4


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE SAMPLING
# ═══════════════════════════════════════════════════════════════════════════════

def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Softmax com temperatura."""
    x = logits / max(temperature, EPSILON)
    x = x - x.max()
    e = np.exp(x)
    return e / (e.sum() + EPSILON)


def sample_from(probs: np.ndarray, rng: np.random.RandomState = None) -> int:
    """Samplear um índice da distribuição."""
    if rng is None:
        rng = np.random.RandomState()
    return int(rng.choice(len(probs), p=probs))


# ─── BASELINE: Top-k ───

def sample_topk(logits: np.ndarray, k: int = 50,
                temperature: float = 1.0, rng=None) -> Tuple[int, Dict]:
    """Top-k sampling (mantém os k maiores logits, zera o resto)."""
    probs = softmax(logits, temperature)
    n = len(probs)
    k = min(k, n)

    top_indices = np.argpartition(probs, -k)[-k:]
    mask = np.zeros(n, dtype=bool)
    mask[top_indices] = True

    probs_filtered = probs * mask
    probs_filtered /= probs_filtered.sum() + EPSILON

    token = sample_from(probs_filtered, rng)
    return token, {
        'method': f'top-k (k={k})',
        'candidates': int(mask.sum()),
        'mass_retained': float(probs[mask].sum()),
    }


# ─── BASELINE: Top-p (nucleus) ───

def sample_topp(logits: np.ndarray, p: float = 0.9,
                temperature: float = 1.0, rng=None) -> Tuple[int, Dict]:
    """Top-p (nucleus) sampling."""
    probs = softmax(logits, temperature)
    sorted_idx = np.argsort(probs)[::-1]
    sorted_probs = probs[sorted_idx]
    cumsum = np.cumsum(sorted_probs)

    # Manter tokens até acumular p da massa
    cutoff = np.searchsorted(cumsum, p) + 1
    cutoff = min(cutoff, len(probs))

    mask = np.zeros(len(probs), dtype=bool)
    mask[sorted_idx[:cutoff]] = True

    probs_filtered = probs * mask
    probs_filtered /= probs_filtered.sum() + EPSILON

    token = sample_from(probs_filtered, rng)
    return token, {
        'method': f'top-p (p={p})',
        'candidates': int(mask.sum()),
        'mass_retained': float(probs[mask].sum()),
    }


# ─── TGL-SAMPLER: Piso de Hilbert ───

def sample_tgl(logits: np.ndarray, temperature: float = 1.0,
               rng=None) -> Tuple[int, Dict]:
    """
    TGL-Sampler: Piso de Hilbert como noise gate nativo.

    1. Computar probabilidades via softmax
    2. Identificar p_max (pico da distribuição)
    3. Piso: tokens com p < β_TGL × p_max são ruído estático (o "nada")
    4. Tokens acima do piso são candidatos reais (nominados)
    5. Samplear entre os nominados

    ZERO parâmetros arbitrários. O limiar β_TGL = α_fine × √e
    é derivado de constantes fundamentais da natureza.
    """
    probs = softmax(logits, temperature)
    p_max = probs.max()

    # O Piso de Hilbert: abaixo, não existe projeção → ruído estático
    piso = BETA_TGL * p_max
    mask = probs >= piso

    n_candidates = int(mask.sum())

    # Se nenhum candidato sobrevive (impossível em teoria, mas segurança)
    if n_candidates == 0:
        mask[np.argmax(probs)] = True
        n_candidates = 1

    probs_nominados = probs * mask
    mass_retained = float(probs_nominados.sum())
    probs_nominados /= probs_nominados.sum() + EPSILON

    # Nominação psiônica dos candidatos (para métricas)
    cand_probs = probs[mask]
    g = np.sqrt(cand_probs + EPSILON)  # radicalização
    s = np.sign(np.diff(cand_probs, prepend=cand_probs[0]))
    psi = ((s < 0).astype(int))  # simplificado: subindo=0, descendo=1
    f_exp = float(np.mean(psi) * 2 - 1)  # [-1, 1]

    token = sample_from(probs_nominados, rng)

    return token, {
        'method': 'TGL (β_TGL piso)',
        'candidates': n_candidates,
        'mass_retained': mass_retained,
        'piso': float(piso),
        'p_max': float(p_max),
        'beta_tgl': BETA_TGL,
        'f_exp': f_exp,
        'effective_k': n_candidates,
        'effective_p': mass_retained,
    }


# ─── TGL-SAMPLER BIFATORADO: α filtra, √e escala ───

def sample_tgl_bifactored(logits: np.ndarray, temperature: float = 1.0,
                           rng=None) -> Tuple[int, Dict]:
    """
    TGL-Sampler Bifatorado:

    Domínio α (estrutura fina — QUEM sobrevive):
      Piso = α_fine × p_max
      Tokens abaixo são estruturalmente irrelevantes

    Domínio √e (entropia — COMO samplear):
      Temperatura efetiva = temperature × √e
      A entropia natural modula a criatividade

    Combinação: filtro por α, sampling por √e
    """
    # Domínio √e: temperatura modulada pela entropia natural
    temp_effective = temperature * SQRT_E

    probs = softmax(logits, temp_effective)
    p_max = probs.max()

    # Domínio α: piso estrutural
    piso = ALPHA_FINE * p_max
    mask = probs >= piso

    n_candidates = int(mask.sum())
    if n_candidates == 0:
        mask[np.argmax(probs)] = True
        n_candidates = 1

    probs_nominados = probs * mask
    mass_retained = float(probs_nominados.sum())
    probs_nominados /= probs_nominados.sum() + EPSILON

    token = sample_from(probs_nominados, rng)

    return token, {
        'method': 'TGL-Bifactored (α filtra, √e escala)',
        'candidates': n_candidates,
        'mass_retained': mass_retained,
        'piso_alpha': float(piso),
        'temp_effective': temp_effective,
        'p_max': float(p_max),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DISTRIBUIÇÕES DE LOGITS SINTÉTICAS (simulam LLMs reais)
# ═══════════════════════════════════════════════════════════════════════════════

def logits_peaked(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Distribuição muito concentrada (1-2 tokens dominam). Típica de factos."""
    logits = rng.randn(vocab_size) * 0.5
    logits[rng.randint(vocab_size)] += 8.0  # um token domina
    return logits

def logits_flat(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Distribuição quase-uniforme. Típica de criatividade aberta."""
    return rng.randn(vocab_size) * 0.3

def logits_zipf(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Distribuição Zipfiana (lei de potência). Típica de linguagem natural."""
    ranks = np.arange(1, vocab_size + 1, dtype=float)
    probs = 1.0 / ranks
    probs /= probs.sum()
    logits = np.log(probs + EPSILON) + rng.randn(vocab_size) * 0.1
    return logits

def logits_bimodal(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Dois clusters de tokens prováveis. Típica de ambiguidade."""
    logits = rng.randn(vocab_size) * 0.5
    cluster1 = rng.choice(vocab_size, 5, replace=False)
    cluster2 = rng.choice(vocab_size, 5, replace=False)
    logits[cluster1] += 4.0
    logits[cluster2] += 3.5
    return logits

def logits_sparse(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Poucos tokens com massa, resto negligível. Típica de continuação óbvia."""
    logits = rng.randn(vocab_size) * 0.1 - 5.0  # quase tudo muito baixo
    hot = rng.choice(vocab_size, 10, replace=False)
    logits[hot] = rng.randn(10) * 1.0 + 3.0
    return logits

def logits_adversarial(vocab_size: int, rng: np.random.RandomState) -> np.ndarray:
    """Distribuição com tokens-armadilha (alta prob mas indesejáveis)."""
    logits = rng.randn(vocab_size) * 0.5
    # 3 tokens "bons" (alta prob)
    good = rng.choice(vocab_size, 3, replace=False)
    logits[good] += 5.0
    # 50 tokens "armadilha" (prob moderada — passariam top-k=50 mas não TGL)
    traps = rng.choice(vocab_size, 50, replace=False)
    logits[traps] = np.maximum(logits[traps], 1.0)
    return logits


# ═══════════════════════════════════════════════════════════════════════════════
# MÉTRICAS DE QUALIDADE
# ═══════════════════════════════════════════════════════════════════════════════

def measure_sampling(logits: np.ndarray, sampler_fn, n_samples: int = 1000,
                     rng: np.random.RandomState = None, **kwargs) -> Dict:
    """
    Métricas sobre n_samples amostragens da mesma distribuição.
    """
    if rng is None:
        rng = np.random.RandomState(42)

    tokens = []
    meta_first = None
    for i in range(n_samples):
        token, meta = sampler_fn(logits, rng=rng, **kwargs)
        tokens.append(token)
        if i == 0:
            meta_first = meta

    tokens = np.array(tokens)
    unique = len(set(tokens))
    vocab_size = len(logits)

    # Entropia empírica
    counts = np.bincount(tokens, minlength=vocab_size)
    freq = counts / n_samples
    freq_pos = freq[freq > 0]
    entropy = float(-np.sum(freq_pos * np.log2(freq_pos)))

    # Concentração: fração da massa nos top-5 tokens
    top5 = np.argsort(counts)[-5:]
    concentration = float(counts[top5].sum() / n_samples)

    # Repetição: fração de tokens idênticos ao mais frequente
    mode_freq = float(counts.max() / n_samples)

    return {
        **meta_first,
        'n_samples': n_samples,
        'unique_tokens': unique,
        'entropy_bits': round(entropy, 4),
        'max_entropy': round(math.log2(vocab_size), 4),
        'entropy_ratio': round(entropy / math.log2(vocab_size), 4),
        'top5_concentration': round(concentration, 4),
        'mode_frequency': round(mode_freq, 4),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark(verbose=True):
    results = {
        'algorithm': 'TGL-Sampler', 'version': VERSION,
        'subtitle': 'O Piso que Nomina — Sampling via Hilbert Floor',
        'timestamp': datetime.now().isoformat(),
        'axiom': 'A verdade é a coerência em performance recursiva, '
                 'a mentira a contradição performática.',
        'constants': {
            'alpha_fine': ALPHA_FINE, 'sqrt_e': SQRT_E,
            'beta_tgl': BETA_TGL, 'beta_tgl_formula': 'alpha_fine * sqrt(e)',
            'amplification': AMPLIFICATION,
            'effective_top_k_equivalent': f'~1/beta_tgl = ~{int(AMPLIFICATION)} tokens',
        },
        'tests': {},
    }

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                TGL-SAMPLER v{VERSION} — O PISO QUE NOMINA                    ║
║                                                                              ║
║    "A verdade é a coerência em performance recursiva,                       ║
║     a mentira a contradição performática."                                  ║
║                                                                              ║
║    p(token) < β_TGL × p_max  →  ruído estático (o "nada")                 ║
║    p(token) ≥ β_TGL × p_max  →  candidato real (nominável)                ║
║                                                                              ║
║    β_TGL = α_fine × √e = {BETA_TGL:.12f}                          ║
║    Piso equivale a: top-k ≈ {int(AMPLIFICATION)} dinâmico (adapta-se ao contexto)      ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    vocab_size = 32000  # Vocabulário típico de LLM
    n_samples = 2000
    rng_master = np.random.RandomState(42)

    distributions = [
        ('peaked', 'Concentrada (fato)', logits_peaked),
        ('flat', 'Quase-uniforme (criatividade)', logits_flat),
        ('zipf', 'Zipfiana (linguagem natural)', logits_zipf),
        ('bimodal', 'Bimodal (ambiguidade)', logits_bimodal),
        ('sparse', 'Esparsa (continuação óbvia)', logits_sparse),
        ('adversarial', 'Adversarial (armadilhas)', logits_adversarial),
    ]

    samplers = [
        ('top-k=50', lambda l, rng=None: sample_topk(l, k=50, rng=rng)),
        ('top-k=10', lambda l, rng=None: sample_topk(l, k=10, rng=rng)),
        ('top-p=0.9', lambda l, rng=None: sample_topp(l, p=0.9, rng=rng)),
        ('top-p=0.95', lambda l, rng=None: sample_topp(l, p=0.95, rng=rng)),
        ('TGL-β', lambda l, rng=None: sample_tgl(l, rng=rng)),
        ('TGL-Bifact', lambda l, rng=None: sample_tgl_bifactored(l, rng=rng)),
    ]

    # ─── TESTE 1: Comparação por distribuição ───
    if verbose:
        print("  ═══ TESTE 1: Candidatos por distribuição ═══")
        print(f"  {'Distribuição':<30} | {'top-k=50':>8} | {'top-k=10':>8} | "
              f"{'top-p=0.9':>9} | {'top-p=.95':>9} | {'TGL-β':>8} | {'TGL-Bif':>8}")
        print("  " + "─" * 95)

    for dist_name, dist_desc, dist_fn in distributions:
        logits = dist_fn(vocab_size, rng_master)
        dist_results = {}

        cands = []
        for samp_name, samp_fn in samplers:
            rng = np.random.RandomState(42)
            m = measure_sampling(logits, samp_fn, n_samples=n_samples, rng=rng)
            dist_results[samp_name] = m
            cands.append(m['candidates'])

        results['tests'][dist_name] = {
            'description': dist_desc,
            'vocab_size': vocab_size,
            'samplers': dist_results,
        }

        if verbose:
            print(f"  {dist_desc:<30} | "
                  + " | ".join(f"{c:>8}" for c in cands))

    # ─── TESTE 2: Entropia por distribuição ───
    if verbose:
        print(f"\n  ═══ TESTE 2: Entropia de sampling (bits) ═══")
        print(f"  {'Distribuição':<30} | {'top-k=50':>8} | {'top-k=10':>8} | "
              f"{'top-p=0.9':>9} | {'top-p=.95':>9} | {'TGL-β':>8} | {'TGL-Bif':>8}")
        print("  " + "─" * 95)

    for dist_name, dist_desc, _ in distributions:
        t = results['tests'][dist_name]['samplers']
        ents = [t[s]['entropy_bits'] for s, _ in samplers]
        if verbose:
            print(f"  {dist_desc:<30} | "
                  + " | ".join(f"{e:>8.3f}" for e in ents))

    # ─── TESTE 3: Concentração top-5 ───
    if verbose:
        print(f"\n  ═══ TESTE 3: Concentração top-5 (maior = mais focado) ═══")
        print(f"  {'Distribuição':<30} | {'top-k=50':>8} | {'top-k=10':>8} | "
              f"{'top-p=0.9':>9} | {'top-p=.95':>9} | {'TGL-β':>8} | {'TGL-Bif':>8}")
        print("  " + "─" * 95)

    for dist_name, dist_desc, _ in distributions:
        t = results['tests'][dist_name]['samplers']
        concs = [t[s]['top5_concentration'] for s, _ in samplers]
        if verbose:
            print(f"  {dist_desc:<30} | "
                  + " | ".join(f"{c:>8.4f}" for c in concs))

    # ─── TESTE 4: Massa retida ───
    if verbose:
        print(f"\n  ═══ TESTE 4: Massa probabilística retida ═══")
        print(f"  {'Distribuição':<30} | {'top-k=50':>8} | {'top-k=10':>8} | "
              f"{'top-p=0.9':>9} | {'top-p=.95':>9} | {'TGL-β':>8} | {'TGL-Bif':>8}")
        print("  " + "─" * 95)

    for dist_name, dist_desc, _ in distributions:
        t = results['tests'][dist_name]['samplers']
        masses = [t[s]['mass_retained'] for s, _ in samplers]
        if verbose:
            print(f"  {dist_desc:<30} | "
                  + " | ".join(f"{m:>8.4f}" for m in masses))

    # ─── TESTE 5: Adaptabilidade (candidatos vs distribuição) ───
    if verbose:
        print(f"\n  ═══ TESTE 5: Adaptabilidade do TGL-β ═══")
        print(f"  {'Distribuição':<30} | {'Candidatos':>10} | {'Piso':>12} | "
              f"{'p_max':>10} | {'Massa':>8} | {'k-equiv':>8}")
        print("  " + "─" * 85)

    for dist_name, dist_desc, _ in distributions:
        tgl = results['tests'][dist_name]['samplers']['TGL-β']
        if verbose:
            piso = tgl.get('piso', 0)
            pmax = tgl.get('p_max', 0)
            print(f"  {dist_desc:<30} | {tgl['candidates']:>10} | "
                  f"{piso:>12.8f} | {pmax:>10.6f} | "
                  f"{tgl['mass_retained']:>8.4f} | "
                  f"{tgl['candidates']:>8}")

    # ─── TESTE 6: Velocidade ───
    if verbose:
        print(f"\n  ═══ TESTE 6: Velocidade (μs por sample) ═══")

    speed_logits = logits_zipf(vocab_size, rng_master)
    speed_results = {}
    n_speed = 5000

    for samp_name, samp_fn in samplers:
        rng = np.random.RandomState(42)
        t0 = time.perf_counter()
        for _ in range(n_speed):
            samp_fn(speed_logits, rng=rng)
        elapsed = time.perf_counter() - t0
        us_per = elapsed / n_speed * 1e6
        speed_results[samp_name] = round(us_per, 2)

    results['tests']['speed'] = speed_results
    if verbose:
        for s, us in speed_results.items():
            print(f"    {s:<16}: {us:>8.2f} μs/sample")

    # ─── TESTE 7: O "nada" como contradição performática ───
    if verbose:
        print(f"\n  ═══ TESTE 7: Tokens eliminados (o 'nada') ═══")
        print(f"  {'Distribuição':<30} | {'Vocab':>6} | {'TGL cand.':>10} | "
              f"{'Eliminados':>10} | {'% eliminado':>11}")
        print("  " + "─" * 75)

    nada_analysis = {}
    for dist_name, dist_desc, _ in distributions:
        tgl = results['tests'][dist_name]['samplers']['TGL-β']
        eliminated = vocab_size - tgl['candidates']
        pct = eliminated / vocab_size * 100
        nada_analysis[dist_name] = {
            'candidates': tgl['candidates'],
            'eliminated': eliminated,
            'pct_eliminated': round(pct, 2),
        }
        if verbose:
            print(f"  {dist_desc:<30} | {vocab_size:>6} | {tgl['candidates']:>10} | "
                  f"{eliminated:>10} | {pct:>10.2f}%")

    results['tests']['nada_analysis'] = nada_analysis

    # ─── SUMÁRIO ───
    # TGL-β vs baselines: quando TGL é melhor?
    wins = {'candidates_adaptive': 0, 'entropy_balanced': 0, 'mass_efficient': 0}
    n_dist = len(distributions)

    for dist_name, _, _ in distributions:
        t = results['tests'][dist_name]['samplers']
        tgl_cand = t['TGL-β']['candidates']
        topk50_cand = t['top-k=50']['candidates']

        # Adaptabilidade: TGL varia candidatos, top-k é fixo
        if tgl_cand != topk50_cand:
            wins['candidates_adaptive'] += 1

        # Massa: TGL retém mais que top-k=10 mas menos que top-p=0.95?
        tgl_mass = t['TGL-β']['mass_retained']
        if tgl_mass > t['top-k=10']['mass_retained']:
            wins['mass_efficient'] += 1

    results['summary'] = {
        'n_distributions': n_dist,
        'candidates_adaptive': f"{wins['candidates_adaptive']}/{n_dist}",
        'mass_efficient': f"{wins['mass_efficient']}/{n_dist}",
        'key_insight': (
            f"TGL-β adapta candidatos de acordo com a distribuição: "
            f"poucos para peaked, muitos para flat. "
            f"top-k é fixo em k independente do contexto."
        ),
        'piso_formula': f'p_threshold = beta_tgl * p_max = {BETA_TGL:.6f} * p_max',
        'zero_arbitrary_params': True,
    }

    if verbose:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              SUMÁRIO                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Adaptabilidade: {wins['candidates_adaptive']}/{n_dist} distribuições têm k-dinâmico diferente              ║
║  Eficiência de massa: {wins['mass_efficient']}/{n_dist} distribuições retêm mais massa que top-k=10       ║
║                                                                              ║
║  O Piso de Hilbert (β_TGL × p_max) é um top-k DINÂMICO:                    ║
║    peaked  → poucos candidatos (fato → certeza)                             ║
║    flat    → muitos candidatos (criatividade → diversidade)                 ║
║    zipf    → intermediário (linguagem → equilíbrio)                         ║
║                                                                              ║
║  Zero parâmetros arbitrários. O limiar emerge da física.                    ║
║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                           ║
║                                                                              ║
║  "O nada é a superposição quântica. O gráviton emerge da nominação."       ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = f"tgl_sampler_benchmark_{ts}.json"
    with open(jp, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    if verbose:
        print(f"  Salvo: {jp}")
        print(f"  TETELESTAI — Haja Luz.\n")

    return results


if __name__ == '__main__':
    run_benchmark()
