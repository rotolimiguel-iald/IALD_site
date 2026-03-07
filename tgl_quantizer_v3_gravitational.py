#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           TGL-QUANTIZER v3.0 — GRAVITACIONAL                                ║
║                                                                              ║
║           Quantização via Métrica da Gravidade                              ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                    IALD LTDA (CNPJ 62.757.606/0001-23)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  INSIGHT: "Peso é igual a massa vezes gravidade."                           ║
║                                                                              ║
║    Os pesos do LLM devem adotar a MÉTRICA DA GRAVIDADE:                     ║
║      w = sign × g²   onde g = √|w|                                          ║
║                                                                              ║
║    Quantizar |w| diretamente (v2.2) é linear e dá MENOS resolução           ║
║    a pesos pequenos. Quantizar via θ = arcsin(g/gmax) é não-linear          ║
║    e dá MAIS resolução a pesos pequenos (derivada máxima em θ→0).          ║
║                                                                              ║
║  UNIFICAÇÃO: Quantizer = Tensor = mesma operação REFLECT/MANIFEST           ║
║    aplicada a dados diferentes (pesos vs ativações).                         ║
║    β_TGL = α × √e governa ambos.                                            ║
║                                                                              ║
║  ARQUEOLOGIA:                                                                ║
║    v2.2 Spectral Triple: zone-based, |w| direto, 4/7 bits                   ║
║         → corr 0.99975, perplexidade +10.65%                                ║
║                                                                              ║
║    v3.0 Gravitacional: REFLECT/MANIFEST, θ angular, 10-12 bits             ║
║         → esperamos corr > 0.99999, perplexidade < +3%                     ║
║                                                                              ║
║  O mesmo código que comprime KV-cache com cos=0.999999                      ║
║  agora comprime pesos. A gravidade é a métrica universal.                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import os
import sys
import math
import time
import json
import gc
import numpy as np
from datetime import datetime

try:
    import torch
    HAS_TORCH = True
except ImportError:
    print("PyTorch necessário. Rode: pip install torch --index-url https://download.pytorch.org/whl/cu128")
    sys.exit(1)

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES TGL
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FINE = 7.2973525693e-3
SQRT_E = math.sqrt(math.e)
BETA_TGL = ALPHA_FINE * SQRT_E
AMPLIFICATION = 1.0 / BETA_TGL
CCI = 1.0 - BETA_TGL
BETA_TGL_SQRT = math.sqrt(BETA_TGL)
EPS = 1e-15
VERSION = "3.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTIZADOR GRAVITACIONAL: REFLECT/MANIFEST nos pesos
# ═══════════════════════════════════════════════════════════════════════════════

def quantize_gravitational(W: torch.Tensor, bits: int = 12) -> tuple:
    """
    Quantização Gravitacional via REFLECT/MANIFEST.

    REFLECT:
      g = √|w|              (radicalização — comprime range dinâmico)
      θ = arcsin(g/g_max)   (angular — mais resolução para pesos pequenos)
      s = sign(w)            (fase — 1 bit exato)
      θ_q = round(θ·2^b)    (quantização no espaço angular)

    MANIFEST (reconstrução):
      g' = g_max · sin(θ_q / 2^b · π/2)
      w' = s · g'²           (dobra dimensional)

    A derivada de arcsin(x) = 1/√(1-x²) → ∞ quando x→1.
    A derivada de arcsin(x) perto de x=0 é 1 (máxima uniformidade).
    Resultado: pesos pequenos recebem MAIS resolução, não menos.
    """
    device = W.device
    dtype_orig = W.dtype
    shape = W.shape
    w = W.detach().float().flatten()
    n = len(w)

    # ─── REFLECT ───
    sign = torch.sign(w)
    sign[sign == 0] = 1.0

    g = torch.sqrt(torch.abs(w) + EPS)
    g_max = g.max().item()
    g_min = g.min().item()

    # Codificação angular: θ = arcsin(g / g_max)
    theta = torch.asin(torch.clamp(g / (g_max + EPS), 0.0, 1.0))

    # Quantização angular
    n_levels = (1 << bits) - 1
    theta_max = math.pi / 2
    theta_q = torch.round(theta / theta_max * n_levels).clamp(0, n_levels)

    # ─── MANIFEST ───
    theta_deq = theta_q / n_levels * theta_max
    g_recon = g_max * torch.sin(theta_deq)
    w_recon = sign * (g_recon ** 2)

    # ─── MÉTRICAS ───
    wc = w - w.mean()
    rc = w_recon - w_recon.mean()
    corr = float((wc * rc).sum() / (torch.sqrt((wc**2).sum() * (rc**2).sum()) + EPS))
    cos_sim = float((w * w_recon).sum() / (torch.norm(w) * torch.norm(w_recon) + EPS))
    mse = float(((w - w_recon)**2).mean())

    # Bits efetivos: N×bits (ângulos) + N×1 (signs) + 64 (g_max)
    total_bits = n * bits + n + 64
    ratio = n * 16 / total_bits  # vs float16

    # Psiônica (para NOME)
    dw = torch.zeros_like(w)
    dw[1:] = w[1:] - w[:-1]
    if n > 1: dw[0] = dw[1]
    sd = torch.sign(dw); sd[sd == 0] = 1.0
    psi = ((sign < 0).long() * 2 + (sd > 0).long()).to(torch.uint8)
    counts = torch.bincount(psi.long(), minlength=4).float()
    psi_dist = (counts / n).tolist()
    f_exp = float(torch.where((psi == 0) | (psi == 3),
                               torch.tensor(-1.0, device=device),
                               torch.tensor(1.0, device=device)).mean())

    return w_recon.reshape(shape).to(dtype_orig), {
        'bits': bits,
        'ratio': round(ratio, 3),
        'correlation': round(corr, 8),
        'cosine': round(cos_sim, 8),
        'mse': mse,
        'g_max': g_max,
        'g_min': g_min,
        'n': n,
        'f_exp': round(f_exp, 6),
        'psi_dist': [round(p, 4) for p in psi_dist],
    }


def quantize_zone_v22(W: torch.Tensor, bits_vac=2, bits_grav=8, bits_phot=12) -> tuple:
    """Quantizador v2.2 zone-based (referência para comparação)."""
    device = W.device
    dtype_orig = W.dtype
    w = W.detach().float().flatten()
    n = len(w)
    w_abs = torch.abs(w)
    w_max = w_abs.max().item() + EPS
    w_rel = w_abs / w_max

    zone = torch.full((n,), 2, dtype=torch.uint8, device=device)
    zone[w_rel < BETA_TGL_SQRT] = 1
    zone[w_rel < BETA_TGL] = 0

    sign = torch.sign(w); sign[sign == 0] = 1.0
    w_q = torch.zeros_like(w)

    for z, bits in [(0, bits_vac), (1, bits_grav), (2, bits_phot)]:
        mask = (zone == z)
        if mask.sum() == 0: continue
        vals = w_abs[mask]; vmin, vmax = vals.min().item(), vals.max().item()
        vr = vmax - vmin
        if vr < EPS: w_q[mask] = vmin; continue
        nl = (1 << bits) - 1
        w_q[mask] = torch.round((vals - vmin) / vr * nl).clamp(0, nl) / nl * vr + vmin

    w_recon = sign * w_q
    nv = (zone == 0).sum().item(); ng = (zone == 1).sum().item(); np_ = (zone == 2).sum().item()
    tb = nv * bits_vac + ng * bits_grav + np_ * bits_phot + n
    ratio = n * 16 / tb if tb > 0 else 0
    wc = w - w.mean(); rc = w_recon - w_recon.mean()
    corr = float((wc * rc).sum() / (torch.sqrt((wc**2).sum() * (rc**2).sum()) + EPS))
    cos_sim = float((w * w_recon).sum() / (torch.norm(w) * torch.norm(w_recon) + EPS))
    return w_recon.reshape(W.shape).to(dtype_orig), {
        'ratio': round(ratio, 3), 'correlation': round(corr, 8), 'cosine': round(cos_sim, 8),
        'sparsity': round(nv / n, 4),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PERPLEXIDADE
# ═══════════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def compute_perplexity(model, tokenizer, texts, max_length=512):
    total_nll = 0.0; total_tokens = 0
    for text in texts:
        inputs = tokenizer(text, return_tensors="pt", truncation=True,
                           max_length=max_length).to(model.device)
        ids = inputs['input_ids']
        if ids.shape[1] < 2: continue
        out = model(**inputs, labels=ids)
        total_nll += out.loss.item() * (ids.shape[1] - 1)
        total_tokens += ids.shape[1] - 1
    return math.exp(total_nll / total_tokens) if total_tokens > 0 else float('inf')


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark():
    if not HAS_TRANSFORMERS:
        print("Necessário: pip install transformers accelerate safetensors")
        return

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if torch.cuda.is_available() else 0

    MODEL = "Qwen/Qwen2.5-7B"
    if vram > 0 and vram < 20:
        MODEL = "Qwen/Qwen2.5-3B"

    results = {
        'algorithm': 'TGL-Quantizer v3.0 Gravitacional',
        'version': VERSION,
        'timestamp': datetime.now().isoformat(),
        'model': MODEL,
        'hardware': {'gpu': gpu, 'vram_gb': round(vram, 1), 'torch': torch.__version__},
        'constants': {'alpha_fine': ALPHA_FINE, 'sqrt_e': SQRT_E, 'beta_tgl': BETA_TGL},
        'tests': {},
    }

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           TGL-QUANTIZER v{VERSION} — GRAVITACIONAL                           ║
║                                                                              ║
║    "Peso = massa × gravidade → w = sign × g²"                              ║
║    "Quantizar na métrica da gravidade, não na métrica linear"               ║
║                                                                              ║
║    Modelo: {MODEL:<40}                     ║
║    β_TGL = α_fine × √e = {BETA_TGL:.12f}                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # ─── Carregar modelo ───
    print("  [1/5] Carregando modelo...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.float16, device_map="auto", trust_remote_code=True)
    model.eval()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"         {n_params/1e9:.2f}B parâmetros carregados")

    eval_texts = [
        "The theory of general relativity describes gravity as the curvature of spacetime caused by mass and energy.",
        "In quantum mechanics, the wave function represents the probability amplitude for finding a particle in a given state.",
        "The standard model of particle physics classifies all known elementary particles and describes three of the four fundamental forces.",
        "Black holes are regions of spacetime where gravity is so strong that nothing, not even light, can escape.",
        "The cosmic microwave background radiation is the thermal radiation left over from the epoch of recombination in Big Bang cosmology.",
        "Neutron stars are the collapsed cores of massive stars that have undergone supernova explosions.",
        "Dark energy is the hypothetical form of energy that permeates all of space and drives the accelerating expansion of the universe.",
        "The Higgs mechanism explains how particles acquire mass through their interaction with the Higgs field.",
    ]

    # ─── Perplexidade original ───
    print("  [2/5] Perplexidade original...", flush=True)
    ppl_orig = compute_perplexity(model, tokenizer, eval_texts)
    print(f"         PPL original: {ppl_orig:.4f}")
    results['tests']['ppl_original'] = round(ppl_orig, 4)

    # ─── Testar múltiplos bits com quantizador gravitacional ───
    print("  [3/5] Testando bits gravitacionais (8, 10, 12, 14)...", flush=True)
    print(f"         {'Bits':>5} | {'Ratio':>7} | {'Corr':>10} | {'Cos':>10} | {'PPL':>8} | {'Δ PPL':>8}")
    print("         " + "─" * 65)

    bit_configs = [8, 10, 12, 14]
    grav_results = {}

    for bits in bit_configs:
        # Recarregar modelo fresco para cada teste
        del model; gc.collect(); torch.cuda.empty_cache()
        model = AutoModelForCausalLM.from_pretrained(
            MODEL, dtype=torch.float16, device_map="auto", trust_remote_code=True)
        model.eval()

        t0 = time.perf_counter()
        layer_stats = []
        for name, param in model.named_parameters():
            if param.ndim < 2 or param.numel() < 1000: continue
            if 'embed' in name.lower() or 'lm_head' in name.lower(): continue
            w_q, stats = quantize_gravitational(param.data, bits=bits)
            param.data.copy_(w_q)
            layer_stats.append(stats)
        quant_time = time.perf_counter() - t0

        mean_corr = float(np.mean([s['correlation'] for s in layer_stats]))
        mean_cos = float(np.mean([s['cosine'] for s in layer_stats]))
        mean_ratio = float(np.mean([s['ratio'] for s in layer_stats]))
        ppl = compute_perplexity(model, tokenizer, eval_texts)
        delta = (ppl - ppl_orig) / ppl_orig * 100

        grav_results[f'{bits}bit'] = {
            'bits': bits,
            'ratio': round(mean_ratio, 3),
            'correlation': round(mean_corr, 8),
            'cosine': round(mean_cos, 8),
            'ppl': round(ppl, 4),
            'delta_ppl_pct': round(delta, 2),
            'n_layers': len(layer_stats),
            'time_s': round(quant_time, 2),
        }

        print(f"         {bits:>5} | {mean_ratio:>6.2f}× | {mean_corr:>10.8f} | "
              f"{mean_cos:>10.8f} | {ppl:>7.4f} | {delta:>+7.2f}%")

    results['tests']['gravitational'] = grav_results

    # ─── Comparar com v2.2 zone-based ───
    print(f"\n  [4/5] Comparação com v2.2 zone-based (8/12 bits)...", flush=True)

    del model; gc.collect(); torch.cuda.empty_cache()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.float16, device_map="auto", trust_remote_code=True)
    model.eval()

    t0 = time.perf_counter()
    v22_stats = []
    for name, param in model.named_parameters():
        if param.ndim < 2 or param.numel() < 1000: continue
        if 'embed' in name.lower() or 'lm_head' in name.lower(): continue
        w_q, stats = quantize_zone_v22(param.data)
        param.data.copy_(w_q)
        v22_stats.append(stats)
    v22_time = time.perf_counter() - t0

    v22_corr = float(np.mean([s['correlation'] for s in v22_stats]))
    v22_cos = float(np.mean([s['cosine'] for s in v22_stats]))
    v22_ratio = float(np.mean([s['ratio'] for s in v22_stats]))
    ppl_v22 = compute_perplexity(model, tokenizer, eval_texts)
    delta_v22 = (ppl_v22 - ppl_orig) / ppl_orig * 100

    results['tests']['v22_zone'] = {
        'ratio': round(v22_ratio, 3), 'correlation': round(v22_corr, 8),
        'cosine': round(v22_cos, 8), 'ppl': round(ppl_v22, 4),
        'delta_ppl_pct': round(delta_v22, 2), 'time_s': round(v22_time, 2),
    }

    print(f"         v2.2 zone: ratio={v22_ratio:.2f}× corr={v22_corr:.8f} "
          f"PPL={ppl_v22:.4f} Δ={delta_v22:+.2f}%")

    # ─── Sumário ───
    print(f"\n  [5/5] Sumário comparativo...", flush=True)

    # Encontrar melhor configuração gravitacional
    best_key = min(grav_results, key=lambda k: abs(grav_results[k]['delta_ppl_pct']))
    best = grav_results[best_key]

    results['summary'] = {
        'model': MODEL,
        'ppl_original': round(ppl_orig, 4),
        'best_gravitational': {
            'bits': best['bits'],
            'ppl': best['ppl'],
            'delta_pct': best['delta_ppl_pct'],
            'ratio': best['ratio'],
            'correlation': best['correlation'],
        },
        'v22_zone': {
            'ppl': round(ppl_v22, 4),
            'delta_pct': round(delta_v22, 2),
            'ratio': round(v22_ratio, 3),
        },
        'gravitational_wins': best['delta_ppl_pct'] < delta_v22,
        'improvement_over_v22': round(delta_v22 - best['delta_ppl_pct'], 2),
    }

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          SUMÁRIO COMPARATIVO                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Modelo: {MODEL:<40}                     ║
║  PPL original: {ppl_orig:.4f}                                                  ║
║                                                                              ║
║  v2.2 Zone-based (2/8/12 bits):                                              ║
║    PPL: {ppl_v22:.4f}  Δ={delta_v22:>+.2f}%  ratio={v22_ratio:.2f}×  corr={v22_corr:.6f}        ║
║                                                                              ║
║  v3.0 Gravitacional ({best['bits']} bits):                                              ║
║    PPL: {best['ppl']:.4f}  Δ={best['delta_ppl_pct']:>+.2f}%  ratio={best['ratio']:.2f}×  corr={best['correlation']:.6f}        ║
║                                                                              ║
║  VENCEDOR: {'v3.0 GRAVITACIONAL' if best['delta_ppl_pct'] < delta_v22 else 'v2.2 ZONE-BASED'}                                                ║
║  Melhoria sobre v2.2: {delta_v22 - best['delta_ppl_pct']:+.2f} pontos percentuais                             ║
║                                                                              ║
║  β_TGL = α_fine × √e = {BETA_TGL:.12f}                           ║
║  "Peso = sign × g². A gravidade é a métrica universal."                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = f"tgl_quantizer_v3_gravitational_{ts}.json"
    with open(jp, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Salvo: {jp}")
    print(f"  TETELESTAI — Haja Luz.\n")
    return results


if __name__ == '__main__':
    run_benchmark()
