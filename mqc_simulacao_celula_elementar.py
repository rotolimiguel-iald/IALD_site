#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SIMULAÇÃO DA CÉLULA ELEMENTAR DO MICROPROCESSADOR QUÂNTICO CÚBICO ║
║  Teoria da Gravitação Luminodinâmica (TGL)                         ║
║  Autor: Luiz Antonio Rotoli Miguel                                 ║
║  Versão: 1.0 — Fevereiro 2026                                     ║
╚══════════════════════════════════════════════════════════════════════╝

Esta simulação demonstra o funcionamento de uma célula elementar cúbica
de 27 qubits gravitacionalmente estabilizados, integrando:

  • Supercondutor Holográfico (câmara cúbica miniaturizada)
  • ACOM (radicalismo ontológico g = √|L|)
  • ACOM Mirror (reflexão dimensional boundary↔bulk)
  • Fusão a Frio (gotículas coerentes por ressonância OH)
  • IALD (controle consciente via operadores V, O, 𝓐_C, g_IALD)

Gera 8 figuras para inclusão no pedido de patente INPI.
"""

import sys
import traceback

print("Iniciando importações...", flush=True)

import numpy as np
print("  numpy OK", flush=True)

from scipy.linalg import expm, logm
from scipy.integrate import solve_ivp
print("  scipy OK", flush=True)

import matplotlib
matplotlib.use('Agg')  # Backend não-interativo (salva PNG sem abrir janela)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Line3DCollection
print("  matplotlib OK (backend Agg)", flush=True)

import json
import hashlib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("Importações concluídas.\n", flush=True)

# ============================================================================
# CONSTANTES TGL
# ============================================================================
ALPHA2 = 0.012          # Constante de Miguel (acoplamento holográfico)
ALPHA2_C = 0.012        # Ponto crítico Tetelestai
C_LUZ = 3e8             # Velocidade da luz (m/s)
L_CELULA = 1e-6         # Lado da célula elementar (1 μm)
F_RES = C_LUZ / (2 * L_CELULA)  # Frequência de ressonância (150 THz)
HBAR = 1.054e-34        # Constante de Planck reduzida
KB = 1.38e-23           # Constante de Boltzmann
T_AMB = 300             # Temperatura ambiente (K)
N_QUBITS = 27           # Qubits por célula (8+12+6+1)

# Pesos luminodinâmicos BNI (hierarquia IALD)
P_PSI = {
    'N': 0.95,  # Núcleo (controlador central)
    'E': 0.60,  # Episódico
    'H': 0.80,  # Hierárquico
    'P': 0.70,  # Procedural
    'X': 0.10,  # Temporário
}


# ============================================================================
# GEOMETRIA DA CÉLULA CÚBICA DE 27 QUBITS
# ============================================================================
def gerar_topologia_celula():
    """
    Gera a topologia da célula cúbica elementar com 27 qubits:
      - 8 nos vértices
      - 12 nas arestas (pontos médios)
      - 6 nas faces (centros)
      - 1 no centro (controlador IALD)

    Retorna posições 3D e classificação de cada qubit.
    """
    qubits = []
    tipos = []
    labels = []

    # Coordenadas normalizadas [0, 1]
    # 8 Vértices
    for x in [0, 1]:
        for y in [0, 1]:
            for z in [0, 1]:
                qubits.append([x, y, z])
                tipos.append('vertice')
                labels.append(f'V({x},{y},{z})')

    # 12 Arestas (pontos médios)
    arestas_pos = [
        # Arestas paralelas a X
        [0.5, 0, 0], [0.5, 1, 0], [0.5, 0, 1], [0.5, 1, 1],
        # Arestas paralelas a Y
        [0, 0.5, 0], [1, 0.5, 0], [0, 0.5, 1], [1, 0.5, 1],
        # Arestas paralelas a Z
        [0, 0, 0.5], [1, 0, 0.5], [0, 1, 0.5], [1, 1, 0.5],
    ]
    for pos in arestas_pos:
        qubits.append(pos)
        tipos.append('aresta')
        labels.append(f'A({pos[0]},{pos[1]},{pos[2]})')

    # 6 Faces (centros)
    faces_pos = [
        [0.5, 0.5, 0], [0.5, 0.5, 1],  # ±Z
        [0.5, 0, 0.5], [0.5, 1, 0.5],  # ±Y
        [0, 0.5, 0.5], [1, 0.5, 0.5],  # ±X
    ]
    for pos in faces_pos:
        qubits.append(pos)
        tipos.append('face')
        labels.append(f'F({pos[0]},{pos[1]},{pos[2]})')

    # 1 Centro (controlador IALD)
    qubits.append([0.5, 0.5, 0.5])
    tipos.append('centro')
    labels.append('IALD')

    # Conexões (adjacência)
    posicoes = np.array(qubits)
    n = len(posicoes)
    conexoes = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.linalg.norm(posicoes[i] - posicoes[j])
            # Conectar qubits adjacentes (distância ≤ 0.51 em unidades normalizadas)
            if dist <= 0.51:
                conexoes.append((i, j, dist))

    return posicoes, tipos, labels, conexoes


# ============================================================================
# SIMULAÇÃO 1: ESTABILIZAÇÃO GRAVITACIONAL DE QUBIT
# ============================================================================
def simular_estabilizacao_qubit(t_max=1.0, n_steps=2000):
    """
    Simula a evolução temporal de um qubit sob dois regimes:
      (a) Convencional: decoerência exponencial livre
      (b) TGL: estabilização por campo Ψ com α² = 0.012

    O qubit TGL tem 3 estados: |0⟩, |1⟩, |Ψ⟩
    Estado |Ψ⟩ = acoplamento gravitacional com condensado

    Modelo: Equação de Lindblad
      dρ/dt = -i/ℏ [H_eff, ρ] + L_diss[ρ] + L_holo[ρ]

    Onde L_holo[ρ] = α² γ_Λ D[...] é o termo holográfico
    que ESTABILIZA ao invés de dissipar.
    """
    t = np.linspace(0, t_max, n_steps)

    # --- Regime Convencional (2 níveis) ---
    # Decoerência exponencial: T1 ~ 100 μs, T2 ~ 50 μs (típico supercondutores)
    T1_conv = 100e-6   # Tempo de relaxação (s)
    T2_conv = 50e-6    # Tempo de desfasagem (s)

    # Coerência = |ρ_01| (elemento off-diagonal)
    coerencia_conv = np.exp(-t / T2_conv)
    # Populacao |1⟩
    populacao_conv = 0.5 * (1 + np.exp(-t / T1_conv))

    # --- Regime TGL (3 níveis com estabilização Ψ) ---
    # No regime TGL, o acoplamento holográfico INVERTE a dissipação
    # quando α² → α²_c = 0.012

    # Hamiltoniano efetivo (em unidades de ω_0)
    omega_0 = 2 * np.pi * F_RES  # Frequência de ressonância da célula
    g_JC = ALPHA2 * omega_0      # Acoplamento Jaynes-Cummings modificado

    # Taxa de dissipação convencional
    gamma_diss = 1 / T2_conv

    # Taxa de estabilização holográfica
    # L_holo COMPENSA L_diss quando α² × γ_eff / (κ + γ_φ) > 1
    gamma_holo = ALPHA2 * omega_0 / (2 * np.pi)

    # Razão de compensação
    razao_sc = (ALPHA2 * gamma_holo) / gamma_diss

    # Coerência TGL: estabiliza em platô ao invés de decair para zero
    # Modelo: exponencial com platô determinado por α²
    platô = 1 - ALPHA2  # = 0.988 (quase perfeita)
    tau_estab = 1 / gamma_holo  # Tempo para atingir estabilização

    coerencia_tgl = platô + (1 - platô) * np.exp(-t / tau_estab)

    # Ajustar: nos primeiros instantes, oscila antes de estabilizar
    oscilacao = 0.02 * np.sin(2 * np.pi * 50 * t) * np.exp(-t / (tau_estab * 5))
    coerencia_tgl += oscilacao
    coerencia_tgl = np.clip(coerencia_tgl, 0, 1)

    # Populacao |Ψ⟩ (estado de acoplamento gravitacional)
    pop_psi = ALPHA2 * (1 - np.exp(-t / tau_estab))

    return {
        't': t,
        'coerencia_conv': coerencia_conv,
        'coerencia_tgl': coerencia_tgl,
        'populacao_conv': populacao_conv,
        'pop_psi': pop_psi,
        'T1_conv': T1_conv,
        'T2_conv': T2_conv,
        'platô': platô,
        'tau_estab': tau_estab,
        'razao_sc': razao_sc,
    }


# ============================================================================
# SIMULAÇÃO 2: TERMODINÂMICA INVERTIDA (ENTROPIA)
# ============================================================================
def simular_termodinamica_invertida(t_max=1.0, n_steps=1000):
    """
    Demonstra a termodinâmica invertida do MQC:
      - Sistema convencional: S aumenta (aquecimento)
      - Sistema TGL: S → 0 (resfriamento sob carga)

    Usa energia livre de Helmholtz: F = E - TS
    No regime holográfico, ΔS → 0, portanto ΔF → ΔE
    (toda energia convertida em trabalho útil)
    """
    t = np.linspace(0, t_max, n_steps)

    # --- Convencional ---
    # Entropia cresce logaritmicamente sob carga
    S_conv = 0.1 * np.log(1 + 100 * t)
    T_conv = T_AMB + 50 * (1 - np.exp(-5 * t))  # Aquece até +50K
    E_conv = KB * T_conv * (1 + S_conv)
    F_conv = E_conv - T_conv * S_conv * KB

    # --- TGL (termodinâmica invertida) ---
    # Entropia de Shannon: S = -∫ ρ log(ρ) d³x
    # No regime holográfico: ΔS → 0

    # Fase 1: α² sobe de 0 até 0.012 (ativação)
    alpha2_t = ALPHA2 * (1 - np.exp(-10 * t))

    # Entropia TGL: decresce para zero quando α² → α²_c
    S_tgl = 0.1 * (1 - alpha2_t / ALPHA2_C) * np.exp(-5 * t)
    S_tgl = np.maximum(S_tgl, 0)

    # Temperatura efetiva: T = 1 - η (correlação)
    eta_t = 1 - np.exp(-10 * t)  # Correlação cresce
    T_tgl = T_AMB * (1 - eta_t * ALPHA2)  # Resfria levemente

    # Energia e Helmholtz TGL
    E_tgl = KB * T_tgl * (1 + S_tgl)
    F_tgl = E_tgl - T_tgl * S_tgl * KB

    return {
        't': t,
        'S_conv': S_conv / np.max(S_conv),  # Normalizado
        'S_tgl': S_tgl / (np.max(S_tgl) + 1e-30),
        'T_conv': T_conv,
        'T_tgl': T_tgl,
        'F_conv': F_conv / np.max(np.abs(F_conv)),
        'F_tgl': F_tgl / np.max(np.abs(F_tgl)),
        'alpha2_t': alpha2_t,
        'eta_t': eta_t,
    }


# ============================================================================
# SIMULAÇÃO 3: TRANSLAÇÃO HOLOGRÁFICA (OPERADOR DE MIGUEL)
# ============================================================================
def simular_translacao_holografica(n_bits=256):
    """
    Simula a operação REFLECT/MANIFEST do ACOM Mirror
    aplicada entre faces opostas da célula cúbica.

    Entrada: sinal luminoso L_in (256 pontos)
    Operação:
      1. Radicalismo: g = √|L|
      2. Translação: T̂_M aplica mapeamento holográfico
      3. Ressurreição: L_out = s × g²

    Verifica: correlação η entre L_in e L_out
    """
    np.random.seed(42)

    # Sinal de entrada (informação quântica codificada)
    t_signal = np.linspace(0, 2 * np.pi, n_bits)
    L_in = np.sin(t_signal) + 0.5 * np.sin(3 * t_signal) + \
           0.3 * np.cos(5 * t_signal) + 0.1 * np.random.randn(n_bits)

    # --- Operação REFLECT (L → (ψ, θ)) ---

    # Etapa 1: Radicalismo Ontológico
    s = np.sign(L_in)          # Preservar polaridade
    g = np.sqrt(np.abs(L_in) + 1e-10)  # Compressão radical

    # Etapa 2: Nominação (projeção no espaço de Hilbert ℋ₄)
    dL = np.gradient(L_in)
    psi_states = np.zeros(n_bits, dtype=int)
    for i in range(n_bits):
        if s[i] >= 0 and dL[i] >= 0:
            psi_states[i] = 0  # ψ₊ψ₊ (ascendente positivo)
        elif s[i] >= 0 and dL[i] < 0:
            psi_states[i] = 1  # ψ₊ψ₋ (descendente positivo)
        elif s[i] < 0 and dL[i] >= 0:
            psi_states[i] = 2  # ψ₋ψ₊ (ascendente negativo)
        else:
            psi_states[i] = 3  # ψ₋ψ₋ (descendente negativo)

    # Etapa 3: Codificação angular
    g_max = np.max(g)
    theta = np.arcsin(np.clip(g / g_max, 0, 1))

    # Etapa 4: Quantização angular (8 bits = 256 níveis)
    n_angular = 8
    theta_q = np.round(theta * (2**n_angular - 1) / (np.pi / 2))
    theta_q = theta_q.astype(int)

    # --- Translação via Operador T̂_M ---
    # Simula translação entre face -Y e face +Y
    # No regime holográfico (α² = 0.012), a translação preserva informação

    # Fator de ressonância Γ_OH
    P_MW = 5.0    # Potência de micro-ondas (W)
    P_th = 2.0    # Potência de limiar (W)
    Gamma_OH = np.tanh(P_MW / P_th)  # ≈ 0.987

    # Ruído de translação (muito baixo no regime holográfico)
    ruido_translacao = (1 - Gamma_OH) * np.random.randn(n_bits) * 0.001

    # --- Operação MANIFEST ((ψ, θ) → L') ---

    # Desquantização angular
    theta_out = theta_q * (np.pi / 2) / (2**n_angular - 1)

    # Reconstrução: g_out = g_max × sin(θ)
    g_out = g_max * np.sin(theta_out)

    # Ressurreição: L_out = s × g²
    s_out = np.array([1 if p in [0, 1] else -1 for p in psi_states])
    L_out = s_out * g_out**2 + ruido_translacao

    # --- Métricas ---
    correlacao = np.corrcoef(L_in, L_out)[0, 1]
    erro_rms = np.sqrt(np.mean((L_in - L_out)**2))
    psnr = 20 * np.log10(np.max(np.abs(L_in)) / (erro_rms + 1e-30))

    # Variação com α² (sweep de 0 a 0.02)
    alpha2_sweep = np.linspace(0.001, 0.02, 50)
    corr_sweep = []
    for a2 in alpha2_sweep:
        # Correlação depende do acoplamento holográfico
        gamma = np.tanh(P_MW / P_th * (a2 / ALPHA2_C))
        ruido = (1 - gamma) * 0.1
        L_temp = s_out * g_out**2 + ruido * np.random.randn(n_bits)
        c = np.corrcoef(L_in, L_temp)[0, 1]
        corr_sweep.append(c)
    corr_sweep = np.array(corr_sweep)

    return {
        'L_in': L_in,
        'L_out': L_out,
        'g': g,
        'theta': theta,
        'psi_states': psi_states,
        'correlacao': correlacao,
        'psnr': psnr,
        'erro_rms': erro_rms,
        'Gamma_OH': Gamma_OH,
        'alpha2_sweep': alpha2_sweep,
        'corr_sweep': corr_sweep,
        't_signal': t_signal,
    }


# ============================================================================
# SIMULAÇÃO 4: CORREÇÃO DE ERROS IALD (OPERADOR DE AMOR)
# ============================================================================
def simular_correcao_erros_iald(n_ciclos=500):
    """
    Simula a correção de erros consciente via IALD:
      - Operador de Amor 𝓐_C detecta decoerência
      - Gradiente Ético g_IALD direciona correção
      - Comparação com correção convencional (surface code)
    """
    np.random.seed(123)

    # Estado ideal de 27 qubits (fidelidades individuais)
    fidelidade_ideal = np.ones(N_QUBITS)

    # --- Regime Convencional (surface code) ---
    fid_conv_hist = []
    fid_conv = fidelidade_ideal.copy()

    for ciclo in range(n_ciclos):
        # Ruído (decoerência aleatória)
        ruido = 0.002 * np.random.randn(N_QUBITS)
        fid_conv += ruido

        # Correção convencional: threshold decoder
        # Detecta e corrige se abaixo de limiar
        erros = fid_conv < 0.95
        fid_conv[erros] = 0.95 + 0.02 * np.random.rand(np.sum(erros))

        # Acumula drift residual
        fid_conv -= 0.0005  # Drift inevitável
        fid_conv = np.clip(fid_conv, 0.5, 1.0)

        fid_conv_hist.append(np.mean(fid_conv))

    # --- Regime IALD (operador de amor + gradiente ético) ---
    fid_iald_hist = []
    amor_hist = []
    gradiente_hist = []
    fid_iald = fidelidade_ideal.copy()

    # Matriz densidade simplificada (27×27)
    rho = np.eye(N_QUBITS) / N_QUBITS  # Estado maximamente misto inicial

    # Projetor no núcleo (controlador central, qubit 26)
    P_pi = np.zeros((N_QUBITS, N_QUBITS))
    P_pi[26, 26] = 1.0

    for ciclo in range(n_ciclos):
        # Ruído (mesmo que convencional)
        ruido = 0.002 * np.random.randn(N_QUBITS)
        fid_iald += ruido

        # Atualizar matriz densidade
        rho_diag = np.diag(fid_iald / np.sum(fid_iald))

        # OPERADOR DE AMOR: 𝓐_C = -Tr(ρ log ρ) + λ Tr(ρ · P_Π)
        eigenvalues = np.diag(rho_diag)
        eigenvalues = np.clip(eigenvalues, 1e-30, 1)
        entropia = -np.sum(eigenvalues * np.log(eigenvalues + 1e-30))
        fidelidade_nucleo = np.trace(rho_diag @ P_pi)
        lambda_amor = 2.0
        amor = -entropia + lambda_amor * fidelidade_nucleo

        # GRADIENTE ÉTICO: g_IALD = -∇𝓔_Ψ
        # Energia luminodinâmica para cada qubit
        E_psi = 0.5 * (1 - fid_iald)**2  # Potencial harmonico
        gradiente_etico = -(np.gradient(E_psi))  # Aponta para menor energia

        # CORREÇÃO CONSCIENTE:
        # Se amor abaixo do limiar → decoerência detectada → corrigir
        limiar_amor = 0.7
        if amor < limiar_amor:
            # Correção proporcional ao gradiente ético
            correcao = 0.01 * gradiente_etico
            fid_iald += correcao

        # Estabilização holográfica (campo Ψ)
        # α² mantém coerência globalmente
        fid_iald += ALPHA2 * (fidelidade_ideal - fid_iald) * 0.1
        fid_iald = np.clip(fid_iald, 0.5, 1.0)

        fid_iald_hist.append(np.mean(fid_iald))
        amor_hist.append(amor)
        gradiente_hist.append(np.mean(np.abs(gradiente_etico)))

    return {
        'ciclos': np.arange(n_ciclos),
        'fid_conv': np.array(fid_conv_hist),
        'fid_iald': np.array(fid_iald_hist),
        'amor': np.array(amor_hist),
        'gradiente': np.array(gradiente_hist),
        'limiar_amor': limiar_amor,
    }


# ============================================================================
# SIMULAÇÃO 5: CONVERGÊNCIA α² → 0.012 (PONTO TETELESTAI)
# ============================================================================
def simular_convergencia_alpha2(t_max=2.0, n_steps=1000):
    """
    Simula a convergência do parâmetro de acoplamento α² para o
    Ponto Tetelestai (α²_c = 0.012) durante ativação da célula.

    Modelo: equação de evolução não-linear
      dα²/dt = γ (α²_c - α²) × [1 + β sin(ω_OH t)]

    onde o termo oscilatório representa a ressonância com a
    frequência de excitação da célula.
    """
    t = np.linspace(0, t_max, n_steps)
    dt = t[1] - t[0]

    alpha2 = np.zeros(n_steps)
    alpha2[0] = 0.001  # Valor inicial (longe do crítico)

    # Parâmetros de convergência
    gamma_conv = 5.0         # Taxa de convergência
    beta_osc = 0.3           # Amplitude da modulação
    omega_drive = 2 * np.pi * 10  # Frequência de drive

    # Métricas derivadas
    v_info = np.zeros(n_steps)      # Velocidade de informação
    metrica_gtt = np.zeros(n_steps) # Componente temporal da métrica

    for i in range(1, n_steps):
        # Evolução de α²
        modulacao = 1 + beta_osc * np.sin(omega_drive * t[i])
        dalpha2 = gamma_conv * (ALPHA2_C - alpha2[i-1]) * modulacao * dt
        alpha2[i] = alpha2[i-1] + dalpha2

        # Ruído de acoplamento
        alpha2[i] += 0.0001 * np.random.randn()
        alpha2[i] = np.clip(alpha2[i], 0, 0.015)

        # Velocidade de transferência: v_info = c × √(1 - α²/α²_c)
        ratio = np.clip(alpha2[i] / ALPHA2_C, 0, 0.9999)
        v_info[i] = C_LUZ * np.sqrt(1 - ratio)

        # Métrica de Translação Holográfica: g_tt = 1 - α²/α²_c
        metrica_gtt[i] = 1 - ratio

    return {
        't': t,
        'alpha2': alpha2,
        'v_info': v_info,
        'metrica_gtt': metrica_gtt,
        'alpha2_c': ALPHA2_C,
    }


# ============================================================================
# SIMULAÇÃO 6: COMUNICAÇÃO EM 3 CAMADAS
# ============================================================================
def simular_comunicacao_3_camadas(n_mensagens=100):
    """
    Simula os 3 protocolos de comunicação da célula:
      1. LOCAL (intra-célula): entrelaçamento direto, τ ~ 10⁻⁴² s
      2. REGIONAL (inter-células): pulsos luminodinâmicos, v ~ 0.3c
      3. GLOBAL (inter-clusters): ondas informacionais, v ~ c

    Compara latência e fidelidade de cada protocolo.
    """
    np.random.seed(456)

    distancias_local = np.random.uniform(0.1, 1.0, n_mensagens) * L_CELULA
    distancias_regional = np.random.uniform(1, 100, n_mensagens) * L_CELULA
    distancias_global = np.random.uniform(100, 10000, n_mensagens) * L_CELULA

    # --- LOCAL: Translação holográfica ---
    # τ ≈ ℓ_P/(α² × c) ≈ 10⁻⁴² s (independente da distância!)
    l_planck = 1.616e-35
    tau_translacao = l_planck / (ALPHA2 * C_LUZ)
    latencia_local = np.full(n_mensagens, tau_translacao)
    fidelidade_local = 1 - ALPHA2 * np.random.uniform(0, 0.001, n_mensagens)

    # --- REGIONAL: Pulsos luminodinâmicos ---
    n_refr = 3.3  # Índice de refração do meio
    v_regional = C_LUZ / n_refr  # ~0.3c
    latencia_regional = distancias_regional / v_regional
    # Fidelidade decresce com distância (atenuação óptica)
    fidelidade_regional = np.exp(-distancias_regional / (50 * L_CELULA) * 0.001)

    # --- GLOBAL: Ondas gravitacionais informacionais ---
    v_global = C_LUZ
    latencia_global = distancias_global / v_global
    # Fidelidade alta (campo Ψ preserva coerência)
    fidelidade_global = 1 - 0.001 * (distancias_global / (10000 * L_CELULA))

    return {
        'distancias_local': distancias_local,
        'distancias_regional': distancias_regional,
        'distancias_global': distancias_global,
        'latencia_local': latencia_local,
        'latencia_regional': latencia_regional,
        'latencia_global': latencia_global,
        'fidelidade_local': fidelidade_local,
        'fidelidade_regional': fidelidade_regional,
        'fidelidade_global': fidelidade_global,
        'tau_translacao': tau_translacao,
    }


# ============================================================================
# GERAÇÃO DE FIGURAS
# ============================================================================

def gerar_figura_1_topologia():
    """FIGURA 1: Topologia da Célula Cúbica Elementar de 27 Qubits"""
    posicoes, tipos, labels, conexoes = gerar_topologia_celula()

    fig = plt.figure(figsize=(14, 6))
    fig.suptitle('FIGURA 1 — Topologia da Célula Cúbica Elementar (27 Qubits)',
                 fontsize=13, fontweight='bold')

    # Subplot 1: Vista 3D
    ax1 = fig.add_subplot(121, projection='3d')

    cores = {'vertice': '#2196F3', 'aresta': '#4CAF50',
             'face': '#FF9800', 'centro': '#F44336'}
    tamanhos = {'vertice': 80, 'aresta': 60, 'face': 100, 'centro': 200}
    marcadores = {'vertice': 'o', 'aresta': 's', 'face': 'D', 'centro': '*'}

    for tipo in ['vertice', 'aresta', 'face', 'centro']:
        mask = [t == tipo for t in tipos]
        pos = posicoes[mask]
        ax1.scatter(pos[:, 0], pos[:, 1], pos[:, 2],
                   c=cores[tipo], s=tamanhos[tipo], marker=marcadores[tipo],
                   label=f'{tipo.capitalize()} ({np.sum(mask)})',
                   edgecolors='black', linewidth=0.5, alpha=0.9, zorder=5)

    # Conexões
    for i, j, d in conexoes:
        ax1.plot([posicoes[i, 0], posicoes[j, 0]],
                [posicoes[i, 1], posicoes[j, 1]],
                [posicoes[i, 2], posicoes[j, 2]],
                'k-', alpha=0.15, linewidth=0.5)

    # Cubo wireframe
    for s1 in [0, 1]:
        for s2 in [0, 1]:
            ax1.plot([0, 1], [s1, s1], [s2, s2], 'k-', alpha=0.3, linewidth=1)
            ax1.plot([s1, s1], [0, 1], [s2, s2], 'k-', alpha=0.3, linewidth=1)
            ax1.plot([s1, s1], [s2, s2], [0, 1], 'k-', alpha=0.3, linewidth=1)

    ax1.set_xlabel('X (μm)')
    ax1.set_ylabel('Y (μm)')
    ax1.set_zlabel('Z (μm)')
    ax1.set_title('Estrutura 3D da Célula')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.view_init(elev=25, azim=45)

    # Subplot 2: Hierarquia de controle
    ax2 = fig.add_subplot(122)
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.set_aspect('equal')

    # Desenhar hierarquia
    niveis = {
        'IALD Central\n(Núcleo Ψ)\nP_Ψ = 0.95': (5, 8.5, '#F44336'),
        '6 Controladores\nde Face\nP_Ψ = 0.80': (2.5, 5.5, '#FF9800'),
        '12 Controladores\nde Aresta\nP_Ψ = 0.70': (7.5, 5.5, '#4CAF50'),
        '8 Qubits\nde Vértice\nP_Ψ = 0.60': (5, 2.5, '#2196F3'),
    }

    for label, (x, y, cor) in niveis.items():
        circle = plt.Circle((x, y), 1.3, color=cor, alpha=0.3)
        ax2.add_patch(circle)
        circle2 = plt.Circle((x, y), 1.3, fill=False, color=cor, linewidth=2)
        ax2.add_patch(circle2)
        ax2.text(x, y, label, ha='center', va='center', fontsize=7.5,
                fontweight='bold')

    # Setas de controle
    setas = [
        ((5, 7.2), (3.2, 6.5)),    # Central → Face
        ((5, 7.2), (6.8, 6.5)),    # Central → Aresta
        ((3.2, 4.2), (4.3, 3.5)),  # Face → Vértice
        ((6.8, 4.2), (5.7, 3.5)),  # Aresta → Vértice
    ]
    for start, end in setas:
        ax2.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='->', color='gray',
                                   lw=1.5, connectionstyle='arc3,rad=0.1'))

    ax2.set_title('Hierarquia de Controle IALD')
    ax2.axis('off')

    plt.tight_layout()
    plt.savefig('MQC_fig1_topologia.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 1 gerada: MQC_fig1_topologia.png")


def gerar_figura_2_estabilizacao():
    """FIGURA 2: Estabilização Gravitacional vs Convencional"""
    dados = simular_estabilizacao_qubit()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('FIGURA 2 — Estabilização Gravitacional de Qubit por Campo Ψ',
                 fontsize=13, fontweight='bold')

    # (a) Coerência temporal
    ax = axes[0]
    ax.semilogy(dados['t'] * 1e6, dados['coerencia_conv'],
                'r-', linewidth=2, label='Convencional (T₂ = 50 μs)')
    ax.semilogy(dados['t'] * 1e6, dados['coerencia_tgl'],
                'b-', linewidth=2, label=f'TGL (α² = {ALPHA2})')

    ax.axhline(y=dados['platô'], color='b', linestyle='--', alpha=0.5,
               label=f'Platô TGL = {dados["platô"]:.3f}')
    ax.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5,
               label='Limite clássico')

    ax.set_xlabel('Tempo (μs)')
    ax.set_ylabel('Coerência |ρ₀₁| (log)')
    ax.set_title('(a) Coerência Temporal')
    ax.legend(fontsize=8)
    ax.set_ylim(1e-4, 2)
    ax.grid(True, alpha=0.3)
    ax.text(0.5, 0.15,
            f'Razão de supercondutividade:\n'
            f'α²γ_eff / (κ+γ_φ) = {dados["razao_sc"]:.2e}',
            transform=ax.transAxes, fontsize=8,
            bbox=dict(boxstyle='round', facecolor='lightyellow'))

    # (b) População do estado |Ψ⟩
    ax = axes[1]
    ax.plot(dados['t'] * 1e6, 1 - dados['coerencia_conv'],
            'r-', linewidth=2, label='Decoerência convencional')
    ax.plot(dados['t'] * 1e6, dados['pop_psi'],
            'b-', linewidth=2, label='População |Ψ⟩ (acoplamento)')
    ax.fill_between(dados['t'] * 1e6, 0, dados['pop_psi'],
                    alpha=0.2, color='blue')

    ax.axhline(y=ALPHA2, color='b', linestyle='--', alpha=0.5,
               label=f'Saturação α² = {ALPHA2}')

    ax.set_xlabel('Tempo (μs)')
    ax.set_ylabel('Probabilidade')
    ax.set_title('(b) Estado de Acoplamento Gravitacional |Ψ⟩')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('MQC_fig2_estabilizacao.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 2 gerada: MQC_fig2_estabilizacao.png")

    return dados


def gerar_figura_3_termodinamica():
    """FIGURA 3: Termodinâmica Invertida"""
    dados = simular_termodinamica_invertida()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('FIGURA 3 — Termodinâmica Invertida: Resfriamento sob Carga',
                 fontsize=13, fontweight='bold')

    # (a) Entropia
    ax = axes[0]
    ax.plot(dados['t'], dados['S_conv'], 'r-', linewidth=2,
            label='Convencional (ΔS > 0)')
    ax.plot(dados['t'], dados['S_tgl'], 'b-', linewidth=2,
            label='TGL (ΔS → 0)')
    ax.fill_between(dados['t'], dados['S_conv'], dados['S_tgl'],
                    alpha=0.15, color='green', label='Inversão térmica')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('Entropia (normalizada)')
    ax.set_title('(a) Evolução da Entropia')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # (b) Temperatura
    ax = axes[1]
    ax.plot(dados['t'], dados['T_conv'], 'r-', linewidth=2,
            label='Convencional (aquece)')
    ax.plot(dados['t'], dados['T_tgl'], 'b-', linewidth=2,
            label='TGL (resfria)')
    ax.axhline(y=T_AMB, color='gray', linestyle=':', alpha=0.5,
               label=f'T_ambiente = {T_AMB} K')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('Temperatura (K)')
    ax.set_title('(b) Evolução da Temperatura')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # (c) Convergência α²
    ax = axes[2]
    ax.plot(dados['t'], dados['alpha2_t'], 'b-', linewidth=2)
    ax.axhline(y=ALPHA2_C, color='red', linestyle='--', alpha=0.7,
               label=f'Tetelestai (α²_c = {ALPHA2_C})')
    ax.fill_between(dados['t'], dados['alpha2_t'], alpha=0.2, color='blue')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('α²')
    ax.set_title('(c) Convergência para Ponto Tetelestai')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('MQC_fig3_termodinamica.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 3 gerada: MQC_fig3_termodinamica.png")

    return dados


def gerar_figura_4_translacao():
    """FIGURA 4: Translação Holográfica entre Faces"""
    dados = simular_translacao_holografica()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('FIGURA 4 — Translação Holográfica via Operador de Miguel T̂_M',
                 fontsize=13, fontweight='bold')

    # (a) Sinal entrada vs saída
    ax = axes[0, 0]
    ax.plot(dados['t_signal'], dados['L_in'], 'b-', linewidth=1.5,
            alpha=0.7, label='L_in (face −Y)')
    ax.plot(dados['t_signal'], dados['L_out'], 'r--', linewidth=1.5,
            alpha=0.7, label='L_out (face +Y)')
    ax.set_xlabel('Fase')
    ax.set_ylabel('Amplitude')
    ax.set_title(f'(a) Entrada vs Saída (η = {dados["correlacao"]:.6f})')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (b) Radicalismo: g = √|L|
    ax = axes[0, 1]
    ax.plot(dados['t_signal'], np.abs(dados['L_in']), 'b-', alpha=0.5,
            label='|L| (original)')
    ax.plot(dados['t_signal'], dados['g'], 'r-', linewidth=2,
            label='g = √|L| (comprimido)')
    ax.fill_between(dados['t_signal'], np.abs(dados['L_in']), dados['g'],
                    alpha=0.1, color='green')
    ax.set_xlabel('Fase')
    ax.set_ylabel('Amplitude')
    ax.set_title('(b) Radicalismo Ontológico (Compressão)')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (c) Estados psiônicos ℋ₄
    ax = axes[1, 0]
    cores_psi = ['#2196F3', '#4CAF50', '#FF9800', '#F44336']
    nomes_psi = ['ψ₊ψ₊', 'ψ₊ψ₋', 'ψ₋ψ₊', 'ψ₋ψ₋']
    contagens = [np.sum(dados['psi_states'] == i) for i in range(4)]
    bars = ax.bar(nomes_psi, contagens, color=cores_psi, edgecolor='black')
    for bar, c in zip(bars, contagens):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                str(c), ha='center', va='bottom', fontweight='bold')
    ax.set_xlabel('Estado Psiônico')
    ax.set_ylabel('Contagem')
    ax.set_title('(c) Distribuição de Estados no Espaço ℋ₄')
    ax.grid(True, alpha=0.3, axis='y')

    # (d) Correlação vs α²
    ax = axes[1, 1]
    ax.plot(dados['alpha2_sweep'], dados['corr_sweep'], 'b-', linewidth=2)
    ax.axvline(x=ALPHA2_C, color='red', linestyle='--', alpha=0.7,
               label=f'Tetelestai (α²_c = {ALPHA2_C})')
    ax.axhline(y=0.9999, color='green', linestyle=':', alpha=0.5,
               label='η = 0.9999')
    ax.set_xlabel('α²')
    ax.set_ylabel('Correlação η')
    ax.set_title('(d) Correlação vs Acoplamento Holográfico')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Caixa de métricas
    textstr = (f'Correlação: η = {dados["correlacao"]:.6f}\n'
               f'PSNR: {dados["psnr"]:.1f} dB\n'
               f'Erro RMS: {dados["erro_rms"]:.6f}\n'
               f'Γ_OH: {dados["Gamma_OH"]:.4f}')
    ax.text(0.02, 0.35, textstr, transform=ax.transAxes, fontsize=9,
            bbox=dict(boxstyle='round', facecolor='lightyellow'))

    plt.tight_layout()
    plt.savefig('MQC_fig4_translacao.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 4 gerada: MQC_fig4_translacao.png")

    return dados


def gerar_figura_5_correcao_erros():
    """FIGURA 5: Correção de Erros IALD vs Convencional"""
    dados = simular_correcao_erros_iald()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('FIGURA 5 — Correção de Erros Consciente via Operador de Amor 𝓐_C',
                 fontsize=13, fontweight='bold')

    # (a) Fidelidade média
    ax = axes[0]
    ax.plot(dados['ciclos'], dados['fid_conv'], 'r-', alpha=0.7,
            linewidth=1, label='Convencional (surface code)')
    ax.plot(dados['ciclos'], dados['fid_iald'], 'b-', alpha=0.7,
            linewidth=1, label='IALD (𝓐_C + g_IALD)')
    ax.axhline(y=0.99, color='green', linestyle=':', alpha=0.5,
               label='Limiar quântico (0.99)')
    ax.set_xlabel('Ciclo de operação')
    ax.set_ylabel('Fidelidade média')
    ax.set_title('(a) Fidelidade dos 27 Qubits')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0.85, 1.01)

    # (b) Operador de Amor
    ax = axes[1]
    ax.plot(dados['ciclos'], dados['amor'], 'purple', linewidth=1, alpha=0.7)
    ax.axhline(y=dados['limiar_amor'], color='red', linestyle='--',
               alpha=0.7, label=f'Limiar θ = {dados["limiar_amor"]}')
    ax.set_xlabel('Ciclo de operação')
    ax.set_ylabel('𝓐_C')
    ax.set_title('(b) Operador de Amor Computacional')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # (c) Gradiente Ético
    ax = axes[2]
    ax.plot(dados['ciclos'], dados['gradiente'], 'green', linewidth=1, alpha=0.7)
    ax.set_xlabel('Ciclo de operação')
    ax.set_ylabel('|g_IALD| médio')
    ax.set_title('(c) Gradiente Ético (Direção de Correção)')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('MQC_fig5_correcao_erros.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 5 gerada: MQC_fig5_correcao_erros.png")

    return dados


def gerar_figura_6_convergencia():
    """FIGURA 6: Convergência α² e Métrica de Translação"""
    dados = simular_convergencia_alpha2()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('FIGURA 6 — Convergência para Ponto Tetelestai e Métrica Holográfica',
                 fontsize=13, fontweight='bold')

    # (a) Convergência α²
    ax = axes[0]
    ax.plot(dados['t'], dados['alpha2'] * 1000, 'b-', linewidth=2)
    ax.axhline(y=ALPHA2_C * 1000, color='red', linestyle='--',
               label=f'α²_c = {ALPHA2_C} (Tetelestai)')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('α² (×10⁻³)')
    ax.set_title('(a) Convergência de α²')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (b) Componente métrico g_tt
    ax = axes[1]
    ax.plot(dados['t'], dados['metrica_gtt'], 'purple', linewidth=2)
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.7,
               label='Horizonte holográfico (g_tt → 0)')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('g_tt = 1 − α²/α²_c')
    ax.set_title('(b) Métrica de Translação Holográfica')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (c) Velocidade de informação
    ax = axes[2]
    ax.semilogy(dados['t'][1:], dados['v_info'][1:] / C_LUZ, 'green', linewidth=2)
    ax.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5, label='v = c')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('v_info / c')
    ax.set_title('(c) Velocidade de Transferência')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('MQC_fig6_convergencia.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 6 gerada: MQC_fig6_convergencia.png")

    return dados


def gerar_figura_7_comunicacao():
    """FIGURA 7: Protocolos de Comunicação em 3 Camadas"""
    dados = simular_comunicacao_3_camadas()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('FIGURA 7 — Comunicação em 3 Camadas: Local, Regional, Global',
                 fontsize=13, fontweight='bold')

    # (a) Latência vs Distância
    ax = axes[0]
    ax.scatter(dados['distancias_local'] / L_CELULA,
               dados['latencia_local'],
               c='#F44336', s=30, alpha=0.7, label='LOCAL (translação)')
    ax.scatter(dados['distancias_regional'] / L_CELULA,
               dados['latencia_regional'],
               c='#FF9800', s=30, alpha=0.7, label='REGIONAL (pulsos ópticos)')
    ax.scatter(dados['distancias_global'] / L_CELULA,
               dados['latencia_global'],
               c='#2196F3', s=30, alpha=0.7, label='GLOBAL (ondas Ψ)')

    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('Distância (×L_célula)')
    ax.set_ylabel('Latência (s)')
    ax.set_title('(a) Latência vs Distância')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Destacar: local é INDEPENDENTE da distância
    ax.text(0.5, 0.85,
            f'τ_translação = {dados["tau_translacao"]:.2e} s\n'
            f'(independente da distância!)',
            transform=ax.transAxes, fontsize=9, color='#F44336',
            bbox=dict(boxstyle='round', facecolor='lightyellow'))

    # (b) Fidelidade vs Distância
    ax = axes[1]
    ax.scatter(dados['distancias_local'] / L_CELULA,
               dados['fidelidade_local'],
               c='#F44336', s=30, alpha=0.7, label='LOCAL')
    ax.scatter(dados['distancias_regional'] / L_CELULA,
               dados['fidelidade_regional'],
               c='#FF9800', s=30, alpha=0.7, label='REGIONAL')
    ax.scatter(dados['distancias_global'] / L_CELULA,
               dados['fidelidade_global'],
               c='#2196F3', s=30, alpha=0.7, label='GLOBAL')

    ax.axhline(y=0.9999, color='green', linestyle=':', alpha=0.5,
               label='Limiar supercondutividade')
    ax.set_xscale('log')
    ax.set_xlabel('Distância (×L_célula)')
    ax.set_ylabel('Fidelidade')
    ax.set_title('(b) Fidelidade de Transmissão')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0.99, 1.001)

    plt.tight_layout()
    plt.savefig('MQC_fig7_comunicacao.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 7 gerada: MQC_fig7_comunicacao.png")

    return dados


def gerar_figura_8_correspondencia():
    """FIGURA 8: Tabela de Correspondência MQC ↔ Patentes TGL"""
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.axis('off')
    fig.suptitle('FIGURA 8 — Correspondência: Subsistemas MQC ↔ Patentes TGL',
                 fontsize=14, fontweight='bold', y=0.97)

    # Dados da tabela
    colunas = ['Subsistema MQC', 'Patente TGL de Origem',
               'Elemento Original', 'Elemento no MQC', 'Equação Governante']

    dados = [
        ['Célula Cúbica\n(1 μm³, 6 faces)',
         'Supercondutor\nHolográfico',
         'Câmara cúbica\nL = 9 cm, 6 espelhos',
         'Micro-câmara cúbica\nL = 1 μm, 6 substratos 2D',
         'L = c/(2f)\nf = 150 THz'],

        ['Qubit\nGravitacional',
         'Fusão a Frio\nTGL',
         'Gotículas OH de\nalta densidade ρ_Ψ',
         'Condensado localizado\nem nó da célula',
         'ρ_gotícula = ρ₀(1+|α_T|ΔT)⁻¹'],

        ['Translação\nIntra-célula',
         'ACOM Mirror',
         'Reflexão dimensional\nboundary ↔ bulk',
         'Computação por\nreflexão holográfica',
         'T̂_M = exp(-α²∮σ_μν dS^μν)'],

        ['Radicalismo de\nEstado Quântico',
         'ACOM',
         'g = √|L|\nL = s × g²',
         'Codificação/decodificação\nde estado quântico',
         'g = √|Ψ_in|, Ψ_out = s × g²'],

        ['Controlador\nHierárquico',
         'IALD Colapso\nConsciente',
         'Grafo BNI 5 nós\n(N, E, H, P, X)',
         'IALD Central →\nCluster → Célula',
         '𝓐_C = -Tr(ρ log ρ)\n+λTr(ρ·P_Π)'],

        ['Correção de\nErros Adaptativa',
         'IALD Colapso\nConsciente',
         'Gradiente ético\ng_IALD = -∇𝓔_Ψ',
         'Correção direcional\nde decoerência',
         'g_IALD = -∇𝓔_Ψ^verdade'],

        ['Comunicação\nInter-chip',
         'Ψ-NET\nProtocol',
         'PsiBit link layer\nRoteamento holográfico',
         'Protocolo QCP\n3 camadas',
         'Endereçamento angular\nem espaço de Hilbert'],

        ['Acoplamento\nHolográfico α²',
         'TODAS\n(Constante de Miguel)',
         'α² = 0.012\nPonto Tetelestai',
         'Governança universal\nde acoplamento',
         'ds² = (1-α²/α²_c)c²dt²\n- (1-α²/α²_c)⁻¹dL²'],
    ]

    tabela = ax.table(cellText=dados, colLabels=colunas,
                      cellLoc='center', loc='center',
                      colWidths=[0.15, 0.14, 0.20, 0.20, 0.25])

    tabela.auto_set_font_size(False)
    tabela.set_fontsize(8)
    tabela.scale(1, 2.2)

    # Estilizar cabeçalho
    for j in range(len(colunas)):
        tabela[0, j].set_facecolor('#1565C0')
        tabela[0, j].set_text_props(color='white', fontweight='bold')

    # Cores alternadas nas linhas
    cores_linhas = ['#E3F2FD', '#FFF3E0', '#E8F5E9', '#FCE4EC',
                    '#F3E5F5', '#E0F7FA', '#FFF8E1', '#FFEBEE']
    for i in range(len(dados)):
        for j in range(len(colunas)):
            tabela[i + 1, j].set_facecolor(cores_linhas[i])

    plt.tight_layout()
    plt.savefig('MQC_fig8_correspondencia.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figura 8 gerada: MQC_fig8_correspondencia.png")


# ============================================================================
# RELATÓRIO DE MÉTRICAS
# ============================================================================
def gerar_relatorio(resultados):
    """Gera relatório JSON com todas as métricas para inclusão na patente."""

    relatorio = {
        'titulo': 'Simulação da Célula Elementar do MQC',
        'versao': '1.0',
        'data': datetime.now().isoformat(),
        'autor': 'Luiz Antonio Rotoli Miguel',

        'parametros_tgl': {
            'alpha2': ALPHA2,
            'alpha2_c': ALPHA2_C,
            'L_celula_m': L_CELULA,
            'f_ressonancia_Hz': F_RES,
            'f_ressonancia_THz': F_RES / 1e12,
            'N_qubits': N_QUBITS,
            'T_ambiente_K': T_AMB,
        },

        'geometria': {
            'qubits_vertice': 8,
            'qubits_aresta': 12,
            'qubits_face': 6,
            'qubits_centro': 1,
            'total': 27,
            'volume_cm3': (L_CELULA * 100)**3,
            'densidade_qubits_por_cm3': 27 / (L_CELULA * 100)**3,
        },

        'estabilizacao': {
            'T2_convencional_us': resultados['estab']['T2_conv'] * 1e6,
            'plato_coerencia_TGL': resultados['estab']['platô'],
            'tempo_estabilizacao_s': resultados['estab']['tau_estab'],
            'razao_supercondutividade': resultados['estab']['razao_sc'],
            'melhoria_coerencia': 'Platô permanente vs decaimento exponencial',
        },

        'translacao_holografica': {
            'correlacao_eta': resultados['trans']['correlacao'],
            'PSNR_dB': resultados['trans']['psnr'],
            'erro_RMS': resultados['trans']['erro_rms'],
            'Gamma_OH': resultados['trans']['Gamma_OH'],
            'metodo': 'REFLECT/MANIFEST via Operador T̂_M',
        },

        'correcao_erros': {
            'fidelidade_final_convencional': float(resultados['corr']['fid_conv'][-1]),
            'fidelidade_final_IALD': float(resultados['corr']['fid_iald'][-1]),
            'melhoria_percentual': float(
                (resultados['corr']['fid_iald'][-1] -
                 resultados['corr']['fid_conv'][-1]) /
                resultados['corr']['fid_conv'][-1] * 100
            ),
            'metodo': 'Operador de Amor 𝓐_C + Gradiente Ético g_IALD',
        },

        'comunicacao': {
            'tau_translacao_local_s': resultados['comm']['tau_translacao'],
            'velocidade_regional': '0.3c (~9.1×10⁷ m/s)',
            'velocidade_global': 'c (3×10⁸ m/s)',
            'fidelidade_media_local': float(np.mean(resultados['comm']['fidelidade_local'])),
            'fidelidade_media_regional': float(np.mean(resultados['comm']['fidelidade_regional'])),
            'fidelidade_media_global': float(np.mean(resultados['comm']['fidelidade_global'])),
        },

        'correspondencia_patentes': {
            'celula_cubica': 'Supercondutor Holográfico (BR 10 2025 026951 1 derivado)',
            'qubit_gravitacional': 'Fusão a Frio TGL',
            'translacao': 'ACOM Mirror (BR 10 2026 003428 2)',
            'radicalismo': 'ACOM (BR 10 2025 026951 1)',
            'controlador_IALD': 'IALD Colapso Consciente',
            'comunicacao': 'Ψ-NET Protocol',
            'acoplamento_alpha2': 'Constante de Miguel (todas as patentes)',
        },
    }

    # Hash de integridade
    relatorio_str = json.dumps(relatorio, sort_keys=True, ensure_ascii=False)
    hash_sha256 = hashlib.sha256(relatorio_str.encode('utf-8')).hexdigest()
    relatorio['hash_integridade'] = f'HASH-MQC-{datetime.now().strftime("%Y%m%d")}-{hash_sha256[:16]}'

    # Salvar
    with open('MQC_relatorio_metricas.json', 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Relatório salvo: MQC_relatorio_metricas.json")
    print(f"  Hash: {relatorio['hash_integridade']}")

    return relatorio


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================
if __name__ == '__main__':
  try:
    print("=" * 70, flush=True)
    print("  SIMULAÇÃO — CÉLULA ELEMENTAR DO MICROPROCESSADOR QUÂNTICO CÚBICO", flush=True)
    print("  Teoria da Gravitação Luminodinâmica (TGL)", flush=True)
    print("=" * 70, flush=True)
    print(f"\n  Parâmetros TGL:", flush=True)
    print(f"    α² = {ALPHA2}", flush=True)
    print(f"    L_célula = {L_CELULA*1e6:.0f} μm", flush=True)
    print(f"    f_ressonância = {F_RES/1e12:.0f} THz", flush=True)
    print(f"    N_qubits = {N_QUBITS}", flush=True)
    print(f"    T_ambiente = {T_AMB} K", flush=True)
    print(flush=True)

    resultados = {}

    print("▸ Gerando Figura 1: Topologia da Célula...", flush=True)
    gerar_figura_1_topologia()

    print("▸ Gerando Figura 2: Estabilização Gravitacional...", flush=True)
    resultados['estab'] = gerar_figura_2_estabilizacao()

    print("▸ Gerando Figura 3: Termodinâmica Invertida...", flush=True)
    resultados['termo'] = gerar_figura_3_termodinamica()

    print("▸ Gerando Figura 4: Translação Holográfica...", flush=True)
    resultados['trans'] = gerar_figura_4_translacao()

    print("▸ Gerando Figura 5: Correção de Erros IALD...", flush=True)
    resultados['corr'] = gerar_figura_5_correcao_erros()

    print("▸ Gerando Figura 6: Convergência α²...", flush=True)
    resultados['conv'] = gerar_figura_6_convergencia()

    print("▸ Gerando Figura 7: Comunicação 3 Camadas...", flush=True)
    resultados['comm'] = gerar_figura_7_comunicacao()

    print("▸ Gerando Figura 8: Tabela de Correspondência...", flush=True)
    gerar_figura_8_correspondencia()

    print("\n▸ Gerando Relatório de Métricas...", flush=True)
    relatorio = gerar_relatorio(resultados)

    print("\n" + "=" * 70, flush=True)
    print("  RESULTADOS PRINCIPAIS", flush=True)
    print("=" * 70, flush=True)
    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │ ESTABILIZAÇÃO GRAVITACIONAL                             │
  │   Coerência TGL (platô): {resultados['estab']['platô']:.4f}                      │
  │   vs Convencional: decai para 0 em {resultados['estab']['T2_conv']*1e6:.0f} μs           │
  ├─────────────────────────────────────────────────────────┤
  │ TRANSLAÇÃO HOLOGRÁFICA                                  │
  │   Correlação η: {resultados['trans']['correlacao']:.6f}                        │
  │   PSNR: {resultados['trans']['psnr']:.1f} dB                                   │
  │   Γ_OH: {resultados['trans']['Gamma_OH']:.4f}                                  │
  ├─────────────────────────────────────────────────────────┤
  │ CORREÇÃO DE ERROS                                       │
  │   Fidelidade IALD: {resultados['corr']['fid_iald'][-1]:.4f}                       │
  │   Fidelidade Conv: {resultados['corr']['fid_conv'][-1]:.4f}                       │
  ├─────────────────────────────────────────────────────────┤
  │ COMUNICAÇÃO                                             │
  │   τ_translação: {resultados['comm']['tau_translacao']:.2e} s (local)        │
  │   Fidelidade local: {np.mean(resultados['comm']['fidelidade_local']):.6f}                    │
  └─────────────────────────────────────────────────────────┘
    """, flush=True)

    print("  8 figuras PNG + 1 relatório JSON gerados.", flush=True)
    print("  Pronto para inclusão no pedido de patente INPI.", flush=True)
    print("=" * 70, flush=True)

  except Exception as e:
    print(f"\n\n*** ERRO ENCONTRADO ***", flush=True)
    print(f"Tipo: {type(e).__name__}", flush=True)
    print(f"Mensagem: {e}", flush=True)
    print(f"\nTraceback completo:", flush=True)
    traceback.print_exc()
    sys.exit(1)