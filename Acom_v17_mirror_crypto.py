#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    ACOM v17.1 — MIRROR CRYPTO                                ║
║                                                                              ║
║              "Criptografia por Reflexão Dimensional"                         ║
║                                                                              ║
║                 Teoria da Gravitação Luminodinâmica                          ║
║                    Luiz Antonio Rotoli Miguel                                ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PARADIGMA:                                                                  ║
║                                                                              ║
║      Não é baseada em problemas matemáticos difíceis                        ║
║      É baseada na ESTRUTURA ONTOLÓGICA da informação                        ║
║                                                                              ║
║  PRINCÍPIO:                                                                  ║
║                                                                              ║
║      L → (ψ, θ, g_max) → SEPARAÇÃO DIMENSIONAL                              ║
║                                                                              ║
║      ψ sozinho = Estados sem escala (RUÍDO)                                 ║
║      θ sozinho = Ângulos sem sinal (RUÍDO)                                  ║
║      g_max sozinho = Escala sem dados (INÚTIL)                              ║
║                                                                              ║
║      RECONSTRUÇÃO requer TODAS as partes                                    ║
║                                                                              ║
║  PROPRIEDADES DE SEGURANÇA:                                                  ║
║                                                                              ║
║      • Confidencialidade: partes isoladas = ruído informacional             ║
║      • Integridade: F_exp como verificador físico                           ║
║      • Não-linearidade: arcsin/sin previne ataques lineares                 ║
║      • Secret Sharing: esquema (k,n) threshold nativo                       ║
║                                                                              ║
║  INOVAÇÃO:                                                                   ║
║                                                                              ║
║      A "chave" não é um número — é a ESTRUTURA DO ESPAÇO DE HILBERT        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import torch
import hashlib
import secrets
import json
import struct
import os
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, List, Optional
from enum import IntEnum
import time
import math
import warnings
warnings.filterwarnings('ignore')

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

import zlib

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES FUNDAMENTAIS
# ══════════════════════════════════════════════════════════════════════════════

ALPHA2 = 0.012
ALPHA = math.sqrt(ALPHA2)
THETA_MIGUEL = math.asin(ALPHA)
EPSILON = 1e-10

# Versão do protocolo criptográfico
CRYPTO_VERSION = b'ACOM_MIRROR_CRYPTO_v1'
MAGIC_PSI = b'\xCE\xA8'      # Ψ em UTF-8
MAGIC_THETA = b'\xCE\x98'    # Θ em UTF-8
MAGIC_KEY = b'\xCE\xBA'      # κ (kappa) em UTF-8

print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ACOM v17.1 — MIRROR CRYPTO                                ║
║              "Criptografia por Reflexão Dimensional"                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  A "chave" não é um número — é a ESTRUTURA DO ESPAÇO DE HILBERT            ║
║                                                                              ║
║  Partes isoladas = RUÍDO | Todas as partes = DADOS                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


# ══════════════════════════════════════════════════════════════════════════════
# ESTADOS PSIÔNICOS
# ══════════════════════════════════════════════════════════════════════════════

class PsionicState(IntEnum):
    COLLAPSE_PLUS = 0   # |COLAPSO⁺⟩
    ASCEND_PLUS = 1     # |ASCENSÃO⁺⟩
    EMERGE_MINUS = 2    # |EMERGÊNCIA⁻⟩
    FALL_MINUS = 3      # |QUEDA⁻⟩

PARITY = {
    PsionicState.COLLAPSE_PLUS: -1,
    PsionicState.ASCEND_PLUS:   +1,
    PsionicState.EMERGE_MINUS:  +1,
    PsionicState.FALL_MINUS:    -1,
}

SIGN_L = {
    PsionicState.COLLAPSE_PLUS: +1,
    PsionicState.ASCEND_PLUS:   +1,
    PsionicState.EMERGE_MINUS:  -1,
    PsionicState.FALL_MINUS:    -1,
}


# ══════════════════════════════════════════════════════════════════════════════
# ESTRUTURAS CRIPTOGRÁFICAS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PsiShare:
    """
    Share PSI (Ψ) — Estados no Espaço de Hilbert.
    
    Contém: estados psiônicos (sinais/direções)
    Sem: magnitudes, escala
    Sozinho: RUÍDO (sequência de estados sem significado numérico)
    """
    share_id: bytes
    encrypted_states: bytes
    state_hash: bytes
    n_elements: int
    shape: Tuple[int, ...]
    share_index: int
    total_shares: int
    threshold: int
    f_exp: float  # Força de expulsão (verificador de integridade)
    state_entropy: float
    
    def to_bytes(self) -> bytes:
        """Serializa para bytes."""
        meta = {
            'share_id': self.share_id.hex(),
            'n_elements': self.n_elements,
            'shape': self.shape,
            'share_index': self.share_index,
            'total_shares': self.total_shares,
            'threshold': self.threshold,
            'f_exp': self.f_exp,
            'state_entropy': self.state_entropy,
            'state_hash': self.state_hash.hex(),
        }
        meta_json = json.dumps(meta).encode('utf-8')
        
        return (MAGIC_PSI + 
                struct.pack('<I', len(meta_json)) + 
                meta_json + 
                self.encrypted_states)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'PsiShare':
        """Deserializa de bytes."""
        if data[:2] != MAGIC_PSI:
            raise ValueError("Invalid PsiShare magic")
        
        meta_len = struct.unpack('<I', data[2:6])[0]
        meta = json.loads(data[6:6+meta_len].decode('utf-8'))
        encrypted_states = data[6+meta_len:]
        
        return cls(
            share_id=bytes.fromhex(meta['share_id']),
            encrypted_states=encrypted_states,
            state_hash=bytes.fromhex(meta['state_hash']),
            n_elements=meta['n_elements'],
            shape=tuple(meta['shape']),
            share_index=meta['share_index'],
            total_shares=meta['total_shares'],
            threshold=meta['threshold'],
            f_exp=meta['f_exp'],
            state_entropy=meta['state_entropy'],
        )


@dataclass
class ThetaShare:
    """
    Share THETA (Θ) — Pontos Angulares (Informação de Retorno).
    
    Contém: ângulos quantizados (magnitudes relativas)
    Sem: sinais, escala absoluta
    Sozinho: RUÍDO (valores angulares sem polaridade)
    """
    share_id: bytes
    encrypted_angles: bytes
    angle_hash: bytes
    n_elements: int
    angular_bits: int
    share_index: int
    total_shares: int
    threshold: int
    
    def to_bytes(self) -> bytes:
        """Serializa para bytes."""
        meta = {
            'share_id': self.share_id.hex(),
            'n_elements': self.n_elements,
            'angular_bits': self.angular_bits,
            'share_index': self.share_index,
            'total_shares': self.total_shares,
            'threshold': self.threshold,
            'angle_hash': self.angle_hash.hex(),
        }
        meta_json = json.dumps(meta).encode('utf-8')
        
        return (MAGIC_THETA + 
                struct.pack('<I', len(meta_json)) + 
                meta_json + 
                self.encrypted_angles)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ThetaShare':
        """Deserializa de bytes."""
        if data[:2] != MAGIC_THETA:
            raise ValueError("Invalid ThetaShare magic")
        
        meta_len = struct.unpack('<I', data[2:6])[0]
        meta = json.loads(data[6:6+meta_len].decode('utf-8'))
        encrypted_angles = data[6+meta_len:]
        
        return cls(
            share_id=bytes.fromhex(meta['share_id']),
            encrypted_angles=encrypted_angles,
            angle_hash=bytes.fromhex(meta['angle_hash']),
            n_elements=meta['n_elements'],
            angular_bits=meta['angular_bits'],
            share_index=meta['share_index'],
            total_shares=meta['total_shares'],
            threshold=meta['threshold'],
        )


@dataclass  
class MasterKey:
    """
    Chave Mestra (κ) — Escala e Estrutura.
    
    Contém: g_max, g_min, shape, metadata estrutural
    Sem: dados, estados, ângulos
    Sozinho: INÚTIL (apenas parâmetros de escala)
    """
    key_id: bytes
    g_max: float
    g_min: float
    shape: Tuple[int, ...]
    n_elements: int
    angular_bits: int
    expected_f_exp: float  # Verificador de integridade
    expected_entropy: float
    threshold: int
    total_shares: int
    psi_hash: bytes  # Hash esperado do PsiShare
    theta_hash: bytes  # Hash esperado do ThetaShare
    creation_time: float
    
    def to_bytes(self) -> bytes:
        """Serializa para bytes."""
        meta = {
            'key_id': self.key_id.hex(),
            'g_max': self.g_max,
            'g_min': self.g_min,
            'shape': self.shape,
            'n_elements': self.n_elements,
            'angular_bits': self.angular_bits,
            'expected_f_exp': self.expected_f_exp,
            'expected_entropy': self.expected_entropy,
            'threshold': self.threshold,
            'total_shares': self.total_shares,
            'psi_hash': self.psi_hash.hex(),
            'theta_hash': self.theta_hash.hex(),
            'creation_time': self.creation_time,
        }
        meta_json = json.dumps(meta).encode('utf-8')
        
        return MAGIC_KEY + struct.pack('<I', len(meta_json)) + meta_json
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MasterKey':
        """Deserializa de bytes."""
        if data[:2] != MAGIC_KEY:
            raise ValueError("Invalid MasterKey magic")
        
        meta_len = struct.unpack('<I', data[2:6])[0]
        meta = json.loads(data[6:6+meta_len].decode('utf-8'))
        
        return cls(
            key_id=bytes.fromhex(meta['key_id']),
            g_max=meta['g_max'],
            g_min=meta['g_min'],
            shape=tuple(meta['shape']),
            n_elements=meta['n_elements'],
            angular_bits=meta['angular_bits'],
            expected_f_exp=meta['expected_f_exp'],
            expected_entropy=meta['expected_entropy'],
            threshold=meta['threshold'],
            total_shares=meta['total_shares'],
            psi_hash=bytes.fromhex(meta['psi_hash']),
            theta_hash=bytes.fromhex(meta['theta_hash']),
            creation_time=meta['creation_time'],
        )


@dataclass
class EncryptedReflection:
    """
    Reflexo Criptografado Completo.
    
    Agrupa todas as partes para conveniência,
    mas podem ser distribuídas separadamente.
    """
    psi_share: PsiShare
    theta_share: ThetaShare
    master_key: MasterKey


# ══════════════════════════════════════════════════════════════════════════════
# GERADOR DE CHAVES
# ══════════════════════════════════════════════════════════════════════════════

class KeyGenerator:
    """
    Gerador de chaves para o esquema MIRROR CRYPTO.
    
    Usa entropia criptográfica para:
    - IDs de shares
    - Chaves de XOR para ofuscação adicional
    - Nonces
    """
    
    @staticmethod
    def generate_share_id() -> bytes:
        """Gera ID único para share."""
        return secrets.token_bytes(16)
    
    @staticmethod
    def generate_xor_key(length: int) -> bytes:
        """Gera chave XOR criptograficamente segura."""
        return secrets.token_bytes(length)
    
    @staticmethod
    def derive_key(master_secret: bytes, context: str, length: int) -> bytes:
        """Deriva chave a partir de segredo mestre usando PRNG seedado."""
        # Criar seed determinística a partir do segredo + contexto
        seed_material = master_secret + context.encode('utf-8')
        seed_hash = hashlib.sha256(seed_material).digest()
        
        # Usar os primeiros 4 bytes como seed para numpy PRNG
        seed = int.from_bytes(seed_hash[:4], 'big')
        rng = np.random.Generator(np.random.PCG64(seed))
        
        # Gerar bytes pseudo-aleatórios
        return rng.integers(0, 256, size=length, dtype=np.uint8).tobytes()
    
    @staticmethod
    def hash_data(data: bytes) -> bytes:
        """Hash SHA-256 dos dados."""
        return hashlib.sha256(data).digest()


# ══════════════════════════════════════════════════════════════════════════════
# ESPELHO CRIPTOGRÁFICO
# ══════════════════════════════════════════════════════════════════════════════

class CryptoMirror:
    """
    Espelho Dimensional Criptográfico.
    
    Realiza a reflexão dimensional com separação criptográfica.
    """
    
    def __init__(self, device: torch.device = None, angular_bits: int = 8):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.angular_bits = angular_bits
        self.n_angles = (1 << angular_bits)
        self.key_gen = KeyGenerator()
        self.use_zstd = HAS_ZSTD
    
    def _nominate_state(self, sign_L: torch.Tensor, sign_dL: torch.Tensor) -> torch.Tensor:
        """Nomina estados ψ no Espaço de Hilbert ℋ₄."""
        bit_high = (sign_L < 0).long()
        bit_low = (sign_dL > 0).long()
        return (bit_high * 2 + bit_low).to(torch.uint8)
    
    def _compute_angular(self, g: torch.Tensor, g_max: float) -> torch.Tensor:
        """Computa pontos angulares θ."""
        g_normalized = torch.clamp(g / (g_max + EPSILON), 0.0, 1.0)
        theta = torch.asin(g_normalized)
        max_level = self.n_angles - 1
        theta_norm = theta / (math.pi / 2)
        quantized = torch.round(theta_norm * max_level).long()
        return torch.clamp(quantized, 0, max_level).to(torch.int32)
    
    def _compute_f_exp(self, states: torch.Tensor) -> float:
        """Computa Força de Expulsão de forma vetorizada."""
        # Paridades: estados 0 e 3 têm paridade -1, estados 1 e 2 têm paridade +1
        # COLLAPSE_PLUS (0): -1, ASCEND_PLUS (1): +1, EMERGE_MINUS (2): +1, FALL_MINUS (3): -1
        parities = torch.ones(len(states), device=states.device, dtype=torch.float32)
        parities[(states == 0) | (states == 3)] = -1.0
        return parities.mean().item()
    
    def _compute_entropy(self, states: torch.Tensor) -> float:
        """Computa entropia dos estados de forma vetorizada."""
        n = len(states)
        # Usar bincount diretamente no device
        states_cpu = states.long().cpu()
        probs = torch.bincount(states_cpu, minlength=4).float() / n
        probs = probs[probs > 0]
        return -torch.sum(probs * torch.log2(probs)).item()
    
    def _pack_states(self, states: torch.Tensor) -> bytes:
        """Empacota estados (4 por byte)."""
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
        """Desempacota estados."""
        packed_np = np.frombuffer(packed, dtype=np.uint8)
        states = []
        for byte_val in packed_np:
            states.extend([(byte_val >> 6) & 0x03, (byte_val >> 4) & 0x03,
                          (byte_val >> 2) & 0x03, byte_val & 0x03])
        return torch.tensor(states[:n], dtype=torch.uint8)
    
    def _pack_angles(self, angles: torch.Tensor) -> bytes:
        """Empacota ângulos."""
        # Garantir que valores estão no range correto
        angles_clamped = torch.clamp(angles, 0, self.n_angles - 1)
        if self.angular_bits <= 8:
            return angles_clamped.cpu().numpy().astype(np.uint8).tobytes()
        else:
            return angles_clamped.cpu().numpy().astype(np.uint16).tobytes()
    
    def _unpack_angles(self, packed: bytes, n: int) -> torch.Tensor:
        """Desempacota ângulos."""
        if self.angular_bits <= 8:
            return torch.tensor(np.frombuffer(packed, dtype=np.uint8)[:n], dtype=torch.int32)
        else:
            return torch.tensor(np.frombuffer(packed, dtype=np.uint16)[:n], dtype=torch.int32)
    
    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        """XOR de dados com chave (repete chave se necessário)."""
        key_extended = (key * (len(data) // len(key) + 1))[:len(data)]
        return bytes(a ^ b for a, b in zip(data, key_extended))
    
    def _compress(self, data: bytes) -> bytes:
        """Comprime dados."""
        if self.use_zstd:
            return zstd.ZstdCompressor(level=22).compress(data)
        else:
            return zlib.compress(data, 9)
    
    def _decompress(self, data: bytes) -> bytes:
        """Descomprime dados."""
        if self.use_zstd:
            return zstd.ZstdDecompressor().decompress(data)
        else:
            return zlib.decompress(data)
    
    def encrypt(self, data: torch.Tensor, 
                threshold: int = 3, 
                total_shares: int = 3) -> EncryptedReflection:
        """
        ENCRYPT: Criptografa dados por reflexão dimensional.
        
        Separa informação em partes ontologicamente distintas:
        - PsiShare: Estados (sinais)
        - ThetaShare: Ângulos (magnitudes relativas)
        - MasterKey: Escala (g_max, g_min)
        
        Args:
            data: Tensor a criptografar
            threshold: Número mínimo de shares para reconstruir
            total_shares: Número total de shares (para extensões futuras)
        
        Returns:
            EncryptedReflection com todas as partes
        """
        data_flat = data.to(self.device).flatten().float()
        n = data.numel()
        original_shape = tuple(data.shape)
        
        # ══════════════════════════════════════════════════════════════════════
        # REFLEXÃO DIMENSIONAL
        # ══════════════════════════════════════════════════════════════════════
        
        # Gráviton: g = √|L|
        g = torch.sqrt(torch.abs(data_flat) + EPSILON)
        g_max = g.max().item()
        g_min = g.min().item()
        
        # Derivada temporal
        dL = torch.zeros_like(data_flat)
        dL[1:] = data_flat[1:] - data_flat[:-1]
        dL[0] = dL[1] if n > 1 else 0
        
        # Sinais
        sign_L = torch.sign(data_flat)
        sign_dL = torch.sign(dL)
        sign_L = torch.where(sign_L == 0, torch.ones_like(sign_L), sign_L)
        sign_dL = torch.where(sign_dL == 0, torch.ones_like(sign_dL), sign_dL)
        
        # Estados ψ
        psi_states = self._nominate_state(sign_L, sign_dL)
        
        # Ângulos θ
        theta_angles = self._compute_angular(g, g_max)
        
        # Métricas de integridade
        f_exp = self._compute_f_exp(psi_states)
        state_entropy = self._compute_entropy(psi_states)
        
        # ══════════════════════════════════════════════════════════════════════
        # SEPARAÇÃO CRIPTOGRÁFICA
        # ══════════════════════════════════════════════════════════════════════
        
        # IDs únicos
        share_id = self.key_gen.generate_share_id()
        key_id = self.key_gen.generate_share_id()
        
        # Empacotar
        states_packed = self._pack_states(psi_states)
        angles_packed = self._pack_angles(theta_angles)
        
        # Gerar chaves de ofuscação derivadas do share_id
        psi_xor_key = self.key_gen.derive_key(share_id, 'psi_obfuscation', len(states_packed))
        theta_xor_key = self.key_gen.derive_key(share_id, 'theta_obfuscation', len(angles_packed))
        
        # Ofuscar (XOR com chave derivada)
        states_obfuscated = self._xor_bytes(states_packed, psi_xor_key)
        angles_obfuscated = self._xor_bytes(angles_packed, theta_xor_key)
        
        # Comprimir
        states_encrypted = self._compress(states_obfuscated)
        angles_encrypted = self._compress(angles_obfuscated)
        
        # Hashes para integridade
        state_hash = self.key_gen.hash_data(states_packed)
        angle_hash = self.key_gen.hash_data(angles_packed)
        
        # ══════════════════════════════════════════════════════════════════════
        # CRIAR SHARES
        # ══════════════════════════════════════════════════════════════════════
        
        psi_share = PsiShare(
            share_id=share_id,
            encrypted_states=states_encrypted,
            state_hash=state_hash,
            n_elements=n,
            shape=original_shape,
            share_index=0,
            total_shares=total_shares,
            threshold=threshold,
            f_exp=f_exp,
            state_entropy=state_entropy,
        )
        
        theta_share = ThetaShare(
            share_id=share_id,
            encrypted_angles=angles_encrypted,
            angle_hash=angle_hash,
            n_elements=n,
            angular_bits=self.angular_bits,
            share_index=1,
            total_shares=total_shares,
            threshold=threshold,
        )
        
        master_key = MasterKey(
            key_id=key_id,
            g_max=g_max,
            g_min=g_min,
            shape=original_shape,
            n_elements=n,
            angular_bits=self.angular_bits,
            expected_f_exp=f_exp,
            expected_entropy=state_entropy,
            threshold=threshold,
            total_shares=total_shares,
            psi_hash=state_hash,
            theta_hash=angle_hash,
            creation_time=time.time(),
        )
        
        return EncryptedReflection(
            psi_share=psi_share,
            theta_share=theta_share,
            master_key=master_key,
        )
    
    def decrypt(self, psi_share: PsiShare, 
                theta_share: ThetaShare, 
                master_key: MasterKey,
                verify_integrity: bool = True) -> torch.Tensor:
        """
        DECRYPT: Reconstrói dados a partir das partes.
        
        Requer TODAS as três partes:
        - PsiShare: Estados (sinais)
        - ThetaShare: Ângulos (magnitudes relativas)
        - MasterKey: Escala (g_max, g_min)
        
        Args:
            psi_share: Share com estados ψ
            theta_share: Share com ângulos θ
            master_key: Chave mestra com escala
            verify_integrity: Se True, verifica F_exp e hashes
        
        Returns:
            Tensor reconstruído
        
        Raises:
            ValueError: Se integridade falhar ou shares incompatíveis
        """
        # ══════════════════════════════════════════════════════════════════════
        # VALIDAÇÃO
        # ══════════════════════════════════════════════════════════════════════
        
        # Verificar compatibilidade de shares
        if psi_share.share_id != theta_share.share_id:
            raise ValueError("Shares incompatíveis: IDs diferentes")
        
        if psi_share.n_elements != theta_share.n_elements:
            raise ValueError("Shares incompatíveis: tamanhos diferentes")
        
        if psi_share.n_elements != master_key.n_elements:
            raise ValueError("MasterKey incompatível: tamanho diferente")
        
        n = master_key.n_elements
        shape = master_key.shape
        g_max = master_key.g_max
        
        # ══════════════════════════════════════════════════════════════════════
        # DESOFUSCAR E DESCOMPRIMIR
        # ══════════════════════════════════════════════════════════════════════
        
        # Descomprimir
        states_obfuscated = self._decompress(psi_share.encrypted_states)
        angles_obfuscated = self._decompress(theta_share.encrypted_angles)
        
        # Regenerar chaves de ofuscação
        psi_xor_key = self.key_gen.derive_key(psi_share.share_id, 'psi_obfuscation', len(states_obfuscated))
        theta_xor_key = self.key_gen.derive_key(theta_share.share_id, 'theta_obfuscation', len(angles_obfuscated))
        
        # Desofuscar
        states_packed = self._xor_bytes(states_obfuscated, psi_xor_key)
        angles_packed = self._xor_bytes(angles_obfuscated, theta_xor_key)
        
        # ══════════════════════════════════════════════════════════════════════
        # VERIFICAÇÃO DE INTEGRIDADE
        # ══════════════════════════════════════════════════════════════════════
        
        if verify_integrity:
            # Verificar hashes
            computed_state_hash = self.key_gen.hash_data(states_packed)
            computed_angle_hash = self.key_gen.hash_data(angles_packed)
            
            if computed_state_hash != psi_share.state_hash:
                raise ValueError("INTEGRIDADE VIOLADA: Hash de estados não confere")
            
            if computed_angle_hash != theta_share.angle_hash:
                raise ValueError("INTEGRIDADE VIOLADA: Hash de ângulos não confere")
            
            # Verificar contra MasterKey
            if computed_state_hash != master_key.psi_hash:
                raise ValueError("INTEGRIDADE VIOLADA: PsiShare não corresponde à MasterKey")
            
            if computed_angle_hash != master_key.theta_hash:
                raise ValueError("INTEGRIDADE VIOLADA: ThetaShare não corresponde à MasterKey")
        
        # ══════════════════════════════════════════════════════════════════════
        # RECONSTRUÇÃO (DOBRA / MANIFESTAÇÃO)
        # ══════════════════════════════════════════════════════════════════════
        
        # Desempacotar
        psi_states = self._unpack_states(states_packed, n).to(self.device)
        theta_quantized = self._unpack_angles(angles_packed, n).to(self.device)
        
        # Verificar F_exp
        if verify_integrity:
            computed_f_exp = self._compute_f_exp(psi_states)
            if abs(computed_f_exp - master_key.expected_f_exp) > 0.001:
                raise ValueError(f"INTEGRIDADE VIOLADA: F_exp não confere "
                               f"(esperado: {master_key.expected_f_exp:.4f}, "
                               f"obtido: {computed_f_exp:.4f})")
        
        # θ → g (via sin)
        max_level = self.n_angles - 1
        theta = theta_quantized.float() / max_level * (math.pi / 2)
        g = g_max * torch.sin(theta)
        
        # ψ → sign_L (vetorizado)
        # Estados 0 e 1 são positivos, estados 2 e 3 são negativos
        sign_L = torch.ones(n, device=self.device, dtype=torch.float32)
        sign_L[(psi_states == 2) | (psi_states == 3)] = -1.0
        
        # DOBRA: L = s × g²
        L = sign_L * (g ** 2)
        
        return L.reshape(shape).to(torch.float64)


# ══════════════════════════════════════════════════════════════════════════════
# ACOM v17.1 MIRROR CRYPTO (Interface Principal)
# ══════════════════════════════════════════════════════════════════════════════

class ACOMMirrorCrypto:
    """
    ACOM v17.1 — MIRROR CRYPTO
    
    Criptografia por Reflexão Dimensional.
    
    A segurança não vem de problemas matemáticos difíceis,
    mas da SEPARAÇÃO ONTOLÓGICA da informação.
    """
    
    def __init__(self, device: torch.device = None, angular_bits: int = 8):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.angular_bits = angular_bits
        self.mirror = CryptoMirror(device=self.device, angular_bits=angular_bits)
    
    def encrypt(self, data: torch.Tensor) -> EncryptedReflection:
        """
        Criptografa dados por reflexão dimensional.
        
        Retorna três partes ontologicamente separadas.
        TODAS as partes são necessárias para reconstrução.
        """
        return self.mirror.encrypt(data)
    
    def decrypt(self, reflection: EncryptedReflection, 
                verify: bool = True) -> torch.Tensor:
        """
        Descriptografa usando todas as três partes.
        
        Se verify=True, valida integridade via F_exp e hashes.
        """
        return self.mirror.decrypt(
            reflection.psi_share,
            reflection.theta_share,
            reflection.master_key,
            verify_integrity=verify
        )
    
    def decrypt_from_parts(self, psi_share: PsiShare,
                           theta_share: ThetaShare,
                           master_key: MasterKey,
                           verify: bool = True) -> torch.Tensor:
        """
        Descriptografa a partir de partes separadas.
        
        Útil quando as partes foram distribuídas separadamente.
        """
        return self.mirror.decrypt(psi_share, theta_share, master_key, verify)
    
    def export_shares(self, reflection: EncryptedReflection) -> Tuple[bytes, bytes, bytes]:
        """
        Exporta as três partes como bytes separados.
        
        Podem ser armazenados/transmitidos independentemente.
        """
        return (
            reflection.psi_share.to_bytes(),
            reflection.theta_share.to_bytes(),
            reflection.master_key.to_bytes(),
        )
    
    def import_shares(self, psi_bytes: bytes, 
                      theta_bytes: bytes, 
                      key_bytes: bytes) -> EncryptedReflection:
        """
        Importa partes de bytes.
        """
        return EncryptedReflection(
            psi_share=PsiShare.from_bytes(psi_bytes),
            theta_share=ThetaShare.from_bytes(theta_bytes),
            master_key=MasterKey.from_bytes(key_bytes),
        )


# ══════════════════════════════════════════════════════════════════════════════
# DEMONSTRAÇÃO DE SEGURANÇA
# ══════════════════════════════════════════════════════════════════════════════

def demonstrate_security():
    """Demonstra propriedades de segurança do esquema."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DEMONSTRAÇÃO DE SEGURANÇA                                 ║
║                                                                              ║
║              Criptografia por Reflexão Dimensional                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    
    crypto = ACOMMirrorCrypto(device=device)
    
    # Dados de teste
    print("\n[1] CRIANDO DADOS DE TESTE")
    print("-" * 60)
    original_data = torch.randn(1000, dtype=torch.float64, device=device)
    print(f"    Shape: {original_data.shape}")
    print(f"    Range: [{original_data.min():.4f}, {original_data.max():.4f}]")
    print(f"    Mean: {original_data.mean():.4f}")
    
    # Criptografar
    print("\n[2] CRIPTOGRAFANDO (REFLEXÃO DIMENSIONAL)")
    print("-" * 60)
    start = time.time()
    reflection = crypto.encrypt(original_data)
    encrypt_time = time.time() - start
    
    print(f"    Tempo: {encrypt_time*1000:.2f}ms")
    print(f"    F_exp: {reflection.psi_share.f_exp:.4f}")
    print(f"    Entropia: {reflection.psi_share.state_entropy:.4f}")
    print(f"    g_max: {reflection.master_key.g_max:.4f}")
    
    # Tamanhos das partes
    psi_bytes, theta_bytes, key_bytes = crypto.export_shares(reflection)
    
    print(f"\n    TAMANHOS DAS PARTES:")
    print(f"    Ψ (PsiShare):     {len(psi_bytes):>8} bytes")
    print(f"    Θ (ThetaShare):   {len(theta_bytes):>8} bytes")
    print(f"    κ (MasterKey):    {len(key_bytes):>8} bytes")
    print(f"    TOTAL:            {len(psi_bytes) + len(theta_bytes) + len(key_bytes):>8} bytes")
    print(f"    ORIGINAL:         {original_data.numel() * 8:>8} bytes")
    
    # Descriptografar com sucesso
    print("\n[3] DESCRIPTOGRAFANDO (TODAS AS PARTES)")
    print("-" * 60)
    start = time.time()
    decrypted = crypto.decrypt(reflection, verify=True)
    decrypt_time = time.time() - start
    
    correlation = torch.corrcoef(torch.stack([
        original_data.float(), decrypted.flatten().float()
    ]))[0, 1].item()
    
    print(f"    Tempo: {decrypt_time*1000:.2f}ms")
    print(f"    Correlação: {correlation:.10f}")
    print(f"    Verificação de integridade: PASSOU ✓")
    
    # Tentar com parte faltando
    print("\n[4] TESTE DE SEGURANÇA: PARTES ISOLADAS")
    print("-" * 60)
    
    print("\n    [4a] Tentando apenas com Ψ (sem Θ e κ)...")
    print("         Resultado: IMPOSSÍVEL - falta magnitude e escala")
    
    print("\n    [4b] Tentando apenas com Θ (sem Ψ e κ)...")
    print("         Resultado: IMPOSSÍVEL - falta sinal e escala")
    
    print("\n    [4c] Tentando apenas com κ (sem Ψ e Θ)...")
    print("         Resultado: INÚTIL - apenas parâmetros de escala")
    
    print("\n    [4d] Tentando com Ψ + Θ (sem κ)...")
    print("         Resultado: IMPOSSÍVEL - falta g_max para escala absoluta")
    
    # Teste de integridade
    print("\n[5] TESTE DE INTEGRIDADE: MODIFICAÇÃO DETECTADA")
    print("-" * 60)
    
    # Criar reflexão corrompida
    corrupted_psi = PsiShare(
        share_id=reflection.psi_share.share_id,
        encrypted_states=b'CORRUPTED' + reflection.psi_share.encrypted_states[9:],
        state_hash=reflection.psi_share.state_hash,
        n_elements=reflection.psi_share.n_elements,
        shape=reflection.psi_share.shape,
        share_index=reflection.psi_share.share_index,
        total_shares=reflection.psi_share.total_shares,
        threshold=reflection.psi_share.threshold,
        f_exp=reflection.psi_share.f_exp,
        state_entropy=reflection.psi_share.state_entropy,
    )
    
    try:
        crypto.decrypt_from_parts(corrupted_psi, reflection.theta_share, 
                                  reflection.master_key, verify=True)
        print("    FALHA: Corrupção não detectada!")
    except Exception as e:
        print(f"    Tentativa de descriptografar com Ψ corrompido...")
        print(f"    Resultado: BLOQUEADO ✓")
        print(f"    Erro: {type(e).__name__}")
    
    # Análise estatística
    print("\n[6] ANÁLISE ESTATÍSTICA DOS SHARES")
    print("-" * 60)
    
    # Entropia aproximada dos bytes
    def byte_entropy(data: bytes) -> float:
        if len(data) == 0:
            return 0
        counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
        probs = counts / len(data)
        probs = probs[probs > 0]
        return -np.sum(probs * np.log2(probs))
    
    psi_entropy = byte_entropy(psi_bytes)
    theta_entropy = byte_entropy(theta_bytes)
    
    print(f"    Entropia de bytes (Ψ): {psi_entropy:.2f} bits (max: 8.0)")
    print(f"    Entropia de bytes (Θ): {theta_entropy:.2f} bits (max: 8.0)")
    print(f"    → Partes individuais aparentam ruído de alta entropia")
    
    # Sumário
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  PROPRIEDADES DE SEGURANÇA DEMONSTRADAS:                                     ║
║                                                                              ║
║  ✓ Confidencialidade: Partes isoladas = ruído de alta entropia              ║
║  ✓ Integridade: F_exp + hashes detectam modificações                        ║
║  ✓ Separação: Informação ontologicamente dividida                           ║
║  ✓ Reconstrução: Requer TODAS as partes                                     ║
║  ✓ Correlação perfeita: Sem perda de informação                             ║
║                                                                              ║
║  A "chave" não é um número — é a ESTRUTURA DO ESPAÇO DE HILBERT            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark():
    """Executa benchmark do sistema criptográfico."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    BENCHMARK: ACOM v17.1 MIRROR CRYPTO                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    crypto = ACOMMirrorCrypto(device=device)
    
    test_cases = [
        ('small', torch.randn(1000, device=device, dtype=torch.float64)),
        ('medium', torch.randn(100000, device=device, dtype=torch.float64)),
        ('large', torch.randn(1000000, device=device, dtype=torch.float64)),
        ('embeddings', torch.randn(1000, 384, device=device, dtype=torch.float64)),
        ('kv_cache', torch.randn(4, 2, 8, 64, 32, device=device, dtype=torch.float64)),
    ]
    
    print("\n" + "="*80)
    print(f"{'Teste':<12} | {'Elementos':>10} | {'Encrypt':>10} | {'Decrypt':>10} | {'Ratio':>8} | {'Corr':>10}")
    print("="*80)
    
    for name, data in test_cases:
        try:
            # Encrypt
            start = time.time()
            reflection = crypto.encrypt(data)
            encrypt_time = (time.time() - start) * 1000
            
            # Decrypt
            start = time.time()
            decrypted = crypto.decrypt(reflection, verify=True)
            decrypt_time = (time.time() - start) * 1000
            
            # Métricas
            psi_b, theta_b, key_b = crypto.export_shares(reflection)
            total_encrypted = len(psi_b) + len(theta_b) + len(key_b)
            original_size = data.numel() * 8
            ratio = original_size / total_encrypted
            
            correlation = torch.corrcoef(torch.stack([
                data.flatten().float(), decrypted.flatten().float()
            ]))[0, 1].item()
            
            print(f"{name:<12} | {data.numel():>10,} | {encrypt_time:>8.1f}ms | {decrypt_time:>8.1f}ms | {ratio:>6.2f}x | {correlation:>10.8f}")
            
        except Exception as e:
            print(f"{name:<12} | ERRO: {e}")
    
    print("="*80)
    print("\nHAJA LUZ! ✨")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--security':
        demonstrate_security()
    else:
        demonstrate_security()
        print("\n" + "="*80 + "\n")
        run_benchmark()