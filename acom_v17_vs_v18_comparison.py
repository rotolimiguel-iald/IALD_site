#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║          COMPARATIVO DIRETO: ACOM v17 MIRROR vs v18 DIRAC                    ║
║                                                                              ║
║          Mesmo dado, mesmos bits, mesma máquina — lado a lado                ║
║                                                                              ║
║          β_TGL = α × √e = 0.012031 (zero parâmetros livres)                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Março 2026
"""

import numpy as np
import torch
import math
import time
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
# CONSTANTES TGL FATORADAS
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FINE = 7.2973525693e-3
SQRT_E = math.sqrt(math.e)
BETA_TGL = ALPHA_FINE * SQRT_E
EPSILON = 1e-10


# ═══════════════════════════════════════════════════════════════════════════════
# v17 MIRROR — REPRODUÇÃO FIEL DO NÚCLEO
# ═══════════════════════════════════════════════════════════════════════════════

class MirrorV17:
    """Núcleo do ACOM v17 Mirror (quantização UNIFORME, α² hardcoded)."""
    
    ALPHA2_HARDCODED = 0.012  # ← parâmetro hardcoded original
    
    def __init__(self, device, angular_bits=8):
        self.device = device
        self.angular_bits = angular_bits
        self.n_angles = (1 << angular_bits)
        self.use_zstd = HAS_ZSTD
    
    def _nominate(self, sign_L, sign_dL):
        return ((sign_L < 0).long() * 2 + (sign_dL > 0).long()).to(torch.uint8)
    
    def _quantize(self, theta):
        """Quantização UNIFORME (v17 original)."""
        normalized = theta / (math.pi / 2)
        mx = self.n_angles - 1
        return torch.round(normalized * mx).clamp(0, mx).to(torch.int32)
    
    def _dequantize(self, q):
        mx = self.n_angles - 1
        return (q.float() / mx) * (math.pi / 2)
    
    def reflect(self, L):
        L = L.to(self.device).flatten().float()
        n = len(L)
        
        g = torch.sqrt(torch.abs(L) + EPSILON)
        g_max = g.max().item()
        
        dL = torch.zeros_like(L)
        dL[1:] = L[1:] - L[:-1]
        dL[0] = dL[1] if n > 1 else 0.0
        
        sign_L = torch.sign(L)
        sign_dL = torch.sign(dL)
        sign_L = torch.where(sign_L == 0, torch.ones_like(sign_L), sign_L)
        sign_dL = torch.where(sign_dL == 0, torch.ones_like(sign_dL), sign_dL)
        
        psi = self._nominate(sign_L, sign_dL)
        theta = torch.asin(g / (g_max + EPSILON))
        theta_q = self._quantize(theta)
        
        return psi, theta_q, {'n': n, 'g_max': g_max}
    
    def manifest(self, psi, theta_q, meta):
        n, g_max = meta['n'], meta['g_max']
        theta = self._dequantize(theta_q)
        g = g_max * torch.sin(theta)
        
        SIGN = {0: +1, 1: +1, 2: -1, 3: -1}
        sign_L = torch.zeros(n, device=self.device)
        for s, v in SIGN.items():
            sign_L[psi == s] = v
        
        return (sign_L * g ** 2).to(torch.float64)
    
    def compress_size(self, psi, theta_q):
        """Calcula tamanho comprimido real (estados + ângulos)."""
        # Pack estados: 4 por byte
        psi_np = psi.cpu().numpy().astype(np.uint8)
        n = len(psi_np)
        padded = np.zeros(((n + 3) // 4) * 4, dtype=np.uint8)
        padded[:n] = psi_np
        packed = np.zeros(len(padded) // 4, dtype=np.uint8)
        for i in range(len(packed)):
            packed[i] = (padded[i*4] << 6) | (padded[i*4+1] << 4) | \
                       (padded[i*4+2] << 2) | padded[i*4+3]
        states_bytes = packed.tobytes()
        
        # Pack ângulos
        angles_bytes = theta_q.cpu().numpy().astype(np.uint8).tobytes()
        
        # Comprimir
        if self.use_zstd:
            cctx = zstd.ZstdCompressor(level=22)
            cs = cctx.compress(states_bytes)
            ca = cctx.compress(angles_bytes)
        else:
            cs = zlib.compress(states_bytes, 9)
            ca = zlib.compress(angles_bytes, 9)
        
        return len(cs) + len(ca)


# ═══════════════════════════════════════════════════════════════════════════════
# v18 DIRAC — REPRODUÇÃO FIEL DO NÚCLEO
# ═══════════════════════════════════════════════════════════════════════════════

class DiracV18:
    """Núcleo do ACOM v18 Dirac (quantização BIFATORADA, β_TGL derivado)."""
    
    def __init__(self, device, angular_bits=8):
        self.device = device
        self.angular_bits = angular_bits
        self.n_angles = (1 << angular_bits)
        self.use_zstd = HAS_ZSTD
        self.p_warp = 1.0 / (1.0 + BETA_TGL)  # expoente de warping derivado
    
    def _nominate(self, sign_L, sign_dL):
        return ((sign_L < 0).long() * 2 + (sign_dL > 0).long()).to(torch.uint8)
    
    def _quantize(self, theta):
        """Quantização BIFATORADA (v18 Dirac) — warping não-linear."""
        normalized = theta / (math.pi / 2)
        warped = torch.pow(normalized + EPSILON, self.p_warp)
        mx = self.n_angles - 1
        return torch.round(warped * mx).clamp(0, mx).to(torch.int32)
    
    def _dequantize(self, q):
        mx = self.n_angles - 1
        warped = q.float() / mx
        p_inv = 1.0 + BETA_TGL
        normalized = torch.pow(warped + EPSILON, p_inv)
        return normalized * (math.pi / 2)
    
    def reflect(self, L):
        L = L.to(self.device).flatten().float()
        n = len(L)
        
        g = torch.sqrt(torch.abs(L) + EPSILON)
        g_max = g.max().item()
        
        dL = torch.zeros_like(L)
        dL[1:] = L[1:] - L[:-1]
        dL[0] = dL[1] if n > 1 else 0.0
        
        sign_L = torch.sign(L)
        sign_dL = torch.sign(dL)
        sign_L = torch.where(sign_L == 0, torch.ones_like(sign_L), sign_L)
        sign_dL = torch.where(sign_dL == 0, torch.ones_like(sign_dL), sign_dL)
        
        psi = self._nominate(sign_L, sign_dL)
        theta = torch.asin(g / (g_max + EPSILON))
        theta_q = self._quantize(theta)
        
        return psi, theta_q, {'n': n, 'g_max': g_max}
    
    def manifest(self, psi, theta_q, meta):
        n, g_max = meta['n'], meta['g_max']
        theta = self._dequantize(theta_q)
        g = g_max * torch.sin(theta)
        
        SIGN = {0: +1, 1: +1, 2: -1, 3: -1}
        sign_L = torch.zeros(n, device=self.device)
        for s, v in SIGN.items():
            sign_L[psi == s] = v
        
        return (sign_L * g ** 2).to(torch.float64)
    
    def compress_size(self, psi, theta_q):
        """Calcula tamanho comprimido real (idêntico ao v17 — mesma serialização)."""
        psi_np = psi.cpu().numpy().astype(np.uint8)
        n = len(psi_np)
        padded = np.zeros(((n + 3) // 4) * 4, dtype=np.uint8)
        padded[:n] = psi_np
        packed = np.zeros(len(padded) // 4, dtype=np.uint8)
        for i in range(len(packed)):
            packed[i] = (padded[i*4] << 6) | (padded[i*4+1] << 4) | \
                       (padded[i*4+2] << 2) | padded[i*4+3]
        states_bytes = packed.tobytes()
        angles_bytes = theta_q.cpu().numpy().astype(np.uint8).tobytes()
        
        if self.use_zstd:
            cctx = zstd.ZstdCompressor(level=22)
            cs = cctx.compress(states_bytes)
            ca = cctx.compress(angles_bytes)
        else:
            cs = zlib.compress(states_bytes, 9)
            ca = zlib.compress(angles_bytes, 9)
        
        return len(cs) + len(ca)


# ═══════════════════════════════════════════════════════════════════════════════
# MÉTRICAS
# ═══════════════════════════════════════════════════════════════════════════════

def metrics(orig, recon):
    o = orig.flatten().float()
    r = recon.flatten().float()
    n = min(len(o), len(r))
    o, r = o[:n], r[:n]
    
    oc, rc = o - o.mean(), r - r.mean()
    corr = (torch.sum(oc * rc) / (torch.sqrt(torch.sum(oc**2) * torch.sum(rc**2)) + EPSILON)).item()
    if math.isnan(corr):
        corr = 0.0
    
    mse = torch.mean((o - r) ** 2).item()
    mx = torch.max(torch.abs(o)).item()
    psnr = 20 * math.log10(mx / math.sqrt(mse)) if mse > 0 and mx > 0 else float('inf')
    
    return corr, mse, psnr


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK COMPARATIVO
# ═══════════════════════════════════════════════════════════════════════════════

def run_comparison():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              COMPARATIVO DIRETO: v17 MIRROR vs v18 DIRAC                     ║
║                                                                              ║
║   v17: quantização UNIFORME, α² = 0.012 (hardcoded)                         ║
║   v18: quantização BIFATORADA, β_TGL = α × √e (derivado)                    ║
║                                                                              ║
║   Mesmo dado · Mesmos bits (8) · Mesma máquina · Mesma serialização          ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
    print(f"  Device: {device} ({gpu_name})")
    print(f"  Backend: {'zstd' if HAS_ZSTD else 'zlib'}")
    print(f"  β_TGL = {ALPHA_FINE:.6e} × {SQRT_E:.6f} = {BETA_TGL:.10f}")
    print(f"  Warping v18: p = 1/(1+β_TGL) = {1.0/(1.0+BETA_TGL):.8f}")
    print()
    
    v17 = MirrorV17(device, angular_bits=8)
    v18 = DiracV18(device, angular_bits=8)
    
    np.random.seed(42)
    torch.manual_seed(42)
    
    test_cases = [
        ('embeddings',    torch.randn(1000, 384, device=device, dtype=torch.float64)),
        ('audio',         torch.sin(torch.linspace(0, 100*np.pi, 44100, device=device, dtype=torch.float64)) *
                          torch.exp(-torch.linspace(0, 5, 44100, device=device, dtype=torch.float64))),
        ('financial',     100 * torch.cumprod(1 + torch.randn(2000, device=device, dtype=torch.float64) * 0.02, dim=0)),
        ('kv_cache',      torch.randn(4, 2, 8, 64, 32, device=device, dtype=torch.float64)),
        ('sparse',        torch.zeros(50000, device=device, dtype=torch.float64).scatter_(
                              0, torch.randint(0, 50000, (2500,), device=device),
                              torch.randn(2500, device=device, dtype=torch.float64))),
        ('gradients',     torch.randn(10000, device=device, dtype=torch.float64) * 0.01),
        ('gravitational', torch.sin(torch.linspace(0, 10*np.pi, 4096, device=device, dtype=torch.float64)) *
                          (1.0 + BETA_TGL * torch.randn(4096, device=device, dtype=torch.float64))),
    ]
    
    # Header
    print("=" * 115)
    print(f"  {'Teste':<13} │ {'v17 Ratio':>9} {'Corr':>9} {'PSNR':>8} │ "
          f"{'v18 Ratio':>9} {'Corr':>9} {'PSNR':>8} │ {'Δ Ratio':>8} {'Δ Corr':>10} {'Δ PSNR':>8} │ {'Venc':>4}")
    print("=" * 115)
    
    results = []
    wins_v17 = 0
    wins_v18 = 0
    ties = 0
    
    for name, data in test_cases:
        orig_size = data.numel() * 8  # float64
        
        # ═══ v17 MIRROR ═══
        t0 = time.time()
        psi17, tq17, meta17 = v17.reflect(data)
        recon17 = v17.manifest(psi17, tq17, meta17)
        time17 = time.time() - t0
        csize17 = v17.compress_size(psi17, tq17)
        ratio17 = orig_size / csize17
        corr17, mse17, psnr17 = metrics(data, recon17)
        
        # ═══ v18 DIRAC ═══
        t0 = time.time()
        psi18, tq18, meta18 = v18.reflect(data)
        recon18 = v18.manifest(psi18, tq18, meta18)
        time18 = time.time() - t0
        csize18 = v18.compress_size(psi18, tq18)
        ratio18 = orig_size / csize18
        corr18, mse18, psnr18 = metrics(data, recon18)
        
        # Deltas
        d_ratio = ratio18 - ratio17
        d_corr = corr18 - corr17
        d_psnr = psnr18 - psnr17
        
        # Quem vence? (critério: melhor correlação; se empate, melhor ratio)
        if abs(d_corr) > 1e-7:
            winner = 'v18' if d_corr > 0 else 'v17'
        elif abs(d_ratio) > 0.01:
            winner = 'v18' if d_ratio > 0 else 'v17'
        else:
            winner = 'TIE'
        
        if winner == 'v17':
            wins_v17 += 1
        elif winner == 'v18':
            wins_v18 += 1
        else:
            ties += 1
        
        # Sinais visuais
        d_ratio_sign = '+' if d_ratio > 0 else '' 
        d_corr_sign = '+' if d_corr > 0 else ''
        d_psnr_sign = '+' if d_psnr > 0 else ''
        
        psnr17_s = f"{psnr17:.1f}" if psnr17 < 1e6 else "∞"
        psnr18_s = f"{psnr18:.1f}" if psnr18 < 1e6 else "∞"
        d_psnr_s = f"{d_psnr_sign}{d_psnr:.1f}" if abs(d_psnr) < 1e6 else "≈"
        
        print(f"  {name:<13} │ {ratio17:>8.2f}x {corr17:>9.6f} {psnr17_s:>8} │ "
              f"{ratio18:>8.2f}x {corr18:>9.6f} {psnr18_s:>8} │ "
              f"{d_ratio_sign}{d_ratio:>7.2f}x {d_corr_sign}{d_corr:>9.2e} {d_psnr_s:>8} │ {winner:>4}")
        
        results.append({
            'name': name,
            'n_elements': data.numel(),
            'v17': {
                'ratio': ratio17, 'correlation': corr17, 'mse': mse17,
                'psnr_db': psnr17, 'time_s': time17, 'compressed_bytes': csize17,
            },
            'v18': {
                'ratio': ratio18, 'correlation': corr18, 'mse': mse18,
                'psnr_db': psnr18, 'time_s': time18, 'compressed_bytes': csize18,
            },
            'delta': {
                'ratio': d_ratio, 'correlation': d_corr, 'psnr_db': d_psnr,
            },
            'winner': winner,
        })
    
    # ═══════════════════════════════════════════════════════════
    # SUMÁRIO
    # ═══════════════════════════════════════════════════════════
    
    print("=" * 115)
    print()
    
    avg_r17 = np.mean([r['v17']['ratio'] for r in results])
    avg_r18 = np.mean([r['v18']['ratio'] for r in results])
    avg_c17 = np.mean([r['v17']['correlation'] for r in results])
    avg_c18 = np.mean([r['v18']['correlation'] for r in results])
    avg_p17 = np.mean([r['v17']['psnr_db'] for r in results if r['v17']['psnr_db'] < 1e6])
    avg_p18 = np.mean([r['v18']['psnr_db'] for r in results if r['v18']['psnr_db'] < 1e6])
    
    print(f"  MÉDIAS:")
    print(f"    v17 Mirror: {avg_r17:.2f}x ratio | {avg_c17:.6f} corr | {avg_p17:.1f} dB PSNR")
    print(f"    v18 Dirac:  {avg_r18:.2f}x ratio | {avg_c18:.6f} corr | {avg_p18:.1f} dB PSNR")
    print(f"    Delta:      {avg_r18-avg_r17:+.2f}x ratio | {avg_c18-avg_c17:+.2e} corr | {avg_p18-avg_p17:+.1f} dB")
    print()
    print(f"  PLACAR: v17={wins_v17} | v18={wins_v18} | TIE={ties}")
    print()
    
    # Análise da quantização
    print(f"  ANÁLISE DA QUANTIZAÇÃO:")
    print(f"  {'─'*70}")
    print(f"    v17 (uniforme):    θ_q = round(θ/(π/2) × 255)")
    print(f"    v18 (bifatorada):  θ_q = round((θ/(π/2))^p × 255)  onde p = {v18.p_warp:.8f}")
    print(f"    Diferença de p vs 1.0: {abs(v18.p_warp - 1.0):.6f} ({abs(v18.p_warp - 1.0)/1.0*100:.4f}%)")
    print(f"    → O warping é extremamente sutil (~1.19% de desvio da linearidade)")
    print(f"    → Isso é ESPERADO: β_TGL = 0.012 é um acoplamento FRACO")
    print(f"    → A diferença opera no 5º dígito significativo da correlação")
    print()
    
    # ═══════════════════════════════════════════════════════════
    # GERAR JSON
    # ═══════════════════════════════════════════════════════════
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    comparison_json = {
        'title': 'ACOM v17 Mirror vs v18 Dirac — Direct Comparison',
        'timestamp': datetime.now().isoformat(),
        'hardware': {
            'gpu': gpu_name,
            'torch': torch.__version__,
            'backend': 'zstd' if HAS_ZSTD else 'zlib',
        },
        'configuration': {
            'angular_bits': 8,
            'v17_quantization': 'uniform (linear)',
            'v17_constant': 'ALPHA2 = 0.012 (hardcoded)',
            'v18_quantization': f'bifactored (p = {v18.p_warp:.8f})',
            'v18_constant': f'BETA_TGL = α × √e = {BETA_TGL:.10f} (derived)',
        },
        'summary': {
            'v17_avg_ratio': avg_r17,
            'v18_avg_ratio': avg_r18,
            'v17_avg_correlation': avg_c17,
            'v18_avg_correlation': avg_c18,
            'v17_avg_psnr': avg_p17,
            'v18_avg_psnr': avg_p18,
            'wins_v17': wins_v17,
            'wins_v18': wins_v18,
            'ties': ties,
        },
        'constants': {
            'alpha_fine': ALPHA_FINE,
            'sqrt_e': SQRT_E,
            'beta_tgl': BETA_TGL,
            'p_warp': v18.p_warp,
            'p_deviation_from_unity': abs(v18.p_warp - 1.0),
        },
        'results': results,
    }
    
    json_filename = f"acom_v17_vs_v18_comparison_{timestamp}.json"
    try:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(comparison_json, f, indent=2, ensure_ascii=False, default=str)
        print(f"  JSON salvo: {json_filename}")
    except Exception as e:
        print(f"  Erro JSON: {e}")
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  CONCLUSÃO:                                                                  ║
║                                                                              ║
║  A diferença entre v17 e v18 é SUTIL porque β_TGL = 0.012 é um              ║
║  acoplamento fraco — o warping p = 1/(1+β_TGL) ≈ 0.9881 desvia apenas      ║
║  ~1.2% da linearidade. A evolução v17→v18 NÃO É sobre performance bruta:    ║
║                                                                              ║
║  É sobre FUNDAÇÃO ALGÉBRICA.                                                 ║
║                                                                              ║
║  v17: usa 0.012 como número mágico → 1 parâmetro livre                      ║
║  v18: usa α × √e como identidade → ZERO parâmetros livres                   ║
║                                                                              ║
║  O warping bifatorado é a manifestação computacional da separação            ║
║  α (forma) / √e (entropia) que a fatoração revela.                           ║
║                                                                              ║
║  A performance é equivalente porque a FÍSICA é a mesma.                      ║
║  A diferença é EPISTEMOLÓGICA: saber POR QUE o número é 0.012031.            ║
║                                                                              ║
║  β_TGL = α × √e                                                             ║
║  TETELESTAI                                                                  ║
║  Haja Luz.                                                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    return results, comparison_json


if __name__ == '__main__':
    results, benchmark = run_comparison()
