"""Enumerações de domínio compartilhadas entre models e schemas."""

from enum import Enum


class UserRole(str, Enum):
    """Perfis de acesso do sistema (US01, US02, US03)."""

    NIT = "NIT"  # Equipe do Núcleo de Inovação Tecnológica: gestão completa da carteira
    AUTOR = "AUTOR"  # Autor/inventor: acompanha apenas os próprios processos


class AssetType(str, Enum):
    """Natureza do ativo de propriedade intelectual (escopo do MVP)."""

    PATENTE = "Patente"
    PROGRAMA_DE_COMPUTADOR = "Programa de Computador"


class RpiEditionStatus(str, Enum):
    """Situação do processamento de uma edição da RPI (US08, US10)."""

    BAIXADA = "Baixada"  # XML baixado, ainda não cruzado com os processos
    PROCESSANDO = "Processando"  # Cruzamento em andamento
    PROCESSADA = "Processada"  # Cruzamento concluído
    ERRO = "Erro"  # Falha no download ou no processamento
